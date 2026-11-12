"""Inputs of GOLD-009, copied from section 2 of specs/golden/GOLD-009.md."""

from routepilot.optimization.engine.models import EngineSnapshot

from ..factories import driver, snapshot
from .common import POINTS, at, load


def build() -> EngineSnapshot:
    p = POINTS
    return snapshot(
        [
            driver(p["Katowice"], identifier="D1", available=at(0, 8)),
            driver(p["Krakow"], identifier="D5", available=at(0, 6, 33), payload=765, pallets=8),
        ],
        [
            load("X", "Katowice", "Wroclaw", 4, 400, 29000, (0, 8, 9), (0, 10, 18)),
            load("Y", "Katowice", "Opole", 6, 800, 19000, (0, 8, 9), (0, 10, 18)),
            load("Z", "Krakow", "Rzeszow", 2, 200, 15000, (0, 6, 9), (0, 9, 18)),
        ],
    )
