"""Documentation checks of FEAT-007 (FR-5, FR-6, FR-7).

Usage: check_docs.py [--readme] [--development] [--wording] [--media] [--root DIR]

--readme       the twelve README sections in order, a Mermaid diagram in the architecture section,
               a Polish summary of at most 25 lines at the end, resolvable relative links, and the
               commands of README steps 1 and 2 (API and web) repeated in `clean_clone_check.sh`
--development  the 14 sections of DEVELOPMENT.md and a standards-matrix row with existing proof
               references for every delivery standard (1-6, 7a-7e, 8a-8e)
--media        `docs/media/` (FEAT-009 §4.3): at least one of `demo.mp4` / `demo.gif`, each within
               its size limit, the MP4 between 120 and 240 s (read from the file; no `ffprobe`
               needed) and the ten screenshots as PNG files of at most 1 MB
--wording      over every Markdown file: no term of `scripts/docs_denylist.txt`; the working-time
               notice in the files that define schedules; no "implemented" claim in the README
               status table for a feature whose specification is not `implemented`

Exit code 1 when a check fails; every problem is printed on its own line.
"""

import argparse
import re
import struct
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

# FEAT-009 section 4.3: names and limits of the demo media.
MEDIA_FOLDER = "docs/media"
MP4_MAX_BYTES = 25 * 1024 * 1024
GIF_MAX_BYTES = 10 * 1024 * 1024
PNG_MAX_BYTES = 1024 * 1024
MP4_SECONDS = (120, 240)
SCREENSHOT_SIZE = (1440, 900)
SCREENSHOTS = [
    "01-login",
    "02-fleet",
    "03-driver-form",
    "04-offers",
    "05-ai-dispatcher-trace",
    "06-plan-variants-co2",
    "07-plan-timeline",
    "08-approval-card",
    "09-optimizer-no-ai",
    "10-pl-locale",
]
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

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


def mp4_seconds(path: Path) -> float | None:
    """Duration from the `mvhd` box of the file, or None when it cannot be read."""
    try:
        with path.open("rb") as handle:
            size = path.stat().st_size

            def boxes(start: int, end: int) -> Iterator[tuple[bytes, int, int]]:
                position = start
                while position + 8 <= end:
                    handle.seek(position)
                    length, kind = struct.unpack(">I4s", handle.read(8))
                    header = 8
                    if length == 1:
                        length = struct.unpack(">Q", handle.read(8))[0]
                        header = 16
                    elif length == 0:
                        length = end - position
                    if length < header:
                        return
                    yield kind, position + header, position + length
                    position += length

            for kind, start, end in boxes(0, size):
                if kind != b"moov":
                    continue
                for inner, inner_start, _ in boxes(start, end):
                    if inner != b"mvhd":
                        continue
                    handle.seek(inner_start)
                    payload = handle.read(32)
                    if payload[0] == 1:
                        timescale, duration = struct.unpack(">IQ", payload[20:32])
                    else:
                        timescale, duration = struct.unpack(">II", payload[12:20])
                    return duration / timescale if timescale else None
    except (OSError, struct.error, IndexError):
        return None
    return None


def png_size(path: Path) -> tuple[int, int] | None:
    head = path.read_bytes()[:24]
    if head[:8] != PNG_SIGNATURE or head[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", head[16:24])
    return width, height


def media_present(root: Path) -> bool:
    return any((root / MEDIA_FOLDER / name).exists() for name in ("demo.mp4", "demo.gif"))


def check_media(root: Path) -> list[str]:
    """FEAT-009 AC-01 and AC-03: the demo files exist within their limits."""
    folder = root / MEDIA_FOLDER
    problems: list[str] = []
    mp4, gif = folder / "demo.mp4", folder / "demo.gif"
    if not mp4.exists() and not gif.exists():
        problems.append(f"{MEDIA_FOLDER}: neither demo.mp4 nor demo.gif exists")
    if mp4.exists():
        if mp4.stat().st_size > MP4_MAX_BYTES:
            problems.append(f"demo.mp4 is larger than {MP4_MAX_BYTES // 1024 // 1024} MB")
        seconds = mp4_seconds(mp4)
        low, high = MP4_SECONDS
        if seconds is None:
            problems.append("demo.mp4: the duration cannot be read (is it an MP4 file?)")
        elif not low <= seconds <= high:
            problems.append(f"demo.mp4 lasts {seconds:.0f} s, not {low}-{high} s")
    if gif.exists():
        if gif.stat().st_size > GIF_MAX_BYTES:
            problems.append(f"demo.gif is larger than {GIF_MAX_BYTES // 1024 // 1024} MB")
        if gif.read_bytes()[:6] not in (b"GIF87a", b"GIF89a"):
            problems.append("demo.gif is not a GIF file")
    for name in SCREENSHOTS:
        path = folder / "screenshots" / f"{name}.png"
        if not path.exists():
            problems.append(f"{MEDIA_FOLDER}/screenshots/{name}.png is missing")
            continue
        size = png_size(path)
        if size is None:
            problems.append(f"{path.name} is not a PNG file")
        elif size != SCREENSHOT_SIZE:
            expected = f"{SCREENSHOT_SIZE[0]} x {SCREENSHOT_SIZE[1]}"
            problems.append(f"{path.name} is {size[0]} x {size[1]}, not {expected}")
        if path.stat().st_size > PNG_MAX_BYTES:
            problems.append(f"{path.name} is larger than 1 MB")
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
    parser.add_argument("--media", action="store_true")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    if not (args.readme or args.development or args.wording or args.media):
        parser.error("choose at least one of --readme, --development, --wording, --media")

    problems: list[str] = []
    if args.readme:
        problems += check_readme(args.root)
    if args.development:
        problems += check_development(args.root)
    if args.wording:
        problems += check_wording(args.root)
    if args.media:
        problems += check_media(args.root)
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print("Documentation checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
