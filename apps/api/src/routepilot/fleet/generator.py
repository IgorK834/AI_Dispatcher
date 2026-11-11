"""Deterministic synthetic fleet generator (FEAT-002 FR-3 through FR-6)."""

import argparse
import json
import random
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

# Approved FEAT-002 section 6.2 demo parameters, never measured fleet data.
BASES: tuple[tuple[str, float, float, int, str, list[float | None], int, bool], ...] = (
    ("Katowice", 50.2649, 19.0238, 10, "EUR_MIXED_6X4", [4.85, 2.10, 2.10], 1085, False),
    ("Wrocław", 51.1079, 17.0385, 10, "EUR_MIXED_6X4", [4.85, 2.10, 2.10], 1050, True),
    ("Poznań", 52.4064, 16.9252, 9, "DECLARED_ONLY", [None, None, None], 1000, False),
    ("Łódź", 51.7592, 19.4560, 8, "EUR_MIXED_5X3", [4.20, 2.10, 2.30], 880, False),
    ("Kraków", 50.0647, 19.9450, 8, "EUR_MIXED_5X3", [4.20, 2.10, 2.15], 765, False),
)
FICTIONAL_NAMES = ("Aster Vellin", "Beryl Quorin", "Cedar Luvin", "Dahlia Merovin", "Elm Tavrin")


def default_cost_profile() -> dict[str, Any]:
    return {
        "name": "DEMO-DEFAULT",
        "currency": "EUR",
        "fuel_price_minor_per_l": 181,
        "driver_cost_minor_per_hour": 1400,
        "vehicle_cost_minor_per_km": 12,
        "accommodation_minor": 5500,
        "per_diem": {"PL": 1059},
        "tolls": {
            "per_km": {"PL": 0, "DE": 0, "FR": 12, "IT": 12},
            "annual_vignettes": ["AT", "CZ", "SK", "HU"],
        },
        "fx_rates": {"PLN": "4.25"},
        "min_profit_minor": 0,
        "min_margin_pct": "0",
        "provenance": {
            "fuel_price_minor_per_l": "source",
            "driver_cost_minor_per_hour": "assumption",
            "vehicle_cost_minor_per_km": "assumption",
            "accommodation_minor": "assumption",
            "per_diem": "source",
            "tolls.PL": "source",
            "tolls.DE": "source",
            "tolls.FR": "assumption",
            "tolls.IT": "assumption",
            "tolls.annual_vignettes": "assumption",
            "fx_rates": "assumption",
            "min_profit_minor": "assumption",
            "min_margin_pct": "assumption",
        },
        "is_synthetic": True,
    }


def generate_fleet(seed: int, reference_date: date) -> dict[str, Any]:
    rng = random.Random(seed)  # noqa: S311 — reproducible synthetic data, never security tokens.
    drivers, vehicles, states = [], [], []
    midnight = datetime.combine(reference_date, time(), UTC)
    days_to_friday = 4 - reference_date.weekday()
    if reference_date.weekday() >= 4:
        days_to_friday += 7
    home_by = datetime.combine(
        reference_date + timedelta(days=days_to_friday), time(18), ZoneInfo("Europe/Warsaw")
    ).astimezone(UTC)
    for index, (city, lat, lon, places, layout, dimensions, payload, sleeper) in enumerate(
        BASES, 1
    ):
        driver_id, vehicle_id = f"MOCK-D{index}", f"MOCK-V{index}"
        drivers.append(
            {
                "id": driver_id,
                "name": FICTIONAL_NAMES[index - 1],
                "phone": f"+00-000-000-{index:03}",
                "home_city": city,
                "home_country": "PL",
                "home_lat": lat,
                "home_lon": lon,
                "default_rules_profile": "pl_domestic_employee_v1",
                "vehicle_id": vehicle_id,
                "is_synthetic": True,
            }
        )
        vehicles.append(
            {
                "id": vehicle_id,
                "label": f"BUS-{index:02}",
                "vehicle_type": "VEHICLE_UP_TO_3_5_T",
                "body_type": "CURTAIN_SIDER",
                "inner_length_m": dimensions[0],
                "inner_width_m": dimensions[1],
                "inner_height_m": dimensions[2],
                "pallet_places": places,
                "layout_template": layout,
                "side_access": "BOTH",
                "payload_kg": payload,
                "gvw_kg": 3500,
                "sleeper_cab": sleeper,
                "fuel": {
                    "l_per_100km_empty_at90": "11.0",
                    "l_per_100km_full_at90": "13.0",
                    "speed_curve": "VAN_DEFAULT_V1",
                    "provenance": "assumption",
                },
                "cost_profile": "DEMO-DEFAULT",
                "is_synthetic": True,
            }
        )
        available = midnight + timedelta(minutes=15 * rng.randrange(97))
        position = rng.choice(BASES)
        work_week = rng.randint(0, 2160)
        states.append(
            {
                "id": f"MOCK-S{index}",
                "driver_id": driver_id,
                "current_city": position[0],
                "current_lat": position[1],
                "current_lon": position[2],
                "available_from": available.isoformat(),
                "work_today_min": 0,
                "drive_today_min": 0,
                "work_since_break_min": 0,
                "drive_since_break_min": 0,
                "work_week_min": work_week,
                "drive_week_min": rng.randint(0, min(work_week, 2016)),
                "drive_prev_week_min": rng.randint(0, 2700),
                "last_daily_rest_end": available.isoformat(),
                "last_weekly_rest_end": (available - timedelta(days=2)).isoformat(),
                "home_by": home_by.isoformat(),
                "source": "generated_mock",
                "is_synthetic": True,
            }
        )
    return {
        "version": 1,
        "seed": seed,
        "reference_date": reference_date.isoformat(),
        "is_synthetic": True,
        "cost_profile": default_cost_profile(),
        "drivers": drivers,
        "vehicles": vehicles,
        "driver_states": states,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--reference-date", type=date.fromisoformat, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            generate_fleet(args.seed, args.reference_date),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
