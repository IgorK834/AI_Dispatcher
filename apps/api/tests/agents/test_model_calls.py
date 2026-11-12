"""Every retry/fallback is charged; offline registered providers share the same path."""

import pytest
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from routepilot.agents.guards import BudgetExceeded, TokenBudget
from routepilot.agents.models import ModelPolicy, ModelRegistry, ProviderFailure
from routepilot.shared.config import Settings
from tests.agents.fakes import ScriptedModel, response


class Decision(BaseModel):
    next: str


@pytest.mark.ac("AC-FEAT-006-17")
@pytest.mark.ac("AC-FEAT-006-18")
@pytest.mark.parametrize("provider", ["google_genai", "anthropic"])
def test_provider_swap_and_structured_retry_are_accounted(provider: str) -> None:
    name = f"{provider}:script"
    model = ScriptedModel(
        script=[response("invalid"), response(tool="Decision", args={"next": "finish"})]
    )
    policy = ModelPolicy.model_validate({"default": {"model": name, "maxTokens": 30}})
    registry = ModelRegistry(
        Settings(app_env="test", _env_file=None), policy, {name: lambda: model}
    )
    budget = TokenBudget(100)
    result = registry.call(
        "dispatcher", [HumanMessage("question")], schema=Decision, budgets=[budget]
    )
    assert result.parsed == Decision(next="finish")
    assert budget.used == 50
    assert len(model.recorded) == 2


@pytest.mark.ac("AC-FEAT-006-18")
def test_provider_error_only_retries_configured_fallback() -> None:
    primary = ScriptedModel(script=[RuntimeError("private provider details")])
    fallback = ScriptedModel(script=[response(tool="Decision", args={"next": "finish"})])
    policy = ModelPolicy.model_validate(
        {
            "default": {"model": "fake:primary", "maxTokens": 30},
            "fallback": {"model": "fake:fallback", "maxTokens": 30},
        }
    )
    registry = ModelRegistry(
        Settings(app_env="test", _env_file=None),
        policy,
        {"fake:primary": lambda: primary, "fake:fallback": lambda: fallback},
    )
    budget = TokenBudget(100)
    result = registry.call("dispatcher", [HumanMessage("q")], schema=Decision, budgets=[budget])
    assert result.fallback
    assert len(primary.recorded) == len(fallback.recorded) == 1
    assert budget.used == 75  # uncertain first request: its entire reservation is charged


@pytest.mark.ac("AC-FEAT-006-11")
def test_insufficient_allowance_prevents_request_and_missing_usage_fails_closed() -> None:
    model = ScriptedModel(script=[response("ok")])
    policy = ModelPolicy.model_validate({"default": {"model": "fake:script", "maxTokens": 30}})
    registry = ModelRegistry(
        Settings(app_env="test", _env_file=None), policy, {"fake:script": lambda: model}
    )
    with pytest.raises(BudgetExceeded):
        registry.call("dispatcher", [HumanMessage("q")], budgets=[TokenBudget(49)])
    assert model.recorded == []
    model.script[0].usage_metadata = None
    budget = TokenBudget(100)
    with pytest.raises(ProviderFailure):
        registry.call("dispatcher", [HumanMessage("q")], budgets=[budget])
    assert budget.used == 50
