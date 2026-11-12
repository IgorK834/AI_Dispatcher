"""Demo orchestration uses service boundaries and preserves account/audit data."""

import secrets
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import MetaData, Table, func, inspect, select, text

from routepilot.bootstrap import DemoDataService, GenerateInput
from routepilot.fleet.service import FleetService
from routepilot.freight.service import FreightService, ImportService
from routepilot.identity.service import IdentityService
from routepilot.integrations.timocom.mapper import TimocomV3Mapper
from routepilot.shared.clock import FixedClock
from routepilot.shared.config import Settings
from routepilot.shared.db.engine import make_engine, migration_config


@pytest.mark.ac("AC-FEAT-002-15", "AC-FEAT-002-17", "AC-FEAT-002-18")
def test_first_seed_restart_and_reset(tmp_path) -> None:
    url = f"sqlite:///{tmp_path}/seed.db"
    command.upgrade(migration_config(url), "head")
    engine = make_engine(url)
    settings = Settings(
        _env_file=None,
        app_env="test",
        secret_key=secrets.token_hex(32),
        mock_seed=20261109,
        mock_reference_date="2026-11-16",
    )
    clock = FixedClock(datetime(2026, 11, 16, tzinfo=UTC))
    identity = IdentityService(engine, settings, clock)
    identity.seed_accounts()
    fleet = FleetService(engine, clock, identity.audit)
    freight = FreightService(engine, clock, identity.audit)
    imports = ImportService(engine, clock, TimocomV3Mapper(), identity.audit)
    seed = DemoDataService(engine, clock, settings, fleet, imports, identity.audit)
    seed.ensure_seed()
    metadata = MetaData()
    tables = [
        Table(name, metadata, autoload_with=engine) for name in inspect(engine).get_table_names()
    ]
    with engine.connect() as connection:
        before = {
            table.name: connection.scalar(select(func.count()).select_from(table))
            for table in tables
        }
    seed.ensure_seed()
    with engine.connect() as connection:
        assert before == {
            table.name: connection.scalar(select(func.count()).select_from(table))
            for table in tables
        }
    assert len(fleet.list_drivers().items) == 5 and len(freight.all_offers()) == 150
    seed.generate(GenerateInput(seed=7, offers=25), str(uuid4()))
    result = seed.reset("system")
    assert result["drivers"] == result["vehicles"] == 5 and result["offers"]["imported"] == 150
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM users")) == 2
        assert connection.scalar(text("SELECT count(*) FROM driver_states")) == 5
        assert connection.scalar(text("SELECT count(*) FROM audit_events")) > before["audit_events"]
    assert len(freight.all_offers()) == 150
    engine.dispose()
