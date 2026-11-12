"""FEAT-003 AC-29: seeded synthetic fleet benchmark; no database or provider calls."""

from __future__ import annotations

import argparse
import json
import platform
from datetime import UTC, date, datetime, time
from pathlib import Path
from statistics import median, quantiles
from time import perf_counter
from typing import Any

from routepilot.compliance.models import DriverState
from routepilot.fleet.generator import generate_fleet
from routepilot.freight.domain.models import NormalizedOffer, RawOfferRecord
from routepilot.freight.generator import generate_offers
from routepilot.integrations.timocom.mapper import TimocomV3Mapper
from routepilot.optimization.engine import optimize
from routepilot.optimization.engine.models import (
    CostProfile,
    DriverSnapshot,
    EngineParams,
    EngineSnapshot,
    OfferSnapshot,
    Point,
    Stop,
    TravelMatrix,
    VehicleSnapshot,
)
from routepilot.optimization.engine.prefilter import offer_pool
from routepilot.routing.domain import GeoPoint
from routepilot.routing.haversine import HaversineRoutingProvider

REFERENCE_DATE = date(2026, 11, 16)
SEEDS = tuple(range(20261116, 20261136))


def build_instance(seed: int, *, fallback_parameters: bool = False) -> EngineSnapshot:
    """Adapt the production generators/mapper, retaining their difficult and missing-data cases."""
    fleet = generate_fleet(seed, REFERENCE_DATE)
    payload, enrichment = generate_offers(seed, REFERENCE_DATE)
    reference = datetime.combine(REFERENCE_DATE, time(), UTC)
    mapper = TimocomV3Mapper()
    points: dict[str, Point] = {}

    def point(
        city: str,
        country: str | None,
        lat: float | None,
        lon: float | None,
        zone: str = "Europe/Warsaw",
    ) -> Point:
        key = f"{country}:{city}:{lat}:{lon}"
        value = Point(key=key, city=city, country=country, lat=lat, lon=lon, timezone=zone)
        if lat is not None and lon is not None:
            points[key] = value
        return value

    raw_cost = fleet["cost_profile"]
    cost = CostProfile(
        **{
            key: value
            for key, value in raw_cost.items()
            if key not in ("name", "is_synthetic", "tolls")
        },
        toll_per_km=raw_cost["tolls"]["per_km"],
        annual_vignettes=raw_cost["tolls"]["annual_vignettes"],
    )
    vehicles = {v["id"]: v for v in fleet["vehicles"]}
    states = {s["driver_id"]: s for s in fleet["driver_states"]}
    drivers = []
    for d in fleet["drivers"]:
        v, s = vehicles[d["vehicle_id"]], states[d["id"]]
        home = point(d["home_city"], d["home_country"], d["home_lat"], d["home_lon"])
        position = point(s["current_city"], "PL", s["current_lat"], s["current_lon"])
        available = datetime.fromisoformat(s["available_from"])
        drivers.append(
            DriverSnapshot(
                id=d["id"],
                home=home,
                position=position,
                available_from=available,
                home_by=datetime.fromisoformat(s["home_by"]),
                cost_profile=cost,
                vehicle=VehicleSnapshot(
                    id=v["id"],
                    vehicle_type=v["vehicle_type"],
                    body_type=v["body_type"],
                    pallet_places=v["pallet_places"],
                    payload_kg=v["payload_kg"],
                    inner_length_m=v["inner_length_m"],
                    inner_height_m=v["inner_height_m"],
                    sleeper_cab=v["sleeper_cab"],
                ),
                rules_state=DriverState(
                    t=available,
                    work_week=s["work_week_min"],
                    drive_week=s["drive_week_min"],
                    drive_prev_week=s["drive_prev_week_min"],
                ),
            )
        )
    offers = []
    for raw in payload["payload"]:
        mapped = mapper.to_domain(
            RawOfferRecord(
                source="mock_timocom_v3",
                source_offer_id=raw["id"],
                payload=raw,
                fetched_at=reference,
                enrichment=enrichment[raw["id"]],
            )
        )
        if not isinstance(mapped, NormalizedOffer):
            raise TypeError(f"generated offer did not normalize: {raw['id']}")
        stops = [
            Stop(
                point=point(s.city, s.country_code, s.lat, s.lon, s.timezone),
                window_start=s.window_start,
                window_end=s.window_end,
                service_min=s.service_minutes,
                service_provenance=s.provenance.get("serviceMinutes", "default"),
            )
            for s in mapped.stops
        ]
        offers.append(
            OfferSnapshot(
                id=mapped.source_offer_id,
                source_offer_id=mapped.source_offer_id,
                weight_kg=mapped.weight_kg,
                pallet_count=mapped.pallet_count,
                pallet_type=mapped.pallet_type,
                pallet_provenance=mapped.field_provenance.get("palletCount", "source"),
                loading_length_m=mapped.loading_length_m,
                revenue_minor=mapped.revenue.amount_minor if mapped.revenue else None,
                revenue_currency=mapped.revenue.currency if mapped.revenue else "EUR",
                required_vehicle_types=mapped.required_vehicle_types,
                required_body_types=mapped.required_body_types,
                required_equipment=mapped.required_equipment,
                stops=(stops[0], stops[1]),
                warnings=mapped.quality_flags,
            )
        )
    ordered = [points[key] for key in sorted(points)]
    matrix = HaversineRoutingProvider().matrix([GeoPoint(lat=p.lat, lon=p.lon) for p in ordered])
    params = EngineParams()
    if fallback_parameters:
        params = params.model_copy(
            update={"max_offers_per_plan": 4, "horizon_days": 3, "top_k_per_driver": 5}
        )
    return EngineSnapshot(
        reference_time=reference,
        drivers=drivers,
        offers=offers,
        params=params,
        matrix=TravelMatrix(
            points=ordered,
            distance_km=matrix.distance_km,
            duration_min=matrix.duration_min,
            provider_id=matrix.provider_id,
            fallback=matrix.fallback,
        ),
    )


def run(seeds: tuple[int, ...], *, fallback_parameters: bool = False) -> dict[str, Any]:
    runs = []
    for seed in seeds:
        source = build_instance(seed, fallback_parameters=fallback_parameters)
        pools = {d.id: len(offer_pool(source, d)[0]) for d in source.drivers}
        start = perf_counter()
        result = optimize(
            source, elapsed_ms=lambda started=start: int((perf_counter() - started) * 1000)
        )
        elapsed = (perf_counter() - start) * 1000
        row = dict(
            seed=seed,
            runtime_ms=round(elapsed, 3),
            nodes=result.stats.nodes,
            truncated=result.stats.truncated,
            pool_truncated=result.stats.pool_truncated,
            pool_sizes=pools,
            plans=sum(len(g["profit"]) for g in result.per_driver.values()),
            fleet_profit_minor=result.fleet["profit"].totals.net_profit_minor,
        )
        print(json.dumps(row, sort_keys=True), flush=True)
        runs.append(row)
    runtimes = [row["runtime_ms"] for row in runs]
    p95 = quantiles(runtimes, n=20, method="inclusive")[18] if len(runtimes) > 1 else runtimes[0]
    summary = dict(
        count=len(runs),
        p50_ms=round(median(runtimes), 3),
        p95_ms=round(p95, 3),
        target_p95_ms=15000,
        target_met=p95 <= 15000,
        truncated_runs=sum(row["truncated"] for row in runs),
    )
    print(json.dumps(summary, sort_keys=True), flush=True)
    return dict(
        reference_date=REFERENCE_DATE.isoformat(),
        is_synthetic=True,
        generated_at=datetime.now(UTC).isoformat(),
        python=platform.python_version(),
        system=platform.system(),
        machine=platform.machine(),
        parameters=source.params.model_dump(mode="json"),
        generator="generate_fleet + generate_offers(150) + TimocomV3Mapper; max pool 60 per driver",
        runs=runs,
        summary=summary,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, choices=range(1, 21), default=20)
    parser.add_argument("--fallback-parameters", action="store_true")
    parser.add_argument("--out", type=Path, default=Path("bench/results/fleet_5x60.json"))
    args = parser.parse_args()
    result = run(SEEDS[: args.runs], fallback_parameters=args.fallback_parameters)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
