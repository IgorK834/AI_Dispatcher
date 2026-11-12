"""First start on an empty database with no API keys (FEAT-002 FR-25, FR-26, AC-FEAT-002-15)."""

import json
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, Table, func, inspect, select, text
from sqlalchemy.engine import Engine

from routepilot.main import create_app
from routepilot.shared.config import Settings
from routepilot.shared.db.engine import make_engine, migration_config
from tests.factories import PassCaptcha

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[4]
OFFER_ROWS = "SELECT id, source_offer_id, version, updated_at FROM freight_offers ORDER BY id"
KEYS = ("google_api_key", "anthropic_api_key", "openai_api_key", "ors_api_key")


def settings_for(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        database_url=f"sqlite:///{tmp_path / 'first.db'}",
        agents_db_path=str(tmp_path / "agents.db"),
        secret_key="s" * 64,
        mock_seed=20261109,
        mock_reference_date="2026-11-16",
    )


def counts(engine: Engine) -> dict[str, int]:
    metadata = MetaData()
    names = inspect(engine).get_table_names()
    with engine.connect() as connection:
        return {
            name: connection.scalar(
                select(func.count()).select_from(Table(name, metadata, autoload_with=engine))
            )
            or 0
            for name in names
        }


def start(settings: Settings) -> None:
    with TestClient(create_app(settings, captcha=PassCaptcha())) as client:
        assert client.get("/ready").status_code == 200


@pytest.mark.ac("AC-FEAT-002-15")
def test_the_first_start_builds_the_demo_world_without_any_api_key(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    assert all(getattr(settings, key) == "" for key in KEYS)
    command.upgrade(migration_config(settings.database_url), "head")
    engine = make_engine(settings.database_url)
    assert counts(engine)["drivers"] == 0  # truly empty

    start(settings)

    with engine.connect() as connection:

        def one(sql: str) -> Any:
            return connection.execute(text(sql)).scalar_one()

        assert one("SELECT count(*) FROM users") == 2
        assert {r[0] for r in connection.execute(text("SELECT role FROM users"))} == {
            "admin",
            "demo",
        }
        assert one("SELECT count(*) FROM cost_profiles WHERE name = 'DEMO-DEFAULT'") == 1
        assert one("SELECT count(*) FROM drivers") == 5
        assert one("SELECT count(*) FROM vehicles") == 5
        assert one("SELECT count(*) FROM driver_states") == 5
        assert one("SELECT count(*) FROM freight_offers") == 150
        assert one("SELECT count(*) FROM freight_stops") == 300
        assert one("SELECT count(*) FROM raw_freight_records") == 150
        assert one("SELECT count(*) FROM import_batches") == 1
        seed = json.loads(one("SELECT value FROM app_meta WHERE key = 'seed_version'"))
        assert set(seed) == {"version", "seed", "referenceDate", "at"}
        assert (seed["version"], seed["seed"], seed["referenceDate"]) == (1, 20261109, "2026-11-16")
        assert one("SELECT count(*) FROM audit_events WHERE action = 'demo_data.generated'") == 1
    engine.dispose()


@pytest.mark.ac("AC-FEAT-002-15")
def test_a_second_start_changes_no_row_count_and_no_row(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    command.upgrade(migration_config(settings.database_url), "head")
    engine = make_engine(settings.database_url)
    start(settings)
    first = counts(engine)
    with engine.connect() as connection:
        offers = connection.execute(text(OFFER_ROWS)).all()
        drivers = connection.execute(text("SELECT id, version, updated_at FROM drivers")).all()

    start(settings)

    assert counts(engine) == first
    with engine.connect() as connection:
        assert offers == connection.execute(text(OFFER_ROWS)).all()  # not re-imported, not updated
        assert (
            drivers == connection.execute(text("SELECT id, version, updated_at FROM drivers")).all()
        )
    engine.dispose()


@pytest.mark.ac("AC-FEAT-002-15")
def test_the_seeded_world_is_reachable_through_the_api(tmp_path: Path) -> None:
    from tests.factories import ORIGIN, login

    settings = settings_for(tmp_path)
    command.upgrade(migration_config(settings.database_url), "head")
    with TestClient(create_app(settings, captcha=PassCaptcha())) as client:
        login(client, "demo")
        headers: dict[str, Any] = {"Origin": ORIGIN}
        drivers = client.get("/api/v1/drivers", headers=headers).json()["items"]
        assert len(drivers) == 5 and all(d["isSynthetic"] for d in drivers)
        assert all(d["vehicle"] and d["state"] for d in drivers)
        offers = client.get("/api/v1/freight-offers?limit=100", headers=headers).json()
        assert len(offers["items"]) == 100 and offers["nextCursor"]
        profiles = client.get("/api/v1/cost-profiles", headers=headers).json()["items"]
        assert [p["name"] for p in profiles] == ["DEMO-DEFAULT"]
