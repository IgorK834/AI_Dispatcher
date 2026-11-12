"""The sole provider boundary: model policy, chat construction and metered calls."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Self

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableBinding
from pydantic import BaseModel, ConfigDict, Field, model_validator

from routepilot.agents.guards import BudgetExceeded, TokenBudget
from routepilot.shared.config import Settings

Role = Literal["dispatcher", "freight_scout", "fleet_compliance", "route_planner", "explainer"]


class ModelSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    model: str
    params: dict[str, Any] = Field(default_factory=dict)
    max_tokens: int = Field(default=8192, alias="maxTokens", ge=1)
    timeout_s: float = Field(default=30, alias="timeoutS", gt=0)

    @model_validator(mode="after")
    def qualified(self) -> Self:
        if ":" not in self.model or not all(self.model.split(":", 1)):
            raise ValueError("model must be provider:model")
        # The policy owns generation parameters; callers cannot enable hidden retries
        # or override the declared hard output cap through params.
        if set(self.params) & {
            "max_tokens",
            "max_output_tokens",
            "timeout",
            "max_retries",
            "api_key",
            "google_api_key",
            "callbacks",
            "cache",
        }:
            raise ValueError("Reserved model parameter")
        return self


class ModelPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dispatcher: ModelSpec | None = None
    freight_scout: ModelSpec | None = None
    fleet_compliance: ModelSpec | None = None
    route_planner: ModelSpec | None = None
    explainer: ModelSpec | None = None
    default: ModelSpec | None = None
    fallback: ModelSpec | None = None

    @classmethod
    def parse(cls, raw: str) -> Self:
        return cls.model_validate_json(raw or "{}")

    def for_role(self, role: Role) -> ModelSpec:
        value: ModelSpec | None = getattr(self, role)
        if value is None and self.default is None:
            raise ValueError(f"No model configured for {role}")
        resolved = value or self.default
        if resolved is None:
            raise ValueError(f"No model configured for {role}")
        return resolved


class ProviderFailure(Exception):
    """Sanitised provider failure; exception content never enters traces."""


class StructuredFailure(ProviderFailure):
    """The model's structured result did not validate."""


@dataclass(frozen=True)
class ModelResult:
    message: AIMessage
    parsed: BaseModel | None
    model: str
    tokens_in: int
    tokens_out: int
    fallback: bool


class ModelRegistry:
    def __init__(
        self,
        settings: Settings,
        policy: ModelPolicy | None = None,
        factories: dict[str, Callable[[], BaseChatModel]] | None = None,
    ) -> None:
        self.settings = settings
        self.policy = policy or ModelPolicy.parse(settings.agent_model_policy)
        self.factories = factories or {}
        if settings.app_env != "test" and (
            self.factories or any(spec.model.startswith("fake:") for spec in self._specs())
        ):
            raise ValueError("Fake models and registrations are test-only")

    def _specs(self) -> list[ModelSpec]:
        return [value for value in self.policy.__dict__.values() if isinstance(value, ModelSpec)]

    def usable(self, spec: ModelSpec) -> bool:
        if self.settings.app_env == "test" and spec.model in self.factories:
            return True
        provider = spec.model.split(":", 1)[0]
        return bool(
            {
                "google_genai": self.settings.google_api_key,
                "anthropic": self.settings.anthropic_api_key,
                "openai": self.settings.openai_api_key,
            }.get(provider)
        )

    @property
    def enabled(self) -> bool:
        try:
            return self.usable(self.policy.for_role("dispatcher"))
        except ValueError:
            return False

    def build_chat_model(self, spec: ModelSpec) -> BaseChatModel:
        if spec.model in self.factories:
            return self.factories[spec.model]()
        if not self.usable(spec):
            raise ProviderFailure("AI_UNAVAILABLE")
        provider, model = spec.model.split(":", 1)
        params = dict(spec.params)
        keys = {
            "google_genai": self.settings.google_api_key,
            "anthropic": self.settings.anthropic_api_key,
            "openai": self.settings.openai_api_key,
        }
        params.update(
            api_key=keys[provider],
            max_tokens=spec.max_tokens,
            timeout=spec.timeout_s,
            max_retries=0,
        )
        if provider == "google_genai":
            # google-genai's attempts includes the first request: one means no retry.
            params["max_retries"] = 1
        built = init_chat_model(model, model_provider=provider, **params)
        if not isinstance(built, BaseChatModel):
            raise ProviderFailure("Invalid model adapter")
        return built

    def _count(
        self,
        model: BaseChatModel,
        messages: list[BaseMessage],
        kwargs: dict[str, Any],
        *,
        live_campaign: bool,
    ) -> int:
        from langchain_google_genai import ChatGoogleGenerativeAI

        if isinstance(model, ChatGoogleGenerativeAI):
            from google.genai.types import Content, Part

            request = model._prepare_request(messages, **kwargs)
            config = request["config"]
            if model.client is None:
                raise ProviderFailure("Count client unavailable")
            contents = list(request["contents"])
            # The Developer API counts `contents` only; system instruction and tool schemas are
            # rejected by that endpoint. Count their JSON as extra text instead: this can only
            # overcount, which is the safe direction for a reservation. The ledger still settles
            # on the provider's exact usage metadata after the call.
            extra = [
                item.model_dump_json(exclude_none=True)
                for item in (config.system_instruction, *(config.tools or []))
                if item is not None
            ]
            if extra:
                contents.append(Content(role="user", parts=[Part(text="\n".join(extra))]))
            count = model.client.models.count_tokens(
                model=model.model, contents=contents
            ).total_tokens
            if count is None or count <= 0:
                raise ProviderFailure("Input token count unavailable")
            return count
        if live_campaign:
            raise ProviderFailure("Exact campaign accounting unavailable for this adapter")
        # Fake/test adapters implement a deterministic counter; production providers
        # may use their official tokenizer. The live campaign requires the exact path above.
        return model.get_num_tokens_from_messages(messages, tools=kwargs.get("tools"))

    def call(
        self,
        role: Role,
        messages: list[BaseMessage],
        *,
        tools: Sequence[dict[str, Any]] = (),
        schema: type[BaseModel] | None = None,
        budgets: Sequence[TokenBudget] = (),
        live_campaign: bool = False,
        observe: Callable[[str, str, int, int], None] | None = None,
    ) -> ModelResult:
        primary = self.policy.for_role(role)
        attempts = [primary, primary] if schema else [primary]
        if self.policy.fallback is not None:
            attempts.append(self.policy.fallback)
        index = 0
        while index < len(attempts):
            spec = attempts[index]
            if observe:
                observe("started", spec.model, 0, 0)
            before_in = budgets[0].tokens_in if budgets else 0
            before_out = budgets[0].tokens_out if budgets else 0
            status = "error"
            try:
                result = self._call_once(
                    spec,
                    messages,
                    tools,
                    schema,
                    budgets,
                    live_campaign,
                    index > 0 and spec != primary,
                )
                status = "ok"
                return result
            except StructuredFailure:
                index += 1
                continue
            except ProviderFailure:
                # Provider failures do not retry the primary; only a configured fallback.
                if spec == self.policy.fallback or self.policy.fallback is None:
                    break
                index = len(attempts) - 1
            finally:
                if observe:
                    observe(
                        status,
                        spec.model,
                        budgets[0].tokens_in - before_in if budgets else 0,
                        budgets[0].tokens_out - before_out if budgets else 0,
                    )
        raise ProviderFailure("AI_PROVIDER_ERROR")

    def _call_once(
        self,
        spec: ModelSpec,
        messages: list[BaseMessage],
        tools: Sequence[dict[str, Any]],
        schema: type[BaseModel] | None,
        budgets: Sequence[TokenBudget],
        live_campaign: bool,
        fallback: bool,
    ) -> ModelResult:
        tickets = []
        try:
            model = self.build_chat_model(spec)
            bound = model.bind_tools(
                list(tools) if schema is None else [schema],
                **({"tool_choice": schema.__name__} if schema else {}),
            )
            kwargs = dict(bound.kwargs) if isinstance(bound, RunnableBinding) else {}
            count = self._count(model, messages, kwargs, live_campaign=live_campaign)
            # The provider feeds earlier turns' hidden reasoning back as input, which no
            # pre-call count can see (a live tool turn: 986 in + 832 out earlier, 1 922 in now).
            # Reserve the earlier turns' reported output plus a margin; settlement always
            # charges the provider's reported usage, never the reservation.
            hidden = sum(
                item.usage_metadata["output_tokens"] if item.usage_metadata else 0
                for item in messages
                if isinstance(item, AIMessage)
            )
            reserved_input = count + count // 4 + hidden
            for budget in budgets:
                tickets.append((budget, budget.reserve(reserved_input, spec.max_tokens)))
            message = bound.invoke(messages)
        except BudgetExceeded:
            for budget, ticket in tickets:
                budget.settle(ticket, 0, 0)
            raise
        except Exception as error:
            for budget, ticket in tickets:
                budget.unknown(ticket)
            raise ProviderFailure("AI_PROVIDER_ERROR") from error
        if not isinstance(message, AIMessage) or not message.usage_metadata:
            for budget, ticket in tickets:
                budget.unknown(ticket)
            raise ProviderFailure("Missing token usage")
        usage = message.usage_metadata
        tokens_in, tokens_out = usage["input_tokens"], usage["output_tokens"]
        # LangChain output_tokens already includes reasoning; do not count it twice.
        # Every budget must record the actual usage even when one of them rejects it, or the
        # others would keep a full reservation for a call that has already finished.
        rejected: BudgetExceeded | None = None
        for budget, ticket in tickets:
            try:
                budget.settle(ticket, tokens_in, tokens_out)
            except BudgetExceeded as error:
                rejected = rejected or error
        if rejected is not None:
            raise rejected
        parsed = None
        if schema is not None:
            try:
                if message.tool_calls:
                    parsed = schema.model_validate(message.tool_calls[0]["args"])
                else:
                    parsed = schema.model_validate_json(str(message.content))
            except (ValueError, TypeError, IndexError) as error:
                raise StructuredFailure("Invalid structured output") from error
        return ModelResult(message, parsed, spec.model, tokens_in, tokens_out, fallback)
