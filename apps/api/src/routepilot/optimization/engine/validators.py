"""Independent timeline and fleet checks; this module never calls the scheduler/search."""

from datetime import timedelta
from decimal import Decimal

from routepilot.compliance.models import DriverState
from routepilot.compliance.rules import advance_clock, choose_profile
from routepilot.optimization.engine.costs import CostModel
from routepilot.optimization.engine.models import (
    EngineSnapshot,
    FleetSolution,
    RoutePlan,
    ValidationResult,
)
from routepilot.optimization.engine.prefilter import pallet_equivalents


class RouteValidator:
    def validate(self, snapshot: EngineSnapshot, plan: RoutePlan) -> ValidationResult:
        errors: list[str] = []

        def fail(code: str) -> None:
            if code not in errors:
                errors.append(code)

        drivers = {d.id: d for d in snapshot.drivers}
        offers = {o.id: o for o in snapshot.offers}
        driver = drivers.get(plan.driver_id)
        if driver is None or any(oid not in offers for oid in plan.offer_ids):
            return ValidationResult(valid=False, errors=["UNKNOWN_REFERENCE"])
        home_required = (
            driver.home_by is not None
            and driver.home_by
            <= snapshot.reference_time + timedelta(days=snapshot.params.horizon_days)
        )
        action_stops = [s for s in plan.stops if s.kind in ("PICKUP", "DELIVERY")]
        countries = [
            driver.position.country,
            *[s.point.country if s.point else None for s in action_stops],
        ]
        if home_required:
            countries.append(driver.home.country)
        profile = choose_profile(driver.home.country or "", countries)
        if plan.rules_profile != profile:
            fail("WRONG_PROFILE")
        if (
            not plan.stops
            or plan.stops[0].kind != "START"
            or plan.departure_at < driver.available_from
        ):
            fail("TIMELINE_INVALID")
        picked: set[str] = set()
        done: set[str] = set()
        kg, eq = 0, Decimal("0")
        for action, stop in zip(plan.actions, action_stops, strict=False):
            if (action.kind, action.offer_id) != (stop.kind, stop.offer_id):
                fail("ACTION_ORDER_INVALID")
        if len(plan.actions) != len(action_stops):
            fail("ACTION_ORDER_INVALID")
        for stop in action_stops:
            if stop.offer_id not in plan.offer_ids:
                fail("ACTION_ORDER_INVALID")
                continue
            offer = offers[stop.offer_id]
            if stop.kind == "PICKUP":
                if stop.offer_id in picked:
                    fail("ACTION_ORDER_INVALID")
                picked.add(stop.offer_id)
                sign, source = 1, offer.stops[0]
            else:
                if stop.offer_id not in picked or stop.offer_id in done:
                    fail("ACTION_ORDER_INVALID")
                done.add(stop.offer_id)
                sign, source = -1, offer.stops[1]
            pallets, _ = pallet_equivalents(offer)
            kg += sign * (offer.weight_kg or 0)
            eq += sign * (pallets or Decimal("0"))
            if (
                not 0 <= kg <= driver.vehicle.payload_kg
                or not 0 <= eq <= driver.vehicle.pallet_places
                or stop.load_kg_after != kg
                or stop.load_pallet_eq_after != eq
            ):
                fail("CAPACITY_INVALID")
            if not source.window_start <= stop.service_start_at <= source.window_end:
                fail("WINDOW_MISSED")
            service = (
                source.service_min
                if source.service_min is not None
                else snapshot.params.default_service_min
            )
            if (
                stop.service_min != service
                or stop.departure_at != stop.service_start_at + timedelta(minutes=service)
            ):
                fail("TIMELINE_INVALID")
            if (
                stop.point != source.point
                or not stop.arrival_at <= stop.service_start_at <= stop.departure_at
            ):
                fail("TIMELINE_INVALID")
        if picked != set(plan.offer_ids) or done != set(plan.offer_ids) or kg or eq:
            fail("ACTION_ORDER_INVALID")
        ends = [s for s in plan.stops if s.kind == "END"]
        if home_required and (
            len(ends) != 1
            or ends[0].point != driver.home
            or (driver.home_by is not None and ends[0].arrival_at > driver.home_by)
            or plan.finish_at != ends[0].arrival_at
            or not plan.home_reached
        ):
            fail("HOME_END_MISSING")
        if not home_required and (ends or plan.home_reached):
            fail("HOME_END_INVALID")
        targets = [*action_stops, *ends]
        if len(targets) != len(plan.legs):
            fail("LEG_INVALID")
        previous_point, previous_time = driver.position, plan.departure_at
        onboard: set[str] = set()
        for index, (leg, target) in enumerate(zip(plan.legs, targets, strict=False)):
            km, minutes = snapshot.matrix.leg(previous_point, target.point or previous_point)
            leg_activities = [a.activity for a in plan.activities if a.leg_index == index]
            elapsed = sum(a.minutes for a in leg_activities)
            recorded_drive = sum(a.minutes for a in leg_activities if a.kind == "DRIVE")
            load = sum(offers[oid].weight_kg or 0 for oid in onboard)
            load_eq = sum(
                (pallet_equivalents(offers[oid])[0] or Decimal("0") for oid in onboard),
                Decimal("0"),
            )
            if (
                leg.start != previous_point
                or leg.end != target.point
                or leg.distance_km != km
                or leg.drive_min != minutes
                or recorded_drive != minutes
                or leg.load_kg != load
                or leg.load_pallet_eq != load_eq
                or leg.departed_at != previous_time
                or leg.arrived_at != previous_time + timedelta(minutes=elapsed)
                or target.arrival_at != leg.arrived_at
            ):
                fail("LEG_INVALID")
            previous_point, previous_time = leg.end, target.departure_at
            if target.kind == "PICKUP" and target.offer_id:
                onboard.add(target.offer_id)
            elif target.kind == "DELIVERY" and target.offer_id:
                onboard.discard(target.offer_id)
        state = driver.rules_state.model_copy(
            update={
                "t": driver.available_from,
                "sleeper_cab": driver.vehicle.sleeper_cab,
                "home_timezone": driver.home.timezone,
            }
        )
        if state.work_today and state.day_start_at is None:
            state = state.model_copy(
                update={"day_start_at": driver.available_from - timedelta(minutes=state.work_today)}
            )
        idle = int((plan.departure_at - driver.available_from).total_seconds() // 60)
        state = advance_clock(state, idle, work=False, driving=False)
        if idle >= 660:
            state = state.model_copy(
                update={
                    "work_today": 0,
                    "drive_today": 0,
                    "work_since_break": 0,
                    "drive_since_break": 0,
                    "breaks_today": 0,
                    "day_start_at": None,
                }
            )
        checkpoints: dict[object, DriverState] = {state.t: state}
        international = profile == "eu561_van_international_v1"
        for entry in plan.activities:
            activity = entry.activity
            if activity.start_at != state.t or activity.minutes <= 0:
                fail("TIMELINE_INVALID")
            if activity.kind in ("WORK", "WAIT", "DRIVE"):
                if state.day_start_at is None:
                    state = state.model_copy(update={"day_start_at": state.t})
                # Check both sides of a home-zone week boundary, independently of the scheduler.
                for _ in range(activity.minutes):
                    state = advance_clock(state, 1, work=True, driving=activity.kind == "DRIVE")
                    if (
                        state.work_since_break > 360
                        or state.work_week > 3600
                        or (
                            state.day_start_at is not None
                            and state.t - state.day_start_at > timedelta(minutes=780)
                        )
                        or (
                            not international
                            and (
                                state.work_today > snapshot.params.max_daily_work_min
                                or (state.work_today > 540 and state.breaks_today < 45)
                            )
                        )
                        or (
                            international
                            and (
                                state.drive_since_break > 270
                                or state.drive_today > 540
                                or state.drive_week > 3360
                                or state.drive_week + state.drive_prev_week > 5400
                            )
                        )
                    ):
                        fail("BREAK_OR_LIMIT_INVALID")
            else:
                if state.day_start_at is not None and state.t - state.day_start_at > timedelta(
                    minutes=780
                ):
                    fail("BREAK_OR_LIMIT_INVALID")
                state = advance_clock(state, activity.minutes, work=False, driving=False)
                if activity.kind == "DAILY_REST":
                    if activity.minutes < 660:
                        fail("BREAK_OR_LIMIT_INVALID")
                    state = state.model_copy(
                        update={
                            "work_today": 0,
                            "drive_today": 0,
                            "work_since_break": 0,
                            "drive_since_break": 0,
                            "breaks_today": 0,
                            "day_start_at": None,
                        }
                    )
                elif activity.kind == "BREAK":
                    if (international and activity.minutes < 45) or (
                        not international
                        and activity.minutes < 30
                        and not (
                            activity.minutes >= 15
                            and state.breaks_today >= 30
                            and state.work_today >= 540
                        )
                    ):
                        fail("BREAK_OR_LIMIT_INVALID")
                    state = state.model_copy(
                        update={
                            "breaks_today": state.breaks_today + activity.minutes,
                            "work_since_break": 0
                            if activity.minutes >= 30
                            else state.work_since_break,
                            "drive_since_break": 0 if international else state.drive_since_break,
                        }
                    )
            checkpoints[state.t] = state
        if state.t != plan.finish_at or plan.duration_min != int(
            (plan.finish_at - plan.departure_at).total_seconds() // 60
        ):
            fail("TIMELINE_INVALID")
        for stop in plan.stops:
            checkpoint = checkpoints.get(stop.departure_at)
            if checkpoint is not None and checkpoint != stop.counters:
                fail("COUNTERS_INVALID")
        recorded_events = [
            (a.activity.kind, a.activity.start_at, a.activity.end_at)
            for a in plan.activities
            if a.activity.kind in ("BREAK", "DAILY_REST")
        ]
        stop_events = [
            (s.kind, s.arrival_at, s.departure_at)
            for s in plan.stops
            if s.kind in ("BREAK", "DAILY_REST")
        ]
        if recorded_events != stop_events:
            fail("BREAK_OR_LIMIT_INVALID")
        costs = CostModel(snapshot.co2_factor_kg_per_l).calculate(
            driver,
            [offers[oid] for oid in plan.offer_ids],
            plan.legs,
            plan.activities,
            plan.departure_at,
            plan.finish_at,
        )
        if (
            plan.calculation != costs.calculation
            or plan.revenue_minor != costs.revenue_minor
            or plan.cost_total_minor != costs.calculation.total
            or plan.net_profit_minor != costs.net_profit_minor
            or plan.margin_pct != costs.margin_pct
        ):
            fail("PROFIT_INVALID")
        if plan.co2_kg != costs.co2_kg:
            fail("CO2_INVALID")
        if (
            plan.fuel_l != costs.fuel_l
            or plan.distance_km != costs.distance_km
            or plan.empty_km != costs.empty_km
            or (plan.work_min, plan.drive_min, plan.service_min, plan.wait_min)
            != (costs.work_min, costs.drive_min, costs.service_min, costs.wait_min)
        ):
            fail("COST_INPUT_INVALID")
        return ValidationResult(valid=not errors, errors=errors)


class FleetValidator:
    def validate(
        self, snapshot: EngineSnapshot, solution: FleetSolution, plans: list[RoutePlan]
    ) -> ValidationResult:
        errors: list[str] = []
        by_ref = {p.plan_ref: p for p in plans}
        drivers: set[str] = set()
        offers: set[str] = set()
        selected: list[RoutePlan] = []
        for assignment in solution.assignments:
            plan = by_ref.get(assignment.plan_ref)
            if plan is None or plan.driver_id != assignment.driver_id:
                errors.append("UNKNOWN_PLAN")
                continue
            if assignment.driver_id in drivers or offers.intersection(plan.offer_ids):
                errors.append("DUPLICATED_ASSIGNMENT")
            drivers.add(assignment.driver_id)
            offers.update(plan.offer_ids)
            selected.append(plan)
            if not RouteValidator().validate(snapshot, plan).valid:
                errors.append("INVALID_ROUTE")
        totals = solution.totals
        if (
            totals.net_profit_minor != sum(p.net_profit_minor for p in selected)
            or totals.fuel_l != sum((p.fuel_l for p in selected), Decimal("0"))
            or totals.co2_kg != sum((p.co2_kg for p in selected), Decimal("0"))
            or totals.distance_km != sum((p.distance_km for p in selected), Decimal("0"))
            or totals.drivers_with_plan != len(selected)
        ):
            errors.append("FLEET_TOTALS_INVALID")
        return ValidationResult(valid=not errors, errors=sorted(set(errors)))
