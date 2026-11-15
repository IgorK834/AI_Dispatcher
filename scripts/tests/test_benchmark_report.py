"""AC-FEAT-007-07: the metrics report has every metric of FR-8 and is reproducible."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]

# A small engine setting keeps the two runs of this test short; the metrics do not depend on it.
SMALL = ["--runs", "2", "--horizon-days", "1", "--max-offers-per-plan", "2", "--top-k", "3"]

REQUIRED_METRICS = {
    "fleet_profit_minor",
    "fleet_profit_vs_baseline_single",
    "fleet_profit_vs_baseline_greedy",
    "empty_km_share_pct",
    "utilisation_ep_km_pct",
    "utilisation_kg_km_pct",
    "drivers_home_by_pct",
    "nodes",
}


def load() -> ModuleType:
    for path in (ROOT, ROOT / "apps/api"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    spec = importlib.util.spec_from_file_location(
        "benchmark_report", ROOT / "scripts/benchmark_report.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stable_part(text: str) -> str:
    """Everything before the timing section (timings vary between runs and machines)."""
    return text.split("## Timings", 1)[0]


@pytest.mark.integration
@pytest.mark.ac("AC-FEAT-007-07")
def test_two_runs_give_every_metric_with_identical_non_timing_values(tmp_path: Path) -> None:
    module = load()
    first_file, second_file = tmp_path / "first.md", tmp_path / "second.md"
    assert module.main([*SMALL, "--out", str(first_file)]) == 0
    assert module.main([*SMALL, "--out", str(second_file)]) == 0
    first, second = first_file.read_text(), second_file.read_text()

    for heading in (
        "Fleet profit",
        "`baseline_single`",
        "`baseline_greedy`",
        "Empty kilometres",
        "EP·km",
        "kg·km",
        "home before `home_by`",
        "Search nodes",
        "## Timings",
        "p50",
        "p95",
    ):
        assert heading in first, heading
    assert stable_part(first) == stable_part(second)


@pytest.mark.integration
@pytest.mark.ac("AC-FEAT-007-07")
def test_the_fleet_profit_is_at_least_both_baselines_and_the_metrics_are_complete() -> None:
    module = load()
    config = module.parse_args(SMALL)
    metrics = module.compute_metrics(config)
    assert REQUIRED_METRICS <= set(metrics)
    profit = metrics["fleet_profit_minor"]
    assert profit["profit"] >= profit["baseline_single"]
    assert profit["profit"] >= profit["baseline_greedy"]
    assert metrics == module.compute_metrics(config)  # nothing in it depends on time or luck
    for key in ("empty_km_share_pct", "utilisation_ep_km_pct", "utilisation_kg_km_pct"):
        assert 0 <= metrics[key] <= 100
    assert 0 <= metrics["drivers_home_by_pct"] <= 100


@pytest.mark.integration
@pytest.mark.ac("AC-FEAT-007-07")
def test_agents_fake_adds_the_time_from_question_to_approval(tmp_path: Path) -> None:
    module = load()
    out = tmp_path / "metrics.md"
    assert module.main([*SMALL, "--agents-fake", "--out", str(out)]) == 0
    assert "Question to `approval_required`" in out.read_text()


def fixture_block(**changes: object) -> dict:
    return {
        "load_factor_ep": "0.4600",
        "load_factor_kg": "0.4000",
        "load_factor_ep_loaded": "0.7600",
        "load_factor_kg_loaded": "0.6700",
        "plans": 14,
        "plans_with_2plus_on_board": 7,
        "empty_km_share": "0.1100",
        "partner_share": "0.1860",
        **changes,
    }


@pytest.mark.ac("AC-FEAT-010-14")
def test_consolidation_table_and_target_lines_say_met_or_not_met_without_failing() -> None:
    module = load()
    text = "\n".join(module.consolidation_lines(fixture_block()))
    assert "46.0 %" in text and "40.0 %" in text and "7 of 14" in text and "18.6 %" in text
    assert "76.0 %" in text and "67.0 %" in text  # fill on loaded kilometres only
    assert "Target A, partner share >= 50%: not met" in text
    assert "Target B, pallet fill >= 60% and >= 70% of plans" in text and ": not met (" in text

    good = fixture_block(
        load_factor_ep="0.6400", plans_with_2plus_on_board=12, partner_share="0.7000"
    )
    text = "\n".join(module.consolidation_lines(good))
    assert "Target A, partner share >= 50%: met" in text
    assert ": met (64.0 %, 85.7 %)" in text

    # A benchmark summary adds the 20-seed row and decides target B on it.
    bench = {
        **fixture_block(load_factor_ep="0.6100", plans=100, plans_with_2plus_on_board=71),
        "runs": 20,
    }
    text = "\n".join(module.consolidation_lines(good, bench))
    assert "Over 20 benchmark seeds" in text and "71 of 100 plans" in text
    assert "(20 benchmark seeds): met (61.0 %, 71.0 %)" in text


@pytest.mark.integration
@pytest.mark.ac("AC-FEAT-010-14")
def test_report_has_the_consolidation_table_and_it_is_the_same_in_two_runs(tmp_path: Path) -> None:
    module = load()
    first_file, second_file = tmp_path / "first.md", tmp_path / "second.md"
    assert module.main([*SMALL, "--out", str(first_file)]) == 0
    assert module.main([*SMALL, "--out", str(second_file)]) == 0
    first = first_file.read_text()
    section = first.split("## Consolidation", 1)[1].split("## Timings", 1)[0]
    for heading in (
        "Van fill, pallet places",
        "Van fill, payload",
        "2 or more orders on board",
        "Empty kilometres",
        "partner share",
        "Target A",
        "Target B",
    ):
        assert heading in section, heading
    assert stable_part(first) == stable_part(second_file.read_text())


@pytest.mark.integration
@pytest.mark.ac("AC-FEAT-010-14")
def test_benchmark_runs_carry_the_consolidation_block_and_the_summary_aggregates_it() -> None:
    load()  # puts the repository root on the path
    from bench.fleet_5x60 import (
        REFERENCE_DATE,
        SEEDS,
        build_instance,
        consolidation_block,
        consolidation_summary,
    )

    from routepilot.freight.generator import generate_offers
    from routepilot.optimization.engine import optimize

    blocks = []
    for seed in SEEDS[:2]:
        source = build_instance(seed, fallback_parameters=True)
        params = source.params.model_copy(
            update={"horizon_days": 1, "max_offers_per_plan": 2, "top_k_per_driver": 2}
        )
        source = source.model_copy(update={"params": params})
        blocks.append(
            consolidation_block(
                source, optimize(source), generate_offers(seed, REFERENCE_DATE)[0]["payload"]
            )
        )
    for block in blocks:
        assert {
            "load_factor_ep",
            "load_factor_kg",
            "load_factor_ep_loaded",
            "load_factor_kg_loaded",
            "plans",
            "plans_with_2plus_on_board",
            "empty_km_share",
            "partner_share",
        } <= set(block)
        assert 0 <= float(block["load_factor_ep"]) <= 1 and 0 <= float(block["load_factor_kg"]) <= 1
        # Excluding the empty legs can only raise the fill.
        assert float(block["load_factor_ep_loaded"]) >= float(block["load_factor_ep"])
        assert block["plans_with_2plus_on_board"] <= block["plans"]
    summary = consolidation_summary(blocks)
    assert summary["plans"] == sum(b["plans"] for b in blocks)
    assert summary["plans_with_2plus_on_board"] == sum(
        b["plans_with_2plus_on_board"] for b in blocks
    )
