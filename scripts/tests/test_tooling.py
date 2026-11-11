"""Failure propagation and secret scanning for the foundation tooling."""

import os
import secrets
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.ac("AC-FEAT-000-05")
@pytest.mark.parametrize(
    "failure", ["", "ruff", "mypy", "prettier", "eslint", "tsc", "pytest", "vitest"]
)
def test_make_check_propagates_tool_failures(tmp_path: Path, failure: str) -> None:
    (tmp_path / "apps/api").mkdir(parents=True)
    (tmp_path / "Makefile").write_bytes((ROOT / "Makefile").read_bytes())
    tools = tmp_path / "bin"
    tools.mkdir()
    script = """#!/usr/bin/env python3
import os, sys
args = sys.argv[1:]
aliases = {"format:check": "prettier", "lint": "eslint", "typecheck": "tsc", "test": "vitest"}
tool = aliases.get(args[-1], args[1] if args[0] == "run" else args[-1])
with open(os.environ["TOOL_LOG"], "a") as log: log.write(tool + "\\n")
raise SystemExit(1 if tool == os.environ["FAIL_TOOL"] else 0)
"""
    for name in ["uv", "pnpm"]:
        binary = tools / name
        binary.write_text(script)
        binary.chmod(0o755)
    log = tmp_path / "commands"
    result = subprocess.run(
        ["make", "check"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        env={
            **os.environ,
            "PATH": str(tools) + os.pathsep + os.environ["PATH"],
            "TOOL_LOG": str(log),
            "FAIL_TOOL": failure,
        },
    )
    assert (result.returncode != 0) == bool(failure)
    if not failure:
        assert {"ruff", "mypy", "prettier", "eslint", "tsc", "pytest", "vitest"} <= set(
            log.read_text().splitlines()
        )


@pytest.mark.ac("AC-FEAT-000-06")
def test_gitleaks_staged_hook_and_ruff_format(tmp_path: Path) -> None:
    assert shutil.which("gitleaks"), "Install gitleaks 8.30.1 before running tooling checks"
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    shutil.copy(ROOT / ".gitleaks.toml", tmp_path)
    shutil.copy(ROOT / ".pre-commit-config.yaml", tmp_path)
    # Deliberately fake scanner input generated at runtime, never a committed key.
    key = "ghp_" + secrets.token_hex(18)
    (tmp_path / "fixture.txt").write_text(f"token={key}\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "fixture.txt"], check=True)
    scan = subprocess.run(
        [
            "gitleaks",
            "git",
            "--staged",
            "--redact",
            "--config",
            str(tmp_path / ".gitleaks.toml"),
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
    )
    assert scan.returncode == 1
    assert key.encode() not in scan.stdout + scan.stderr
    hook = subprocess.run(
        [str(ROOT / "apps/api/.venv/bin/pre-commit"), "run", "gitleaks", "--all-files"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        env={**os.environ, "PRE_COMMIT_HOME": str(tmp_path / "pre-commit-cache")},
    )
    assert hook.returncode == 1
    assert b"gitleaks" in hook.stdout
    assert key.encode() not in hook.stdout + hook.stderr
    fixture = tmp_path / "bad.py"
    fixture.write_text("value=  1\n")
    result = subprocess.run(
        [str(ROOT / "apps/api/.venv/bin/ruff"), "format", "--check", str(fixture)],
        check=False,
        capture_output=True,
    )
    assert result.returncode == 1
