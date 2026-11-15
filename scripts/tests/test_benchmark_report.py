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
