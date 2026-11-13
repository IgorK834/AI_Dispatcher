"""PlanValidator removes invalid plans, asks the planner once more, then reports an error note."""

from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import BaseMessage, ToolMessage

from routepilot.optimization.engine.models import ValidationResult
from routepilot.optimization.jobs.service import PlanService
from routepilot.shared.errors import DomainError
from tests.agents.conftest import FLEET_POOL, ToolEnv
from tests.agents.fakes import response
from tests.agents.scenario import (
    PLAN_REF,
    DynamicModel,
    Scenario,
    context_of,
    decision,
    dispatcher_script,
    final_answer,
    request_approval,
    specialist_models,
)

REPORT = response(
    tool="PlannerReport",
    args={
        "recommended": {"variant": "profit", "fleet_solution_id": "profit"},
        "alternatives": [],
        "tradeoffs": [],
        "baseline_uplift": None,
    },
)


class FakePlans(PlanService):
    """A PlanService whose validator is switched from the test (the spec's fake PlanService)."""

    mode = "invalid"  # "invalid", "unknown" or "valid"

    def validate(self, plan_id: Any) -> ValidationResult:
        if self.mode == "unknown":
            raise DomainError("NOT_FOUND", 404)
        if self.mode == "invalid":
            return ValidationResult(valid=False, errors=["WORK_LIMIT_EXCEEDED"])
        return super().validate(plan_id)


def install(env: ToolEnv) -> FakePlans:
    fake = FakePlans(env.plans.repository.engine, env.clock, env.plans.routing)
    env.registry.plans = fake
    return fake


def planner_turn(env: ToolEnv, after: Any = None) -> list[Any]:
    offers = [*FLEET_POOL, f"OFF-{env.offer.id.hex[:8]}"]
    optimize = response(tool="optimize_fleet", args={"offer_ids": offers})
    return [after or optimize, REPORT]


def refs_seen_by(model: Any) -> list[str]:
    seen: list[str] = []
    for messages in model.recorded:
        for message in messages:
            if isinstance(message, ToolMessage):
                seen.extend(PLAN_REF.findall(str(message.content)))
    return list(dict.fromkeys(seen))


def count(run: Scenario, name: str) -> int:
    return len([step for step in run.steps() if step["agent"] == name])


@pytest.mark.ac("AC-FEAT-006-08")
@pytest.mark.parametrize("mode", ["invalid", "unknown"])
def test_two_failures_remove_the_plans_and_leave_an_error_note_for_the_dispatcher(
    worker_env: ToolEnv, generated_offers: object, tmp_path: Path, mode: str
) -> None:
    fake = install(worker_env)
    fake.mode = mode
    models = specialist_models(worker_env)
    # The planner is asked twice and produces plans that fail both times.
    models["route_planner"] = DynamicModel(
        script=[*planner_turn(worker_env), *planner_turn(worker_env)]
    )

    def request_removed_plans(messages: list[BaseMessage]) -> list[str]:
        return refs_seen_by(models["route_planner"])[:2]

    models["dispatcher"] = DynamicModel(
        script=[
            *dispatcher_script(
                request_approval(request_removed_plans), decision("approve"), decision("finish")
            ),
            final_answer,
        ]
    )
    run = Scenario(worker_env, tmp_path / "agents.db", models)
    outcome = run.start()
    state = outcome.state
    assert count(run, "PlanValidator") == 2, "validated after each planner turn, asked once more"
    assert len(models["route_planner"].recorded) == 4 and not models["route_planner"].script
    # The second planner turn was told why its plans were removed.
    second_turn = context_of(models["route_planner"].recorded[2])
    assert any("Invalid plans removed" in note for note in second_turn["notes"])
    # After the second failure nothing is left: no plans, no report, and an error note.
    assert state["plan_facts"] == {} and state["validated_plans"] == []
    assert state["planner_report"] == {}
    assert any(note.startswith("Invalid plans removed") for note in state["notes"])
    dispatcher_notes = [
        context_of(messages)["notes"]
        for role, messages in run.recorded()
        if role == "dispatcher" and messages[-1].type == "human"
    ]
    assert any("Invalid plans removed" in " ".join(notes) for notes in dispatcher_notes)
    # An invalid plan never reaches request_approval's acceptance, so there is no approval wait.
    replies = [
        message.content
        for _role, messages in run.recorded()
        for message in messages
        if isinstance(message, ToolMessage) and "accepted" in str(message.content)
    ]
    assert replies and all('"accepted": false' in str(item) for item in replies)
    assert not outcome.waiting and "ApprovalGate" not in {s["agent"] for s in run.steps()}
    assert run.store.find("approval_requests", run_id=run.run_id) == []
    assert run.assignments() == []


@pytest.mark.ac("AC-FEAT-006-08")
def test_a_second_attempt_that_validates_continues_to_the_approval(
    worker_env: ToolEnv, generated_offers: object, tmp_path: Path
) -> None:
    fake = install(worker_env)
    models = specialist_models(worker_env)

    def repair(messages: list[BaseMessage]) -> Any:
        fake.mode = "valid"  # the planner's second answer is checked by the real validator
        return planner_turn(worker_env)[0]

    models["route_planner"] = DynamicModel(script=[*planner_turn(worker_env), repair, REPORT])
    models["dispatcher"] = DynamicModel(
        script=[
            *dispatcher_script(request_approval(), decision("approve"), decision("finish")),
            final_answer,
        ]
    )
    run = Scenario(worker_env, tmp_path / "agents.db", models)
    outcome = run.start()
    assert count(run, "PlanValidator") == 2
    assert outcome.waiting and outcome.state["validated_plans"]
    approved = {row["planRef"] for row in run.pending()["payload"]["plans"]}
    assert approved <= set(outcome.state["validated_plans"]), "only validated plans are proposed"
    assert any(note.startswith("Invalid plans removed") for note in outcome.state["notes"])
