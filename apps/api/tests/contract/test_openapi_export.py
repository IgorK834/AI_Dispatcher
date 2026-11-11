"""AC-FEAT-000-07: deterministic contract generation and drift detection."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.ac("AC-FEAT-000-07")
def test_export_is_stable_and_detects_drift(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[4]
    output = tmp_path / "openapi.json"
    command = [sys.executable, str(root / "scripts/export_openapi.py"), "--out", str(output)]
    subprocess.run(command, check=True)
    first = output.read_bytes()
    subprocess.run(command, check=True)
    assert output.read_bytes() == first
    subprocess.run([*command, "--check"], check=True)
    output.write_text("{}\n")
    assert subprocess.run([*command, "--check"], check=False).returncode == 1
