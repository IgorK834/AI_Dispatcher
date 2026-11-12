"""Inputs transcribed from the approved specs/golden/GOLD-001 through GOLD-010 files."""

from datetime import timedelta

from routepilot.optimization.engine.models import EngineSnapshot

from .factories import T, driver, offer, point, snapshot

CITIES = {
    "Katowice": (50.2649, 19.0238, "PL"),
    "Wroclaw": (51.1079, 17.0385, "PL"),
    "Opole": (50.6751, 17.9213, "PL"),
    "Dresden": (51.0504, 13.7373, "DE"),
    "Leipzig": (51.3397, 12.3731, "DE"),
    "Krakow": (50.0647, 19.9450, "PL"),
    "Czestochowa": (50.8118, 19.1203, "PL"),
    "Lodz": (51.7592, 19.4560, "PL"),
    "Warszawa": (52.2297, 21.0122, "PL"),
    "Poznan": (52.4064, 16.9252, "PL"),
    "Gdansk": (54.3520, 18.6466, "PL"),
    "Szczecin": (53.4285, 14.5528, "PL"),
    "Rzeszow": (50.0412, 21.9991, "PL"),
}
POINTS = {name: point(name, *values) for name, values in CITIES.items()}


def at(day: int, hour: int, minute: int = 0):
    """Local CET table timestamp to aware UTC."""
    return T + timedelta(days=day, hours=hour - 6, minutes=minute)


def load(
    identifier: str,
    start: str,
    end: str,
    pallets: int,
    weight: int,
    revenue: int,
    pickup: tuple[int, int, int],
    delivery: tuple[int, int, int],
):
    pd, ps, pe = pickup
    dd, ds, de = delivery
    return offer(
        identifier,
        POINTS[start],
        POINTS[end],
        weight=weight,
        pallets=pallets,
        revenue=revenue,
        pickup=(at(pd, ps), at(pd, pe)),
        delivery=(at(dd, ds), at(dd, de)),
    )


def case(number: int) -> EngineSnapshot:
    p = POINTS
    if number == 1:
        return snapshot(
            [driver(p["Katowice"], identifier="D1")],
            [
                load("A", "Katowice", "Wroclaw", 4, 380, 19000, (0, 6, 10), (0, 8, 16)),
                load("B", "Opole", "Dresden", 4, 420, 30000, (0, 7, 12), (0, 12, 20)),
                load("C", "Wroclaw", "Leipzig", 2, 200, 29000, (0, 9, 14), (1, 6, 12)),
            ],
        )
    if number == 2:
        return snapshot(
            [driver(p["Katowice"], identifier="D1")],
            [
                load("A", "Katowice", "Wroclaw", 3, 300, 20000, (0, 6, 12), (0, 8, 20)),
                load("X", "Krakow", "Czestochowa", 2, 200, 11500, (0, 6, 12), (0, 8, 20)),
            ],
        )
    if number == 3:
        return snapshot(
            [driver(p["Krakow"], identifier="D5", payload=765, pallets=8)],
            [
                load("E", "Krakow", "Katowice", 4, 450, 14000, (0, 6, 7), (0, 7, 12)),
                load("F", "Krakow", "Opole", 4, 400, 23000, (0, 6, 7), (0, 8, 14)),
            ],
        )
    if number in (4, 5):
        d = driver(p["Wroclaw"], identifier="D2", payload=1050)
        d = d.model_copy(update={"vehicle": d.vehicle.model_copy(update={"sleeper_cab": True})})
        if number == 4:
            offers = [
                load("G", "Wroclaw", "Opole", 3, 300, 15000, (0, 6, 8), (0, 12, 15)),
                load("H", "Wroclaw", "Katowice", 3, 350, 22000, (0, 6, 8), (0, 8, 11)),
            ]
        else:
            item = load("I", "Wroclaw", "Dresden", 5, 500, 32000, (0, 6, 7), (0, 8, 12))
            offers = [
                item.model_copy(
                    update={
                        "stops": (
                            item.stops[0].model_copy(update={"window_end": at(0, 6, 30)}),
                            item.stops[1].model_copy(update={"window_end": at(0, 11, 45)}),
                        )
                    }
                )
            ]
        return snapshot([d], offers)
    if number == 6:
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
                        update={
                            "point": point("Unknown").model_copy(update={"lat": None, "lon": None})
                        }
                    ),
                )
            }
        )
        return snapshot([d], offers)
    if number == 7:
        return snapshot(
            [driver(p["Katowice"], identifier="D1")],
            [
                load("J", "Katowice", "Gdansk", 5, 500, 52000, (0, 6, 8), (0, 12, 20)),
                load("K", "Gdansk", "Szczecin", 4, 400, 33000, (0, 14, 20), (1, 6, 14)),
            ],
        )
    if number == 8:
        d = driver(p["Katowice"], identifier="D1", available=at(3, 6), home_by=at(4, 18))
        d = d.model_copy(
            update={
                "rules_state": d.rules_state.model_copy(
                    update={"work_week": 1500, "drive_week": 1100}
                )
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
    if number == 9:
        return snapshot(
            [
                driver(p["Katowice"], identifier="D1", available=at(0, 8)),
                driver(
                    p["Krakow"], identifier="D5", available=at(0, 6, 33), payload=765, pallets=8
                ),
            ],
            [
                load("X", "Katowice", "Wroclaw", 4, 400, 29000, (0, 8, 9), (0, 10, 18)),
                load("Y", "Katowice", "Opole", 6, 800, 19000, (0, 8, 9), (0, 10, 18)),
                load("Z", "Krakow", "Rzeszow", 2, 200, 15000, (0, 6, 9), (0, 9, 18)),
            ],
        )
    if number == 10:
        industrial = load("P", "Lodz", "Warszawa", 4, 320, 21000, (0, 6, 7), (0, 8, 14))
        industrial = industrial.model_copy(update={"pallet_type": "INDUSTRIAL_1200x1000"})
        return snapshot(
            [driver(p["Lodz"], identifier="D4", payload=880, pallets=8)],
            [
                industrial,
                load("Q", "Lodz", "Warszawa", 3, 240, 15000, (0, 6, 7), (0, 8, 14)),
                load("R", "Lodz", "Warszawa", 2, 160, 10000, (0, 6, 7), (0, 8, 14)),
            ],
        )
    raise ValueError(number)


# Ranked sets and all shared assertions from each file's section 4. Monetary values are cents.
EXPECTED = {
    1: dict(
        sets=[["A", "B", "C"], ["A", "B"], ["B", "C"], ["A"], ["A", "C"], ["B"]],
        profits=[32354, 17548, 14562, 5611, 4085, 1129],
        sequence=["PA", "PB", "DA", "PC", "DB", "DC"],
        kg=[380, 800, 420, 620, 200, 0],
        eq=[4, 8, 4, 6, 2, 0],
        starts=[(0, 6, 0), (0, 8, 23), (0, 10, 31), (0, 11, 1), (0, 17, 4), (1, 7, 25)],
        finish=(1, 7, 55),
        distance="624.81",
        drive=625,
        work=805,
        fuel="76.601",
        co2="199.16",
        breaks=90,
        rest=660,
        components=[13865, 0, 18783, 0, 5500, 7498],
        revenue=78000,
        cost=45646,
        profile="eu561_van_international_v1",
    ),
    2: dict(
        sets=[["A"], ["A", "X"]],
        profits=[6668, 5334],
        sequence=["PA", "DA"],
        kg=[300, 0],
        eq=[3, 0],
        starts=[(0, 6, 0), (0, 10, 0)],
        finish=(0, 10, 30),
        distance="210.45",
        drive=210,
        work=270,
        fuel="24.898",
        co2="64.73",
        breaks=0,
        rest=0,
        components=[4507, 0, 6300, 0, 0, 2525],
        revenue=20000,
        cost=13332,
    ),
    3: dict(
        sets=[["F"], ["E"]],
        profits=[10168, 7571],
        sequence=["PF", "DF"],
        kg=[400, 0],
        eq=[4, 0],
        starts=[(0, 6, 0), (0, 9, 48)],
        finish=(0, 10, 18),
        distance="198.45",
        drive=198,
        work=258,
        fuel="24.478",
        co2="63.64",
        breaks=0,
        rest=0,
        components=[4431, 0, 6020, 0, 0, 2381],
        revenue=23000,
        cost=12832,
    ),
    4: dict(
        sets=[["G", "H"], ["H"], ["G"]],
        profits=[15583, 8624],
        sequence=["PG", "PH", "DH", "DG"],
        kg=[300, 650, 300, 0],
        eq=[3, 6, 3, 0],
        starts=[(0, 6, 0), (0, 6, 30), (0, 10, 30), (0, 13, 23)],
        finish=(0, 13, 53),
        distance="323.43",
        drive=323,
        work=443,
        fuel="39.775",
        co2="103.42",
        breaks=30,
        rest=0,
        components=[7199, 0, 10337, 0, 0, 3881],
        revenue=37000,
        cost=21417,
    ),
    7: dict(
        sets=[["J", "K"], ["J"]],
        profits=[21985, 17414],
        sequence=["PJ", "DJ", "PK", "DK"],
        kg=[500, 0, 400, 0],
        eq=[5, 0, 4, 0],
        starts=[(0, 6, 0), (0, 16, 43), (0, 17, 13), (1, 10, 41)],
        finish=(1, 11, 11),
        distance="927.98",
        drive=926,
        work=1046,
        fuel="112.612",
        co2="292.79",
        breaks=45,
        rest=660,
        components=[20383, 0, 24407, 1589, 5500, 11136],
        revenue=85000,
        cost=63015,
    ),
    8: dict(
        sets=[["L", "M"]],
        profits=[4636],
        sequence=["PL", "DL", "PM", "DM"],
        kg=[600, 0, 350, 0],
        eq=[6, 0, 4, 0],
        starts=[(3, 6, 0), (3, 12, 48), (3, 13, 18), (4, 6, 51)],
        finish=(4, 7, 21),
        distance="697.96",
        drive=696,
        work=816,
        fuel="84.854",
        co2="220.62",
        breaks=45,
        rest=660,
        components=[15359, 0, 19040, 1589, 5500, 8376],
        revenue=54500,
        cost=49864,
    ),
    10: dict(
        sets=[["P", "R"], ["Q", "R"], ["P"], ["Q"], ["R"]],
        profits=[19642, 13693, 11142, 5192, 242],
        sequence=["PP", "PR", "DP", "DR"],
        kg=[320, 480, 160, 0],
        eq=[6, 8, 2, 0],
        starts=[(0, 6, 0), (0, 6, 30), (0, 9, 28), (0, 9, 58)],
        finish=(0, 10, 28),
        distance="148.37",
        drive=148,
        work=268,
        fuel="18.368",
        co2="47.76",
        breaks=0,
        rest=0,
        components=[3325, 0, 6253, 0, 0, 1780],
        revenue=31000,
        cost=11358,
    ),
}
