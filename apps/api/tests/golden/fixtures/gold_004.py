"""Inputs of GOLD-004, copied from section 2 of specs/golden/GOLD-004.md."""

from routepilot.optimization.engine.models import EngineSnapshot

from ..factories import driver, snapshot
from .common import POINTS, load


def build() -> EngineSnapshot:
    p = POINTS
    d = driver(p["Wroclaw"], identifier="D2", payload=1050)
    d = d.model_copy(update={"vehicle": d.vehicle.model_copy(update={"sleeper_cab": True})})
    offers = [
        load("G", "Wroclaw", "Opole", 3, 300, 15000, (0, 6, 8), (0, 12, 15)),
        load("H", "Wroclaw", "Katowice", 3, 350, 22000, (0, 6, 8), (0, 8, 11)),
    ]
    return snapshot([d], offers)
