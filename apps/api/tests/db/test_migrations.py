"""AC-FEAT-001-02: reversible initial schema and specified constraints."""

from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import inspect

from routepilot.shared.db.engine import make_engine, migration_config

TABLES = {
    "users",
    "sessions",
    "drivers",
    "driver_states",
    "vehicles",
    "cost_profiles",
    "import_batches",
    "raw_freight_records",
    "freight_offers",
    "freight_stops",
    "optimization_jobs",
    "route_plans",
    "route_stops",
    "assignments",
    "agent_threads",
    "agent_runs",
    "agent_steps",
    "approval_requests",
    "route_explanations",
    "routing_cache",
    "audit_events",
    "app_meta",
}


@pytest.mark.ac("AC-FEAT-001-02")
def test_up_down_up_and_constraints(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    config = migration_config(url)
    engine = make_engine(url)
    command.upgrade(config, "head")
    first = inspect(engine)
    assert set(first.get_table_names()) == TABLES | {"alembic_version"}
    columns = {name: {c["name"] for c in first.get_columns(name)} for name in TABLES}
    assert {"user_message", "final_answer", "idempotency_key"} <= columns["agent_runs"]
    assert {"co2_g", "fuel_ml", "distance_m", "empty_m", "fleet_role"} <= columns["route_plans"]
    assert "result" in columns["optimization_jobs"]
    assert "expires_at" in columns["approval_requests"]
    for table in ["agent_runs", "route_explanations"]:
        assert {"cost_estimate_minor", "currency"} <= columns[table]
    assert "version" not in columns["driver_states"]
    assert {"public_remark", "loading_length_mm"} <= columns["freight_offers"]
    assert any(
        set(c["column_names"]) == {"source", "source_offer_id"}
        for c in first.get_unique_constraints("freight_offers")
    )
    assert any(
        set(c["column_names"]) == {"offer_id", "sequence"}
        for c in first.get_unique_constraints("freight_stops")
    )
    assert any(
        "window_start <= window_end" in c["sqltext"]
        for c in first.get_check_constraints("freight_stops")
    )
    assert (
        not first.get_foreign_keys("assignments")[0].get("options", {}).get("ondelete") == "CASCADE"
    )
    command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    command.upgrade(config, "head")
    assert {
        name: {c["name"] for c in inspect(engine).get_columns(name)} for name in TABLES
    } == columns
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    engine.dispose()
