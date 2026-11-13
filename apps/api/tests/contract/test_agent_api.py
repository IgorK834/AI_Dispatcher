"""The agent API as a contract on the real application and scripted models.

AC-17 provider swap, AC-19 no model key, AC-23 resume authorisation, AC-24 daily budget.
"""

import ast
import time
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from tests.agents.live_app import LiveApp, serve

SOURCE = Path(__file__).resolve().parents[2] / "src" / "routepilot"
PROVIDER_PACKAGES = (
    "langchain_google_genai",
    "langchain_anthropic",
    "langchain_openai",
    "google.genai",
    "google.generativeai",
    "anthropic",
    "openai",
)


def sequence(live: LiveApp, run_id: str) -> list[tuple[str, str | None]]:
    """The run's events as (event, agent) pairs: what happened, independent of ids and times."""
    return [
        (event.event, event.data.get("agent"))
        for event in live.stream(run_id, after=0, until=lambda e: e.event == "approval_required")
    ]


@pytest.mark.ac("AC-FEAT-006-17")
def test_the_same_scenario_succeeds_under_two_providers_and_records_the_policy(tmp_path) -> None:
    runs: dict[str, tuple[dict, list[tuple[str, str | None]]]] = {}
    for provider in ("google_genai", "anthropic"):
        with serve(tmp_path / provider, scenario_id="approval-driver", provider=provider) as live:
            live.sign_in_as("dispatcher")
            _, run_id = live.start_run()
            run = live.wait_for(run_id, {"waiting_approval"})
            runs[provider] = (run, sequence(live, run_id))

    (google, google_events), (anthropic, anthropic_events) = runs["google_genai"], runs["anthropic"]
    assert google_events == anthropic_events  # no code path depends on the provider
    for provider, (run, _) in runs.items():
        policy = run["modelPolicy"]
        assert policy["dispatcher"]["model"] == f"{provider}:eval-dispatcher"
        assert policy["promptVersions"] == {
            role: "v1"
            for role in (
                "dispatcher",
                "explainer",
                "fleet_compliance",
                "freight_scout",
                "route_planner",
            )
        }
    assert google["modelPolicy"] != anthropic["modelPolicy"]


@pytest.mark.ac("AC-FEAT-006-17")
def test_only_the_model_registry_imports_a_provider_package() -> None:
    offenders = []
    for path in sorted(SOURCE.rglob("*.py")):
        if path == SOURCE / "agents" / "models.py":
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            for name in names:
                if any(name == pkg or name.startswith(pkg + ".") for pkg in PROVIDER_PACKAGES):
                    offenders.append(f"{path.relative_to(SOURCE)}: {name}")
    assert offenders == []


@pytest.mark.ac("AC-FEAT-006-19")
def test_without_a_model_key_the_app_says_so_and_the_non_ai_features_still_work(tmp_path) -> None:
    with serve(tmp_path) as live:  # no scenario: the real registry, no key configured
        live.sign_in("admin@example.invalid")
        status = live.http.get("/api/v1/agent/status")
        assert status.status_code == 200 and status.json()["aiEnabled"] is False

        thread = live.http.post("/api/v1/agent/threads", json={}).json()
        refused = live.post_message(thread["id"])
        assert refused.status_code == 503
        assert refused.json()["code"] == "AI_UNAVAILABLE"

        job = live.http.post(
            "/api/v1/optimization-jobs",
            headers={"Idempotency-Key": uuid4().hex},
            json={
                "scope": "fleet",
                "driverIds": [],
                "objectives": ["profit"],
                "params": {"horizonDays": 1, "maxOffersPerPlan": 2, "topKPerDriver": 10},
            },
        )
        assert job.status_code == 202, job.text
        deadline = time.monotonic() + 120
        state = job.json()
        while state["status"] not in {"succeeded", "failed", "cancelled"}:
            assert time.monotonic() < deadline, "the fleet job did not finish"
            time.sleep(0.5)
            state = live.http.get(f"/api/v1/optimization-jobs/{job.json()['id']}").json()
        assert state["status"] == "succeeded", state
        result = live.http.get(f"/api/v1/optimization-jobs/{job.json()['id']}/result").json()
        plan_id = result["fleet"]["profit"]["assignments"][0]["routePlanId"]

        explained = live.http.post(f"/api/v1/route-plans/{plan_id}/explanations", json={})
        assert explained.status_code == 201, explained.text
        assert explained.json()["source"] == "template"


@pytest.mark.ac("AC-FEAT-006-23")
def test_resume_is_refused_for_other_users_anonymous_callers_and_unknown_approvals(
    tmp_path,
) -> None:
    with serve(tmp_path, scenario_id="approval-driver") as live:
        owner = live.add_user("dispatcher")
        stranger = live.add_user("dispatcher")
        live.sign_in(owner)
        _, run_id = live.start_run()
        pending = live.wait_for(run_id, {"waiting_approval"})["pendingApproval"]
        approve = {"approvalId": pending["approvalId"], "decision": "approve"}
        resume = f"/api/v1/agent/runs/{run_id}/resume"

        def nothing_written() -> None:
            assert live.count("assignments") == 0
            assert live.count("approval_requests", run_id=run_id, status="pending") == 1

        live.sign_in(stranger)  # another user: the run does not exist for them
        assert live.http.get(f"/api/v1/agent/runs/{run_id}").status_code == 404
        assert live.http.post(resume, json=approve).status_code == 404
        nothing_written()

        live.sign_out()  # anonymous
        assert live.http.post(resume, json=approve).status_code == 401
        nothing_written()

        live.sign_in(owner)  # unknown approval id
        unknown = live.http.post(resume, json={"approvalId": str(uuid4()), "decision": "approve"})
        assert unknown.status_code == 409
        assert unknown.json()["code"] == "APPROVAL_NOT_PENDING"
        nothing_written()

        assert live.http.post(resume, json=approve).status_code == 202
        live.wait_for(run_id, {"succeeded", "failed", "cancelled"})
        again = live.http.post(resume, json=approve)
        assert again.status_code == 409
        assert again.json()["code"] == "APPROVAL_NOT_PENDING"
        assert live.count("assignments") == 1  # the second resume wrote nothing


@pytest.mark.ac("AC-FEAT-006-24")
def test_a_demo_user_over_the_demo_budget_gets_429_and_a_dispatcher_is_accepted(tmp_path) -> None:
    with serve(tmp_path, scenario_id="approval-driver", agent_daily_token_budget_demo=100) as live:
        demo = live.sign_in("demo@example.invalid")
        store = live.services.store
        now = live.services.agents.clock.now()
        thread = store.create(
            "agent_threads",
            {"user_id": demo, "title": "Earlier", "created_at": now, "updated_at": now},
        )
        store.create(
            "agent_runs",
            {
                "thread_id": thread["id"],
                "status": "succeeded",
                "user_message": "Earlier question",
                "model_policy": {},
                "tokens_in": 80,
                "tokens_out": 40,  # 120 tokens today, over the demo limit of 100
                "cost_estimate_minor": 0,
                "currency": "USD",
                "created_at": now,
            },
        )
        status = live.http.get("/api/v1/agent/status").json()
        assert status["dailyBudget"] == {"usedTokens": 120, "limitTokens": 100}
        created = live.http.post("/api/v1/agent/threads", json={}).json()
        refused = live.post_message(created["id"])
        assert refused.status_code == 429
        assert refused.json()["code"] == "AI_BUDGET_EXCEEDED"
        assert live.count("agent_runs") == 1  # nothing was started

        live.sign_in_as("dispatcher")  # the dispatcher limit is a separate, larger number
        _, run_id = live.start_run()
        assert live.wait_for(run_id, {"waiting_approval"})["status"] == "waiting_approval"
        assert UUID(run_id)
