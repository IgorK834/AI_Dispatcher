"""Fixed rejection ordering and conservative source handling (FR-15/16)."""

from datetime import timedelta
from decimal import Decimal

import pytest

from routepilot.optimization.engine.prefilter import pallet_equivalents, prefilter_offer

from .factories import T, driver, offer, point, snapshot


@pytest.mark.ac("AC-FEAT-003-21")
@pytest.mark.parametrize(
    ("updates", "code"),
    [
        ({"status": "expired"}, "OFFER_NOT_OPEN"),
        ({"required_vehicle_types": ["TRUCK"]}, "VEHICLE_TYPE_MISMATCH"),
        ({"required_body_types": ["BOX"]}, "BODY_TYPE_MISMATCH"),
        ({"required_equipment": ["LIFT"]}, "EQUIPMENT_MISSING"),
        ({"revenue_minor": None, "weight_kg": 2000}, "MISSING_REVENUE"),
        ({"pallet_count": None}, "MISSING_CAPACITY_DATA"),
        ({"weight_kg": 2000}, "OVERWEIGHT"),
        ({"pallet_count": 11}, "PALLET_CAPACITY_EXCEEDED"),
        ({"loading_length_m": Decimal("8")}, "DIMENSIONS_EXCEEDED"),
    ],
)
def test_first_prefilter_failure(updates: dict[str, object], code: str) -> None:
    a, b = point("A"), point("B", 52, 20)
    d = driver(a)
    d = d.model_copy(
        update={"vehicle": d.vehicle.model_copy(update={"inner_length_m": Decimal("4")})}
    )
    o = offer("X", a, b).model_copy(update=updates)
    source = snapshot([d], [o])
    assert prefilter_offer(source, d, o) == code


@pytest.mark.ac("AC-FEAT-003-21")
def test_prefilter_coordinate_horizon_reachability_and_ai_capacity() -> None:
    a, b = point("A"), point("B", 52, 20)
    d, o = driver(a), offer("X", a, b)
    missing = o.model_copy(
        update={
            "stops": (
                o.stops[0],
                o.stops[1].model_copy(update={"point": b.model_copy(update={"lat": None})}),
            )
        }
    )
    assert prefilter_offer(snapshot([d], [missing]), d, missing) == "MISSING_COORDINATES"
    horizon = o.model_copy(
        update={
            "stops": (
                o.stops[0].model_copy(update={"window_start": T + timedelta(days=5)}),
                o.stops[1],
            )
        }
    )
    assert prefilter_offer(snapshot([d], [horizon]), d, horizon) == "OUTSIDE_HORIZON"
    unreachable = o.model_copy(
        update={
            "stops": (
                o.stops[0].model_copy(update={"window_end": T - timedelta(minutes=1)}),
                o.stops[1],
            )
        }
    )
    assert (
        prefilter_offer(snapshot([d], [unreachable]), d, unreachable) == "PICKUP_WINDOW_UNREACHABLE"
    )
    ai = o.model_copy(
        update={"pallet_count": 3, "pallet_provenance": "ai", "loading_length_m": Decimal("2")}
    )
    assert pallet_equivalents(ai) == (Decimal("5"), ["PALLETS_DERIVED"])
    unknown = o.model_copy(update={"pallet_type": "UNKNOWN"})
    assert pallet_equivalents(unknown) == (Decimal("2"), ["PALLET_TYPE_UNKNOWN"])
