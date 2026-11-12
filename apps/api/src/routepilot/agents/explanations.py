"""One explanation service for the HTTP API and the Dispatcher tool."""

import hashlib
import json
from collections.abc import Callable
from typing import Any
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage

from routepilot.agents.graph import DISCLAIMER
from routepilot.agents.guards import TokenBudget, grounding_violations
from routepilot.agents.models import ModelRegistry, ProviderFailure
from routepilot.agents.ports import AgentStore, ModelCall
from routepilot.agents.prompt_loader import load_prompts
from routepilot.agents.schemas import ExplanationOutput
from routepilot.shared.clock import Clock
from routepilot.shared.config import Settings


def template_explanation(facts: dict[str, Any], locale: str) -> ExplanationOutput:
    polish = locale == "pl"
    reasons = []
    for key, en, pl, unit in [
        ("net_profit_eur", "Estimated net profit", "Szacowany zysk netto", "EUR"),
        ("distance_km", "Estimated distance", "Szacowana odległość", "km"),
        ("fuel_l", "Estimated fuel", "Szacowane paliwo", "l"),
        ("co2_kg", "Estimated CO₂", "Szacowana emisja CO₂", "kg CO₂"),
    ]:
        if facts.get(key) is not None:
            reasons.append(f"{pl if polish else en}: {facts[key]} {unit}")
    return ExplanationOutput(
        headline=f"{'Planowany wariant' if polish else 'Proposed plan'} {facts['plan_ref']}",
        reasons=reasons,
        tradeoffs=[],
        warnings=facts.get("warnings", []),
    )


class ExplanationService:
    def __init__(
        self,
        store: AgentStore,
        registry: ModelRegistry,
        clock: Clock,
        settings: Settings,
        facts_for_plan: Callable[[UUID], dict[str, Any]],
    ) -> None:
        self.store, self.registry, self.clock, self.settings = store, registry, clock, settings
        self.facts_for_plan = facts_for_plan
        self.prompt = load_prompts()["explainer"]

    def explain(
        self,
        plan_id: UUID,
        locale: str = "en",
        facts: dict[str, Any] | None = None,
        model_call: ModelCall | None = None,
    ) -> dict[str, Any]:
        facts = facts if facts is not None else self.facts_for_plan(plan_id)
        output = template_explanation(facts, locale)
        source, model, grounding_ok = "template", None, True
        tokens_in, tokens_out = 0, 0
        try:
            enabled = self.registry.usable(self.registry.policy.for_role("explainer"))
        except ValueError:
            enabled = False
        if enabled:
            messages = [
                SystemMessage(self.prompt.text),
                HumanMessage(json.dumps({"locale": locale, "facts": facts}, default=str)),
            ]
            try:
                result = (
                    model_call(messages, ExplanationOutput)
                    if model_call
                    else self.registry.call(
                        "explainer",
                        messages,
                        schema=ExplanationOutput,
                        budgets=[TokenBudget(self.settings.agent_run_token_budget)],
                    )
                )
                candidate = ExplanationOutput.model_validate(result.parsed)
                model = result.model
                tokens_in, tokens_out = result.tokens_in, result.tokens_out
                grounding_ok = not grounding_violations(
                    " ".join(
                        [
                            candidate.headline,
                            *candidate.reasons,
                            *candidate.tradeoffs,
                            *candidate.warnings,
                        ]
                    ),
                    [facts],
                )
                if grounding_ok:
                    output, source = candidate, "llm"
            except ProviderFailure:
                grounding_ok = False
        row = self.store.create(
            "route_explanations",
            {
                "route_plan_id": plan_id,
                "status": "succeeded",
                "source": source,
                "model": model,
                "prompt_version": self.prompt.version,
                "input_sha256": hashlib.sha256(
                    json.dumps(facts, sort_keys=True, default=str).encode()
                ).hexdigest(),
                "output": output.model_dump(),
                "grounding_ok": grounding_ok,
                "tokens": {"in": tokens_in, "out": tokens_out},
                "cost_estimate_minor": 0,
                "currency": "USD",
                "error": None,
            },
        )
        return {
            "id": row["id"],
            "routePlanId": plan_id,
            "source": source,
            "model": model,
            "promptVersion": self.prompt.version,
            "groundingOk": grounding_ok,
            "output": output.model_dump(),
            "disclaimer": DISCLAIMER,
        }
