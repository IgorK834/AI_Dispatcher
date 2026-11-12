"""`make seed-fleet` wraps the generator CLIs and reproduces the committed files (FR-28)."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
MOCK = ROOT / "data/mock"


def make(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            shutil.which("make") or "make",
            "-C",
            str(ROOT),
            "seed-fleet",
            f"FLEET_OUT={tmp_path / 'fleet.json'}",
            f"OFFERS_OUT={tmp_path / 'offers.timocom.json'}",
            f"ENRICHMENT_OUT={tmp_path / 'offers.enrichment.json'}",
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.ac("AC-FEAT-002-01")
@pytest.mark.ac("AC-FEAT-002-04")
def test_seed_fleet_reproduces_the_committed_files_byte_for_byte(tmp_path: Path) -> None:
    result = make(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "not available" not in result.stdout
    for name in ("fleet.json", "offers.timocom.json", "offers.enrichment.json"):
        assert (tmp_path / name).read_bytes() == (MOCK / name).read_bytes(), name


@pytest.mark.ac("AC-FEAT-002-01")
def test_seed_fleet_passes_the_documented_seed_and_reference_date(tmp_path: Path) -> None:
    dry = make(tmp_path, "-n")
    commands = dry.stdout
    assert dry.returncode == 0 and commands.count("--seed 20261109") == 2
    assert commands.count("--reference-date 2026-11-16") == 2
    assert "routepilot.fleet.generator" in commands and "routepilot.freight.generator" in commands
    other = make(tmp_path, "SEED=7", "REFERENCE_DATE=2026-12-01", "-n").stdout
    assert other.count("--seed 7") == 2 and other.count("--reference-date 2026-12-01") == 2
