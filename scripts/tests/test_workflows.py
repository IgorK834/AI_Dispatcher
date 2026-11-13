"""AC-FEAT-000-10: workflow security and gate structure."""

import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.ac("AC-FEAT-000-10")
def test_ci_fast_is_pinned_read_only_and_has_all_gates() -> None:
    source = (ROOT / ".github/workflows/ci-fast.yml").read_text()
    workflow = yaml.safe_load(source)
    assert set(workflow["on"]) == {"pull_request"}
    assert workflow["permissions"] == {"contents": "read"}
    assert "pull_request_target" not in source
    assert "secrets." not in source
    assert "continue-on-error" not in source
    assert not re.search(
        r"https?://[^\s]*(?:openai|anthropic|generativelanguage|openrouteservice|timocom|cloudflare)",
        source,
    )
    steps = workflow["jobs"]["checks"]["steps"]
    for gate in ["1", "2", "3", "3a", "4", "5", "8a", "8c", "9", "10"]:
        assert any(step.get("name", "").startswith(f"Gate {gate}:") for step in steps)
    assert any(
        job.get("name") == "ci-fast" and job.get("if") == "${{ always() }}"
        for job in workflow["jobs"].values()
    )
    for step in steps:
        if "uses" in step:
            assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", step["uses"])


FULL_PATH = ROOT / ".github/workflows/ci-full.yml"
FORBIDDEN_HOSTS = (
    r"https?://[^\s]*(?:openai|anthropic|generativelanguage|openrouteservice|timocom|cloudflare)"
)


def gate_ids(steps: list[dict]) -> set[str]:
    return {
        step["name"].split(":")[0].removeprefix("Gate ")
        for step in steps
        if step.get("name", "").startswith("Gate ")
    }


@pytest.mark.ac("AC-FEAT-007-01")
def test_ci_full_runs_on_main_and_nightly_and_contains_every_gate() -> None:
    source = FULL_PATH.read_text()
    workflow = yaml.safe_load(source)
    assert set(workflow["on"]) == {"push", "schedule", "workflow_dispatch"}
    assert workflow["on"]["push"]["branches"] == ["main"]
    assert workflow["on"]["schedule"][0]["cron"]
    assert workflow["permissions"] == {"contents": "read"}
    assert "pull_request" not in workflow["on"] and "pull_request_target" not in source
    assert "secrets." not in source  # no secret and no paid service (NFR-012)
    assert "continue-on-error" not in source
    assert not re.search(FORBIDDEN_HOSTS, source)

    job = workflow["jobs"]["checks"]
    assert job["env"]["HYPOTHESIS_PROFILE"] == "nightly"
    steps = job["steps"]
    assert gate_ids(steps) >= {"1", "2", "3", "3a", "4", "5", "6", "7", "8a", "8b", "8c", "9", "10"}
    by_gate = {step["name"].split(":")[0]: step for step in steps if "name" in step}
    assert "-m integration" in by_gate["Gate 6"]["run"]
    assert "playwright test" in by_gate["Gate 7"]["run"]
    assert "scripts/ci/gate_8b.sh" in by_gate["Gate 8b"]["run"]
    for step in steps:
        if "name" in step and step["name"].startswith("Gate "):
            assert step["if"] == "${{ !cancelled() }}"  # a failed gate never hides the later ones

    required = workflow["jobs"]["required"]
    assert required["name"] == "ci-full"
    assert required["needs"] == "checks" and required["if"] == "${{ always() }}"
    assert required["permissions"] == {}


@pytest.mark.ac("AC-FEAT-007-01")
def test_ci_full_contains_everything_ci_fast_runs_and_pins_the_same_actions() -> None:
    fast_source = (ROOT / ".github/workflows/ci-fast.yml").read_text()
    full_source = FULL_PATH.read_text()
    fast = yaml.safe_load(fast_source)["jobs"]["checks"]["steps"]
    full = yaml.safe_load(full_source)["jobs"]["checks"]["steps"]
    assert gate_ids(fast) <= gate_ids(full)
    commands = {
        line.strip()
        for step in fast
        for line in step.get("run", "").splitlines()
        if line.strip().startswith(("make ", "bash scripts/", "uv run ", "pnpm "))
    }
    assert commands
    assert all(command in full_source for command in commands), [
        command for command in commands if command not in full_source
    ]
    for step in full:
        if "uses" in step:
            assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", step["uses"])
    pinned = set(re.findall(r"uses: ([^\s@]+@[0-9a-f]{40})", fast_source))
    pinned |= set(
        re.findall(
            r"uses: ([^\s@]+@[0-9a-f]{40})", (ROOT / ".github/workflows/ai-evals.yml").read_text()
        )
    )
    used = set(re.findall(r"uses: ([^\s@]+@[0-9a-f]{40})", full_source))
    assert used <= pinned, (
        "ci-full uses an action that is not already pinned by ci-fast or ai-evals"
    )


def load_license_check():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "license_check", ROOT / "scripts/ci/license_check.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.ac("AC-FEAT-007-08")
@pytest.mark.parametrize(
    ("licence", "is_denied"),
    [
        ("GPL-3.0-or-later", True),
        ("AGPL-3.0-only", True),
        ("GNU General Public License v2 (GPLv2)", True),
        ("GNU Affero General Public License v3", True),
        ("GPL-2.0-only WITH Classpath-exception-2.0", True),
        ("LGPL-3.0-or-later", False),
        ("GNU Lesser General Public License v3 (LGPLv3)", False),
        ("MIT", False),
        ("Apache-2.0", False),
        ("MIT OR GPL-2.0-only", False),  # the user may choose the permissive side
        ("GPL-2.0-only OR GPL-3.0-only", True),
        ("", False),  # unknown is reported as a warning, not denied
    ],
)
def test_licence_policy_denies_gpl_and_agpl_only(licence: str, is_denied: bool) -> None:
    assert load_license_check().denied(licence) is is_denied


@pytest.mark.ac("AC-FEAT-007-08")
def test_requirement_pins_are_read_from_an_exported_lockfile(tmp_path: Path) -> None:
    export = tmp_path / "requirements.txt"
    export.write_text(
        "# autogenerated by uv\nfastapi==0.115.0 ; python_version >= '3.9'\n"
        "uvicorn[standard]==0.30.6\n    # via fastapi\n\n-e .\n"
    )
    assert load_license_check().pins(export) == [("fastapi", "0.115.0"), ("uvicorn", "0.30.6")]


FIXTURES = ROOT / "scripts/tests/fixtures/lockfiles"


def run_gate(*args: str) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(
        ["bash", str(ROOT / "scripts/ci/gate_8b.sh"), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )


@pytest.mark.integration
@pytest.mark.ac("AC-FEAT-007-08")
def test_gate_8b_fails_on_a_known_advisory() -> None:
    result = run_gate(str(FIXTURES / "vulnerable-requirements.txt"))
    assert result.returncode != 0
    assert "requests" in result.stdout + result.stderr


@pytest.mark.integration
@pytest.mark.ac("AC-FEAT-007-08")
def test_gate_8b_fails_on_a_gpl_runtime_licence() -> None:
    result = run_gate(str(FIXTURES / "gpl-requirements.txt"))
    assert result.returncode != 0
    assert "DENIED" in result.stdout and "pylint" in result.stdout


@pytest.mark.integration
@pytest.mark.ac("AC-FEAT-007-08")
def test_gate_8b_passes_on_the_real_lockfiles() -> None:
    result = run_gate()
    assert result.returncode == 0, result.stdout + result.stderr
