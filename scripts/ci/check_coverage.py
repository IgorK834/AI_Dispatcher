"""Coverage gate of FEAT-007 (FR-9, AC-FEAT-007-10): fail when a package is below its threshold.

Usage: check_coverage.py COVERAGE_XML

Reads a Cobertura report (`coverage xml`), adds up lines and branch outcomes per package and
prints one row per gated package. Exit code 1 when a package is below a threshold or has no
measured file at all. The thresholds are those of `context.md` → Testing Standards
(`scripts/tests/test_check_coverage.py` compares them with that file); the web `lib/` threshold
is enforced by vitest (`apps/web/vitest.config.ts`).
"""

import re
import sys
import xml.etree.ElementTree as ET  # the report is written by the CI run itself, not by a third party
from pathlib import Path

# package -> (line threshold in %, branch threshold in % or None, path prefixes under routepilot/)
THRESHOLDS: dict[str, tuple[int, int | None, tuple[str, ...]]] = {
    "optimization.engine": (90, 85, ("optimization/engine/",)),
    "compliance": (90, 85, ("compliance/",)),
    "identity": (90, 80, ("identity/",)),
    "freight": (85, 75, ("freight/",)),
    "fleet": (85, 75, ("fleet/",)),
    "routing": (85, 75, ("routing/",)),
    "agents": (85, 75, ("agents/",)),
    # Routers: the HTTP layer of every module. Only lines are gated ("routers ≥ 75").
    "routers": (75, None, ()),
}

ROUTER_FILE = re.compile(r"(?:^|/)api(?:/[^/]+)?\.py$")
BRANCHES = re.compile(r"\((\d+)/(\d+)\)")


def package_path(filename: str) -> str:
    """The file path below `routepilot/` ('src/routepilot/fleet/api/routes.py' -> 'fleet/api/routes.py')."""
    marker = "routepilot/"
    return filename.split(marker, 1)[1] if marker in filename else filename


def counts(report: Path) -> dict[str, list[int]]:
    """Per package: [lines, covered lines, branch outcomes, covered branch outcomes]."""
    totals: dict[str, list[int]] = {name: [0, 0, 0, 0] for name in THRESHOLDS}
    for item in ET.parse(report).getroot().iter("class"):
        path = package_path(item.attrib["filename"])
        names = [
            name
            for name, (_, _, prefixes) in THRESHOLDS.items()
            if any(path.startswith(prefix) for prefix in prefixes)
        ]
        if ROUTER_FILE.search(path):
            names.append("routers")
        for line in item.iter("line"):
            for name in names:
                totals[name][0] += 1
                totals[name][1] += line.attrib["hits"] != "0"
            outcome = BRANCHES.search(line.attrib.get("condition-coverage", ""))
            if line.attrib.get("branch") == "true" and outcome:
                for name in names:
                    totals[name][2] += int(outcome.group(2))
                    totals[name][3] += int(outcome.group(1))
    return totals


def percent(covered: int, total: int) -> float:
    return 100.0 if total == 0 else 100.0 * covered / total


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    totals = counts(Path(argv[0]))
    failed = False
    print(f"{'package':<22}{'lines %':>9}{'branches %':>12}   threshold (lines/branches)")
    for name, (line_limit, branch_limit, _) in THRESHOLDS.items():
        lines, covered, branches, covered_branches = totals[name]
        limit = f"{line_limit}/{branch_limit}" if branch_limit is not None else f"{line_limit}/-"
        if lines == 0:
            print(f"{name:<22}{'no data':>21}   {limit}  FAIL")
            failed = True
            continue
        line_rate = percent(covered, lines)
        branch_rate = percent(covered_branches, branches)
        low = line_rate < line_limit or (branch_limit is not None and branch_rate < branch_limit)
        failed = failed or low
        print(
            f"{name:<22}{line_rate:>9.1f}{branch_rate:>12.1f}   {limit}{'  FAIL' if low else ''}"
        )
    if failed:
        print("Coverage gate failed: a package is below its threshold (context.md → Testing Standards).")
        return 1
    print("Coverage gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
