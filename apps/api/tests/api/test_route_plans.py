"""Immutable stored schedule contracts and model-safe computed facts."""

import asyncio
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from routepilot.optimization.jobs.service import JobCreate, PlanService


def plan_ids(result: dict) -> set[str]:
    """Every routePlanId a job result mentions: fleet solutions, baselines and per-driver lists."""
    solutions = [*result["fleet"].values(), *result["baselines"].values()]
    ids = {a["routePlanId"] for solution in solutions for a in solution["assignments"]}
    for driver in result["perDriver"]:
        ids |= {plan["id"] for plans in driver["plans"].values() for plan in plans}
    return ids


@pytest.mark.ac("AC-FEAT-004-12")
def test_result_of_a_succeeded_job_has_every_part_and_each_plan_is_readable(job_client):
    client, (_service, _plans, _assignments, _user, job_id) = job_client
    response = client.get(f"/api/v1/optimization-jobs/{job_id}/result")
    assert response.status_code == 200
    body = response.json()
    assert body["jobId"] == str(job_id)
    assert set(body["fleet"]) == {"profit", "fastest", "fuel"}, "the job requested all three"
    for objective, solution in body["fleet"].items():
        assert solution["objective"] == objective
        assert {"netProfit", "fuelL", "co2Kg", "distanceKm", "driversWithPlan"} <= set(
            solution["totals"]
        )
    assert body["perDriver"] and all(
        set(driver["plans"]) == {"profit", "fastest", "fuel"} for driver in body["perDriver"]
    )
    summary = body["perDriver"][0]["plans"]["profit"][0]
    assert {"id", "driverId", "kind", "variant", "rank", "offerIds", "rulesProfile"} <= set(summary)
    assert {"netProfit", "marginPct", "distanceKm", "emptyKm", "fuelL", "co2Kg"} <= set(summary)
    assert {"durationMin", "finishAt", "homeReached", "warnings"} <= set(summary)
    assert set(body["baselines"]) == {"baselineSingle", "baselineGreedy"}
    assert isinstance(body["rejections"], list) and isinstance(body["warnings"], list)
    assert body["stats"]["nodes"] > 0
    assert body["disclaimer"].endswith("It does not certify legal compliance.")
    ids = plan_ids(body)
    assert ids, "the result references plans"
    for plan_id in sorted(ids):
        assert client.get(f"/api/v1/route-plans/{plan_id}").status_code == 200, plan_id


@pytest.mark.ac("AC-FEAT-004-12")
def test_a_subset_of_objectives_is_always_part_of_the_result(routed_job):
    # The spec does not say that other objectives are left out; the engine computes all three
    # and the result carries all three. Reported to the owner as an open reading of AC-12.
    service, _plans, _assignments, user, job_id = routed_job
    driver = service.get_snapshot(job_id).drivers[0].id
    job = service.create(
        JobCreate(scope="driver", driver_ids=[UUID(driver)], objectives=["fuel"]), user
    )
    asyncio.run(service.run_one(job.id))
    result = service.result(job.id)
    assert job.objectives == ["fuel"]
    assert "fuel" in result.fleet and result.fleet["fuel"].objective == "fuel"
    assert result.per_driver[0].plans["fuel"], "the requested objective has plans"


@pytest.mark.ac("AC-FEAT-004-17")
def test_a_stored_plan_has_ordered_stops_breakdown_with_provenance_and_the_notice(job_client):
    client, (service, _plans, _assignments, _user, job_id) = job_client
    result = service.result(job_id)
    plan_id = result.fleet["profit"].assignments[0].route_plan_id
    response = client.get(f"/api/v1/route-plans/{plan_id}")
    assert response.status_code == 200
    plan = response.json()
    assert plan["id"] == str(plan_id)
    assert [stop["sequence"] for stop in plan["stops"]] == sorted(
        stop["sequence"] for stop in plan["stops"]
    )
    for stop in plan["stops"]:
        assert {"kind", "label", "lat", "lon", "arrivalAt", "waitMin", "serviceStartAt"} <= set(
            stop
        )
        assert {"departureAt", "legKm", "legDriveMin", "loadPalletEqAfter", "loadKgAfter"} <= set(
            stop
        )
        assert set(stop["counters"]) == {
            "workToday",
            "driveToday",
            "workSinceBreak",
            "driveSinceBreak",
        }
    times = [stop["arrivalAt"] for stop in plan["stops"]]
    assert times == sorted(times), "stops are in time order"
    breakdown = plan["calculation"]
    assert {"fuel", "toll", "driver", "perDiem", "accommodation", "vehicle"} <= set(breakdown)
    assert breakdown["parameters"], "the breakdown names its parameters"
    for name, parameter in breakdown["parameters"].items():
        assert parameter["value"] != "" and parameter["provenance"], name
    assert float(plan["fuelL"]) > 0 and float(plan["co2Kg"]) > 0
    assert isinstance(plan["warnings"], list)
    assert {"revenue", "costTotal", "workMin", "driveMin", "waitMin"} <= set(plan)
    assert (
        plan["disclaimer"]
        == client.get(f"/api/v1/optimization-jobs/{job_id}/result").json()["disclaimer"]
    ), "one notice everywhere"
    assert client.get(f"/api/v1/route-plans/{uuid4()}").status_code == 404


@pytest.mark.ac("AC-FEAT-004-16")
def test_no_route_can_modify_a_stored_plan_or_a_job(job_client):
    client, (service, _plans, _assignments, _user, job_id) = job_client
    plan_id = service.result(job_id).fleet["profit"].assignments[0].route_plan_id
    paths = client.app.openapi()["paths"]
    for path, operations in paths.items():
        if path.startswith("/api/v1/route-plans") or "{job_id}" in path:
            assert set(operations) == {"get"}, f"{path} must be read-only"
    before = client.get(f"/api/v1/route-plans/{plan_id}").json()
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        response = client.request(method, f"/api/v1/route-plans/{plan_id}", json={})
        assert response.status_code == 405, method
    assert client.get(f"/api/v1/route-plans/{plan_id}").json() == before


@pytest.mark.ac("AC-FEAT-004-17")
def test_geometry_is_computed_on_the_first_read_and_served_from_the_store_afterwards(routed_job):
    service, _plans, _assignments, _user, job_id = routed_job
    plan_id = service.result(job_id).fleet["profit"].assignments[0].route_plan_id

    class CountingRouting:
        provider_id = "counting"

        def __init__(self, inner):
            self.inner, self.calls = inner, 0

        def matrix(self, points):
            return self.inner.matrix(points)

        def route(self, waypoints, *, variant):
            self.calls += 1
            return self.inner.route(waypoints, variant=variant)

    routing = CountingRouting(service.routing)
    reader = PlanService(service.repository.engine, service.clock, routing)
    first = reader.get(plan_id)
    second = reader.get(plan_id)
    assert routing.calls == 1, "the second read does not route again"
    assert first.geometry == second.geometry and first.geometry["type"] == "LineString"
    assert "GEOMETRY_APPROXIMATE" in first.warnings, "straight lines are flagged as approximate"


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
