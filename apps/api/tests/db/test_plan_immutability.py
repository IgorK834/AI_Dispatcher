"""Stored snapshots, plans and stops never change after their sources do (FEAT-004 AC-16)."""

import json

import pytest
from sqlalchemy import select, update

from routepilot.optimization.jobs.repository import JobRow


def table_rows(service, name: str) -> list[dict]:
    table = service.repository.table(name)
    with service.repository.engine.connect() as connection:
        rows = connection.execute(select(table).order_by(table.c.id)).mappings().all()
    return json.loads(json.dumps([dict(row) for row in rows], default=str))


@pytest.mark.ac("AC-FEAT-004-16")
def test_snapshot_plans_and_stops_are_unchanged_after_a_driver_offer_and_profile_edit(routed_job):
    service, plans, _assignments, _user, job_id = routed_job
    plan_id = service.result(job_id).fleet["profit"].assignments[0].route_plan_id
    before_plan = plans.get(plan_id).model_dump(mode="json")
    stored_before = {name: table_rows(service, name) for name in ("route_plans", "route_stops")}
    assert stored_before["route_plans"] and stored_before["route_stops"], "plans were stored"
    with service.repository.session() as session:
        row = session.get(JobRow, job_id)
        request_before, result_before = json.dumps(row.request), json.dumps(row.result)

    for name, values in [
        ("drivers", {"name": "Changed synthetic name"}),
        ("cost_profiles", {"fuel_price_minor_per_l": 999}),
        ("freight_offers", {"revenue_amount_minor": 1}),
    ]:
        table = service.repository.table(name)
        with service.repository.engine.begin() as connection:
            connection.execute(update(table).values(**values))

    for name, rows in stored_before.items():
        assert table_rows(service, name) == rows, f"{name} rows are unchanged"
    with service.repository.session() as session:
        row = session.get(JobRow, job_id)
        assert json.dumps(row.request) == request_before, "the input snapshot is unchanged"
        assert json.dumps(row.result) == result_before, "the stored result is unchanged"
    assert plans.get(plan_id).model_dump(mode="json") == before_plan
    assert plans.validate(plan_id).valid, "the stored plan still validates against its snapshot"
