"""Metrics report of FEAT-007 (FR-8, AC-FEAT-007-07): every result number the README may quote.

Run from `apps/api` (it needs the API's virtual environment):

    uv run python ../../scripts/benchmark_report.py [--agents-fake] [--runs 20] [--out FILE]

The default output is `docs/metrics.md`.

The instance is the seeded demo data (fixed seed and reference date, synthetic). The result
metrics come from one engine run without a wall-clock cut-off, so they only depend on the data and
the settings: two runs give the same values. Timings are measured on the running machine and are
reported, never compared.
"""

import argparse
import platform
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from statistics import median, quantiles
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "docs" / "metrics.md"
DEMO_SEED = 20261109  # the seed of the committed demo data (Makefile: SEED)
TARGET_P95_MS = 15000  # NFR-002
# FEAT-010 section 5: recorded as met or not met, never asserted.
TARGET_PARTNER_SHARE = Decimal("0.50")  # target A
TARGET_LOAD_FACTOR_EP = Decimal("0.60")  # target B, km-weighted
TARGET_PLANS_2PLUS = Decimal("0.70")  # target B, share of plans


@dataclass(frozen=True)
class Config:
    seed: int
    runs: int
    horizon_days: int
    max_offers_per_plan: int
    top_k: int
    agents_fake: bool = False
    out: Path = DEFAULT_OUT
    bench_json: Path | None = None


def parse_args(argv: list[str]) -> Config:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--seed", type=int, default=DEMO_SEED)
    parser.add_argument("--runs", type=int, default=20, help="timed engine runs (FR-8: 20)")
    parser.add_argument("--horizon-days", type=int, default=5)
    parser.add_argument("--max-offers-per-plan", type=int, default=3)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--agents-fake", action="store_true", help="also time question -> approval")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--bench-json",
        type=Path,
        help="result file of bench/fleet_5x60.py: adds the 20-seed consolidation row (FEAT-010)",
    )
    args = parser.parse_args(argv)
    return Config(
        seed=args.seed,
        runs=args.runs,
        horizon_days=args.horizon_days,
        max_offers_per_plan=args.max_offers_per_plan,
        top_k=args.top_k,
        agents_fake=args.agents_fake,
        out=args.out,
        bench_json=args.bench_json,
    )


def instance(config: Config) -> Any:
    """The demo-data engine instance (the benchmark's builder) with the chosen engine settings."""
    for path in (ROOT, ROOT / "apps" / "api"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from bench.fleet_5x60 import build_instance

    source = build_instance(config.seed)
    params = source.params.model_copy(
        update={
            "horizon_days": config.horizon_days,
            "max_offers_per_plan": config.max_offers_per_plan,
            "top_k_per_driver": config.top_k,
        }
    )
    return source.model_copy(update={"params": params})


def share(part: Decimal | int, whole: Decimal | int) -> float:
    return round(float(Decimal(part) * 100 / Decimal(whole)), 1) if whole else 0.0


def compute_metrics(config: Config) -> dict[str, Any]:
    """The non-timing metrics of FR-8 from one engine run without a wall-clock cut-off."""
    source = instance(config)  # also puts the repository on the import path
    from bench.fleet_5x60 import REFERENCE_DATE, consolidation_block

    from routepilot.freight.generator import generate_offers
    from routepilot.optimization.engine import optimize

    result = optimize(source)  # no `elapsed_ms`: the search stops by its node budget only
    offers = generate_offers(config.seed, REFERENCE_DATE)[0]["payload"]
    plans = {
        plan.plan_ref: plan
        for plan in [
            *(p for groups in result.per_driver.values() for g in groups.values() for p in g),
            *result.fleet_candidates,
            *result.baseline_plans,
        ]
    }
    vehicles = {driver.id: driver.vehicle for driver in source.drivers}
    chosen = [plans[a.plan_ref] for a in result.fleet["profit"].assignments]

    distance = sum((p.distance_km for p in chosen), Decimal(0))
    empty = sum((p.empty_km for p in chosen), Decimal(0))
    ep_used = ep_available = kg_used = kg_available = Decimal(0)
    for plan in chosen:
        vehicle = vehicles[plan.driver_id]
        for leg in plan.legs:
            ep_used += leg.distance_km * leg.load_pallet_eq
            ep_available += leg.distance_km * vehicle.pallet_places
            kg_used += leg.distance_km * leg.load_kg
            kg_available += leg.distance_km * vehicle.payload_kg

    profit = {
        "profit": result.fleet["profit"].totals.net_profit_minor,
        "baseline_single": result.baselines["baseline_single"].totals.net_profit_minor,
        "baseline_greedy": result.baselines["baseline_greedy"].totals.net_profit_minor,
    }

    def against(name: str) -> dict[str, Any]:
        base = profit[name]
        return {
            "absolute_minor": profit["profit"] - base,
            "pct": round((profit["profit"] - base) * 100 / abs(base), 1) if base else None,
        }

    return {
        "drivers": len(source.drivers),
        "offers": len(source.offers),
        "fleet_profit_minor": profit,
        "fleet_profit_vs_baseline_single": against("baseline_single"),
        "fleet_profit_vs_baseline_greedy": against("baseline_greedy"),
        "drivers_with_plan": len(chosen),
        "empty_km_share_pct": share(empty, distance),
        "utilisation_ep_km_pct": share(ep_used, ep_available),
        "utilisation_kg_km_pct": share(kg_used, kg_available),
        "drivers_home_by_pct": share(sum(p.home_reached for p in chosen), len(chosen)),
        "nodes": result.stats.nodes,
        "search_truncated": result.stats.truncated,
        "consolidation": consolidation_block(source, result, offers),
    }


def percentile_95(values: list[float]) -> float:
    return quantiles(values, n=20, method="inclusive")[18] if len(values) > 1 else values[0]


def compute_timings(config: Config) -> dict[str, Any]:
    """Engine runtime as the product runs it (with the 30 s wall-clock safety) over N runs."""
    from routepilot.optimization.engine import optimize

    source = instance(config)
    runtimes: list[float] = []
    truncated = 0
    for _ in range(config.runs):
        start = time.perf_counter()
        result = optimize(source, elapsed_ms=lambda s=start: int((time.perf_counter() - s) * 1000))
        runtimes.append((time.perf_counter() - start) * 1000)
        truncated += result.stats.truncated
    timings: dict[str, Any] = {
        "runs": config.runs,
        "p50_ms": round(median(runtimes)),
        "p95_ms": round(percentile_95(runtimes)),
        "cut_by_wall_clock": truncated,
    }
    if config.agents_fake:
        timings["question_to_approval_s"] = round(agent_seconds(), 2)
    return timings


def agent_seconds(repeats: int = 3) -> float:
    """Median time from the question to `approval_required` on the scripted fake model."""
    for path in (ROOT, ROOT / "apps" / "api"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from tests.agents.live_app import serve

    seconds = []
    for _ in range(repeats):  # the scripted model plays its script once per application
        with tempfile.TemporaryDirectory() as folder:
            with serve(Path(folder), scenario_id="approval-driver") as live:
                live.sign_in_as("dispatcher")
                start = time.monotonic()
                _, run_id = live.start_run()
                live.wait_for(run_id, {"waiting_approval"})
                seconds.append(time.monotonic() - start)
    return median(seconds)


def euros(minor: int) -> str:
    return f"EUR {Decimal(minor) / 100:,.2f}"


def signed(item: dict[str, Any]) -> str:
    pct = "n/a" if item["pct"] is None else f"{item['pct']:+.1f} %"
    return f"{euros(item['absolute_minor'])} ({pct})"


def table(rows: list[tuple[str, str]]) -> list[str]:
    return ["| Metric | Value |", "|---|---|", *(f"| {name} | {value} |" for name, value in rows)]


def pct(value: str | Decimal) -> str:
    return f"{Decimal(value) * 100:.1f} %"


def verdict(met: bool) -> str:
    return "met" if met else "not met"


def consolidation_lines(block: dict[str, Any], bench: dict[str, Any] | None = None) -> list[str]:
    """The "Consolidation" table and the target lines (FEAT-010 FR-14); targets are not asserted."""
    plans = f"{block['plans_with_2plus_on_board']} of {block['plans']}"
    share_of_plans = (
        Decimal(block["plans_with_2plus_on_board"]) / block["plans"]
        if block["plans"]
        else Decimal(0)
    )
    rows = [
        ("Van fill, pallet places (EP·km), km-weighted", pct(block["load_factor_ep"])),
        ("Van fill, payload (kg·km), km-weighted", pct(block["load_factor_kg"])),
        ("Plans with 2 or more orders on board at once", plans),
        ("Empty kilometres, share of all kilometres", pct(block["empty_km_share"])),
        ("Offers with a consolidation partner (partner share)", pct(block["partner_share"])),
    ]
    lines = [*table(rows), ""]
    lines.append(
        f"Target A, partner share >= {TARGET_PARTNER_SHARE:.0%}: "
        f"{verdict(Decimal(block['partner_share']) >= TARGET_PARTNER_SHARE)}"
        f" ({pct(block['partner_share'])})."
    )
    scope = "this demo run"
    if bench is not None:
        block, scope = bench, f"{bench['runs']} benchmark seeds"
        share_of_plans = (
            Decimal(block["plans_with_2plus_on_board"]) / block["plans"]
            if block["plans"]
            else Decimal(0)
        )
        lines.insert(
            1,
            f"Over {scope}: van fill {pct(block['load_factor_ep'])} of pallet places and "
            f"{pct(block['load_factor_kg'])} of payload; {block['plans_with_2plus_on_board']} of "
            f"{block['plans']} plans carry 2 or more orders at once.",
        )
    both = (
        Decimal(block["load_factor_ep"]) >= TARGET_LOAD_FACTOR_EP
        and share_of_plans >= TARGET_PLANS_2PLUS
    )
    lines.append(
        f"Target B, pallet fill >= {TARGET_LOAD_FACTOR_EP:.0%} and >= {TARGET_PLANS_2PLUS:.0%} "
        f"of plans with 2 or more orders on board ({scope}): {verdict(both)} "
        f"({pct(block['load_factor_ep'])}, {pct(share_of_plans)})."
    )
    return lines


def load_bench_summary(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    import json

    stored = json.loads(path.read_text())
    return {**stored["summary"]["consolidation"], "runs": stored["summary"]["count"]}


def render(config: Config, metrics: dict[str, Any], timings: dict[str, Any]) -> str:
    from routepilot.optimization.engine.models import EngineParams

    defaults = EngineParams()
    profit = metrics["fleet_profit_minor"]
    runs, p95_s = timings["runs"], timings["p95_ms"] / 1000
    met = "MET" if timings["p95_ms"] <= TARGET_P95_MS else "NOT MET"
    results = [
        ("Fleet profit, `profit` solution", euros(profit["profit"])),
        ("Fleet profit, `baseline_single`", euros(profit["baseline_single"])),
        ("Fleet profit, `baseline_greedy`", euros(profit["baseline_greedy"])),
        ("`profit` against `baseline_single`", signed(metrics["fleet_profit_vs_baseline_single"])),
        ("`profit` against `baseline_greedy`", signed(metrics["fleet_profit_vs_baseline_greedy"])),
        ("Drivers with a plan", f"{metrics['drivers_with_plan']} of {metrics['drivers']}"),
        ("Empty kilometres, share of all kilometres", f"{metrics['empty_km_share_pct']:.1f} %"),
        ("Capacity use, EP·km over available EP·km", f"{metrics['utilisation_ep_km_pct']:.1f} %"),
        ("Capacity use, kg·km over available kg·km", f"{metrics['utilisation_kg_km_pct']:.1f} %"),
        (
            "Drivers with a plan who are home before `home_by`",
            f"{metrics['drivers_home_by_pct']:.1f} %",
        ),
        ("Search nodes", str(metrics["nodes"])),
        ("Search stopped by the node budget", "yes" if metrics["search_truncated"] else "no"),
    ]
    timed = [
        (f"Engine runtime p50 over {runs} runs", f"{timings['p50_ms'] / 1000:.1f} s"),
        (f"Engine runtime p95 over {runs} runs", f"{p95_s:.1f} s"),
        ("Runs cut by the 30 s wall-clock safety", f"{timings['cut_by_wall_clock']} of {runs}"),
        (f"NFR-002 target p95 <= {TARGET_P95_MS // 1000} s", f"{met} (p95 = {p95_s:.1f} s)"),
    ]
    if "question_to_approval_s" in timings:
        timed.append(
            (
                "Question to `approval_required` (scripted fake model)",
                f"{timings['question_to_approval_s']:.2f} s",
            )
        )
    stamp = f"{datetime.now(UTC):%Y-%m-%d %H:%M} UTC on {platform.system()} {platform.machine()}"
    lines = [
        "# Metrics",
        "",
        "Generated by `scripts/benchmark_report.py`; do not edit by hand. Every result number that",
        "the README quotes comes from this file. The data is synthetic (`is_synthetic = true`).",
        "",
        "## Instance and settings",
        "",
        f"- Demo data: seed `{config.seed}`, reference date `2026-11-16`,"
        f" {metrics['drivers']} drivers, {metrics['offers']} synthetic offers",
        "  (the generators of the committed demo data).",
        f"- Engine settings: horizon {config.horizon_days} days, at most"
        f" {config.max_offers_per_plan} offers per plan,",
        f"  top {config.top_k} plans per driver. Other parameters are the engine defaults.",
        f"  The defaults for the first three are {defaults.horizon_days} days,"
        f" {defaults.max_offers_per_plan} offers and {defaults.top_k_per_driver} plans;",
        "  fewer offers and plans per driver keep 20 timed runs under ten minutes.",
        "- Distances and times use the haversine fallback provider (estimates, not road routing).",
        "",
        "## Results (identical between runs)",
        "",
        "Measured on the `profit` fleet solution of one engine run without a wall-clock cut-off.",
        "",
        *table(results),
        "",
        "Definitions: empty kilometres are the legs without load; EP·km and kg·km sum, over every",
        "leg of the chosen plans, the leg distance times the load (euro-pallet equivalents or kg)",
        "and are divided by the distance times the vehicle's capacity (pallet places or payload).",
        "The engine plans the way home only when `home_by` lies inside the planning horizon and",
        "then ends the plan at the home base on time; with a shorter horizon no plan returns home.",
        "",
        "## Consolidation (identical between runs)",
        "",
        "How full the vans of the `profit` fleet solution are and how many orders they carry at",
        "once (FEAT-010). The targets are recorded as met or not met and are never asserted.",
        "",
        *consolidation_lines(metrics["consolidation"], load_bench_summary(config.bench_json)),
        "",
        "## Timings (vary between machines)",
        "",
        f"Measured at {stamp}, Python {platform.python_version()}.",
        "Timings are reported, not asserted.",
        "",
        *table(timed),
        "",
        "The NFR-002 target (p95 <= 15 s) is set for the engine defaults. This report uses reduced",
        "settings (see above), so the target line is an indication, not a verdict on NFR-002.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    config = parse_args(argv)
    metrics = compute_metrics(config)
    timings = compute_timings(config)
    config.out.parent.mkdir(parents=True, exist_ok=True)
    config.out.write_text(render(config, metrics, timings))
    print(f"wrote {config.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
