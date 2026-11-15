"""Cities, synthetic towns and zones of the demo data (FEAT-002 §6.1, FEAT-010 §6.2)."""

import argparse
import json
import math
import random
from pathlib import Path

City = tuple[str, str, float, float, str]  # name, country, lat, lon, IANA time zone

# Approved FEAT-002 section 6.1 (revision 6); immutable inputs keep the generator pure.
NAMED_CITIES: tuple[City, ...] = (
    ("Katowice", "PL", 50.2649, 19.0238, "Europe/Warsaw"),
    ("Wrocław", "PL", 51.1079, 17.0385, "Europe/Warsaw"),
    ("Opole", "PL", 50.6751, 17.9213, "Europe/Warsaw"),
    ("Kraków", "PL", 50.0647, 19.945, "Europe/Warsaw"),
    ("Łódź", "PL", 51.7592, 19.456, "Europe/Warsaw"),
    ("Poznań", "PL", 52.4064, 16.9252, "Europe/Warsaw"),
    ("Warszawa", "PL", 52.2297, 21.0122, "Europe/Warsaw"),
    ("Gdańsk", "PL", 54.352, 18.6466, "Europe/Warsaw"),
    ("Szczecin", "PL", 53.4285, 14.5528, "Europe/Warsaw"),
    ("Rzeszów", "PL", 50.0412, 21.9991, "Europe/Warsaw"),
    ("Bielsko-Biała", "PL", 49.8224, 19.0584, "Europe/Warsaw"),
    ("Częstochowa", "PL", 50.8118, 19.1203, "Europe/Warsaw"),
    ("Dresden", "DE", 51.0504, 13.7373, "Europe/Berlin"),
    ("Leipzig", "DE", 51.3397, 12.3731, "Europe/Berlin"),
    ("Berlin", "DE", 52.52, 13.405, "Europe/Berlin"),
    ("Hamburg", "DE", 53.5511, 9.9937, "Europe/Berlin"),
    ("München", "DE", 48.1351, 11.582, "Europe/Berlin"),
    ("Nürnberg", "DE", 49.4521, 11.0767, "Europe/Berlin"),
    ("Köln", "DE", 50.9375, 6.9603, "Europe/Berlin"),
    ("Frankfurt", "DE", 50.1109, 8.6821, "Europe/Berlin"),
    ("Stuttgart", "DE", 48.7758, 9.1829, "Europe/Berlin"),
    ("Hannover", "DE", 52.3759, 9.732, "Europe/Berlin"),
    ("Praha", "CZ", 50.0755, 14.4378, "Europe/Prague"),
    ("Brno", "CZ", 49.1951, 16.6068, "Europe/Prague"),
    ("Ostrava", "CZ", 49.8209, 18.2625, "Europe/Prague"),
    ("Žilina", "SK", 49.2231, 18.7394, "Europe/Bratislava"),
    ("Bratislava", "SK", 48.1486, 17.1077, "Europe/Bratislava"),
    ("Wien", "AT", 48.2082, 16.3738, "Europe/Vienna"),
    ("Linz", "AT", 48.3069, 14.2858, "Europe/Vienna"),
    ("Budapest", "HU", 47.4979, 19.0402, "Europe/Budapest"),
    ("Győr", "HU", 47.6875, 17.6504, "Europe/Budapest"),
    ("Venlo", "NL", 51.3704, 6.1724, "Europe/Amsterdam"),
    ("Rotterdam", "NL", 51.9244, 4.4777, "Europe/Amsterdam"),
    ("Antwerpen", "BE", 51.2194, 4.4025, "Europe/Brussels"),
    ("Strasbourg", "FR", 48.5734, 7.7521, "Europe/Paris"),
    ("Lyon", "FR", 45.764, 4.8357, "Europe/Paris"),
    ("Verona", "IT", 45.4384, 10.9916, "Europe/Rome"),
    ("Milano", "IT", 45.4642, 9.19, "Europe/Rome"),
    ("Kolding", "DK", 55.4904, 9.4722, "Europe/Copenhagen"),
    # FEAT-010 revision 3: named towns close to the cities above.
    ("Gliwice", "PL", 50.2945, 18.6714, "Europe/Warsaw"),
    ("Tychy", "PL", 50.1218, 18.9872, "Europe/Warsaw"),
    ("Sosnowiec", "PL", 50.2863, 19.1041, "Europe/Warsaw"),
    ("Rybnik", "PL", 50.1022, 18.5463, "Europe/Warsaw"),
    ("Legnica", "PL", 51.207, 16.1619, "Europe/Warsaw"),
    ("Wałbrzych", "PL", 50.7714, 16.2843, "Europe/Warsaw"),
    ("Gniezno", "PL", 52.5348, 17.5826, "Europe/Warsaw"),
    ("Leszno", "PL", 51.842, 16.5749, "Europe/Warsaw"),
    ("Konin", "PL", 52.223, 18.2511, "Europe/Warsaw"),
    ("Piotrków Trybunalski", "PL", 51.4052, 19.703, "Europe/Warsaw"),
    ("Radom", "PL", 51.4027, 21.1471, "Europe/Warsaw"),
    ("Gdynia", "PL", 54.5189, 18.5305, "Europe/Warsaw"),
    ("Chemnitz", "DE", 50.8278, 12.9214, "Europe/Berlin"),
    ("Halle", "DE", 51.497, 11.9688, "Europe/Berlin"),
    ("Potsdam", "DE", 52.3906, 13.0645, "Europe/Berlin"),
    ("Olomouc", "CZ", 49.5938, 17.2509, "Europe/Prague"),
)

# FEAT-010 section 6.2: every named city belongs to exactly one zone (assumption).
NAMED_ZONES: dict[str, tuple[str, ...]] = {
    "PL-SIL": (
        "Katowice",
        "Bielsko-Biała",
        "Częstochowa",
        "Kraków",
        "Gliwice",
        "Tychy",
        "Sosnowiec",
        "Rybnik",
    ),
    "PL-OPW": ("Wrocław", "Opole", "Legnica", "Wałbrzych"),
    "PL-WLK": ("Poznań", "Gniezno", "Leszno", "Konin"),
    "PL-CEN": ("Łódź", "Warszawa", "Piotrków Trybunalski", "Radom"),
    "PL-POM": ("Gdańsk", "Gdynia"),
    "PL-ZPM": ("Szczecin",),
    "PL-PDK": ("Rzeszów",),
    "DE-SAX": ("Dresden", "Leipzig", "Chemnitz", "Halle"),
    "DE-BER": ("Berlin", "Potsdam"),
    "DE-NOR": ("Hamburg", "Hannover"),
    "DE-SOU": ("München", "Nürnberg"),
    "DE-RHM": ("Köln", "Frankfurt"),
    "UPPER-RHINE": ("Stuttgart", "Strasbourg"),
    "BENELUX": ("Venlo", "Rotterdam", "Antwerpen"),
    "CZ-BOH": ("Praha",),
    "MOR-SIL": ("Ostrava", "Žilina", "Olomouc"),
    "DANUBE": ("Brno", "Wien", "Bratislava", "Győr"),
    "AT-LNZ": ("Linz",),
    "HU-BUD": ("Budapest",),
    "IT-NOR": ("Verona", "Milano"),
    "FR-LYO": ("Lyon",),
    "DK": ("Kolding",),
}

# FEAT-010 revision 3: synthetic towns around every named city, so that pickups and deliveries
# can be close together without sharing one point. They are generated, not real places.
TOWNS_PER_CITY = 10
TOWN_DISTANCE_KM = (5.0, 30.0)  # assumption
TOWN_SEED = 20261109
KM_PER_DEGREE = 111.2


def generate_towns(cities: tuple[City, ...] = NAMED_CITIES) -> tuple[City, ...]:
    """`TOWNS_PER_CITY` points per city at a seeded bearing and distance; pure and repeatable."""
    rng = random.Random(TOWN_SEED)  # noqa: S311 — reproducible synthetic simulation, never security tokens.
    towns: list[City] = []
    for name, country, lat, lon, timezone in cities:
        for number in range(1, TOWNS_PER_CITY + 1):
            bearing = math.radians(rng.uniform(0, 360))
            distance = rng.uniform(*TOWN_DISTANCE_KM)
            towns.append(
                (
                    f"{name} area {number:02}",
                    country,
                    round(lat + distance * math.cos(bearing) / KM_PER_DEGREE, 4),
                    round(
                        lon
                        + distance
                        * math.sin(bearing)
                        / (KM_PER_DEGREE * math.cos(math.radians(lat))),
                        4,
                    ),
                    timezone,
                )
            )
    return tuple(towns)


def parent_city(name: str) -> str:
    """The named city a town belongs to (a named city is its own parent)."""
    return name.split(" area ")[0]


CITIES: tuple[City, ...] = NAMED_CITIES + generate_towns()
ZONES: dict[str, tuple[str, ...]] = {
    zone: tuple(city[0] for city in CITIES if parent_city(city[0]) in names)
    for zone, names in NAMED_ZONES.items()
}
COUNTRY_TIMEZONES = {city[1]: city[4] for city in NAMED_CITIES}


def city_document() -> dict[str, object]:
    """The content of data/mock/cities.json."""
    return {
        "version": 1,
        "cities": [
            {"name": name, "countryCode": country, "lat": lat, "lon": lon, "timezone": timezone}
            for name, country, lat, lon, timezone in CITIES
        ],
        "countryTimezones": COUNTRY_TIMEZONES,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.write_text(json.dumps(city_document(), indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
