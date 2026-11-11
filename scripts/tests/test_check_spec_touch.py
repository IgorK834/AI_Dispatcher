"""AC-FEAT-000-09/13: spec changes and canonical instruction rules."""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "check_spec_touch.py"


@pytest.mark.ac("AC-FEAT-000-09")
def test_spec_touch(tmp_path: Path) -> None:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(tmp_path), *args],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()

    git("init", "-q")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    (tmp_path / "contracts").mkdir()
    (tmp_path / "specs").mkdir()
    (tmp_path / "contracts/openapi.json").write_text("{}\n")
    git("add", ".")
    git("commit", "-qm", "fixture")
    base = git("rev-parse", "HEAD")
    (tmp_path / "contracts/openapi.json").write_text('{"changed": true}\n')
    git("add", ".")
    git("commit", "-qm", "contract fixture")
    command = [sys.executable, str(SCRIPT), "--root", str(tmp_path), "--base", base]
    assert subprocess.run(command, check=False).returncode == 1
    (tmp_path / "specs/FEAT-000.md").write_text("fixture\n")
    git("add", ".")
    git("commit", "-qm", "spec fixture")
    assert subprocess.run(command, check=False).returncode == 0


@pytest.mark.ac("AC-FEAT-000-13")
def test_real_agent_docs_and_invalid_fixtures(tmp_path: Path) -> None:
    assert (
        subprocess.run([sys.executable, str(SCRIPT), "--agent-docs"], check=False).returncode == 0
    )
    for agents, claude in [
        ("context.md\n", "wrong\ncontext.md\n"),
        ("context.md\n" * 151, "@AGENTS.md\ncontext.md\n"),
        ("missing reference\n", "@AGENTS.md\ncontext.md\n"),
    ]:
        (tmp_path / "AGENTS.md").write_text(agents)
        (tmp_path / "CLAUDE.md").write_text(claude)
        assert (
            subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(tmp_path), "--agent-docs"],
                check=False,
            ).returncode
            == 1
        )
