"""GOLD-CP-1 copied from specs/golden/README.md conventions G9-G11."""

from routepilot.optimization.engine.models import CostProfile


def gold_cp_1() -> CostProfile:
    return CostProfile(
        id="GOLD-CP-1",
        currency="EUR",
        fuel_price_minor_per_l=181,
        driver_cost_minor_per_hour=1400,
        vehicle_cost_minor_per_km=12,
        accommodation_minor=5500,
        per_diem={"PL": 1059},
        toll_per_km={"FR": 12},
        fx_rates={"PLN": "4.25"},
        provenance={
            "fuel_price_minor_per_l": "source",
            "driver_cost_minor_per_hour": "assumption",
            "vehicle_cost_minor_per_km": "assumption",
            "accommodation_minor": "assumption",
            "toll_per_km.FR": "assumption",
        },
    )
