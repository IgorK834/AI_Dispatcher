"""AC-FEAT-000-11: architectural contracts reject forbidden imports."""

import os
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any

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


def _contract(name: str) -> dict[str, Any]:
    api = Path(__file__).resolve().parents[2]
    contracts = tomllib.loads((api / "pyproject.toml").read_text())["tool"]["importlinter"][
        "contracts"
    ]
    return next(item for item in contracts if item["name"] == name)


def _lint_imports(root: Path, extra_module: tuple[str, str] | None = None) -> tuple[int, str]:
    """Run lint-imports on a copy of the package, optionally with one extra module."""
    api = Path(__file__).resolve().parents[2]
    shutil.copytree(
        api / "src/routepilot",
        root / "routepilot",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    shutil.copy(api / "pyproject.toml", root / "pyproject.toml")
    if extra_module is not None:
        (root / "routepilot" / extra_module[0]).write_text(extra_module[1])
    result = subprocess.run(
        [str(api / ".venv/bin/lint-imports"), "--no-cache"],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root)},
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout + result.stderr


@pytest.mark.ac("AC-FEAT-003-28")
@pytest.mark.parametrize(
    "name, source",
    [
        ("optimization engine is pure", "routepilot.optimization.engine"),
        ("compliance is pure", "routepilot.compliance"),
    ],
)
def test_engine_and_compliance_purity_contracts_forbid_io_modules(name: str, source: str) -> None:
    contract = _contract(name)
    assert contract["type"] == "forbidden"
    assert contract["source_modules"] == [source]
    forbidden = set(contract["forbidden_modules"])
    # "os" covers os.environ; import-linter forbids modules, not attributes.
    assert {
        "fastapi",
        "sqlalchemy",
        "httpx",
        "os",
        "routepilot.routing",
        "routepilot.agents",
    } <= forbidden, name


@pytest.mark.ac("AC-FEAT-003-28")
def test_oracles_are_test_only_contract_is_present() -> None:
    contract = _contract("oracles are test-only")
    assert contract["type"] == "forbidden"
    # Every module of the package must be a source, except the oracles themselves and the three
    # package __init__ files that contain an oracle (import-linter skips those sources); those
    # __init__ files must not mention an oracle.
    package = Path(__file__).resolve().parents[2] / "src/routepilot"
    expected: set[str] = set()
    for entry in sorted(package.iterdir()):
        if entry.name.startswith("__") or entry.name == "optimization":
            continue
        expected.add(f"routepilot.{entry.stem}")
    expected.add("routepilot.optimization.jobs")
    for entry in sorted((package / "optimization/engine").glob("*.py")):
        if entry.stem not in ("__init__", "oracle", "fleet_oracle"):
            expected.add(f"routepilot.optimization.engine.{entry.stem}")
    assert set(contract["source_modules"]) == expected
    for init in (
        package / "__init__.py",
        package / "optimization/__init__.py",
        package / "optimization/engine/__init__.py",
    ):
        assert "oracle" not in init.read_text(), init
    assert set(contract["forbidden_modules"]) == {
        "routepilot.optimization.engine.oracle",
        "routepilot.optimization.engine.fleet_oracle",
    }


@pytest.mark.ac("AC-FEAT-003-28")
def test_lint_imports_passes_on_the_real_package(tmp_path: Path) -> None:
    code, output = _lint_imports(tmp_path)
    assert code == 0, output


@pytest.mark.ac("AC-FEAT-003-28")
@pytest.mark.parametrize("oracle", ["oracle", "fleet_oracle"])
def test_importing_an_oracle_from_src_is_rejected(tmp_path: Path, oracle: str) -> None:
    code, output = _lint_imports(
        tmp_path,
        ("optimization/jobs/uses_oracle.py", f"import routepilot.optimization.engine.{oracle}\n"),
    )
    assert code == 1, output
    assert "oracles are test-only" in output
