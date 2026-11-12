"""Explanation grounding uses plan facts and preserves the template output shape."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from routepilot.agents.explanations import ExplanationService
from routepilot.agents.models import ModelPolicy, ModelRegistry
from routepilot.shared.clock import FixedClock
from routepilot.shared.config import Settings
from tests.agents.fakes import ScriptedModel, response
from tests.agents.memory_store import MemoryStore


@pytest.mark.ac("AC-FEAT-006-25")
@pytest.mark.ac("AC-FEAT-006-37")
@pytest.mark.parametrize("number,source", [("260", "template"), ("323.54", "llm")])
def test_explanation_grounding_and_template_shape(number: str, source: str) -> None:
    model = ScriptedModel(
        script=[
            response(
                tool="ExplanationOutput",
                args={
                    "headline": f"Profit €{number}",
                    "reasons": [],
                    "tradeoffs": [],
                    "warnings": [],
                },
            )
        ]
    )
    settings = Settings(app_env="test", _env_file=None)
    registry = ModelRegistry(
        settings,
        ModelPolicy.model_validate({"default": {"model": "fake:explain", "maxTokens": 30}}),
        {"fake:explain": lambda: model},
    )
    store = MemoryStore()
    facts = {
        "plan_ref": "PLAN-1a2b3c4d",
        "net_profit_eur": "323.54",
        "fuel_l": "76.601",
        "co2_kg": "199.16",
    }
    service = ExplanationService(
        store, registry, FixedClock(datetime(2026, 11, 12, tzinfo=UTC)), settings, lambda id: facts
    )
    result = service.explain(uuid4())
    assert result["source"] == source
    assert result["groundingOk"] is (source == "llm")
    assert set(result["output"]) == {"headline", "reasons", "tradeoffs", "warnings"}
    assert len(store.find("route_explanations")) == 1
    assert len(model.recorded) == 1


@pytest.mark.ac("AC-FEAT-006-19")
def test_no_key_explanation_still_succeeds() -> None:
    settings = Settings(app_env="test", _env_file=None)
    store = MemoryStore()
    service = ExplanationService(
        store,
        ModelRegistry(settings),
        FixedClock(datetime(2026, 11, 12, tzinfo=UTC)),
        settings,
        lambda id: {"plan_ref": "PLAN-1a2b3c4d", "net_profit_eur": "323.54"},
    )
    result = service.explain(uuid4(), "pl")
    assert result["source"] == "template"
    assert "323.54" in str(result["output"])
