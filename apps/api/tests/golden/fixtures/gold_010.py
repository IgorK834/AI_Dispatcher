"""Inputs of GOLD-010, copied from section 2 of specs/golden/GOLD-010.md."""

from routepilot.optimization.engine.models import EngineSnapshot

from ..factories import driver, snapshot
from .common import POINTS, load


def build() -> EngineSnapshot:
    p = POINTS
    industrial = load("P", "Lodz", "Warszawa", 4, 320, 21000, (0, 6, 7), (0, 8, 14))
    industrial = industrial.model_copy(update={"pallet_type": "IND_1200x1000"})
    return snapshot(
        [driver(p["Lodz"], identifier="D4", payload=880, pallets=8)],
        [
            industrial,
            load("Q", "Lodz", "Warszawa", 3, 240, 15000, (0, 6, 7), (0, 8, 14)),
            load("R", "Lodz", "Warszawa", 2, 160, 10000, (0, 6, 7), (0, 8, 14)),
        ],
    )
