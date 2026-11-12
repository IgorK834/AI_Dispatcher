"""City table and builders shared by the golden fixture modules.

Coordinates are the ones listed in section 2.1 of each specs/golden/GOLD-00N.md file; times in the
tables are local CET and converted to UTC by ``at`` (G14).
"""

from datetime import timedelta

from ..factories import T, offer, point

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
