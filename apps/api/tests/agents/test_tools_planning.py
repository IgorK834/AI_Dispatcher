"""Route Planner tools through the real registry, with the real job worker and the engine."""

import json
import re
from decimal import Decimal
from typing import Any

import pytest

from routepilot.agents.guards import grounding_violations
from routepilot.agents.tools import contracts
from tests.agents.conftest import D1_POOL, FLEET_POOL, ToolEnv

PLANNER = "route_planner"
OBJECTIVES = {"profit", "fastest", "fuel"}
UUID_TEXT = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def optimize_d1(env: ToolEnv, **extra: Any) -> dict[str, Any]:
    result = env.call(
        PLANNER, "optimize_driver", driver_ref="D1", offer_ids=env.planning_pool(D1_POOL), **extra
    )
    if "error" in result or not any(result["plans"].values()):
        pytest.fail(f"D1_POOL in conftest.py no longer produces plans: {result}")
    return result


def optimize_fleet(env: ToolEnv, **extra: Any) -> dict[str, Any]:
    result = env.call(PLANNER, "optimize_fleet", offer_ids=env.planning_pool(FLEET_POOL), **extra)
    if "error" in result or not any(item["plans"] for item in result["fleet"].values()):
        pytest.fail(f"FLEET_POOL in conftest.py no longer produces plans: {result}")
    return result


def stored(env: ToolEnv, reference: str) -> Any:
    return env.plans.get(env.registry._plan_id(reference, env.state))


@pytest.mark.ac("AC-FEAT-006-33")
def test_optimize_driver_returns_bounded_plans_baselines_and_grounded_numbers(
    worker_env: ToolEnv, generated_offers: object
) -> None:
    result = optimize_d1(worker_env)
    assert set(result) == set(contracts.OptimizeOutput.model_fields)
    assert set(result["plans"]) == OBJECTIVES
    assert all(1 <= len(plans) <= 3 for plans in result["plans"].values())
    assert sum(len(plans) for plans in result["plans"].values()) <= 9
    assert set(result["baselines"]) == {"single_profit_eur", "greedy_profit_eur"}
    assert re.fullmatch(r"JOB-[0-9a-f]{8}", result["job_id"]), "the job id is an alias"
    facts = worker_env.state["plan_facts"]
    for plans in result["plans"].values():
        for plan in plans:
            assert (
                re.fullmatch(r"PLAN-[0-9a-f]{8}", plan["plan_ref"]) and plan["driver_ref"] == "D1"
            )
            assert set(plan) == set(contracts.PlanFacts.model_fields)
            assert facts[plan["plan_ref"]] == plan, "exported facts are what the run keeps"
            service = stored(worker_env, plan["plan_ref"])
            assert Decimal(plan["net_profit_eur"]) * 100 == service.net_profit.amount_minor
            assert plan["offer_ids"], "offers appear by reference"
    # Every number the model may cite is among the run's facts (GroundingGuard input).
    cited = [plan for plans in result["plans"].values() for plan in plans]
    text = (
        " ".join(
            f"{plan['net_profit_eur']} € {plan['distance_km']} km {plan['fuel_l']} l "
            f"{plan['co2_kg']} kg CO₂ {plan['plan_ref']} {plan['driver_ref']}"
            for plan in cited
        )
        + f" {result['baselines']['single_profit_eur']} €"
        + f" {result['baselines']['greedy_profit_eur']} €"
    )
    assert grounding_violations(text, [result, *facts.values()]) == []
    dump = json.dumps(result)
    assert not UUID_TEXT.search(dump)
    for driver in worker_env.fleet.list_active():
        assert driver.name not in dump and driver.phone not in dump


@pytest.mark.ac("AC-FEAT-006-33")
def test_optimize_driver_objective_filter_and_input_errors(
    worker_env: ToolEnv, generated_offers: object
) -> None:
    only_fuel = optimize_d1(worker_env, objectives=["fuel"])
    assert set(only_fuel["plans"]) == {"fuel"}
    call = worker_env.call
    assert call(PLANNER, "optimize_driver", driver_ref="D9")["error"]["code"] == "NOT_FOUND"
    unknown_offer = call(PLANNER, "optimize_driver", driver_ref="D1", offer_ids=["MOCK-999999"])
    assert unknown_offer["error"]["code"] == "NOT_FOUND"
    for arguments in (
        {"extra": 1},
        {"objectives": ["cheapest"]},
        {"objectives": []},
        {"offer_ids": ["MOCK-000001"] * 61},
    ):
        error = call(PLANNER, "optimize_driver", driver_ref="D1", **arguments)
        assert error["error"]["code"] == "VALIDATION_ERROR", arguments


@pytest.mark.ac("AC-FEAT-006-33")
def test_optimization_that_does_not_finish_in_time_is_reported_as_job_timeout(
    worker_env: ToolEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def never_in_time(job_id: object, *, timeout_s: float = 60) -> None:
        raise TimeoutError

    monkeypatch.setattr(worker_env.jobs, "wait", never_in_time)
    error = worker_env.call(PLANNER, "optimize_driver", driver_ref="D1", offer_ids=[])
    assert error["error"]["code"] == "JOB_TIMEOUT"


@pytest.mark.ac("AC-FEAT-006-33")
def test_optimization_without_a_worker_loop_is_a_tool_error(tool_env: ToolEnv) -> None:
    error = tool_env.call(PLANNER, "optimize_driver", driver_ref="D1", offer_ids=[])
    assert error["error"]["code"] == "TOOL_ERROR"


@pytest.mark.ac("AC-FEAT-006-34")
def test_optimize_fleet_returns_one_solution_per_objective_without_shared_offers(
    worker_env: ToolEnv, generated_offers: object
) -> None:
    result = optimize_fleet(worker_env)
    assert set(result) == set(contracts.OptimizeFleetOutput.model_fields)
    assert set(result["fleet"]) == OBJECTIVES
    for objective, solution in result["fleet"].items():
        plans = solution["plans"]
        assert len(plans) <= 20
        offer_ids = [offer for plan in plans for offer in plan["offer_ids"]]
        assert len(offer_ids) == len(set(offer_ids)), f"{objective}: an offer is in two plans"
        drivers = [plan["driver_ref"] for plan in plans]
        assert len(drivers) == len(set(drivers)), f"{objective}: a driver has two plans"
        totals = solution["totals"]
        assert set(totals) == set(contracts.FleetTotals.model_fields)
        assert totals["drivers_with_plan"] == len(plans)
        assert Decimal(totals["net_profit_eur"]) == sum(
            (Decimal(plan["net_profit_eur"]) for plan in plans), Decimal(0)
        )
        assert Decimal(totals["fuel_l"]) == sum((Decimal(plan["fuel_l"]) for plan in plans), 0)
    best = max(Decimal(value) for value in result["baselines"].values())
    profit = Decimal(result["fleet"]["profit"]["totals"]["net_profit_eur"])
    assert Decimal(result["uplift_vs_best_baseline_eur"]) == profit - best
    assert not UUID_TEXT.search(json.dumps(result))


@pytest.mark.ac("AC-FEAT-006-34")
def test_optimize_fleet_driver_subset_and_input_errors(
    worker_env: ToolEnv, generated_offers: object
) -> None:
    subset = optimize_fleet(worker_env, driver_refs=["D2", "D3"])
    drivers = {
        plan["driver_ref"] for solution in subset["fleet"].values() for plan in solution["plans"]
    }
    assert drivers <= {"D2", "D3"} and drivers
    call = worker_env.call
    assert call(PLANNER, "optimize_fleet", driver_refs=["D9"])["error"]["code"] == "NOT_FOUND"
    assert call(PLANNER, "optimize_fleet", driver_refs=["D1"] * 21)["error"]["code"] == (
        "VALIDATION_ERROR"
    )
    assert call(PLANNER, "optimize_fleet", extra=1)["error"]["code"] == "VALIDATION_ERROR"
    # An optimisation tool is never available to the other agents.
    assert call("freight_scout", "optimize_fleet")["error"]["code"] == "TOOL_NOT_ALLOWED"


@pytest.mark.ac("AC-FEAT-006-35")
def test_get_plan_returns_cost_breakdown_and_at_most_thirty_stops(
    worker_env: ToolEnv, generated_offers: object
) -> None:
    reference = optimize_d1(worker_env)["plans"]["profit"][0]["plan_ref"]
    detail = worker_env.call(PLANNER, "get_plan", plan_ref=reference)
    assert set(detail) == set(contracts.PlanDetail.model_fields)
    assert set(detail["cost_breakdown"]) == {
        "fuel",
        "toll",
        "driver",
        "per_diem",
        "accommodation",
        "vehicle",
    }
    service = stored(worker_env, reference)
    assert len(detail["stops"]) == min(len(service.stops), 30) <= 30
    assert [stop["seq"] for stop in detail["stops"]] == list(range(len(detail["stops"])))
    breakdown = sum((Decimal(value) for value in detail["cost_breakdown"].values()), Decimal(0))
    assert breakdown == Decimal(detail["cost_eur"]), "the breakdown adds up to the plan cost"
    refs = {stop["offer_id"] for stop in detail["stops"] if stop["offer_id"]}
    assert refs == set(detail["offer_ids"]), "stops name offers by the same references"
    assert not UUID_TEXT.search(json.dumps(detail))
    for name in ("PLAN-ffffffff", "PLAN-00000000", "not-a-plan"):
        assert worker_env.call(PLANNER, "get_plan", plan_ref=name)["error"]["code"] == "NOT_FOUND"
    assert worker_env.call(PLANNER, "get_plan", plan_ref=reference, x=1)["error"]["code"] == (
        "VALIDATION_ERROR"
    )


@pytest.mark.ac("AC-FEAT-006-36")
def test_compare_plans_returns_rows_and_service_computed_deltas_against_the_first(
    worker_env: ToolEnv, generated_offers: object
) -> None:
    references = [plan["plan_ref"] for plan in optimize_d1(worker_env)["plans"]["profit"]]
    assert len(references) == 3
    result = worker_env.call(PLANNER, "compare_plans", plan_refs=references)
    assert [row["plan_ref"] for row in result["rows"]] == references
    assert [row["plan_ref"] for row in result["deltas_vs_first"]] == references[1:]
    base = stored(worker_env, references[0])
    for row, delta in zip(result["rows"][1:], result["deltas_vs_first"], strict=True):
        other = stored(worker_env, row["plan_ref"])
        assert (
            Decimal(delta["d_profit_eur"])
            == Decimal(other.net_profit.amount_minor - base.net_profit.amount_minor) / 100
        )
        assert delta["d_finish_min"] == int(
            (other.finish_at - base.finish_at).total_seconds() // 60
        )
        assert Decimal(delta["d_fuel_l"]) == other.fuel_l - base.fuel_l
        assert Decimal(delta["d_co2_kg"]) == other.co2_kg - base.co2_kg
        # The rows hold the stored values the model would otherwise subtract itself.
        assert Decimal(row["net_profit_eur"]) * 100 == other.net_profit.amount_minor
    assert not UUID_TEXT.search(json.dumps(result))


@pytest.mark.ac("AC-FEAT-006-36")
def test_compare_plans_input_and_reference_errors(
    worker_env: ToolEnv, generated_offers: object
) -> None:
    references = [plan["plan_ref"] for plan in optimize_d1(worker_env)["plans"]["profit"]]
    call = worker_env.call
    assert call(PLANNER, "compare_plans", plan_refs=references[:1])["error"]["code"] == (
        "VALIDATION_ERROR"
    )
    assert call(PLANNER, "compare_plans", plan_refs=references * 3)["error"]["code"] == (
        "VALIDATION_ERROR"
    )
    unknown = call(PLANNER, "compare_plans", plan_refs=[references[0], "PLAN-ffffffff"])
    assert unknown["error"]["code"] == "NOT_FOUND"
