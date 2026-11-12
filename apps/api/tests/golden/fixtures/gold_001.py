"""Inputs of GOLD-001, copied from section 2 of specs/golden/GOLD-001.md."""

from routepilot.optimization.engine.models import EngineSnapshot

from ..factories import driver, snapshot
from .common import POINTS, load


def build() -> EngineSnapshot:
    p = POINTS
    return snapshot(
        [driver(p["Katowice"], identifier="D1")],
        [
            load("A", "Katowice", "Wroclaw", 4, 380, 19000, (0, 6, 10), (0, 8, 16)),
            load("B", "Opole", "Dresden", 4, 420, 30000, (0, 7, 12), (0, 12, 20)),
            load("C", "Wroclaw", "Leipzig", 2, 200, 29000, (0, 9, 14), (1, 6, 12)),
        ],
    )
