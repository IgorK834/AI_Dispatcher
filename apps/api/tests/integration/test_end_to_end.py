"""The whole product path on an empty database without any key (FEAT-007 FR-2, AC-FEAT-007-02).

First-start seed → demo login → a manual offer → a fleet optimisation → an agent run on a scripted
fake model up to `approval_required` → approve → assignments → the driver delete is refused. The
application is the production composition (`create_app`) served by uvicorn on temporary SQLite
files; only the chat models are the scripted offline models of `evals/`. The clock is fixed to a
Monday, so the run does not depend on the weekday it happens on.
"""

import secrets
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from alembic import command
from evals.fakes import offline_registry

from routepilot.main import create_app
from routepilot.shared.clock import FixedClock
from routepilot.shared.config import Settings
from routepilot.shared.db.engine import migration_config
from tests.agents.live_app import (
    LOGIN_KEY,
    NOW,
    AcceptingCaptcha,
    Event,
    LiveApp,
    free_port,
    scenario,
)

pytestmark = pytest.mark.integration

DEMO = "demo@example.invalid"
KEYS = ("google_api_key", "anthropic_api_key", "openai_api_key", "ors_api_key")


@contextmanager
def first_start(tmp_path: Path) -> Iterator[LiveApp]:
    """An empty database, no provider key, the approval scenario as the only chat model."""
    url = f"sqlite:///{tmp_path / 'routepilot.db'}"
    command.upgrade(migration_config(url), "head")
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=url,
        agents_db_path=str(tmp_path / "agents.db"),
        secret_key=secrets.token_hex(32),
        admin_email="admin@example.invalid",
        admin_password=LOGIN_KEY,
        demo_email=DEMO,
        demo_password=LOGIN_KEY,
        login_rate_limit_per_ip="1000/minute",
        login_rate_limit_per_account="1000/minute",
        **{key: "" for key in KEYS},
    )
    app = create_app(
        settings,
        clock=FixedClock(NOW),
        model_registry=offline_registry(settings, scenario("approval-driver")),
        captcha=AcceptingCaptcha(),
    )
    port = free_port()
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="on")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 30
    while not server.started:
        assert time.monotonic() < deadline and thread.is_alive(), "the server did not start"
        time.sleep(0.05)
    live = LiveApp(f"http://127.0.0.1:{port}", app, settings)
    try:
        yield live
    finally:
        live.http.close()
        server.should_exit = True
        thread.join(20)


def manual_offer() -> dict[str, Any]:
    return {
        "description": "Integration scenario load",
        "revenue": {"amountMinor": 15000, "currency": "EUR"},
        "weightKg": 500,
        "palletCount": 3,
        "palletType": "EUR_1200x800",
        "requiredBodyTypes": ["CURTAIN_SIDER"],
        "stops": [
            {
                "stopType": "LOADING",
                "city": "Katowice",
                "countryCode": "PL",
                "windowStart": "2026-11-16T08:00Z",
                "windowEnd": "2026-11-16T12:00Z",
            },
            {
                "stopType": "UNLOADING",
                "city": "Berlin",
                "countryCode": "DE",
                "windowStart": "2026-11-17T08:00Z",
                "windowEnd": "2026-11-17T12:00Z",
            },
        ],
    }


def wait_for_job(live: LiveApp, job_id: str, timeout: float = 240) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job: dict[str, Any] = live.http.get(f"/api/v1/optimization-jobs/{job_id}").json()
        if job["status"] in {"succeeded", "failed", "cancelled"}:
            return job
        time.sleep(0.5)
    raise AssertionError(f"job {job_id} did not finish")


def is_approval(event: Event) -> bool:
    return event.event == "approval_required"


@pytest.mark.ac("AC-FEAT-007-02")
def test_the_whole_product_path_runs_on_an_empty_database_without_any_key(tmp_path: Path) -> None:
    with first_start(tmp_path) as live:
        # 1. The first start seeded the demo world; the demo account can sign in.
        live.sign_in(DEMO)
        drivers = live.http.get("/api/v1/drivers").json()["items"]
        assert len(drivers) == 5

        # 2. A manual offer through the API.
        created = live.http.post("/api/v1/freight-offers", json=manual_offer())
        assert created.status_code == 201
        assert created.headers["Location"].endswith(created.json()["id"])

        # 3. A fleet optimisation (three days, two offers per plan keep the run short).
        job = live.http.post(
            "/api/v1/optimization-jobs",
            json={"scope": "fleet", "params": {"horizonDays": 3, "maxOffersPerPlan": 2}},
        )
        assert job.status_code == 202
        assert wait_for_job(live, job.json()["id"])["status"] == "succeeded"
        result = live.http.get(f"/api/v1/optimization-jobs/{job.json()['id']}/result").json()
        assert set(result["fleet"]) == {"profit", "fastest", "fuel"}
        assert set(result["baselines"]) == {"baselineSingle", "baselineGreedy"}
        assert live.http.get("/api/v1/assignments").json()["items"] == []  # a run assigns nothing

        # 4. An agent run on the scripted model stops at the approval request.
        _, run_id = live.start_run()
        live.stream(run_id, until=is_approval)
        pending = live.wait_for(run_id, {"waiting_approval"})["pendingApproval"]
        assert pending["action"] == "assign_plan" and pending["payload"]["plans"]
        assert live.http.get("/api/v1/assignments").json()["items"] == []

        # 5. Approving it assigns the plans and finishes the run.
        decided = live.http.post(
            f"/api/v1/agent/runs/{run_id}/resume",
            json={"approvalId": pending["approvalId"], "decision": "approve"},
        )
        assert decided.status_code == 202
        assert live.wait_for(run_id, {"succeeded", "failed", "cancelled"})["status"] == "succeeded"
        assignments = live.http.get("/api/v1/assignments").json()["items"]
        assert assignments and all(item["status"] == "active" for item in assignments)

        # 6. The assigned driver cannot be deleted any more.
        plan = live.http.get(f"/api/v1/route-plans/{assignments[0]['routePlanId']}").json()
        refused = live.http.delete(f"/api/v1/drivers/{plan['driverId']}")
        assert refused.status_code == 409
        assert refused.json()["code"] == "DRIVER_HAS_ACTIVE_ASSIGNMENT"
