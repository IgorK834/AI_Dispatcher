"""Inputs of GOLD-005, copied from section 2 of specs/golden/GOLD-005.md."""

from routepilot.optimization.engine.models import EngineSnapshot

from ..factories import driver, snapshot
from .common import POINTS, at, load


def build() -> EngineSnapshot:
    p = POINTS
    d = driver(p["Wroclaw"], identifier="D2", payload=1050)
    d = d.model_copy(update={"vehicle": d.vehicle.model_copy(update={"sleeper_cab": True})})
    item = load("I", "Wroclaw", "Dresden", 5, 500, 32000, (0, 6, 7), (0, 8, 12))
    offers = [
        item.model_copy(
            update={
                "stops": (
                    item.stops[0].model_copy(update={"window_end": at(0, 6, 30)}),
                    item.stops[1].model_copy(update={"window_end": at(0, 11, 45)}),
                )
            }
        )
    ]
    return snapshot([d], offers)
