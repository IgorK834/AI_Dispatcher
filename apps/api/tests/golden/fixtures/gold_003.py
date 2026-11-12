"""Inputs of GOLD-003, copied from section 2 of specs/golden/GOLD-003.md."""

from routepilot.optimization.engine.models import EngineSnapshot

from ..factories import driver, snapshot
from .common import POINTS, load


def build() -> EngineSnapshot:
    p = POINTS
    return snapshot(
        [driver(p["Krakow"], identifier="D5", payload=765, pallets=8)],
        [
            load("E", "Krakow", "Katowice", 4, 450, 14000, (0, 6, 7), (0, 7, 12)),
            load("F", "Krakow", "Opole", 4, 400, 23000, (0, 6, 7), (0, 8, 14)),
        ],
    )
