"""Load metrics of a plan: how full the van was per kilometre (FEAT-010 FR-10). Pure."""

from collections.abc import Iterable, Sequence
from decimal import ROUND_HALF_UP, Decimal

from routepilot.optimization.engine.models import Action, PlanLeg, VehicleSnapshot

PLACES = Decimal("0.0001")
Step = tuple[Decimal, Decimal, int]  # leg distance in km, pallet equivalents and kg on that leg


def _factors(steps: Iterable[Step], vehicle: VehicleSnapshot) -> tuple[Decimal, Decimal]:
    distance = pallet_km = kg_km = Decimal(0)
    for km, pallet_eq, kg in steps:
        distance += km
        pallet_km += pallet_eq * km
        kg_km += kg * km
    if distance == 0:
        return Decimal("0.0000"), Decimal("0.0000")
    return (
        (pallet_km / (vehicle.pallet_places * distance)).quantize(PLACES, rounding=ROUND_HALF_UP),
        (kg_km / (vehicle.payload_kg * distance)).quantize(PLACES, rounding=ROUND_HALF_UP),
    )


def max_on_board(kinds: Iterable[str]) -> int:
    """The highest number of offers on board at the same time, from the stop or action kinds."""
    on_board = highest = 0
    for kind in kinds:
        on_board += (kind == "PICKUP") - (kind == "DELIVERY")
        highest = max(highest, on_board)
    return highest


def load_metrics(
    legs: Sequence[PlanLeg], actions: Sequence[Action], vehicle: VehicleSnapshot
) -> tuple[Decimal, Decimal, int]:
    """`load_factor_ep`, `load_factor_kg` (0 … 1, 4 places) and `max_orders_on_board`."""
    factors = _factors(
        ((leg.distance_km, leg.load_pallet_eq, leg.load_kg) for leg in legs), vehicle
    )
    return (*factors, max_on_board(action.kind for action in actions))


def stop_load_metrics(
    stops: Iterable[tuple[str, Decimal, Decimal, int]], vehicle: VehicleSnapshot
) -> tuple[Decimal, Decimal, int]:
    """The same metrics from stored stops: (kind, leg km to the stop, load after the stop).

    The leg that ends at a stop carries the load left after the stop before it; the first leg
    starts empty. The informational `WEEKLY_REST` marker repeats the leg of the `END` stop and
    is not a leg of its own.
    """
    rows = list(stops)
    loads = [(Decimal(0), 0), *((pallet_eq, kg) for _, _, pallet_eq, kg in rows)][: len(rows)]
    steps = [
        (Decimal(0) if kind == "WEEKLY_REST" else km, pallet_eq, kg)
        for (kind, km, _, _), (pallet_eq, kg) in zip(rows, loads, strict=True)
    ]
    return (*_factors(steps, vehicle), max_on_board(kind for kind, _, _, _ in rows))
