"""AC-FEAT-007-10: the coverage gate fails below a package threshold and prints the numbers."""

import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_coverage", ROOT / "scripts/ci/check_coverage.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def line(number: int, hits: int, branch: tuple[int, int] | None = None) -> str:
    if branch is None:
        return f'<line number="{number}" hits="{hits}"/>'
    covered, total = branch
    return (
        f'<line number="{number}" hits="{hits}" branch="true" '
        f'condition-coverage="{covered * 100 // total}% ({covered}/{total})"/>'
    )


def report(files: dict[str, list[str]]) -> str:
    classes = "".join(
        f'<class filename="{name}"><lines>{"".join(lines)}</lines></class>'
        for name, lines in files.items()
    )
    package = f'<package name="p"><classes>{classes}</classes></package>'
    return f"<coverage><packages>{package}</packages></coverage>"


def covered_world() -> dict[str, list[str]]:
    """Every gated package with 10 lines and 4 branch outcomes, all of them covered."""
    body = [line(n, 1, (4, 4) if n == 1 else None) for n in range(1, 11)]
    names = [
        "optimization/engine/optimizer.py",
        "compliance/rules.py",
        "identity/service/auth.py",
        "freight/service/offers.py",
        "fleet/service/fleet.py",
        "routing/haversine.py",
        "agents/graph.py",
        "fleet/api/routes.py",
    ]
    return {f"src/routepilot/{name}": body for name in names}


def run(tmp_path: Path, files: dict[str, list[str]], capsys: pytest.CaptureFixture[str]):
    path = tmp_path / "coverage.xml"
    path.write_text(report(files))
    code = load().main([str(path)])
    return code, capsys.readouterr().out


@pytest.mark.ac("AC-FEAT-007-10")
def test_every_package_above_its_threshold_passes_and_the_numbers_are_printed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = run(tmp_path, covered_world(), capsys)
    assert code == 0
    for package in ("optimization.engine", "compliance", "identity", "freight", "fleet"):
        assert package in out
    assert "routers" in out and "100.0" in out


@pytest.mark.ac("AC-FEAT-007-10")
def test_a_package_below_its_line_threshold_fails_and_is_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    world = covered_world()
    # compliance needs 90 % of lines: 8 of 10 is not enough.
    world["src/routepilot/compliance/rules.py"] = [
        line(n, int(n <= 8), (4, 4) if n == 1 else None) for n in range(1, 11)
    ]
    code, out = run(tmp_path, world, capsys)
    assert code == 1
    assert re.search(r"compliance\s+80\.0.*FAIL", out)
    assert len([row for row in out.splitlines() if row.endswith("FAIL")]) == 1


@pytest.mark.ac("AC-FEAT-007-10")
def test_a_package_below_its_branch_threshold_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    world = covered_world()
    # identity needs 80 % of branches: 3 of 4 is 75 %.
    world["src/routepilot/identity/service/auth.py"] = [
        line(n, 1, (3, 4) if n == 1 else None) for n in range(1, 11)
    ]
    code, out = run(tmp_path, world, capsys)
    assert code == 1
    assert re.search(r"identity\s+100\.0\s+75\.0.*FAIL", out)


@pytest.mark.ac("AC-FEAT-007-10")
def test_a_gated_package_without_any_measured_file_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    world = covered_world()
    del world["src/routepilot/routing/haversine.py"]
    code, out = run(tmp_path, world, capsys)
    assert code == 1
    assert re.search(r"routing.*no data.*FAIL", out)


@pytest.mark.ac("AC-FEAT-007-10")
def test_a_router_file_below_75_percent_fails_even_when_its_package_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    world = covered_world()
    world["src/routepilot/fleet/api/routes.py"] = [
        line(n, int(n <= 7), (4, 4) if n == 1 else None) for n in range(1, 11)
    ]
    code, out = run(tmp_path, world, capsys)
    assert code == 1
    assert re.search(r"routers\s+70\.0.*FAIL", out)


@pytest.mark.ac("AC-FEAT-007-10")
def test_the_thresholds_equal_those_of_context_md() -> None:
    """context.md → Testing Standards is the source; the script must not drift from it."""
    text = (ROOT / "context.md").read_text()
    sentence = re.search(r"Coverage thresholds \(lines/branches\):([^\n]+)", text)
    assert sentence is not None
    expected: dict[str, tuple[int, int | None]] = {}
    for group in sentence.group(1).split(";"):
        numbers = re.search(r"≥ (\d+)(?:/(\d+))?", group)
        assert numbers is not None
        lines = int(numbers.group(1))
        branches = int(numbers.group(2)) if numbers.group(2) else None
        for name in re.findall(r"`([^`]+)`", group):
            expected[name] = (lines, branches)
        if "routers" in group:
            expected["routers"] = (lines, branches)

    module = load()
    configured = {name: (item[0], item[1]) for name, item in module.THRESHOLDS.items()}
    assert configured == {name: value for name, value in expected.items() if name != "lib/"}
    assert expected["lib/"] == (80, None)
