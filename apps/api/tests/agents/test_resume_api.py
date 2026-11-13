"""Approval over HTTP on the real application: nothing is written before the decision (AC-03)
and an approval by a dispatcher commits the plan and lets the run finish (AC-04)."""

import pytest

from tests.agents.live_app import Event, serve


def is_approval(event: Event) -> bool:
    return event.event == "approval_required"


@pytest.mark.ac("AC-FEAT-006-03")
def test_run_waits_for_approval_and_writes_nothing_before_the_decision(tmp_path) -> None:
    with serve(tmp_path, scenario_id="approval-driver") as live:
        live.sign_in_as("dispatcher")
        _, run_id = live.start_run()
        events = live.stream(run_id, until=is_approval)
        run = live.wait_for(run_id, {"waiting_approval"})

        assert live.count("assignments") == 0
        assert live.count("approval_requests", run_id=run_id, status="pending") == 1
        assert live.count("freight_offers", status="assigned") == 0
        assert run["pendingApproval"]["action"] == "assign_plan"

        payload = events[-1].data["payload"]
        assert payload["plans"], "the approval request lists the plans"
        plan = payload["plans"][0]
        assert {"planRef", "routePlanId", "driverRef", "driverLabel", "offerIds"} <= set(plan)
        assert {"netProfit", "fuelL", "co2Kg"} <= set(payload["totals"])
        assert events[-1].data["approvalId"] == run["pendingApproval"]["approvalId"]


@pytest.mark.ac("AC-FEAT-006-04")
def test_approval_by_a_dispatcher_assigns_the_plan_and_the_run_finishes(tmp_path) -> None:
    with serve(tmp_path, scenario_id="approval-driver") as live:
        user_id = live.sign_in_as("dispatcher")
        _, run_id = live.start_run()
        live.stream(run_id, until=is_approval)
        pending = live.wait_for(run_id, {"waiting_approval"})["pendingApproval"]
        planned = pending["payload"]["plans"]

        decided = live.http.post(
            f"/api/v1/agent/runs/{run_id}/resume",
            json={"approvalId": pending["approvalId"], "decision": "approve"},
        )
        assert decided.status_code == 202
        run = live.wait_for(run_id, {"succeeded", "failed", "cancelled"})

        assert run["status"] == "succeeded"
        assert run["finalAnswer"] is not None and run["error"] is None
        assignments = live.http.get("/api/v1/assignments").json()["items"]
        assert len(assignments) == len(planned)  # one active assignment per approved plan
        for assignment in assignments:
            assert assignment["status"] == "active"
            assert assignment["agentRunId"] == run_id
            assert assignment["approvedBy"] == str(user_id)
        plan = live.http.get(f"/api/v1/route-plans/{planned[0]['routePlanId']}").json()
        assert live.count("freight_offers", status="assigned") == len(plan["offerIds"])
        events = live.stream(run_id)
        resolved = [event for event in events if event.event == "approval_resolved"]
        assert [event.data["decision"] for event in resolved] == ["approve"]
        assert resolved[0].data["decidedBy"] == str(user_id)
        assert events[-1].event == "run_finished" and events[-1].data["status"] == "succeeded"
