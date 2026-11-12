"""Immutable stored schedule contracts and model-safe computed facts."""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import update

from routepilot.optimization.jobs.repository import JobRow


@pytest.mark.ac("AC-FEAT-004-16", "AC-FEAT-004-17")
def test_read_only_plan_and_snapshot_survive_source_edits(job_client):
    client, (service, plans, _assignments, _user, job_id) = job_client
    plan_id = service.result(job_id).fleet["profit"].assignments[0].route_plan_id
    before = plans.get(plan_id).model_dump(mode="json")
    with service.repository.session() as session:
        row = session.get(JobRow, job_id)
        snapshot = row.request.copy()
    for name, values in [
        ("drivers", {"name": "Changed synthetic name"}),
        ("cost_profiles", {"fuel_price_minor_per_l": 999}),
        ("freight_offers", {"revenue_amount_minor": 1}),
    ]:
        table = service.repository.table(name)
        with service.repository.engine.begin() as connection:
            connection.execute(update(table).values(**values))
    assert plans.get(plan_id).model_dump(mode="json") == before
    with service.repository.session() as session:
        assert session.get(JobRow, job_id).request == snapshot
    path = f"/api/v1/route-plans/{plan_id}"
    response = client.get(path)
    assert response.status_code == 200 and response.json()["stops"]
    assert response.json()["disclaimer"] == before["disclaimer"]
    assert client.patch(path, json={"netProfit": {"amountMinor": 123}}).status_code == 405
    assert client.get(f"/api/v1/route-plans/{uuid4()}").status_code == 404


@pytest.mark.ac("AC-FEAT-006-31", "AC-FEAT-006-32", "AC-FEAT-006-36")
def test_availability_rule_summary_and_comparison_are_computed_by_services(routed_job):
    service, plans, _assignments, _user, job_id = routed_job
    result = service.result(job_id)
    ids = [
        result.per_driver[0].plans[objective][0].id for objective in ("profit", "fastest", "fuel")
    ]
    availability = plans.driver_availability(result.per_driver[0].driver_id)
    assert availability.remaining.work_today_min == 720
    assert availability.remaining_561.drive_before_break_min == 270
    assert availability.remaining_561.drive_today_min == 540
    assert not availability.has_active_assignment
    rules = plans.check_plan_rules(ids[0])
    assert rules.valid and not rules.violations
    assert rules.rules_profile == "pl_domestic_employee_v1"
    assert rules.max_work_day_min >= rules.max_drive_day_min
    comparison = plans.compare(ids)
    base, other = plans.get(ids[0]), plans.get(ids[1])
    assert comparison["deltas_vs_first"][0]["d_profit_eur"] == str(
        Decimal(other.net_profit.amount_minor - base.net_profit.amount_minor) / 100
    )
    assert comparison["deltas_vs_first"][0]["d_finish_min"] == int(
        (other.finish_at - base.finish_at).total_seconds() // 60
    )
