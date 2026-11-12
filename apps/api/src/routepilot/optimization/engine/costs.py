"""Deterministic Decimal fuel, CO₂ and money calculations (FEAT-003 FR-10-14)."""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from itertools import pairwise

from pydantic import Field

from routepilot.optimization.engine.models import (
    Calculation,
    CostProfile,
    DriverSnapshot,
    EngineModel,
    OfferSnapshot,
    PlanActivity,
    PlanLeg,
    VehicleSnapshot,
)

CURVE = ((50, "1.10"), (70, "0.95"), (90, "1.00"), (110, "1.18"), (130, "1.35"))


def rounded(value: Decimal, places: int = 0) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def speed_curve(speed: Decimal) -> Decimal:
    if speed <= CURVE[0][0]:
        return Decimal(CURVE[0][1])
    for (left, a), (right, b) in pairwise(CURVE):
        if speed <= right:
            return Decimal(a) + (Decimal(b) - Decimal(a)) * (speed - left) / (right - left)
    return Decimal(CURVE[-1][1])


def revenue_in_profile_currency(
    amount_minor: int, currency: str, profile: CostProfile
) -> int | None:
    if currency == profile.currency:
        return amount_minor
    rate = profile.fx_rates.get(currency)
    if rate is None or rate <= 0:
        return None
    # Rates quote foreign currency units per one profile-currency unit (e.g. PLN 4.25 / EUR).
    return int(rounded(Decimal(amount_minor) / rate))


class CostResult(EngineModel):
    calculation: Calculation
    revenue_minor: int
    net_profit_minor: int
    margin_pct: Decimal
    fuel_l: Decimal
    co2_kg: Decimal
    distance_km: Decimal
    empty_km: Decimal
    drive_min: int
    service_min: int
    wait_min: int
    work_min: int
    warnings: list[str] = Field(default_factory=list)


class CostModel:
    def __init__(self, co2_factor_kg_per_l: Decimal = Decimal("2.6")) -> None:
        self.co2_factor = co2_factor_kg_per_l

    def leg_fuel(
        self, vehicle: VehicleSnapshot, distance_km: Decimal, drive_min: int, load_kg: int
    ) -> Decimal:
        if drive_min == 0:
            return Decimal("0.000")
        speed = distance_km * 60 / drive_min
        load_factor = Decimal(load_kg) / vehicle.payload_kg
        consumption = (
            vehicle.fuel_l_per_100km_empty
            + (vehicle.fuel_l_per_100km_full - vehicle.fuel_l_per_100km_empty) * load_factor
        )
        return rounded(distance_km * consumption * speed_curve(speed) / 100, 3)

    def co2(self, fuel_l: Decimal) -> Decimal:
        return rounded(fuel_l * self.co2_factor, 2)

    @staticmethod
    def per_diem_multiplier(minutes: int) -> Decimal:
        if minutes <= 1440:
            return (
                Decimal("0")
                if minutes < 480
                else (Decimal("0.5") if minutes <= 720 else Decimal("1"))
            )
        days, rest = divmod(minutes, 1440)
        return Decimal(days) + (
            Decimal("0") if not rest else (Decimal("0.5") if rest <= 480 else Decimal("1"))
        )

    def calculate(
        self,
        driver: DriverSnapshot,
        offers: list[OfferSnapshot],
        legs: list[PlanLeg],
        activities: list[PlanActivity],
        departure_at: datetime,
        finish_at: datetime,
    ) -> CostResult:
        profile, vehicle = driver.cost_profile, driver.vehicle
        converted = [
            revenue_in_profile_currency(o.revenue_minor, o.revenue_currency, profile)
            if o.revenue_minor is not None
            else None
            for o in offers
        ]
        if any(amount is None for amount in converted):
            raise ValueError("cannot calculate a plan without convertible revenue")
        revenue = sum(amount for amount in converted if amount is not None)
        fuel = sum(
            (self.leg_fuel(vehicle, leg.distance_km, leg.drive_min, leg.load_kg) for leg in legs),
            Decimal("0.000"),
        )
        distance = sum((leg.distance_km for leg in legs), Decimal("0.00"))
        empty = sum((leg.distance_km for leg in legs if leg.load_kg == 0), Decimal("0.00"))
        drive_min = sum(a.activity.minutes for a in activities if a.activity.kind == "DRIVE")
        service_min = sum(a.activity.minutes for a in activities if a.activity.kind == "WORK")
        wait_min = sum(a.activity.minutes for a in activities if a.activity.kind == "WAIT")
        points = {point.key: point for leg in legs for point in (leg.start, leg.end)}
        points[driver.home.key] = driver.home

        def at_home(point_key: str | None) -> bool:
            point = points.get(point_key) if point_key is not None else None
            return point is not None and (
                point.key == driver.home.key
                or (
                    point.lat is not None
                    and point.lon is not None
                    and point.lat == driver.home.lat
                    and point.lon == driver.home.lon
                    and point.country == driver.home.country
                )
            )

        rest_count = sum(
            1 for a in activities if a.activity.kind == "DAILY_REST" and not at_home(a.point_key)
        )
        foreign = any(
            point.country != driver.home.country for leg in legs for point in (leg.start, leg.end)
        )
        elapsed = int((finish_at - departure_at).total_seconds() // 60)
        per_diem = (
            Decimal("0")
            if foreign
            else (
                Decimal(profile.per_diem.get(driver.home.country or "", 0))
                * self.per_diem_multiplier(elapsed)
            )
        )
        toll = sum(
            (
                leg.distance_km * profile.toll_per_km.get(leg.end.country or "", 0)
                for leg in legs
                if leg.end.country not in profile.annual_vignettes
            ),
            Decimal("0"),
        )
        warnings = (
            ["VIGNETTE_ASSUMED_ANNUAL"]
            if any(leg.end.country in profile.annual_vignettes for leg in legs)
            else []
        )
        parameters = {
            "fuel_price_minor_per_l": {
                "value": str(profile.fuel_price_minor_per_l),
                "provenance": profile.provenance.get("fuel_price_minor_per_l", "source"),
            },
            "driver_cost_minor_per_hour": {
                "value": str(profile.driver_cost_minor_per_hour),
                "provenance": profile.provenance.get("driver_cost_minor_per_hour", "assumption"),
            },
            "vehicle_cost_minor_per_km": {
                "value": str(profile.vehicle_cost_minor_per_km),
                "provenance": profile.provenance.get("vehicle_cost_minor_per_km", "assumption"),
            },
            "accommodation_minor": {
                "value": str(profile.accommodation_minor),
                "provenance": profile.provenance.get("accommodation_minor", "assumption"),
            },
            "co2_factor_kg_per_l": {"value": str(self.co2_factor), "provenance": "assumption"},
            "fuel_consumption": {
                "value": f"{vehicle.fuel_l_per_100km_empty}/{vehicle.fuel_l_per_100km_full}",
                "provenance": vehicle.fuel_provenance,
            },
        }
        calculation = Calculation(
            fuel=int(rounded(fuel * profile.fuel_price_minor_per_l)),
            toll=int(rounded(toll)),
            driver=int(
                rounded(
                    Decimal(drive_min + service_min + wait_min)
                    * profile.driver_cost_minor_per_hour
                    / 60
                )
            ),
            per_diem=int(rounded(per_diem)),
            accommodation=0 if vehicle.sleeper_cab else rest_count * profile.accommodation_minor,
            vehicle=int(rounded(distance * profile.vehicle_cost_minor_per_km)),
            parameters=parameters,
        )
        profit = revenue - calculation.total
        return CostResult(
            calculation=calculation,
            revenue_minor=revenue,
            net_profit_minor=profit,
            margin_pct=rounded(Decimal(profit) * 100 / revenue, 2) if revenue else Decimal("0.00"),
            fuel_l=fuel,
            co2_kg=self.co2(fuel),
            distance_km=distance,
            empty_km=empty,
            drive_min=drive_min,
            service_min=service_min,
            wait_min=wait_min,
            work_min=drive_min + service_min + wait_min,
            warnings=warnings,
        )
