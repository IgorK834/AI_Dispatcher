"""AC-FEAT-000-08: traceability rejects missing and unknown ACs."""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "trace.py"


@pytest.mark.ac("AC-FEAT-000-08")
@pytest.mark.parametrize(
    "status, test_ac, expected",
    [
        ("approved", "", 1),
        ("draft", "", 0),
        ("approved", "AC-FEAT-000-01", 0),
        ("approved", "AC-FEAT-999-01", 1),
    ],
)
def test_trace_validation(tmp_path: Path, status: str, test_ac: str, expected: int) -> None:
    (tmp_path / "specs").mkdir()
    (tmp_path / "apps/api/tests").mkdir(parents=True)
    (tmp_path / "specs/FEAT-000-fixture.md").write_text(
        f"---\nid: FEAT-000\nstatus: {status}\n---\n- **AC-FEAT-000-01** [unit] Given fixture\n"
    )
    (tmp_path / "apps/api/tests/test_fixture.py").write_text(
        f'@pytest.mark.ac("{test_ac}")\ndef test_fixture():\n    pass\n' if test_ac else ""
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == expected, result.stdout + result.stderr
    if expected:
        assert "AC-FEAT-" in result.stdout


@pytest.mark.ac("AC-FEAT-000-08")
def test_malformed_front_matter(tmp_path: Path) -> None:
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs/FEAT-000-broken.md").write_text("---\nstatus: [broken\n---\n")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "FEAT-000-broken.md" in result.stdout


@pytest.mark.ac("AC-FEAT-000-08")
def test_implemented_criterion_with_failing_junit(tmp_path: Path) -> None:
    (tmp_path / "specs").mkdir()
    (tmp_path / "apps/api/tests").mkdir(parents=True)
    (tmp_path / "specs/FEAT-000-fixture.md").write_text(
        "---\nid: FEAT-000\nstatus: implemented\n---\n- **AC-FEAT-000-01** [unit] Given fixture\n"
    )
    (tmp_path / "apps/api/tests/test_fixture.py").write_text(
        '@pytest.mark.ac("AC-FEAT-000-01")\ndef test_fixture():\n    pass\n'
    )
    report = tmp_path / "junit.xml"
    report.write_text(
        '<testsuite><testcase name="test_fixture"><properties>'
        '<property name="ac" value="AC-FEAT-000-01"/></properties>'
        '<failure message="fixture failed"/></testcase></testsuite>'
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "--check", "--junit", str(report)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "failing test for implemented AC-FEAT-000-01" in result.stdout
