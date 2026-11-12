"""Inputs of GOLD-002, copied from section 2 of specs/golden/GOLD-002.md."""

from routepilot.optimization.engine.models import EngineSnapshot

from ..factories import driver, snapshot
from .common import POINTS, load


def build() -> EngineSnapshot:
    p = POINTS
    return snapshot(
        [driver(p["Katowice"], identifier="D1")],
        [
            load("A", "Katowice", "Wroclaw", 3, 300, 20000, (0, 6, 12), (0, 8, 20)),
            load("X", "Krakow", "Czestochowa", 2, 200, 11500, (0, 6, 12), (0, 8, 20)),
        ],
    )
