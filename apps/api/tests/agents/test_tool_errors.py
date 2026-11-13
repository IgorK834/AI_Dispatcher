"""Section 6.6 common rules: `{error: {code, message}}`, and TOOL_ERROR after one retry."""

from pathlib import Path
from typing import Any

import pytest

from tests.agents.conftest import ToolEnv
from tests.agents.scenario import (
    DynamicModel,
    Scenario,
    context_of,
    decision,
    final_answer,
    specialist_models,
)

SCOUT = "freight_scout"
TOOL = "search_offers"


def test_every_error_carries_a_code_and_a_message_without_the_input(tool_env: ToolEnv) -> None:
    marker = "ZZ-unique-marker"
    cases = [
        tool_env.call("dispatcher", "optimize_fleet", offer_ids=[]),  # not allowed
        tool_env.call(SCOUT, TOOL, origin_city=[marker]),  # invalid input
        tool_env.call(SCOUT, "get_offer", offer_id="MOCK-999999"),  # unknown reference
        tool_env.call("route_planner", "optimize_driver", driver_ref="D1", offer_ids=[]),  # no loop
    ]
    codes = [case["error"]["code"] for case in cases]
    assert codes == ["TOOL_NOT_ALLOWED", "VALIDATION_ERROR", "NOT_FOUND", "TOOL_ERROR"]
    for case in cases:
        assert set(case["error"]) == {"code", "message"}
        assert case["error"]["message"] and marker not in case["error"]["message"]


class Failing:
    """Make the real registry answer one tool with TOOL_ERROR for the first `times` calls."""

    def __init__(self, env: ToolEnv, monkeypatch: pytest.MonkeyPatch, times: int) -> None:
        self.calls = 0
        self.times = times
        original = env.registry.execute

        def execute(role: Any, name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
            if name == TOOL:
                self.calls += 1
                if self.calls <= self.times:
                    return {"error": {"code": "TOOL_ERROR", "message": "The tool failed."}}
            return original(role, name, *args, **kwargs)

        monkeypatch.setattr(env.registry, "execute", execute)


def run_scout(env: ToolEnv, path: Path) -> Scenario:
    models = specialist_models(env)
    models["dispatcher"] = DynamicModel(script=[decision(SCOUT), decision("finish"), final_answer])
    return Scenario(env, path / "agents.db", models)


def test_a_tool_error_is_retried_once_and_a_second_success_is_used(
    worker_env: ToolEnv, generated_offers: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    failing = Failing(worker_env, monkeypatch, times=1)
    outcome = run_scout(worker_env, tmp_path).start()
    assert failing.calls == 2
    assert outcome.state["scout_report"]["notes"] == "Synthetic offers"
    assert not any("freight_scout" in note for note in outcome.state["notes"])


def test_a_second_tool_error_ends_the_specialist_turn_with_a_note_for_the_dispatcher(
    worker_env: ToolEnv, generated_offers: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    failing = Failing(worker_env, monkeypatch, times=5)
    run = run_scout(worker_env, tmp_path)
    outcome = run.start()
    assert failing.calls == 2, "one call and one retry, nothing more"
    assert "scout_report" not in outcome.state or not outcome.state["scout_report"]
    notes = [note for note in outcome.state["notes"] if "freight_scout" in note]
    assert notes and TOOL in notes[0] and "TOOL_ERROR" in notes[0]
    assert not outcome.state.get("error"), "the run goes on; it does not fail"
    # The Dispatcher's next turn sees the note.
    seen = [
        context_of(messages)["notes"]
        for role, messages in run.recorded()
        if role == "dispatcher" and messages[-1].type == "human"
    ]
    assert any(TOOL in " ".join(notes_) for notes_ in seen[1:])
    assert not outcome.waiting and outcome.state["final_answer"]["grounded"] is True
