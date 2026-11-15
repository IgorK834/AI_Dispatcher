"""Fixed rejection ordering and conservative source handling (FR-15/16)."""

from datetime import timedelta
from decimal import Decimal

import pytest

from routepilot.optimization.engine.models import EngineParams
from routepilot.optimization.engine.prefilter import offer_pool, pallet_equivalents, prefilter_offer

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


@pytest.mark.ac("AC-FEAT-010-08")
def test_pool_cut_keeps_the_partner_of_a_kept_offer_before_filling_by_ratio() -> None:
    home = point("HOME")
    d = driver(home)
    window = (T, T + timedelta(days=2))
    # 70 offers picked up at the driver's position; deliveries on a grid more than 150 km apart,
    # so no two are pool partners. Offer N has the (N + 1)-th best revenue per km.
    ends = [point(f"E{n:02}", 40 + 2 * (n % 10), 5 + 4 * (n // 10)) for n in range(70)]
    ends[60] = ends[0].model_copy(update={"key": "E60", "city": "E60"})  # P delivers where O00 does
    offers = []
    for n, end in enumerate(ends):
        o = offer(f"O{n:02}", home, end, pickup=window, delivery=window)
        offers.append(o)
    source = snapshot([d], offers)
    offers = [
        o.model_copy(
            update={
                "revenue_minor": int(
                    (1000 - 10 * n) * source.matrix.leg(o.stops[0].point, o.stops[1].point)[0]
                )
            }
        )
        for n, o in enumerate(offers)
    ]
    source = source.model_copy(update={"offers": offers})
    pool, rejected, truncated = offer_pool(source, d)
    ids = [o.id for o in pool]
    assert rejected == {} and truncated is True
    assert len(ids) == 60 and ids == sorted(ids)
    assert {f"O{n:02}" for n in range(30)} <= set(ids)  # phase 1: the 30 best ratios
    assert "O60" in ids  # phase 2: P, the 61st best, is a pool partner of the best offer
    assert "O59" not in ids  # phase 3 fills by ratio and stops before the 60th best
    assert set(ids) == {f"O{n:02}" for n in range(59)} | {"O60"}


@pytest.mark.ac("AC-FEAT-010-08")
def test_pool_partner_radii_are_positive_parameters_with_the_spec_defaults() -> None:
    params = EngineParams()
    assert params.pool_partner_pickup_km == Decimal("80")
    assert params.pool_partner_delivery_km == Decimal("150")
    for field in ("pool_partner_pickup_km", "pool_partner_delivery_km"):
        with pytest.raises(ValueError):
            EngineParams(**{field: Decimal("0")})
