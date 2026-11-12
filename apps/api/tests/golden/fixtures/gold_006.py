"""Inputs of GOLD-006, copied from section 2 of specs/golden/GOLD-006.md."""

from routepilot.optimization.engine.models import EngineSnapshot

from ..factories import driver, point, snapshot
from .common import POINTS, at, load


def build() -> EngineSnapshot:
    p = POINTS
    d = driver(p["Lodz"], identifier="D4", available=at(0, 8), payload=880, pallets=8)
    offers = [
        load("O1", "Lodz", "Warszawa", 6, 1200, 26000, (0, 8, 12), (0, 10, 18)),
        load("O2", "Lodz", "Poznan", 3, 300, 15000, (0, 8, 12), (0, 10, 18)).model_copy(
            update={"revenue_minor": None}
        ),
        load("O3", "Gdansk", "Warszawa", 2, 200, 30000, (0, 14, 20), (1, 6, 14)),
        load("O4", "Lodz", "Katowice", 2, 150, 18000, (0, 6, 7), (0, 9, 14)),
        load("O5", "Lodz", "Wroclaw", 2, 200, 19000, (0, 8, 12), (0, 10, 18)).model_copy(
            update={"required_body_types": ["BOX"]}
        ),
        load("O6", "Lodz", "Warszawa", 9, 400, 24000, (0, 8, 12), (0, 10, 18)),
        load("O7", "Lodz", "Warszawa", 2, 300, 15000, (0, 8, 12), (0, 10, 18)).model_copy(
            update={"pallet_count": None}
        ),
        load("O8", "Lodz", "Warszawa", 2, 200, 20000, (0, 8, 12), (0, 10, 18)),
    ]
    offers[3] = offers[3].model_copy(
        update={
            "stops": (
                offers[3].stops[0].model_copy(update={"window_end": at(0, 7, 30)}),
                offers[3].stops[1],
            )
        }
    )
    offers[-1] = offers[-1].model_copy(
        update={
            "stops": (
                offers[-1].stops[0],
                offers[-1]
                .stops[1]
                .model_copy(
                    update={"point": point("Unknown").model_copy(update={"lat": None, "lon": None})}
                ),
            )
        }
    )
    return snapshot([d], offers)
