"""P1-P13: random synthetic instances checked independently and against exhaustive oracles."""

from datetime import timedelta
from decimal import Decimal

import pytest
from golden.factories import T, driver, offer, point, snapshot
from hypothesis import given, settings
from hypothesis import strategies as st

from routepilot.optimization.engine import FleetValidator, RouteValidator, optimize
from routepilot.optimization.engine.fleet_oracle import brute_force_fleet
from routepilot.optimization.engine.models import EngineSnapshot
from routepilot.optimization.engine.oracle import brute_force
from routepilot.optimization.engine.search import plan_key


@st.composite
def snapshots(draw: st.DrawFn) -> EngineSnapshot:
    cities = [
        point("Lodz"),
        point("Warszawa", 52.2297, 21.0122),
        point("Katowice", 50.2649, 19.0238),
        point("Dresden", 51.0504, 13.7373, "DE"),
    ]
    count = draw(st.integers(min_value=0, max_value=5))
    driver_count = draw(st.integers(min_value=1, max_value=3))
    drivers = []
    for index in range(driver_count):
        home = draw(st.sampled_from(cities[:3]))
        home_by = T + timedelta(days=2) if draw(st.booleans()) else None
        d = driver(
            home,
            identifier=f"D{index}",
            payload=draw(st.sampled_from([765, 880, 1085])),
            pallets=draw(st.sampled_from([8, 10])),
            home_by=home_by,
        )
        worked = draw(st.sampled_from([0, 0, 0, 120, 350]))
        d = d.model_copy(
            update={
                "rules_state": d.rules_state.model_copy(
                    update={
                        "work_today": worked,
                        "drive_today": worked,
                        "work_since_break": worked,
                        "drive_since_break": min(worked, 250),
                        "work_week": draw(st.sampled_from([0, 1500, 3500])),
                    }
                )
            }
        )
        drivers.append(d)
    offers = []
    for index in range(count):
        start, end = draw(st.sampled_from(cities)), draw(st.sampled_from(cities))
        opening = draw(st.integers(min_value=0, max_value=560))
        closing = opening + draw(st.integers(min_value=30, max_value=360))
        delivery_open = draw(st.integers(min_value=0, max_value=720))
        offers.append(
            offer(
                f"O{index}",
                start,
                end,
                weight=draw(st.integers(min_value=100, max_value=800)),
                pallets=draw(st.integers(min_value=1, max_value=6)),
                revenue=draw(st.integers(min_value=5000, max_value=100000)),
                pickup=(T + timedelta(minutes=opening), T + timedelta(minutes=closing)),
                delivery=(T + timedelta(minutes=delivery_open), T + timedelta(days=2)),
            )
        )
    source = snapshot(drivers, offers)
    return source.model_copy(
        update={"params": source.params.model_copy(update={"top_k_per_driver": 3})}
    )


@pytest.mark.ac(*[f"AC-FEAT-003-{i:02}" for i in range(1, 14)])
@given(snapshots())
@settings(deadline=None)
def test_p1_to_p13_engine_invariants(source: EngineSnapshot) -> None:
    result = optimize(source)
    shuffled = source.model_copy(
        update={"offers": list(reversed(source.offers)), "drivers": list(reversed(source.drivers))}
    )
    assert optimize(source) == result == optimize(shuffled)
    all_plans = [
        plan for groups in result.per_driver.values() for plans in groups.values() for plan in plans
    ]
    for driver_snapshot in source.drivers:
        groups = result.per_driver[driver_snapshot.id]
        oracle = brute_force(source, driver_snapshot)
        assert groups == oracle
        for objective, plans in groups.items():
            assert len({tuple(plan.offer_ids) for plan in plans}) == len(plans)
            assert plans == sorted(plans, key=lambda p: plan_key(p, objective))
            for plan in plans:
                assert RouteValidator().validate(source, plan).valid
                assert plan.net_profit_minor == plan.revenue_minor - plan.calculation.total
                assert plan.co2_kg == (plan.fuel_l * source.co2_factor_kg_per_l).quantize(
                    Decimal(".01")
                )
                for stop in plan.stops:
                    assert 0 <= stop.load_kg_after <= driver_snapshot.vehicle.payload_kg
                    assert 0 <= stop.load_pallet_eq_after <= driver_snapshot.vehicle.pallet_places
        returned = {oid for plans in groups.values() for plan in plans for oid in plan.offer_ids}
        rejected = [r.offer_id for r in result.rejections if r.driver_id == driver_snapshot.id]
        assert len(rejected) == len(set(rejected))
        assert set(rejected) == {o.id for o in source.offers} - returned
        if groups["profit"]:
            assert groups["fastest"][0].finish_at <= groups["profit"][0].finish_at
            assert groups["fuel"][0].fuel_l <= groups["profit"][0].fuel_l
    for objective, solution in result.fleet.items():
        assert FleetValidator().validate(source, solution, all_plans).valid
        # Four candidate slots suffice for the <=3-offer instances after deduplication by ref.
        candidates = {
            d: list({p.plan_ref: p for p in groups[objective] + groups["profit"]}.values())
            for d, groups in result.per_driver.items()
        }
        required = (
            frozenset(a.driver_id for a in result.fleet["profit"].assignments)
            if objective != "profit"
            else frozenset()
        )
        if all(len(plans) <= 4 for plans in candidates.values()):
            assert solution == brute_force_fleet(
                candidates, objective, source.reference_time, required
            )
    assert all(
        result.fleet["profit"].totals.net_profit_minor >= b.totals.net_profit_minor
        for b in result.baselines.values()
    )
    by_ref = {p.plan_ref: p for p in all_plans}
    profits = [by_ref[a.plan_ref] for a in result.fleet["profit"].assignments]
    fastest = [by_ref[a.plan_ref] for a in result.fleet["fastest"].assignments]
    assert sum((p.finish_at - source.reference_time for p in fastest), timedelta()) <= sum(
        (p.finish_at - source.reference_time for p in profits), timedelta()
    )
    assert result.fleet["fuel"].totals.fuel_l <= result.fleet["profit"].totals.fuel_l
