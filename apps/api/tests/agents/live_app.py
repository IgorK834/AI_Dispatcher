"""A real application on scripted models, served by uvicorn so that SSE really streams.

The production composition (`create_app`: database, services, engine, tools, graph, approval
gate) runs on a temporary SQLite file with the synthetic demo data; only the chat models are the
offline evaluation fakes of `evals/`. Tests talk to it over HTTP with a session cookie and the
CSRF header, exactly like the web client.
"""

import json
import secrets
import socket
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import httpx
import uvicorn
from alembic import command
from evals.fakes import EvalModel, offline_registry
from evals.fixtures import prepare_fixture
from evals.schema import Scenario, load_scenarios
from fastapi import FastAPI
from sqlalchemy.orm import Session

from routepilot.agents.models import ModelPolicy, ModelRegistry, Role
from routepilot.identity.ports import CaptchaResult
from routepilot.identity.repository.models import User
from routepilot.main import create_app
from routepilot.shared.clock import FixedClock
from routepilot.shared.config import Settings
from routepilot.shared.db.engine import migration_config

EVALS = Path(__file__).resolve().parents[4] / "evals"
ORIGIN = "http://localhost:3000"
NOW = datetime(2026, 11, 16, 6, tzinfo=UTC)
LOGIN_KEY = "synthetic-test-password"
ROLES: list[Role] = [
    "dispatcher",
    "freight_scout",
    "fleet_compliance",
    "route_planner",
    "explainer",
]


class AcceptingCaptcha:
    def verify(self, token: str, remote_ip: str | None) -> CaptchaResult:
        return CaptchaResult(True, [])


def scenario(scenario_id: str) -> Scenario:
    return next(item for item in load_scenarios(EVALS) if item.id == scenario_id)


def provider_registry(settings: Settings, chosen: Scenario, provider: str) -> ModelRegistry:
    """The offline evaluation models registered under `<provider>:eval-<role>`."""
    from evals.schema import load_fixture

    offers = load_fixture(EVALS, chosen.offer_fixture)["offers"]
    controller: dict[str, Any] = {"offer_ids": [offer["id"] for offer in offers]}
    models = {role: EvalModel(role=role, scenario=chosen, controller=controller) for role in ROLES}
    for model in models.values():
        model.controller = controller
    policy = ModelPolicy.model_validate(
        {role: {"model": f"{provider}:eval-{role}", "maxTokens": 100} for role in ROLES}
    )
    return ModelRegistry(
        settings,
        policy,
        {f"{provider}:eval-{role}": lambda model=model: model for role, model in models.items()},
    )


@dataclass
class Event:
    id: int
    event: str
    data: dict[str, Any]


def parse_event(lines: list[str]) -> Event | None:
    fields = dict(
        line.split(": ", 1) for line in lines if ": " in line and not line.startswith(":")
    )
    if "event" not in fields:
        return None
    return Event(int(fields.get("id", "0")), fields["event"], json.loads(fields["data"]))


class LiveApp:
    def __init__(self, base_url: str, app: FastAPI, settings: Settings) -> None:
        self.http = httpx.Client(base_url=base_url, headers={"Origin": ORIGIN}, timeout=60)
        self.app = app
        self.settings = settings
        self.services: SimpleNamespace = app.state.services

    def add_user(self, role: str, email: str | None = None) -> str:
        """Insert a user the way `seed_accounts` does (only admin and demo are seeded)."""
        email = email or f"{role}-{uuid4().hex[:6]}@example.invalid"
        identity = self.services.identity
        with Session(identity.engine) as session, session.begin():
            session.add(
                User(
                    email=email,
                    password_hash=identity.password_hasher.hash(LOGIN_KEY),
                    role=role,
                    locale="en",
                    is_active=True,
                    failed_logins=0,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        return email

    def sign_in(self, email: str, password: str = LOGIN_KEY) -> UUID:
        self.sign_out()
        response = self.http.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password, "captchaToken": "ok"},
        )
        response.raise_for_status()
        self.http.headers["X-CSRF-Token"] = response.json()["csrfToken"]
        return UUID(response.json()["user"]["id"])

    def sign_in_as(self, role: str) -> UUID:
        return self.sign_in(self.add_user(role))

    def sign_out(self) -> None:
        self.http.cookies.clear()
        self.http.headers.pop("X-CSRF-Token", None)

    def post_message(self, thread_id: str, text: str = "Find loads") -> httpx.Response:
        return self.http.post(
            f"/api/v1/agent/threads/{thread_id}/messages",
            json={"content": text},
            headers={"Idempotency-Key": uuid4().hex},
        )

    def start_run(self, text: str = "Find loads") -> tuple[str, str]:
        thread = self.http.post("/api/v1/agent/threads", json={})
        thread.raise_for_status()
        accepted = self.post_message(thread.json()["id"], text)
        if accepted.status_code != 202:
            raise AssertionError(accepted.text)
        return thread.json()["id"], accepted.json()["runId"]

    def run(self, run_id: str) -> dict[str, Any]:
        response = self.http.get(f"/api/v1/agent/runs/{run_id}")
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    def wait_for(self, run_id: str, statuses: set[str], timeout: float = 90) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            run = self.run(run_id)
            if run["status"] in statuses:
                return run
            time.sleep(0.2)
        raise AssertionError(f"run {run_id} did not reach {statuses}: {self.run(run_id)}")

    def stream(
        self,
        run_id: str,
        *,
        after: int | None = None,
        until: Callable[[Event], bool] | None = None,
        timeout: float = 60,
    ) -> list[Event]:
        """Read the event stream until it closes or `until` accepts an event."""
        headers = {"Last-Event-ID": str(after)} if after is not None else {}
        events: list[Event] = []
        block: list[str] = []
        deadline = time.monotonic() + timeout
        with self.http.stream(
            "GET", f"/api/v1/agent/runs/{run_id}/events", headers=headers, timeout=timeout
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    block.append(line)
                else:
                    event = parse_event(block)
                    block = []
                    if event is not None:
                        events.append(event)
                        if until is not None and until(event):
                            return events
                if time.monotonic() > deadline:
                    raise AssertionError("event stream did not finish in time")
        return events

    def count(self, table: str, **where: Any) -> int:
        clause = " AND ".join(f"{column} = :{column}" for column in where) or "1 = 1"
        with self.services.identity.engine.connect() as connection:
            return int(
                connection.exec_driver_sql(
                    f"SELECT count(*) FROM {table} WHERE {clause}",  # noqa: S608  # reason: fixed table names in tests
                    where,
                ).scalar_one()
            )


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@contextmanager
def serve(
    tmp_path: Path,
    *,
    scenario_id: str | None = None,
    provider: str | None = None,
    **settings: Any,
) -> Iterator[LiveApp]:
    """Start the application; with a scenario the chat models are the offline evaluation fakes."""
    url = f"sqlite:///{tmp_path / 'app.db'}"
    command.upgrade(migration_config(url), "head")
    configured = Settings(
        _env_file=None,
        app_env="test",
        database_url=url,
        agents_db_path=str(tmp_path / "agents.db"),
        secret_key=secrets.token_hex(32),
        admin_email="admin@example.invalid",
        admin_password=LOGIN_KEY,
        demo_email="demo@example.invalid",
        demo_password=LOGIN_KEY,
        google_api_key="",
        anthropic_api_key="",
        openai_api_key="",
        login_rate_limit_per_ip="1000/minute",
        login_rate_limit_per_account="1000/minute",
        **settings,
    )
    chosen = scenario(scenario_id) if scenario_id else None
    registry = None
    if chosen is not None:
        registry = (
            provider_registry(configured, chosen, provider)
            if provider
            else offline_registry(configured, chosen)
        )
    app = create_app(
        configured, clock=FixedClock(NOW), model_registry=registry, captcha=AcceptingCaptcha()
    )
    port = free_port()
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="on")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 30
    while not server.started:
        if time.monotonic() > deadline or not thread.is_alive():
            raise RuntimeError("the test server did not start")
        time.sleep(0.05)
    live = LiveApp(f"http://127.0.0.1:{port}", app, configured)
    try:
        if chosen is not None:
            prepare_fixture(live.services, chosen, EVALS)
        yield live
    finally:
        live.http.close()
        server.should_exit = True
        thread.join(20)
