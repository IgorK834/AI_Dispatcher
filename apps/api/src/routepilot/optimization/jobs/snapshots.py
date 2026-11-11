"""Build serializable engine inputs from persisted records, without live IO."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from routepilot.compliance.models import DriverState
from routepilot.optimization.engine.models import (
    CostProfile,
    DriverSnapshot,
    EngineParams,
    EngineSnapshot,
    OfferSnapshot,
    Point,
    Stop,
    TravelMatrix,
    VehicleSnapshot,
)
from routepilot.optimization.jobs.domain import JobCreate
from routepilot.optimization.jobs.repository import JobsRepository
from routepilot.shared.errors import DomainError


def utc(value: Any) -> datetime:
    result = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    return result.replace(tzinfo=UTC) if result.tzinfo is None else result.astimezone(UTC)


def metres(value: Any) -> Decimal | None:
    return Decimal(value) / 1000 if value is not None else None


def _timezone(country: str) -> str:
    # IANA zones used by the approved city fixture. Offer stops retain their own
    # stored zone; driver homes use the same country mapping as the geocoder.
    return {
        "PL": "Europe/Warsaw",
        "DE": "Europe/Berlin",
        "CZ": "Europe/Prague",
        "AT": "Europe/Vienna",
        "SK": "Europe/Bratislava",
        "NL": "Europe/Amsterdam",
        "BE": "Europe/Brussels",
        "FR": "Europe/Paris",
        "IT": "Europe/Rome",
        "ES": "Europe/Madrid",
        "HU": "Europe/Budapest",
        "LT": "Europe/Vilnius",
        "DK": "Europe/Copenhagen",
    }.get(country, "UTC")


def build_snapshot(
    repository: JobsRepository,
    session: Session,
    body: JobCreate,
    now: datetime,
    params: EngineParams,
    co2: Decimal,
) -> EngineSnapshot:
    drivers_table, states_table = repository.table("drivers"), repository.table("driver_states")
    vehicles_table, costs_table = repository.table("vehicles"), repository.table("cost_profiles")
    query = (
        select(drivers_table)
        .where(drivers_table.c.deleted_at.is_(None))
        .order_by(drivers_table.c.id)
    )
    if body.driver_ids:
        query = query.where(drivers_table.c.id.in_([str(v) for v in body.driver_ids]))
    drivers = session.execute(query).mappings().all()
    if body.driver_ids and {str(row["id"]) for row in drivers} != {
        str(value) for value in body.driver_ids
    }:
        raise DomainError("NOT_FOUND", 404)
    driver_inputs = []
    for row in drivers:
        state = (
            session.execute(
                select(states_table)
                .where(states_table.c.driver_id == str(row["id"]))
                .order_by(states_table.c.valid_from.desc(), states_table.c.id.desc())
            )
            .mappings()
            .first()
        )
        vehicle = (
            session.execute(
                select(vehicles_table).where(vehicles_table.c.id == str(row["vehicle_id"]))
            )
            .mappings()
            .first()
            if row["vehicle_id"]
            else None
        )
        # Incomplete fleet entities cannot enter a feasible optimization plan.
        if state is None or vehicle is None:
            continue
        cost = (
            session.execute(
                select(costs_table).where(costs_table.c.id == str(vehicle["cost_profile_id"]))
            )
            .mappings()
            .one()
        )
        home = Point(
            key=f"home:{row['id']}",
            city=row["home_city"],
            country=row["home_country"],
            lat=row["home_lat"],
            lon=row["home_lon"],
            timezone=_timezone(row["home_country"]),
        )
        position = Point(
            key=f"position:{row['id']}",
            city=state["current_city"] or "",
            country=None,
            lat=state["current_lat"],
            lon=state["current_lon"],
            timezone=home.timezone,
        )
        available = utc(state["available_from"])
        tolls = cost["tolls"]
        driver_inputs.append(
            DriverSnapshot(
                id=str(row["id"]),
                home=home,
                position=position,
                available_from=available,
                home_by=utc(state["home_by"]) if state["home_by"] else None,
                vehicle=VehicleSnapshot(
                    id=str(vehicle["id"]),
                    vehicle_type=vehicle["vehicle_type"],
                    body_type=vehicle["body_type"],
                    pallet_places=vehicle["pallet_places"],
                    payload_kg=vehicle["payload_kg"],
                    inner_length_m=metres(vehicle["inner_length_mm"]),
                    inner_height_m=metres(vehicle["inner_height_mm"]),
                    sleeper_cab=vehicle["sleeper_cab"],
                    fuel_l_per_100km_empty=Decimal(vehicle["fuel_l_per_100km_empty_x10"]) / 10,
                    fuel_l_per_100km_full=Decimal(vehicle["fuel_l_per_100km_full_x10"]) / 10,
                    fuel_speed_curve=vehicle["fuel_speed_curve"],
                    fuel_provenance=vehicle["fuel_provenance"],
                ),
                cost_profile=CostProfile(
                    id=str(cost["id"]),
                    currency=cost["currency"],
                    fuel_price_minor_per_l=cost["fuel_price_minor_per_l"],
                    driver_cost_minor_per_hour=cost["driver_cost_minor_per_hour"],
                    vehicle_cost_minor_per_km=cost["vehicle_cost_minor_per_km"],
                    accommodation_minor=cost["accommodation_minor"],
                    per_diem=cost["per_diem"],
                    toll_per_km=tolls.get("perKm", tolls.get("per_km", {})),
                    annual_vignettes=tolls.get(
                        "annualVignettes", tolls.get("annual_vignettes", [])
                    ),
                    fx_rates=cost["fx_rates"],
                    min_profit_minor=cost["min_profit_minor"],
                    min_margin_pct=cost["min_margin_pct"],
                    provenance=cost["provenance"],
                ),
                rules_state=DriverState(
                    t=available,
                    work_today=state["work_today_min"],
                    drive_today=state["drive_today_min"],
                    work_since_break=state["work_since_break_min"],
                    drive_since_break=state["drive_since_break_min"],
                    work_week=state["work_week_min"],
                    drive_week=state["drive_week_min"],
                    drive_prev_week=state["drive_prev_week_min"],
                    day_start_at=utc(state["last_daily_rest_end"])
                    if state["last_daily_rest_end"]
                    else None,
                    sleeper_cab=vehicle["sleeper_cab"],
                    home_timezone=home.timezone,
                ),
            )
        )
    offer_table, stop_table = repository.table("freight_offers"), repository.table("freight_stops")
    offer_query = select(offer_table).order_by(offer_table.c.id)
    if body.offer_ids is None:
        offer_query = offer_query.where(offer_table.c.status == "open")
    else:
        offer_query = offer_query.where(
            offer_table.c.id.in_([str(value) for value in body.offer_ids])
        )
    offers = session.execute(offer_query).mappings().all()
    if body.offer_ids is not None and {str(row["id"]) for row in offers} != {
        str(value) for value in body.offer_ids
    }:
        raise DomainError("NOT_FOUND", 404)
    offer_inputs = []
    for row in offers:
        stops = (
            session.execute(
                select(stop_table)
                .where(stop_table.c.offer_id == str(row["id"]))
                .order_by(stop_table.c.sequence)
            )
            .mappings()
            .all()
        )
        if len(stops) != 2:
            # Multi-stop offers have already been tagged as unsupported by the
            # mapper; retain that rejection rather than silently truncating them.
            continue
        required_equipment: list[str] = []
        if row["raw_record_id"]:
            raw_table = repository.table("raw_freight_records")
            raw = session.execute(
                select(raw_table.c.payload).where(raw_table.c.id == str(row["raw_record_id"]))
            ).scalar_one_or_none()
            if isinstance(raw, dict):
                required_equipment = raw.get("vehicleProperties", {}).get("equipment", [])
        mapped = [
            Stop(
                point=Point(
                    key=f"offer:{row['id']}:{stop['sequence']}",
                    city=stop["city"],
                    country=stop["country_code"],
                    lat=stop["lat"],
                    lon=stop["lon"],
                    timezone=stop["timezone"],
                ),
                window_start=utc(stop["window_start"]),
                window_end=utc(stop["window_end"]),
                service_min=stop["service_minutes"],
                service_provenance=stop["provenance"].get("serviceMinutes", "default"),
            )
            for stop in stops
        ]
        offer_inputs.append(
            OfferSnapshot(
                id=str(row["id"]),
                source_offer_id=row["source_offer_id"],
                version=row["version"],
                status=row["status"],
                weight_kg=row["weight_kg"],
                pallet_count=row["pallet_count"],
                pallet_type=row["pallet_type"] or "UNKNOWN",
                pallet_provenance=row["field_provenance"].get("palletCount", "source"),
                loading_length_m=metres(row["loading_length_mm"]),
                revenue_minor=row["revenue_amount_minor"],
                revenue_currency=row["revenue_currency"] or "EUR",
                required_vehicle_types=row["required_vehicle_types"],
                required_body_types=row["required_body_types"],
                required_equipment=required_equipment,
                stops=(mapped[0], mapped[1]),
                warnings=row["quality_flags"],
                field_provenance=row["field_provenance"],
            )
        )
    params = params.model_copy(update=body.params.model_dump())
    return EngineSnapshot(
        reference_time=now,
        drivers=driver_inputs,
        offers=offer_inputs,
        matrix=TravelMatrix(points=[], distance_km=[], duration_min=[], provider_id="pending"),
        params=params,
        objectives=body.objectives,
        co2_factor_kg_per_l=co2,
    )
