"""Inputs of GOLD-008, copied from section 2 of specs/golden/GOLD-008.md."""

from routepilot.optimization.engine.models import EngineSnapshot

from ..factories import driver, snapshot
from .common import POINTS, at, load


def build() -> EngineSnapshot:
    p = POINTS
    d = driver(p["Katowice"], identifier="D1", available=at(3, 6), home_by=at(4, 18))
    d = d.model_copy(
        update={
            "rules_state": d.rules_state.model_copy(update={"work_week": 1500, "drive_week": 1100})
        }
    )
    return snapshot(
        [d],
        [
            load("L", "Katowice", "Poznan", 6, 600, 33000, (3, 6, 9), (3, 11, 18)),
            load("M", "Poznan", "Katowice", 4, 350, 21500, (3, 12, 18), (4, 6, 14)),
            load("N", "Katowice", "Gdansk", 5, 500, 50000, (3, 6, 9), (3, 14, 20)),
        ],
    )
