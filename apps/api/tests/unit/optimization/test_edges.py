"""Budget, pool caps, objective ties and explicit normalization boundary cases."""

from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from routepilot.optimization.engine import RouteValidator, optimize
from routepilot.optimization.engine.fleet import assign_fleet
from routepilot.optimization.engine.fleet_oracle import brute_force_fleet
from routepilot.optimization.engine.models import Action, TravelMatrix
from routepilot.optimization.engine.oracle import brute_force
from routepilot.optimization.engine.prefilter import offer_pool
from routepilot.optimization.engine.schedule import ScheduleBuilder, build_plan
from routepilot.optimization.engine.search import plan_key, rank_plans

from .factories import T, driver, offer, point, snapshot


@pytest.mark.ac("AC-FEAT-003-27")
def test_node_budget_keeps_only_valid_plans() -> None:
    a = point("A")
    source = snapshot(
        [driver(a)], [offer(str(i), a, a, delivery=(T, T + timedelta(hours=8))) for i in range(5)]
    )
    source = source.model_copy(
        update={"params": source.params.model_copy(update={"node_budget_per_driver": 50})}
    )
    result = optimize(source)
    assert result.stats.nodes == 50
    assert result.stats.truncated
    assert all(
        RouteValidator().validate(source, p).valid
        for groups in result.per_driver.values()
        for plans in groups.values()
        for p in plans
    )


@pytest.mark.ac("AC-FEAT-003-21")
def test_pool_cap_is_ratio_ranked_and_stable() -> None:
    a, b = point("A"), point("B", 52, 20)
    source = snapshot(
        [driver(a)], [offer("A", a, b, revenue=10000), offer("B", a, b, revenue=20000)]
    )
    source = source.model_copy(
        update={"params": source.params.model_copy(update={"max_pool_per_driver": 1})}
    )
    pool, _, cut = offer_pool(source, source.drivers[0])
    assert cut and [o.id for o in pool] == ["B"]
    result = optimize(source)
    assert result.stats.pool_truncated
    assert result.warnings == ["POOL_TRUNCATED"]
    assert [(r.offer_id, r.code) for r in result.rejections] == [("A", "NOT_IN_TOP_K")]


@pytest.mark.ac("AC-FEAT-003-23")
def test_objective_ties_use_finish_fuel_then_delivery_sequence() -> None:
    a = point("A")
    source = snapshot([driver(a)], [offer("A", a, a, delivery=(T, T + timedelta(days=1)))])
    p, _ = build_plan(
        source,
        source.drivers[0],
        [Action(kind="PICKUP", offer_id="A"), Action(kind="DELIVERY", offer_id="A")],
    )
    assert p is not None
    late = p.model_copy(update={"finish_at": p.finish_at + timedelta(minutes=1)})
    thirsty = p.model_copy(update={"fuel_l": p.fuel_l + 1})
    assert plan_key(p, "profit") < plan_key(late, "profit")
    assert plan_key(p, "profit") < plan_key(thirsty, "profit")
    delivery_first = p.model_copy(
        update={
            "actions": [
                Action(kind="PICKUP", offer_id="A"),
                Action(kind="DELIVERY", offer_id="A"),
                Action(kind="PICKUP", offer_id="B"),
            ]
        }
    )
    pickup_first = p.model_copy(
        update={
            "actions": [
                Action(kind="PICKUP", offer_id="A"),
                Action(kind="PICKUP", offer_id="B"),
                Action(kind="DELIVERY", offer_id="A"),
            ]
        }
    )
    assert (
        rank_plans([pickup_first, delivery_first], "profit", 1)[0].actions == delivery_first.actions
    )


@pytest.mark.ac("AC-FEAT-003-24")
def test_fleet_required_drivers_and_exact_oracle() -> None:
    a = point("A")
    source = snapshot(
        [driver(a, identifier="D1"), driver(a, identifier="D2")],
        [
            offer("A", a, a, delivery=(T, T + timedelta(days=1))),
            offer("B", a, a, delivery=(T, T + timedelta(days=1))),
        ],
    )
    result = optimize(source)
    for objective in ("fastest", "fuel"):
        assert {a.driver_id for a in result.fleet[objective].assignments} == {"D1", "D2"}
    candidates = {d: groups["profit"] for d, groups in result.per_driver.items()}
    assert assign_fleet(candidates, "profit", T) == brute_force_fleet(candidates, "profit", T)


@pytest.mark.ac("AC-FEAT-003-11")
def test_return_constraint_and_initial_idle_rest() -> None:
    a = point("A")
    d = driver(a, home_by=T - timedelta(minutes=1))
    source = snapshot([d], [offer("A", a, a, delivery=(T, T + timedelta(days=1)))])
    result = optimize(source)
    assert result.rejections[0].code == "HOME_BY_UNREACHABLE"
    d = driver(a)
    d = d.model_copy(
        update={
            "rules_state": d.rules_state.model_copy(
                update={"work_today": 700, "work_since_break": 350}
            )
        }
    )
    o = offer(
        "A",
        a,
        a,
        pickup=(T + timedelta(days=1), T + timedelta(days=2)),
        delivery=(T, T + timedelta(days=2)),
    )
    source = snapshot([d], [o])
    plan = optimize(source).per_driver["D"]["profit"][0]
    assert plan.stops[0].counters.work_today == 0
    assert plan.departure_at == T + timedelta(days=1)
    assert plan.work_min == 60


@pytest.mark.ac("AC-FEAT-003-09")
def test_oracle_limits_and_matrix_shape_are_checked() -> None:
    a = point("A")
    source = snapshot([driver(a)], [])
    with pytest.raises(ValueError, match="oracle supports"):
        brute_force(source, source.drivers[0])
    with pytest.raises(ValueError, match="fleet oracle"):
        brute_force_fleet({str(i): [] for i in range(4)}, "profit", T)
    for data in (
        dict(points=[a, a], distance_km=[[0, 0], [0, 0]], duration_min=[[0, 0], [0, 0]]),
        dict(points=[a], distance_km=[], duration_min=[[0]]),
        dict(points=[a], distance_km=[[Decimal("-1")]], duration_min=[[0]]),
    ):
        with pytest.raises(ValidationError):
            TravelMatrix(**data)


@pytest.mark.ac("AC-FEAT-003-22")
def test_builder_rejects_invalid_order_and_capacity() -> None:
    a = point("A")
    source = snapshot([driver(a)], [offer("A", a, a, weight=2000)])
    b = ScheduleBuilder(source, source.drivers[0], "pl_domestic_employee_v1")
    assert b.extend(b.initial(), Action(kind="DELIVERY", offer_id="A"))[1] == "INVALID_ACTION_ORDER"
    assert b.extend(b.initial(), Action(kind="PICKUP", offer_id="A"))[1] == "CAPACITY_EXCEEDED"
    assert b.finish(b.initial())[1] == "INVALID_ACTION_ORDER"


@pytest.mark.ac("AC-FEAT-003-27")
def test_injected_timer_sets_runtime_and_truncates_without_reading_a_clock() -> None:
    a = point("A")
    source = snapshot(
        [driver(a)], [offer(str(i), a, a, delivery=(T, T + timedelta(hours=8))) for i in range(5)]
    )
    source = source.model_copy(
        update={"params": source.params.model_copy(update={"wall_clock_safety_s": Decimal(".005")})}
    )
    tick = 0

    def elapsed_ms() -> int:
        nonlocal tick
        tick += 1
        return tick

    result = optimize(source, elapsed_ms=elapsed_ms)
    assert result.stats.truncated
    assert result.stats.nodes == 4
    assert result.stats.runtime_ms == tick == 7


@pytest.mark.ac("AC-FEAT-003-12")
def test_baseline_candidates_preserve_profit_with_top_k_one() -> None:
    a = point("A")
    source = snapshot(
        [driver(a, identifier="D1"), driver(a, identifier="D2")],
        [
            offer("X", a, a, revenue=30000, delivery=(T, T + timedelta(days=1))),
            offer("Y", a, a, revenue=29000, delivery=(T, T + timedelta(days=1))),
        ],
    )
    source = source.model_copy(
        update={
            "params": source.params.model_copy(
                update={"max_offers_per_plan": 1, "top_k_per_driver": 1}
            )
        }
    )
    result = optimize(source)
    assert result.fleet["profit"].totals.net_profit_minor == 56200
    assert all(len(groups["profit"]) == 1 for groups in result.per_driver.values())
    assert result.fleet_candidates
    assert all(p.kind == "optimized" for p in result.fleet_candidates)
    assert all(
        result.fleet["profit"].totals.net_profit_minor >= b.totals.net_profit_minor
        for b in result.baselines.values()
    )


@pytest.mark.ac("AC-FEAT-003-09")
def test_exhaustive_oracle_matches_international_consolidation() -> None:
    from golden.cases import case

    source = case(1)
    source = source.model_copy(
        update={"params": source.params.model_copy(update={"top_k_per_driver": 3})}
    )
    expected = brute_force(source, source.drivers[0])
    assert optimize(source).per_driver["D1"] == expected


@pytest.mark.ac("AC-FEAT-003-12")
def test_baseline_already_in_fuel_list_still_enters_profit_candidate_pool() -> None:
    a, b = point("A"), point("B", 52.2297, 21.0122)
    source = snapshot(
        [driver(a, identifier="D1"), driver(a, identifier="D2")],
        [
            offer("X", a, b, revenue=40000, delivery=(T, T + timedelta(days=1))),
            offer("Y", a, a, revenue=15000, delivery=(T, T + timedelta(days=1))),
        ],
    )
    source = source.model_copy(
        update={
            "params": source.params.model_copy(
                update={"max_offers_per_plan": 1, "top_k_per_driver": 1}
            )
        }
    )
    result = optimize(source)
    assert result.per_driver["D1"]["profit"][0].offer_ids == ["X"]
    assert result.per_driver["D1"]["fuel"][0].offer_ids == ["Y"]
    assert all(
        result.fleet["profit"].totals.net_profit_minor >= b.totals.net_profit_minor
        for b in result.baselines.values()
    )
