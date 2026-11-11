"""Fixed-order offer checks and conservative pallet equivalents (FR-15-19)."""

from datetime import timedelta
from decimal import ROUND_CEILING, Decimal

from routepilot.optimization.engine.costs import revenue_in_profile_currency
from routepilot.optimization.engine.models import DriverSnapshot, EngineSnapshot, OfferSnapshot


def pallet_equivalents(offer: OfferSnapshot) -> tuple[Decimal | None, list[str]]:
    warnings: list[str] = []
    count = offer.pallet_count
    derived = (
        int((offer.loading_length_m * Decimal("2.4")).to_integral_value(rounding=ROUND_CEILING))
        if offer.loading_length_m is not None
        else None
    )
    if count is None or offer.pallet_provenance == "ai":
        if derived is not None:
            count = max(derived, count or 0)
            warnings.append("PALLETS_DERIVED")
        elif count is None or offer.pallet_provenance == "ai":
            return None, warnings
    factors = {
        "EUR_1200x800": Decimal("1"),
        "HALF_800x600": Decimal(".5"),
        "INDUSTRIAL_1200x1000": Decimal("1.5"),
    }
    factor = factors.get(offer.pallet_type)
    if factor is None:
        factor = Decimal("1")
        warnings.append("PALLET_TYPE_UNKNOWN")
    return Decimal(count) * factor, warnings


def prefilter_offer(
    snapshot: EngineSnapshot, driver: DriverSnapshot, offer: OfferSnapshot
) -> str | None:
    vehicle = driver.vehicle
    if offer.status != "open":
        return "OFFER_NOT_OPEN"
    if offer.required_vehicle_types and vehicle.vehicle_type not in offer.required_vehicle_types:
        return "VEHICLE_TYPE_MISMATCH"
    if offer.required_body_types and vehicle.body_type not in offer.required_body_types:
        return "BODY_TYPE_MISMATCH"
    if not set(offer.required_equipment).issubset(vehicle.equipment):
        return "EQUIPMENT_MISSING"
    if (
        offer.revenue_minor is None
        or revenue_in_profile_currency(
            offer.revenue_minor, offer.revenue_currency, driver.cost_profile
        )
        is None
    ):
        return "MISSING_REVENUE"
    if any(stop.point.lat is None or stop.point.lon is None for stop in offer.stops):
        return "MISSING_COORDINATES"
    equivalents, _ = pallet_equivalents(offer)
    if equivalents is None or offer.weight_kg is None:
        return "MISSING_CAPACITY_DATA"
    if offer.weight_kg > vehicle.payload_kg:
        return "OVERWEIGHT"
    if equivalents > vehicle.pallet_places:
        return "PALLET_CAPACITY_EXCEEDED"
    if (
        offer.loading_length_m is not None
        and vehicle.inner_length_m is not None
        and offer.loading_length_m > vehicle.inner_length_m
    ) or (
        offer.height_m is not None
        and vehicle.inner_height_m is not None
        and offer.height_m > vehicle.inner_height_m
    ):
        return "DIMENSIONS_EXCEEDED"
    if offer.stops[0].window_start >= snapshot.reference_time + timedelta(
        days=snapshot.params.horizon_days
    ):
        return "OUTSIDE_HORIZON"
    _, drive = snapshot.matrix.leg(driver.position, offer.stops[0].point)
    if driver.available_from + timedelta(minutes=drive) > offer.stops[0].window_end:
        return "PICKUP_WINDOW_UNREACHABLE"
    return None


def offer_pool(
    snapshot: EngineSnapshot, driver: DriverSnapshot
) -> tuple[list[OfferSnapshot], dict[str, str], bool]:
    rejected: dict[str, str] = {}
    pool: list[OfferSnapshot] = []
    for offer in sorted(snapshot.offers, key=lambda item: item.id):
        code = prefilter_offer(snapshot, driver, offer)
        if code:
            rejected[offer.id] = code
        else:
            pool.append(offer)
    truncated = len(pool) > snapshot.params.max_pool_per_driver
    if truncated:

        def key(offer: OfferSnapshot) -> tuple[Decimal, str]:
            deadhead, _ = snapshot.matrix.leg(driver.position, offer.stops[0].point)
            loaded, _ = snapshot.matrix.leg(offer.stops[0].point, offer.stops[1].point)
            revenue = (
                revenue_in_profile_currency(
                    offer.revenue_minor or 0, offer.revenue_currency, driver.cost_profile
                )
                or 0
            )
            distance = deadhead + loaded
            ratio = Decimal(revenue) / distance if distance else Decimal("Infinity")
            return -ratio, offer.id

        pool = sorted(pool, key=key)[: snapshot.params.max_pool_per_driver]
    return sorted(pool, key=lambda item: item.id), rejected, truncated
