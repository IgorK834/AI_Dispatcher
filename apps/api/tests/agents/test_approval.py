"""request_approval, the ApprovalGate interrupt and the atomic, human-approved write."""

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from langchain_core.messages import ToolMessage
from sqlalchemy import update

from tests.agents.conftest import D1_POOL, ToolEnv
from tests.agents.scenario import (
    PLAN_REF,
    DynamicModel,
    Scenario,
    context_of,
    decision,
    dispatcher_script,
    final_answer,
    pick_plans,
    request_approval,
    same_driver_plans,
    specialist_models,
)


def scenario(env: ToolEnv, path: Path, *dispatcher_tail: Any) -> Scenario:
    models = specialist_models(env)
    models["dispatcher"] = DynamicModel(script=[*dispatcher_script(*dispatcher_tail), final_answer])
    return Scenario(env, path / "agents.db", models)


def approved_once(env: ToolEnv, path: Path) -> Scenario:
    """Request approval for the best consistent set, wait, and finish after the decision."""
    return scenario(env, path, request_approval(), decision("approve"), decision("finish"))


@pytest.mark.ac("AC-FEAT-006-05")
@pytest.mark.parametrize(("value", "comment"), [("reject", "Too expensive"), ("edit", "Use D2")])
def test_reject_or_edit_writes_nothing_and_the_dispatcher_receives_decision_and_comment(
    worker_env: ToolEnv, generated_offers: object, tmp_path: Path, value: str, comment: str
) -> None:
    run = approved_once(worker_env, tmp_path)
    assert run.start().waiting
    requested = run.pending()["payload"]["plans"]
    assert len(requested) >= 1
    outcome = run.decide(value, comment)
    assert not outcome.waiting, "the run continues to a final answer"
    assert run.assignments() == []
    offers = worker_env.freight.all_offers(status="assigned")
    assert offers == [], "no offer was taken"
    # The Dispatcher's next input carries the human's decision and comment.
    dispatcher_inputs = [
        context_of(messages)["notes"]
        for role, messages in run.recorded()
        if role == "dispatcher" and messages[-1].type == "human"
    ]
    assert any(f"Human decision: {value}; {comment}" in notes for notes in dispatcher_inputs)
    state = outcome.state
    assert state["assigned"] is False and state["pending_approval"] is None
    answer = state["final_answer"]
    assert answer["grounded"] is True and answer["source"] == "llm"
    assert "Approved" not in answer["summary"]
    row = run.store.find("approval_requests", run_id=run.run_id)
    assert [item["status"] for item in row] == [value], "one request, decided by the human"


@pytest.mark.ac("AC-FEAT-006-06")
def test_gate_restarted_by_resume_keeps_one_request_and_assigns_each_plan_once(
    worker_env: ToolEnv,
    generated_offers: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[UUID]] = []
    original = worker_env.registry.assign

    def spy(plan_ids: Any, actor: UUID, run_id: UUID) -> list[dict[str, Any]]:
        calls.append(list(plan_ids))
        return original(plan_ids, actor, run_id)

    monkeypatch.setattr(worker_env.registry, "assign", spy)
    run = approved_once(worker_env, tmp_path)
    assert run.start().waiting
    plans = run.pending()["payload"]["plans"]
    assert len(plans) >= 2, "this check needs at least two plans"
    outcome = run.decide("approve")
    assert not outcome.waiting
    # The node body ran twice (before and after the interrupt) but left one request behind.
    requests = run.store.find("approval_requests", run_id=run.run_id)
    assert len(requests) == 1 and requests[0]["status"] == "approve"
    events = run.store.events(run.run_id)
    assert [e["event"] for e in events].count("approval_required") == 1
    assert [step["type"] for step in run.steps()].count("interrupt") == 1
    # assign ran once, for every approved plan exactly once, in one transaction.
    assert len(calls) == 1 and len(calls[0]) == len(plans) == len(set(calls[0]))
    created = run.assignments()
    assert sorted(item.route_plan_id for item in created) == sorted(calls[0])
    assert all(
        item.agent_run_id == run.run_id and item.approved_by == run.user.id for item in created
    )
    assert all(item.status == "active" for item in created)
    assert outcome.state["assigned"] is True


@pytest.mark.ac("AC-FEAT-006-38")
def test_request_approval_reports_conflicting_unvalidated_and_consistent_sets(
    worker_env: ToolEnv, generated_offers: object
) -> None:
    env = worker_env
    pool = env.planning_pool(D1_POOL)
    result = env.call("route_planner", "optimize_driver", driver_ref="D1", offer_ids=pool)
    first, second, *_ = (plan["plan_ref"] for plan in result["plans"]["profit"])
    request = {"action": "assign_plan", "summary": "Proposed"}
    # Plans of one driver share offers: validated or not, they cannot be approved together.
    reply = env.call("dispatcher", "request_approval", plan_refs=[first, second], **request)
    assert reply["accepted"] is False and env.state["pending_approval"] is None
    assert {item["code"] for item in reply["problems"]} == {"PLAN_NOT_VALIDATED"}
    assert not env.registry.validate_plans(env.state)
    reply = env.call("dispatcher", "request_approval", plan_refs=[first, second], **request)
    assert reply["accepted"] is False and env.state["pending_approval"] is None
    assert {item["plan_ref"] for item in reply["problems"]} == {first, second}
    assert {item["code"] for item in reply["problems"]} == {"CONFLICTING_PLANS"}
    # One plan of a validated, consistent set is accepted and prepares the gate's payload.
    reply = env.call("dispatcher", "request_approval", plan_refs=[first], **request)
    assert reply == {"accepted": True, "problems": []}
    pending = env.state["pending_approval"]
    assert pending["plan_refs"] == [first] and len(pending["plan_ids"]) == 1
    assert [row["planRef"] for row in pending["payload"]["plans"]] == [first]
    assert set(pending["payload"]["totals"]) >= {"netProfit", "fuelL", "co2Kg"}
    unknown = env.call("dispatcher", "request_approval", plan_refs=["PLAN-ffffffff"], **request)
    assert unknown == {
        "accepted": False,
        "problems": [{"plan_ref": "PLAN-ffffffff", "code": "NOT_FOUND"}],
    }


@pytest.mark.ac("AC-FEAT-006-38")
def test_a_conflicting_request_never_reaches_the_gate_and_a_consistent_one_does(
    worker_env: ToolEnv, generated_offers: object, tmp_path: Path
) -> None:
    def conflicting(messages: Any) -> list[str]:
        return same_driver_plans(messages, "D1", 2)

    run = scenario(
        worker_env,
        tmp_path,
        request_approval(conflicting),
        decision("approve"),
        decision("finish"),
    )
    outcome = run.start()
    replies = [
        json.loads(str(message.content))
        for _role, messages in run.recorded()
        for message in messages
        if isinstance(message, ToolMessage) and "accepted" in str(message.content)
    ]
    assert replies and replies[0]["accepted"] is False
    assert {item["code"] for item in replies[0]["problems"]} == {"CONFLICTING_PLANS"}
    assert not outcome.waiting and "ApprovalGate" not in {s["agent"] for s in run.steps()}
    assert run.store.find("approval_requests", run_id=run.run_id) == []
    assert run.assignments() == []


def offer_uuid(env: ToolEnv, reference: str) -> str:
    if reference.startswith("OFF-"):
        assert reference == f"OFF-{env.offer.id.hex[:8]}"
        return str(env.offer.id)
    return str(env.freight.get_by_source_id(reference).id)


def make_stale(env: ToolEnv, run: Scenario, plan_ref: str) -> None:
    """Another dispatcher takes one offer of the plan after the approval was requested."""
    plan = next(row for row in run.pending()["payload"]["plans"] if row["planRef"] == plan_ref)
    offers = env.jobs.repository.table("freight_offers")
    taken = offer_uuid(env, plan["offerIds"][0])
    with env.freight.engine.begin() as connection:
        connection.execute(update(offers).where(offers.c.id == taken).values(status="assigned"))


@pytest.mark.ac("AC-FEAT-006-39")
def test_a_stale_plan_aborts_the_whole_approval_and_a_later_request_for_the_rest_succeeds(
    worker_env: ToolEnv, generated_offers: object, tmp_path: Path
) -> None:
    run = scenario(
        worker_env,
        tmp_path,
        request_approval(),
        decision("approve"),
        request_approval(pick_plans),  # the Dispatcher drops the plan named in the notes
        decision("approve"),
        decision("finish"),
    )
    assert run.start().waiting
    plans = run.pending()["payload"]["plans"]
    assert len(plans) >= 2
    stale_ref = plans[-1]["planRef"]
    kept = [row["planRef"] for row in plans[:-1]]
    make_stale(worker_env, run, stale_ref)
    outcome = run.decide("approve")
    # Nothing at all was assigned, although the other plans were fine, and the Dispatcher was
    # told which plan failed.
    assert run.assignments() == []
    notes = " ".join(outcome.state["notes"])
    assert "PLAN_NOT_ASSIGNABLE" in notes and stale_ref in notes
    assert not set(PLAN_REF.findall(notes)) & set(kept), "only the stale plan is named"
    assert outcome.waiting, "the Dispatcher asked again for the remaining plans"
    again = run.pending()["payload"]["plans"]
    assert [row["planRef"] for row in again] == kept
    # Approving the remaining plans alone succeeds.
    final = run.decide("approve")
    assert not final.waiting and final.state["assigned"] is True
    created = run.assignments()
    assert len(created) == len(kept) and all(item.status == "active" for item in created)
    statuses = [row["status"] for row in run.store.find("approval_requests", run_id=run.run_id)]
    assert statuses == ["approve", "approve"]
