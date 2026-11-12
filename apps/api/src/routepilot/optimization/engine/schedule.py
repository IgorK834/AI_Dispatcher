"""Incremental schedule construction, shared by search, baselines and test oracles."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256

from routepilot.compliance.models import DriverState, Infeasible, Ok, ProfileId, RuleActivity
from routepilot.compliance.rules import advance_clock, choose_profile, rules_for_profile
from routepilot.optimization.engine.costs import CostModel
from routepilot.optimization.engine.models import (
    Action,
    DriverSnapshot,
    EngineSnapshot,
    PlanActivity,
    PlanKind,
    PlanLeg,
    PlanStop,
    Point,
    RoutePlan,
)
from routepilot.optimization.engine.prefilter import pallet_equivalents


class FailureCode(str):
    """A schedule failure code that also carries the detail of the rejection report (FR-19)."""

    detail: str

    def __new__(cls, code: str, detail: str = "") -> "FailureCode":
        value = super().__new__(cls, code)
        value.detail = detail
        return value


def _utc_minute(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ")


def recorded_state(state: DriverState, activity: RuleActivity, profile: ProfileId) -> DriverState:
    """Apply an already-recorded activity; validation independently checks its admissibility."""
    work = activity.kind in ("DRIVE", "WAIT", "WORK")
    if work and state.day_start_at is None:
        state = state.model_copy(update={"day_start_at": state.t})
    state = advance_clock(state, activity.minutes, work=work, driving=activity.kind == "DRIVE")
    if activity.kind == "DAILY_REST":
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
        state = state.model_copy(
            update={
                "breaks_today": state.breaks_today + activity.minutes,
                "work_since_break": 0 if activity.minutes >= 30 else state.work_since_break,
                "drive_since_break": 0
                if profile == "eu561_van_international_v1"
                else state.drive_since_break,
            }
        )
    return state


@dataclass(frozen=True)
class Label:
    state: DriverState
    point: Point
    departure: datetime
    load_kg: int = 0
    load_eq: Decimal = Decimal("0")
    actions: tuple[Action, ...] = ()
    picked: frozenset[str] = frozenset()
    onboard: frozenset[str] = frozenset()
    done: frozenset[str] = frozenset()
    stops: tuple[PlanStop, ...] = ()
    legs: tuple[PlanLeg, ...] = ()
    activities: tuple[PlanActivity, ...] = ()
    warnings: tuple[str, ...] = ()


class ScheduleBuilder:
    def __init__(
        self, snapshot: EngineSnapshot, driver: DriverSnapshot, profile: ProfileId
    ) -> None:
        self.snapshot, self.driver, self.profile = snapshot, driver, profile
        self.rules = rules_for_profile(profile, snapshot.params.max_daily_work_min)
        self.offers = {offer.id: offer for offer in snapshot.offers}

    def initial(self) -> Label:
        driver = self.driver
        state = driver.rules_state.model_copy(
            update={
                "t": driver.available_from,
                "sleeper_cab": driver.vehicle.sleeper_cab,
                "home_timezone": driver.home.timezone,
            }
        )
        if state.work_today and state.day_start_at is None:
            state = state.model_copy(
                update={"day_start_at": state.t - timedelta(minutes=state.work_today)}
            )
        stop = PlanStop(
            sequence=0,
            kind="START",
            point=driver.position,
            arrival_at=state.t,
            service_start_at=state.t,
            departure_at=state.t,
            counters=state,
        )
        return Label(state=state, point=driver.position, departure=state.t, stops=(stop,))

    def _append(
        self, label: Label, outcome: Ok, point: Point | None, leg_index: int | None
    ) -> Label:
        state, stops = label.state, list(label.stops)
        activities = list(label.activities)
        for activity in outcome.activities:
            state = recorded_state(state, activity, self.profile)
            activities.append(
                PlanActivity(
                    activity=activity, point_key=point.key if point else None, leg_index=leg_index
                )
            )
            if activity.kind in ("BREAK", "DAILY_REST"):
                stops.append(
                    PlanStop(
                        sequence=len(stops),
                        kind=activity.kind,
                        point=point,
                        label=activity.reason,
                        arrival_at=activity.start_at,
                        service_start_at=activity.start_at,
                        departure_at=activity.end_at,
                        load_kg_after=label.load_kg,
                        load_pallet_eq_after=label.load_eq,
                        counters=state,
                    )
                )
        return replace(label, state=outcome.state, activities=tuple(activities), stops=tuple(stops))

    def extend(self, label: Label, action: Action) -> tuple[Label | None, str | None]:
        offer = self.offers[action.offer_id]
        pickup = action.kind == "PICKUP"
        if pickup:
            if (
                action.offer_id in label.picked
                or len(label.picked) >= self.snapshot.params.max_offers_per_plan
            ):
                return None, "INVALID_ACTION_ORDER"
        elif action.offer_id not in label.onboard:
            return None, "INVALID_ACTION_ORDER"
        stop = offer.stops[0 if pickup else 1]
        eq, pallet_warnings = pallet_equivalents(offer)
        if eq is None or offer.weight_kg is None:
            return None, "MISSING_CAPACITY_DATA"
        new_kg = label.load_kg + (offer.weight_kg if pickup else -offer.weight_kg)
        new_eq = label.load_eq + (eq if pickup else -eq)
        if new_kg > self.driver.vehicle.payload_kg or new_eq > self.driver.vehicle.pallet_places:
            return None, "CAPACITY_EXCEEDED"
        distance, drive = self.snapshot.matrix.leg(label.point, stop.point)
        if not label.actions and distance > self.snapshot.params.max_first_deadhead_km:
            return None, "FIRST_DEADHEAD_TOO_LONG"
        if not label.actions:
            # Calculate arrival with the initial counters before deferring; mandatory pauses count.
            trial = self.rules.advance_drive(label.state, drive)
            if isinstance(trial, Infeasible):
                return None, trial.code
            delay = max(0, int((stop.window_start - trial.state.t).total_seconds() // 60))
            if delay:
                state = label.state
                if delay >= 660:
                    idle = self.rules.advance_wait(state, delay)
                    if isinstance(idle, Infeasible):
                        return None, idle.code
                    state = idle.state
                else:
                    state = advance_clock(state, delay, work=False, driving=False)
                start = label.stops[0].model_copy(
                    update={
                        "arrival_at": state.t,
                        "service_start_at": state.t,
                        "departure_at": state.t,
                        "counters": state,
                    }
                )
                label = replace(label, state=state, departure=state.t, stops=(start,))
        departed = label.state.t
        travel = self.rules.advance_drive(label.state, drive)
        if isinstance(travel, Infeasible):
            return None, travel.code
        label = self._append(label, travel, None, len(label.legs))
        arrival = label.state.t
        leg = PlanLeg(
            start=label.point,
            end=stop.point,
            distance_km=distance,
            drive_min=drive,
            load_kg=label.load_kg,
            load_pallet_eq=label.load_eq,
            departed_at=departed,
            arrived_at=arrival,
        )
        label = replace(label, point=stop.point, legs=(*label.legs, leg))
        if label.state.t < stop.window_start:
            wait = self.rules.advance_wait(
                label.state, int((stop.window_start - label.state.t).total_seconds() // 60)
            )
            if isinstance(wait, Infeasible):
                return None, wait.code
            label = self._append(label, wait, stop.point, None)
        service = (
            stop.service_min
            if stop.service_min is not None
            else self.snapshot.params.default_service_min
        )
        worked = self.rules.advance_work(label.state, service)
        if isinstance(worked, Infeasible):
            return None, worked.code
        actual_start = worked.state.t - timedelta(minutes=service)
        if actual_start > stop.window_end:
            return None, FailureCode(
                "PICKUP_WINDOW_MISSED" if pickup else "DELIVERY_WINDOW_MISSED",
                f"earliest service start {_utc_minute(actual_start)}, "
                f"window end {_utc_minute(stop.window_end)}",
            )
        label = self._append(label, worked, stop.point, None)
        wait_min = sum(
            activity.activity.minutes
            for activity in label.activities
            if activity.activity.kind == "WAIT" and activity.activity.start_at >= arrival
        )
        plan_stop = PlanStop(
            sequence=len(label.stops),
            kind=action.kind,
            offer_id=offer.id,
            point=stop.point,
            arrival_at=arrival,
            service_start_at=actual_start,
            departure_at=label.state.t,
            wait_min=wait_min,
            service_min=service,
            leg_km=distance,
            leg_drive_min=drive,
            load_kg_after=new_kg,
            load_pallet_eq_after=new_eq,
            counters=label.state,
        )
        warnings = [*label.warnings, *pallet_warnings, *offer.warnings]
        if stop.service_min is None:
            warnings.append("SERVICE_TIME_DEFAULTED")
        return replace(
            label,
            load_kg=new_kg,
            load_eq=new_eq,
            actions=(*label.actions, action),
            picked=label.picked | {offer.id} if pickup else label.picked,
            onboard=label.onboard | {offer.id} if pickup else label.onboard - {offer.id},
            done=label.done if pickup else label.done | {offer.id},
            stops=(*label.stops, plan_stop),
            warnings=tuple(sorted(set(warnings))),
        ), None

    def finish(
        self, label: Label, kind: PlanKind = "optimized", *, thresholds: bool = True
    ) -> tuple[RoutePlan | None, str | None]:
        if label.onboard or not label.done:
            return None, "INVALID_ACTION_ORDER"
        home = self.driver.home_by
        required = home is not None and home <= self.snapshot.reference_time + timedelta(
            days=self.snapshot.params.horizon_days
        )
        if required:
            distance, drive = self.snapshot.matrix.leg(label.point, self.driver.home)
            departed = label.state.t
            traveled = self.rules.advance_drive(label.state, drive)
            if isinstance(traveled, Infeasible):
                return None, traveled.code
            label = self._append(label, traveled, None, len(label.legs))
            if home is not None and label.state.t > home:
                return None, "HOME_BY_UNREACHABLE"
            leg = PlanLeg(
                start=label.point,
                end=self.driver.home,
                distance_km=distance,
                drive_min=drive,
                load_kg=0,
                load_pallet_eq=Decimal("0"),
                departed_at=departed,
                arrived_at=label.state.t,
            )
            end = PlanStop(
                sequence=len(label.stops),
                kind="END",
                point=self.driver.home,
                arrival_at=label.state.t,
                service_start_at=label.state.t,
                departure_at=label.state.t,
                leg_km=distance,
                leg_drive_min=drive,
                counters=label.state,
            )
            marker = end.model_copy(
                update={
                    "sequence": len(label.stops) + 1,
                    "kind": "WEEKLY_REST",
                    "label": "INFORMATIONAL_WEEKLY_REST",
                }
            )
            label = replace(
                label,
                point=self.driver.home,
                legs=(*label.legs, leg),
                stops=(*label.stops, end, marker),
            )
        countries = [
            self.driver.position.country,
            *[
                self.offers[a.offer_id].stops[0 if a.kind == "PICKUP" else 1].point.country
                for a in label.actions
            ],
        ]
        if required:
            countries.append(self.driver.home.country)
        if choose_profile(self.driver.home.country or "", countries) != self.profile:
            return None, "PROFILE_PASS_MISMATCH"
        cost = CostModel(self.snapshot.co2_factor_kg_per_l).calculate(
            self.driver,
            [self.offers[oid] for oid in sorted(label.done)],
            list(label.legs),
            list(label.activities),
            label.departure,
            label.state.t,
        )
        if thresholds and cost.net_profit_minor < self.driver.cost_profile.min_profit_minor:
            return None, "BELOW_MIN_PROFIT"
        if thresholds and cost.margin_pct < self.driver.cost_profile.min_margin_pct:
            return None, "BELOW_MIN_MARGIN"
        identity = "|".join(
            [kind, self.driver.id, *[f"{a.kind}:{a.offer_id}" for a in label.actions]]
        )
        warnings = set(label.warnings) | set(cost.warnings)
        if self.driver.vehicle.body_type == "CURTAIN_SIDER":
            warnings.add("LOADING_ORDER_NOT_MODELLED")
        if self.snapshot.matrix.fallback:
            warnings.add("ROUTING_FALLBACK")
        return RoutePlan(
            plan_ref=sha256(identity.encode()).hexdigest()[:24],
            driver_id=self.driver.id,
            kind=kind,
            offer_ids=sorted(label.done),
            actions=list(label.actions),
            rules_profile=self.profile,
            departure_at=label.departure,
            finish_at=label.state.t,
            home_reached=bool(required),
            cost_total_minor=cost.calculation.total,
            duration_min=int((label.state.t - label.departure).total_seconds() // 60),
            warnings=sorted(warnings),
            stops=list(label.stops),
            legs=list(label.legs),
            activities=list(label.activities),
            **cost.model_dump(exclude={"warnings"}),
        ), None


def build_plan(
    snapshot: EngineSnapshot,
    driver: DriverSnapshot,
    actions: list[Action],
    kind: PlanKind = "optimized",
    *,
    thresholds: bool = True,
) -> tuple[RoutePlan | None, str | None]:
    offers = {o.id: o for o in snapshot.offers}
    countries = [
        driver.position.country,
        *[offers[a.offer_id].stops[0 if a.kind == "PICKUP" else 1].point.country for a in actions],
    ]
    if driver.home_by is not None and driver.home_by <= snapshot.reference_time + timedelta(
        days=snapshot.params.horizon_days
    ):
        countries.append(driver.home.country)
    builder = ScheduleBuilder(
        snapshot, driver, choose_profile(driver.home.country or "", countries)
    )
    label = builder.initial()
    for action in actions:
        extended, code = builder.extend(label, action)
        if extended is None:
            return None, code
        label = extended
    return builder.finish(label, kind, thresholds=thresholds)
