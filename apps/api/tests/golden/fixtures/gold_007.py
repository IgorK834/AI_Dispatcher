"""Inputs of GOLD-007, copied from section 2 of specs/golden/GOLD-007.md."""

from routepilot.optimization.engine.models import EngineSnapshot

from ..factories import driver, snapshot
from .common import POINTS, load


def build() -> EngineSnapshot:
    p = POINTS
    return snapshot(
        [driver(p["Katowice"], identifier="D1")],
        [
            load("J", "Katowice", "Gdansk", 5, 500, 52000, (0, 6, 8), (0, 12, 20)),
            load("K", "Gdansk", "Szczecin", 4, 400, 33000, (0, 14, 20), (1, 6, 14)),
        ],
    )
