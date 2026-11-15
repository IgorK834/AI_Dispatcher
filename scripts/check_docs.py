"""Documentation checks of FEAT-007 (FR-5, FR-6, FR-7).

Usage: check_docs.py [--readme] [--development] [--wording] [--root DIR]

--readme       the twelve README sections in order, a Mermaid diagram in the architecture section,
               a Polish summary of at most 25 lines at the end, resolvable relative links, and the
               commands of README steps 1 and 2 (API and web) repeated in `clean_clone_check.sh`
--development  the 14 sections of DEVELOPMENT.md and a standards-matrix row with existing proof
               references for every delivery standard (1-6, 7a-7e, 8a-8e)
--wording      over every Markdown file: no term of `scripts/docs_denylist.txt`; the working-time
               notice in the files that define schedules; no "implemented" claim in the README
               status table for a feature whose specification is not `implemented`

Exit code 1 when a check fails; every problem is printed on its own line.
"""

import argparse
import re
import sys
from collections.abc import Iterator
from pathlib import Path

README_SECTIONS = [
    "What it is",
    "Features",
    "Creative twist",
    "Technical overview",
    "Architecture",
    "Run locally",
    "How I used AI tools",
    "Demo",
    "Project structure",
    "Limitations",
    "Roadmap",
    "Documentation map",
]
POLISH_MAX_LINES = 25
DEVELOPMENT_SECTIONS = 14
DELIVERY_STANDARDS = [
    *"123456",
    *(f"7{letter}" for letter in "abcde"),
    *(f"8{letter}" for letter in "abcde"),
]
# The working-time notice must sit in every file that defines schedules (FR-7).
NOTICE = "planning estimate based on a simplified model"
SCHEDULE_FILES = (
    "README.md",
    "specs/FEAT-003-*.md",
    "specs/FEAT-004-*.md",
    "specs/golden/GOLD-*.md",
)
SKIPPED_FOLDERS = {".git", "node_modules", ".venv", ".next", ".pytest_cache", "fixtures"}

LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
COMMENT = re.compile(r"\s+#.*$")


def lines_outside_fences(text: str) -> Iterator[tuple[int, str]]:
    fenced = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced:
            yield number, line


def sections(text: str) -> dict[int, tuple[str, str]]:
    """The numbered `## N. Title` sections: number -> (title, body)."""
    found: list[tuple[int, str, int]] = []
    lines = text.splitlines()
    for number, line in lines_outside_fences(text):
        match = re.match(r"^## (\d+)\. (.+?)\s*$", line)
        if match:
            found.append((int(match.group(1)), match.group(2), number))
    result: dict[int, tuple[str, str]] = {}
    for index, (value, title, start) in enumerate(found):
        end = found[index + 1][2] - 1 if index + 1 < len(found) else len(lines)
        result[value] = (title, "\n".join(lines[start:end]))
    return result


def denylist(root: Path) -> list[re.Pattern[str]]:
    path = root / "scripts" / "docs_denylist.txt"
    if not path.exists():
        return []
    terms = [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    return [re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE) for term in terms]


def denied_terms(text: str, name: str, patterns: list[re.Pattern[str]]) -> list[str]:
    return [
        f"{name}:{number}: a term of the deny-list appears (the fixed purpose statement rule)"
        for number, line in enumerate(text.splitlines(), start=1)
        for pattern in patterns
        if pattern.search(line)
    ]


def step_commands(section: str) -> list[str]:
    """Commands in the fenced blocks under the README labels `**Step 1 ...` and `**Step 2 ...`."""
    commands: list[str] = []
    label, fenced = "", False
    for line in section.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif fenced:
            command = COMMENT.sub("", line).strip()
            if re.match(r"^\*\*Step [12]\b", label) and command and not command.startswith("#"):
                commands.append(" ".join(command.split()))
        elif line.startswith("**"):
            label = line
    return commands


def check_readme(root: Path) -> list[str]:
    path = root / "README.md"
    if not path.exists():
        return ["README.md is missing"]
    text = path.read_text()
    problems: list[str] = []

    found = sections(text)
    for number, name in enumerate(README_SECTIONS, start=1):
        title = found.get(number, ("", ""))[0]
        if not title.lower().startswith(name.lower()):
            problems.append(f"README section {number} must be '{name}', found '{title or 'none'}'")
    if list(found) != sorted(found):
        problems.append("README sections are not in ascending order")
    if "```mermaid" not in found.get(5, ("", ""))[1]:
        problems.append("README section 5 (Architecture) needs a Mermaid diagram")

    headings = [line for _, line in lines_outside_fences(text) if line.startswith("## ")]
    summary = text.split(headings[-1], 1)[1] if headings else ""
    if not headings or not headings[-1].startswith("## Polski"):
        problems.append("README must end with the Polish summary ('## Polski ...')")
    elif len([line for line in summary.splitlines() if line.strip()]) > POLISH_MAX_LINES:
        problems.append(f"The Polish summary has more than {POLISH_MAX_LINES} lines")

    for number, line in lines_outside_fences(text):
        for target in LINK.findall(line):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
                continue
            if not (root / target.split("#", 1)[0]).exists():
                problems.append(f"README:{number}: the link '{target}' does not resolve")

    script = root / "scripts" / "clean_clone_check.sh"
    script_lines = (
        [" ".join(line.split()) for line in script.read_text().splitlines()]
        if script.exists()
        else []
    )
    if not script_lines:
        problems.append("scripts/clean_clone_check.sh is missing")
    commands = step_commands(found.get(6, ("", ""))[1])
    if not commands:
        problems.append("README section 6 has no commands under 'Step 1' and 'Step 2'")
    for command in commands:
        # `pnpm dev` is served as `pnpm build && pnpm start` by the check (FR-4).
        expected = ["pnpm build", "pnpm start"] if command == "pnpm dev" else [command]
        for item in expected:
            if script_lines and not any(item in line for line in script_lines):
                problems.append(f"README command '{command}' is not in clean_clone_check.sh")
    problems += denied_terms(text, "README.md", denylist(root))
    return problems


def table_rows(section: str) -> Iterator[list[str]]:
    for line in section.splitlines():
        if line.startswith("|") and not re.match(r"^\|[\s:|-]+\|$", line):
            yield [cell.strip() for cell in line.strip().strip("|").split("|")]


def spec_text(root: Path) -> str:
    return "\n".join(path.read_text() for path in sorted((root / "specs").glob("FEAT-*.md")))


def missing_references(proof: str, root: Path, specs: str) -> list[str]:
    missing: list[str] = []
    files = set(re.findall(r"`([^`\s]+\.(?:md|json|ya?ml|sh|py|ts|tsx|txt))`", proof))
    files |= {
        target.split("#", 1)[0]
        for target in LINK.findall(proof)
        if not re.match(r"^[a-z][a-z0-9+.-]*:", target) and not target.startswith("#")
    }
    missing += [name for name in sorted(files) if name and not (root / name).exists()]
    for feature in sorted(set(re.findall(r"FEAT-\d{3}", proof))):
        if not list((root / "specs").glob(f"{feature}-*.md")):
            missing.append(feature)
    for adr in sorted(set(re.findall(r"ADR-\d{4}", proof))):
        if not list((root / "docs" / "adr").glob(f"{adr}-*.md")):
            missing.append(adr)
    missing += [
        criterion
        for criterion in sorted(set(re.findall(r"AC-FEAT-\d{3}-\d{2}", proof)))
        if criterion not in specs
    ]
    return missing


def check_development(root: Path) -> list[str]:
    path = root / "DEVELOPMENT.md"
    if not path.exists():
        return ["DEVELOPMENT.md is missing"]
    problems: list[str] = []
    found = sections(path.read_text())
    for number in range(1, DEVELOPMENT_SECTIONS + 1):
        if number not in found:
            problems.append(f"DEVELOPMENT.md section {number} is missing")
    matrix = {row[0]: row for row in table_rows(found.get(1, ("", ""))[1]) if len(row) >= 4}
    specs = spec_text(root)
    for standard in DELIVERY_STANDARDS:
        row = matrix.get(standard)
        if row is None:
            problems.append(f"The standards matrix has no row for standard {standard}")
        elif not row[-1]:
            problems.append(f"The standards matrix row {standard} has an empty proof")
        else:
            problems += [
                f"The proof of standard {standard} refers to '{item}', which does not exist"
                for item in missing_references(row[-1], root, specs)
            ]
    return problems


def markdown_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.md")
        if not SKIPPED_FOLDERS & set(path.relative_to(root).parts)
    )


def spec_status(root: Path, feature: str) -> str | None:
    for path in (root / "specs").glob(f"{feature}-*.md"):
        match = re.search(r"^status:\s*(\S+)", path.read_text(), re.MULTILINE)
        return match.group(1) if match else None
    return None


def check_wording(root: Path) -> list[str]:
    problems: list[str] = []
    patterns = denylist(root)
    for path in markdown_files(root):
        problems += denied_terms(path.read_text(), str(path.relative_to(root)), patterns)

    for pattern in SCHEDULE_FILES:
        for path in sorted(root.glob(pattern)):
            if NOTICE not in path.read_text().lower():
                problems.append(
                    f"{path.relative_to(root)} defines schedules but has no working-time notice"
                )

    readme = root / "README.md"
    if readme.exists():
        for number, line in enumerate(readme.read_text().splitlines(), start=1):
            if not line.startswith("|") or not re.search(r"\bimplemented\b", line, re.IGNORECASE):
                continue
            for feature in sorted(set(re.findall(r"FEAT-\d{3}", line))):
                status = spec_status(root, feature)
                if status != "implemented":
                    problems.append(
                        f"README:{number}: says '{feature}' is implemented, its specification is"
                        f" '{status}'"
                    )
    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--readme", action="store_true")
    parser.add_argument("--development", action="store_true")
    parser.add_argument("--wording", action="store_true")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    if not (args.readme or args.development or args.wording):
        parser.error("choose at least one of --readme, --development, --wording")

    problems: list[str] = []
    if args.readme:
        problems += check_readme(args.root)
    if args.development:
        problems += check_development(args.root)
    if args.wording:
        problems += check_wording(args.root)
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print("Documentation checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
