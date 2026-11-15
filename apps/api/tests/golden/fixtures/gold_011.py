"""Inputs of GOLD-011, copied from section 2 of specs/golden/GOLD-011.md."""

from routepilot.optimization.engine.models import EngineSnapshot

from ..factories import driver, snapshot
from .common import POINTS, load


def build() -> EngineSnapshot:
    p = POINTS
    return snapshot(
        [driver(p["Katowice"], identifier="D1")],
        [
            load("A1", "Katowice", "Dresden", 3, 300, 24400, (0, 6, 10), (0, 12, 20)),
            load("A2", "Katowice", "Dresden", 2, 220, 17500, (0, 6, 10), (0, 12, 20)),
            load("A3", "Katowice", "Dresden", 3, 310, 24800, (0, 6, 10), (0, 12, 20)),
            load("A4", "Katowice", "Dresden", 2, 200, 16600, (0, 6, 10), (0, 12, 20)),
            load("R", "Dresden", "Katowice", 6, 600, 37900, (1, 6, 10), (1, 12, 20)),
            load("C1", "Katowice", "Wroclaw", 2, 200, 12300, (0, 6, 10), (0, 8, 16)),
            load("C2", "Wroclaw", "Dresden", 3, 300, 18900, (0, 9, 14), (0, 12, 20)),
            load("C3", "Dresden", "Katowice", 5, 500, 32300, (1, 6, 10), (1, 12, 20)),
        ],
    )
