"""Admin demo-data endpoints: generate and reset (FEAT-002 FR-27, §6.7)."""

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, Table, delete, func, insert, inspect, select, text
from sqlalchemy.engine import Engine

from tests.factories import ORIGIN, api_client, driver, offer

GENERATE = "/api/v1/admin/demo-data/generate"
RESET = "/api/v1/admin/demo-data/reset"
FIXED = {"mock_seed": 20261109, "mock_reference_date": "2026-11-16"}
KEPT = {"users", "sessions", "audit_events"}  # reset never deletes these (plus app_meta keys)


def engine_of(client: TestClient) -> Engine:
    engine: Engine = client.app.state.services.fleet.engine
    return engine


def table(engine: Engine, name: str) -> Table:
    return Table(name, MetaData(), autoload_with=engine)


def count(engine: Engine, name: str) -> int:
    with engine.connect() as connection:
        return connection.scalar(select(func.count()).select_from(table(engine, name))) or 0


def insert_row(engine: Engine, name: str, **given: Any) -> str:
    """Insert a row, filling every other required column with a placeholder.

    Reflected tables expose the stored form: ids and datetimes are text, so they are written so.
    """
    target = table(engine, name)
    values: dict[str, Any] = {"id": str(uuid.uuid4())}
    values.update({key: str(v) if isinstance(v, uuid.UUID) else v for key, v in given.items()})
    for column in target.columns:
        if column.name in values or column.nullable or column.server_default is not None:
            continue
        kind = str(column.type).upper()
        if column.name.endswith("_id"):
            values[column.name] = str(uuid.uuid4())
        elif column.name.endswith("_at"):
            values[column.name] = datetime(2026, 11, 16, tzinfo=UTC).isoformat()
        elif "INT" in kind or "BOOL" in kind:
            values[column.name] = 0
        elif "JSON" in kind:
            values[column.name] = {}
        else:
            values[column.name] = "x"
    with engine.begin() as connection:
        connection.execute(insert(target).values(**values))
    return str(values["id"])


def world(engine: Engine) -> dict[str, list[tuple[Any, ...]]]:
    """The demo data of a database, without ids, timestamps and other volatile columns."""
    out: dict[str, list[tuple[Any, ...]]] = {}
    volatile = {"id", "created_at", "updated_at", "fetched_at", "valid_from", "started_at"}
    for name in (
        "cost_profiles",
        "vehicles",
        "drivers",
        "driver_states",
        "freight_offers",
        "freight_stops",
        "raw_freight_records",
    ):
        target = table(engine, name)
        keep = [
            c.name
            for c in target.columns
            if c.name not in volatile
            and not (c.name.endswith("_id") and c.name != "source_offer_id")
        ]
        with engine.connect() as connection:
            rows = connection.execute(select(*[target.c[c] for c in keep])).all()
        out[name] = sorted(tuple(map(repr, row)) for row in rows)
    return out


@pytest.mark.ac("AC-FEAT-002-16")
def test_admin_generates_with_a_seed_and_the_action_is_audited(tmp_path: Path) -> None:
    with api_client(tmp_path, "admin", seeded=True, settings_overrides=FIXED) as client:
        engine = engine_of(client)
        before = world(engine)
        audit_before = count(engine, "audit_events")

        response = client.post(GENERATE, json={"seed": 7})
        body = response.json()
        assert response.status_code == 200, response.text
        uuid.UUID(body["importBatchId"])
        assert (body["drivers"], body["vehicles"]) == (5, 5)
        assert set(body["offers"]) == {"imported", "updated", "unchanged", "failed"}
        assert sum(body["offers"].values()) == 150 and body["offers"]["failed"] == 0

        assert world(engine) != before  # another seed, another world
        assert count(engine, "drivers") == count(engine, "vehicles") == 5  # upserted, not doubled
        # The same ids are updated with the new payloads, never duplicated.
        assert count(engine, "freight_offers") == 150 and body["offers"]["updated"] > 0
        assert count(engine, "raw_freight_records") == 300  # the old and the new raw payloads

        with engine.connect() as connection:
            event = connection.execute(
                text(
                    "SELECT actor, entity_type, diff FROM audit_events "
                    "WHERE action = 'demo_data.generated' ORDER BY at DESC LIMIT 1"
                )
            ).one()
            admin = connection.execute(
                text("SELECT id FROM users WHERE role = 'admin'")
            ).scalar_one()
        assert count(engine, "audit_events") > audit_before
        assert event.actor == admin and event.entity_type == "demo_data"
        assert '"seed": 7' in str(event.diff) or '"seed":7' in str(event.diff)


@pytest.mark.ac("AC-FEAT-002-16")
def test_generating_the_same_seed_again_changes_nothing(tmp_path: Path) -> None:
    with api_client(tmp_path, "admin", seeded=True, settings_overrides=FIXED) as client:
        first = client.post(GENERATE, json={"seed": 7, "referenceDate": "2026-11-16"}).json()
        engine = engine_of(client)
        snapshot = world(engine)
        second = client.post(GENERATE, json={"seed": 7, "referenceDate": "2026-11-16"}).json()
        assert second["offers"]["unchanged"] == 150 and second["offers"]["imported"] == 0
        assert world(engine) == snapshot and second["importBatchId"] != first["importBatchId"]


@pytest.mark.ac("AC-FEAT-002-16")
@pytest.mark.parametrize("role", ["dispatcher", "demo"])
def test_only_an_admin_may_generate_or_reset(tmp_path: Path, role: str) -> None:
    with api_client(tmp_path, role, seeded=True, settings_overrides=FIXED) as client:
        for path, body in ((GENERATE, {"seed": 7}), (RESET, None)):
            response = client.post(path, json=body)
            assert response.status_code == 403 and response.json()["code"] == "FORBIDDEN"
        assert count(engine_of(client), "drivers") == 5  # nothing happened


@pytest.mark.ac("AC-FEAT-002-16")
def test_anonymous_callers_are_refused(tmp_path: Path) -> None:
    with api_client(tmp_path, "admin", seeded=True) as client:
        anonymous = TestClient(client.app)
        anonymous.headers["Origin"] = ORIGIN
        assert anonymous.post(GENERATE, json={}).status_code == 401
        assert anonymous.post(RESET).status_code == 401


@pytest.mark.ac("AC-FEAT-002-16")
@pytest.mark.parametrize(
    "body",
    [
        {"drivers": 6},
        {"drivers": 4},
        {"offers": 0},
        {"offers": 501},
        {"seed": "seven"},
        {"referenceDate": "not-a-date"},
        {"unknown": 1},
    ],
)
def test_invalid_requests_are_422_and_change_nothing(tmp_path: Path, body: dict[str, Any]) -> None:
    with api_client(tmp_path, "admin", seeded=True, settings_overrides=FIXED) as client:
        engine = engine_of(client)
        snapshot = world(engine)
        response = client.post(GENERATE, json=body)
        assert response.status_code == 422
        assert response.headers["content-type"] == "application/problem+json"
        assert response.json()["code"] == "VALIDATION_ERROR"
        assert world(engine) == snapshot


@pytest.mark.ac("AC-FEAT-002-16")
def test_the_offer_count_is_honoured(tmp_path: Path) -> None:
    with api_client(tmp_path, "admin", seeded=True, settings_overrides=FIXED) as client:
        body = client.post(GENERATE, json={"offers": 20}).json()
        assert sum(body["offers"].values()) == 20


@pytest.mark.ac("AC-FEAT-002-17")
def test_reset_removes_everything_user_made_and_restores_the_first_start_world(
    tmp_path: Path,
) -> None:
    with api_client(tmp_path, "admin", seeded=True, settings_overrides=FIXED) as client:
        engine = engine_of(client)
        fresh = world(engine)
        fresh_counts = {n: count(engine, n) for n in inspect(engine).get_table_names()}

        # User-made data: a manual offer, a driver, a vehicle and a cost profile.
        manual = client.post("/api/v1/freight-offers", json=offer()).json()["id"]
        own_driver = client.post("/api/v1/drivers", json=driver(0)).json()["id"]
        # A job, a route plan and an assignment (inserted directly: FEAT-004 is not needed here).
        with engine.connect() as connection:
            admin = connection.execute(text("SELECT id FROM users WHERE role='admin'")).scalar_one()
            seeded_driver = connection.execute(text("SELECT id FROM drivers LIMIT 1")).scalar_one()
        job = insert_row(engine, "optimization_jobs", requested_by=admin, status="succeeded")
        plan = insert_row(
            engine,
            "route_plans",
            job_id=job,
            driver_id=seeded_driver,
        )
        assignment = insert_row(
            engine,
            "assignments",
            route_plan_id=plan,
            driver_id=seeded_driver,
            approved_by=admin,
            status="active",
            version=1,
        )
        insert_row(engine, "agent_threads", user_id=admin)
        assert count(engine, "optimization_jobs") == count(engine, "assignments") == 1

        users_before = count(engine, "users")
        audit_before = count(engine, "audit_events")
        with engine.connect() as connection:
            old_events = {r[0] for r in connection.execute(text("SELECT id FROM audit_events"))}
            secret = connection.execute(
                text("SELECT value FROM app_meta WHERE key = 'secret_key'")
            ).scalar_one_or_none()

        response = client.post(RESET)
        assert response.status_code == 200, response.text
        body = response.json()
        assert (body["drivers"], body["vehicles"]) == (5, 5)
        assert body["offers"]["imported"] == 150 and body["offers"]["failed"] == 0

        # Everything user-made is gone ...
        assert client.get(f"/api/v1/freight-offers/{manual}").status_code == 404
        assert client.get(f"/api/v1/drivers/{own_driver}").status_code == 404
        for name, row_id in (("optimization_jobs", job), ("assignments", assignment)):
            gone = table(engine, name)
            with engine.connect() as connection:
                assert connection.execute(select(gone).where(gone.c.id == row_id)).first() is None
        for name in ("optimization_jobs", "route_plans", "assignments", "agent_threads"):
            assert count(engine, name) == 0, name

        # ... users, their sessions and the audit history stay ...
        assert count(engine, "users") == users_before
        assert client.get("/api/v1/auth/me").status_code == 200  # the admin session survived
        with engine.connect() as connection:
            now_events = {r[0] for r in connection.execute(text("SELECT id FROM audit_events"))}
            assert old_events <= now_events and len(now_events) > audit_before
            assert (
                connection.execute(
                    text("SELECT count(*) FROM audit_events WHERE action = 'demo_data.reset'")
                ).scalar_one()
                == 1
            )
            assert (
                secret
                == connection.execute(
                    text("SELECT value FROM app_meta WHERE key = 'secret_key'")
                ).scalar_one_or_none()
            )

        # ... and the demo data equals a fresh first-start seed.
        assert world(engine) == fresh
        after = {n: count(engine, n) for n in inspect(engine).get_table_names()}
        for name, number in fresh_counts.items():
            if name not in KEPT | {"app_meta"}:
                assert after[name] == number, name


@pytest.mark.ac("AC-FEAT-002-17")
def test_reset_also_undoes_a_generate_with_another_seed(tmp_path: Path) -> None:
    with api_client(tmp_path, "admin", seeded=True, settings_overrides=FIXED) as client:
        engine = engine_of(client)
        fresh = world(engine)
        client.post(GENERATE, json={"seed": 7, "offers": 30})
        assert world(engine) != fresh
        assert client.post(RESET).status_code == 200
        assert world(engine) == fresh
        with engine.begin() as connection:  # leave the table in place for other readers
            connection.execute(delete(table(engine, "agent_threads")))
