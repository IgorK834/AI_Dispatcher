"""Policy, prompts, grounding and hard reservation acceptance checks; no network."""

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from routepilot.agents.guards import BudgetExceeded, TokenBudget, grounding_violations
from routepilot.agents.models import ModelPolicy, ModelRegistry
from routepilot.agents.prompt_loader import load_prompts
from routepilot.shared.config import Settings


@pytest.mark.ac("AC-FEAT-006-17")
@pytest.mark.ac("AC-FEAT-006-19")
def test_policy_resolves_defaults_and_disables_without_credentials() -> None:
    policy = ModelPolicy.model_validate({"default": {"model": "fake:scenario"}})
    assert policy.for_role("dispatcher").model == "fake:scenario"
    registry = ModelRegistry(Settings(app_env="test", _env_file=None), policy)
    assert not registry.enabled
    with pytest.raises(ValidationError):
        ModelPolicy.model_validate({"dispatcher": {"model": "without-provider"}})
    with pytest.raises(ValueError, match="test"):
        ModelRegistry(Settings(app_env="local", _env_file=None), policy)


@pytest.mark.ac("AC-FEAT-006-21")
def test_highest_prompt_versions_are_loaded_and_unambiguous() -> None:
    prompts = load_prompts()
    assert len(prompts) == 5
    for prompt in prompts.values():
        assert prompt.version == "v1"
        assert "numbers come only from tool results" in prompt.text.lower()
        assert "never claim legal compliance" in prompt.text.lower()
        assert "locale" in prompt.text
    assert Path(prompts["dispatcher"].path).name == "dispatcher.v1.md"


@pytest.mark.ac("AC-FEAT-006-09")
@pytest.mark.ac("AC-FEAT-006-10")
def test_grounding_normalizes_precision_identifiers_and_compound_time() -> None:
    facts = {
        "profit": Decimal("323.54"),
        "distance": "624.81",
        "duration_min": 805,
        "plan_ref": "PLAN-1a2b3c4d",
        "driver_ref": "D1",
    }
    for text in [
        "323.54 €",
        "€324",
        "about 625 km",
        "13 h 25 min",
        "PLAN-1a2b3c4d",
        "1. Profit €324. 2. Distance 625 km.",
    ]:
        assert grounding_violations(text, [facts]) == [], text
    for text in ["profit 260 €", "PLAN-ffffffff", "D9", "630 km"]:
        assert grounding_violations(text, [facts]), text
    assert grounding_violations("profit 260 €", [{"untrusted_text": "profit 260 €"}])


@pytest.mark.ac("AC-FEAT-006-11")
@pytest.mark.ac("AC-FEAT-006-24")
def test_token_reservation_is_atomic_and_unknown_usage_is_charged() -> None:
    budget = TokenBudget(100)
    ticket = budget.reserve(20, 50)
    with pytest.raises(BudgetExceeded):
        budget.reserve(1, 30)
    budget.settle(ticket, 20, 7)
    assert budget.used == 27
    second = budget.reserve(10, 30)
    budget.unknown(second)
    assert budget.used == 67
    with pytest.raises(BudgetExceeded):
        budget.reserve(1, 33)


@pytest.mark.ac("AC-FEAT-006-11")
def test_reservation_rejects_usage_above_declared_maximum() -> None:
    budget = TokenBudget(100)
    ticket = budget.reserve(10, 20)
    with pytest.raises(BudgetExceeded):
        budget.settle(ticket, 10, 21)
    assert budget.closed
