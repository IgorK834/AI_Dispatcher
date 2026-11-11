"""AC-FEAT-000-11: architectural contracts reject forbidden imports."""

import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest


@pytest.mark.ac("AC-FEAT-000-11")
def test_boundary_contracts_and_deliberate_violation(tmp_path: Path) -> None:
    api = Path(__file__).resolve().parents[2]
    config = tomllib.loads((api / "pyproject.toml").read_text())
    contracts = config["tool"]["importlinter"]["contracts"]
    covered = {module for item in contracts for module in item.get("source_modules", [])}
    assert {
        "routepilot.shared",
        "routepilot.identity",
        "routepilot.fleet",
        "routepilot.freight",
        "routepilot.routing",
        "routepilot.compliance",
        "routepilot.optimization.engine",
        "routepilot.optimization.jobs",
        "routepilot.agents",
        "routepilot.integrations",
    } <= covered
    shutil.copytree(
        api / "src/routepilot",
        tmp_path / "routepilot",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    shutil.copy(api / "pyproject.toml", tmp_path / "pyproject.toml")
    (tmp_path / "routepilot/optimization/engine/violation.py").write_text(
        "import routepilot.agents\n"
    )
    result = subprocess.run(
        [str(api / ".venv/bin/lint-imports"), "--no-cache"],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "optimization engine is pure" in result.stdout
