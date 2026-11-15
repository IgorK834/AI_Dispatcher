"""AC-FEAT-007-05 and AC-FEAT-007-06: README and DEVELOPMENT.md completeness, wording checks.

AC-FEAT-009-01, 03 and 04: the demo media check and the README demo section.
"""

import importlib.util
import shutil
import struct
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "docs"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_docs", ROOT / "scripts/check_docs.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_root(tmp_path: Path) -> Path:
    """A small repository with the valid fixture documents and the files they refer to."""
    (tmp_path / "scripts").mkdir(parents=True)
    (tmp_path / "docs/adr").mkdir(parents=True)
    (tmp_path / "specs").mkdir()
    shutil.copy(FIXTURES / "README.valid.md", tmp_path / "README.md")
    shutil.copy(FIXTURES / "DEVELOPMENT.valid.md", tmp_path / "DEVELOPMENT.md")
    shutil.copy(FIXTURES / "clean_clone_check.valid.sh", tmp_path / "scripts/clean_clone_check.sh")
    (tmp_path / "scripts/docs_denylist.txt").write_text("# comment\nrecruitment\n")
    (tmp_path / "docs/linked.md").write_text("# Guide\n")
    (tmp_path / "docs/adr/ADR-0001-fixture.md").write_text("# ADR\n")
    (tmp_path / "specs/FEAT-001-fixture.md").write_text(
        "status: approved\n\n- **AC-FEAT-001-04**\n"
    )
    return tmp_path


def change(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    assert old in text, old
    path.write_text(text.replace(old, new))


def problems(root: Path, *flags: str) -> list[str]:
    module = load()
    found: list[str] = []
    if "--readme" in flags:
        found += module.check_readme(root)
    if "--development" in flags:
        found += module.check_development(root)
    if "--wording" in flags:
        found += module.check_wording(root)
    if "--media" in flags:
        found += module.check_media(root)
    return found


@pytest.mark.ac("AC-FEAT-007-05")
def test_a_readme_with_the_twelve_sections_in_order_and_a_short_polish_summary_passes(
    tmp_path: Path,
) -> None:
    assert problems(make_root(tmp_path), "--readme") == []


@pytest.mark.ac("AC-FEAT-007-05")
def test_a_missing_section_fails(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    change(root / "README.md", "## 3. Creative twist\n\n- two\n\n", "")
    assert any("section 3" in item for item in problems(root, "--readme"))


@pytest.mark.ac("AC-FEAT-007-05")
def test_a_reordered_section_fails(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    change(root / "README.md", "## 2. Features", "## 2. Creative twist")
    change(root / "README.md", "## 3. Creative twist", "## 3. Features")
    found = problems(root, "--readme")
    assert any("section 2" in item for item in found) and any("section 3" in item for item in found)


@pytest.mark.ac("AC-FEAT-007-05")
def test_a_polish_summary_of_more_than_25_lines_or_not_at_the_end_fails(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    readme = root / "README.md"
    readme.write_text(readme.read_text() + "".join(f"- linia {n}\n" for n in range(30)))
    assert any("Polish summary" in item for item in problems(root, "--readme"))

    root = make_root(tmp_path / "second")
    readme = root / "README.md"
    readme.write_text(readme.read_text() + "\n## 13. Afterword\n")
    assert any("must end with the Polish summary" in item for item in problems(root, "--readme"))


@pytest.mark.ac("AC-FEAT-007-05")
def test_a_relative_link_that_does_not_resolve_fails_and_external_links_are_not_followed(
    tmp_path: Path,
) -> None:
    root = make_root(tmp_path)
    change(root / "README.md", "- one", "- one [web](https://example.invalid/x)")
    assert problems(root, "--readme") == []
    change(root / "README.md", "docs/linked.md#intro", "docs/missing.md")
    assert any("docs/missing.md" in item for item in problems(root, "--readme"))


@pytest.mark.ac("AC-FEAT-007-05")
def test_the_architecture_section_needs_a_mermaid_diagram(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    change(root / "README.md", "```mermaid", "```text")
    assert any("Mermaid" in item for item in problems(root, "--readme"))


@pytest.mark.ac("AC-FEAT-007-05")
def test_a_readme_command_missing_from_the_clean_clone_script_fails(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    change(root / "scripts/clean_clone_check.sh", "uv sync\n", "")
    assert any("'uv sync'" in item for item in problems(root, "--readme"))


@pytest.mark.ac("AC-FEAT-007-05")
def test_pnpm_dev_needs_the_production_commands_in_the_script_and_comments_are_ignored(
    tmp_path: Path,
) -> None:
    root = make_root(tmp_path)
    assert problems(root, "--readme") == []  # `cp .env.example .env  # works as-is` has a comment
    change(root / "scripts/clean_clone_check.sh", "pnpm start &\n", "")
    assert any("pnpm dev" in item for item in problems(root, "--readme"))


@pytest.mark.ac("AC-FEAT-007-05")
def test_a_term_of_the_deny_list_in_the_readme_fails(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    change(root / "README.md", "A fixture.", "A fixture made for a Recruitment process.")
    assert any("deny-list" in item for item in problems(root, "--readme"))


@pytest.mark.ac("AC-FEAT-007-06")
def test_a_development_guide_with_14_sections_and_a_complete_matrix_passes(tmp_path: Path) -> None:
    assert problems(make_root(tmp_path), "--development") == []


@pytest.mark.ac("AC-FEAT-007-06")
def test_a_missing_matrix_row_an_empty_proof_or_a_missing_section_fails(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    change(root / "DEVELOPMENT.md", "| 7c | standard | decision | `README.md` |\n", "")
    assert any("7c" in item for item in problems(root, "--development"))

    root = make_root(tmp_path / "empty")
    change(
        root / "DEVELOPMENT.md",
        "| 8d | standard | decision | `README.md` |",
        "| 8d | standard | decision |  |",
    )
    assert any("8d" in item and "empty proof" in item for item in problems(root, "--development"))

    root = make_root(tmp_path / "section")
    change(root / "DEVELOPMENT.md", "## 14. Section 14\n\nText.\n", "")
    assert any("section 14" in item for item in problems(root, "--development"))


@pytest.mark.ac("AC-FEAT-007-06")
def test_a_proof_that_refers_to_something_that_does_not_exist_fails(tmp_path: Path) -> None:
    for old, new, name in [
        (
            "| 5 | standard | decision | `README.md` §7 |",
            "| 5 | standard | decision | `gone.md` |",
            "gone.md",
        ),
        (
            "| 2 | standard | decision | ADR-0001; FEAT-001 (AC-FEAT-001-04) |",
            "| 2 | standard | decision | ADR-0042 |",
            "ADR-0042",
        ),
        (
            "| 3 | standard | decision | FEAT-001 |",
            "| 3 | standard | decision | FEAT-077 |",
            "FEAT-077",
        ),
        (
            "| 4 | standard | decision | ADR-0001 |",
            "| 4 | standard | decision | AC-FEAT-001-99 |",
            "AC-FEAT-001-99",
        ),
    ]:
        root = make_root(tmp_path / name)
        change(root / "DEVELOPMENT.md", old, new)
        assert any(name in item for item in problems(root, "--development")), name


@pytest.mark.ac("AC-FEAT-007-05")
def test_the_working_time_notice_is_required_in_files_that_define_schedules(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    notice = "A planning estimate based on a simplified model of selected rules."
    (root / "README.md").write_text((root / "README.md").read_text() + f"\n{notice}\n")
    (root / "specs/FEAT-003-optimizer.md").write_text("status: approved\n")
    found = problems(root, "--wording")
    assert any("FEAT-003-optimizer.md" in item and "notice" in item for item in found)
    (root / "specs/FEAT-003-optimizer.md").write_text(f"status: approved\n\n{notice}\n")
    assert problems(root, "--wording") == []


@pytest.mark.ac("AC-FEAT-007-05")
def test_a_status_table_row_that_calls_a_not_implemented_feature_implemented_fails(
    tmp_path: Path,
) -> None:
    root = make_root(tmp_path)
    notice = "A planning estimate based on a simplified model of selected rules."
    readme = root / "README.md"
    readme.write_text(readme.read_text() + f"\n{notice}\n\n| FEAT-001 | implemented |\n")
    assert any("FEAT-001" in item and "implemented" in item for item in problems(root, "--wording"))


@pytest.mark.ac("AC-FEAT-007-05")
def test_a_deny_listed_term_in_any_markdown_file_fails(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    (root / "docs/notes.md").write_text("# Notes\n\nThis was a recruitment exercise.\n")
    assert any("docs/notes.md" in item for item in problems(root, "--wording"))
    (root / "docs/notes.md").write_text("# Notes\n\nRecruitments are not a word here either.\n")
    assert not any("docs/notes.md" in item for item in problems(root, "--wording"))  # whole words


@pytest.mark.ac("AC-FEAT-007-05")
@pytest.mark.ac("AC-FEAT-007-06")
def test_the_repository_passes_every_check() -> None:
    assert problems(ROOT, "--readme", "--development", "--wording") == []


@pytest.mark.ac("AC-FEAT-007-04")
def test_the_clean_clone_script_checks_every_step_of_the_readme_and_runs_in_ci_full() -> None:
    """The run is Gate 11 of `ci-full`; this pins what the script checks and that CI runs it."""
    script = (ROOT / "scripts/clean_clone_check.sh").read_text()
    assert "set -euo pipefail" in script
    for expected in (
        "unset",  # keys and settings of the machine never reach the app
        "http://localhost:8000/ready",
        "http://localhost:8000/health",
        "/api/v1/auth/login",
        '[[ "$drivers" == 5 ]]',
        "http://localhost:3000/login",
        '[[ "$status" == 200 ]]',
        "elapsed <= 600",
    ):
        assert expected in script, expected
    workflow = (ROOT / ".github/workflows/ci-full.yml").read_text()
    assert "bash scripts/clean_clone_check.sh --here" in workflow
    assert "python3 scripts/check_docs.py --readme --development --wording" in workflow


# --- FEAT-009: demo media ---------------------------------------------------------------------


def make_mp4(path: Path, seconds: float, padding: int = 0) -> None:
    """A minimal MP4: `ftyp`, then `moov` with an `mvhd` of the given duration, then padding."""
    mvhd = b"\x00\x00\x00\x00" + b"\x00" * 8 + struct.pack(">II", 1000, int(seconds * 1000))
    mvhd = struct.pack(">I4s", 8 + len(mvhd), b"mvhd") + mvhd + b"\x00" * 80
    moov = struct.pack(">I4s", 8 + len(mvhd), b"moov") + mvhd
    ftyp = struct.pack(">I4s4sI", 16, b"ftyp", b"isom", 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(ftyp + moov + b"\x00" * padding)


def make_png(path: Path, width: int = 1440, height: int = 900, padding: int = 0) -> None:
    head = (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I4sII", 13, b"IHDR", width, height)
        + b"\x08\x02\x00\x00\x00"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(head + b"\x00" * padding)


def make_gif(path: Path, padding: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"GIF89a" + struct.pack("<HH", 960, 600) + b"\x00" * padding)


def make_media(root: Path) -> None:
    media = root / "docs/media"
    make_mp4(media / "demo.mp4", 130)
    make_gif(media / "demo.gif")
    module = load()
    for name in module.SCREENSHOTS:
        make_png(media / "screenshots" / f"{name}.png")


@pytest.mark.ac("AC-FEAT-009-01")
@pytest.mark.ac("AC-FEAT-009-03")
def test_complete_media_within_the_limits_passes(tmp_path: Path) -> None:
    make_media(tmp_path)
    assert problems(tmp_path, "--media") == []


@pytest.mark.ac("AC-FEAT-009-01")
def test_no_video_and_no_gif_fails_but_one_of_them_is_enough(tmp_path: Path) -> None:
    make_media(tmp_path)
    (tmp_path / "docs/media/demo.mp4").unlink()
    assert problems(tmp_path, "--media") == []  # the GIF alone satisfies AC-01
    (tmp_path / "docs/media/demo.gif").unlink()
    assert any("neither demo.mp4 nor demo.gif" in item for item in problems(tmp_path, "--media"))


@pytest.mark.ac("AC-FEAT-009-01")
@pytest.mark.parametrize(
    ("seconds", "fails"), [(119, True), (120, False), (240, False), (241, True)]
)
def test_the_mp4_duration_must_be_120_to_240_seconds(
    tmp_path: Path, seconds: int, fails: bool
) -> None:
    make_media(tmp_path)
    make_mp4(tmp_path / "docs/media/demo.mp4", seconds)
    found = [item for item in problems(tmp_path, "--media") if "lasts" in item]
    assert bool(found) is fails


@pytest.mark.ac("AC-FEAT-009-01")
def test_a_file_that_is_not_an_mp4_has_no_readable_duration(tmp_path: Path) -> None:
    make_media(tmp_path)
    (tmp_path / "docs/media/demo.mp4").write_bytes(b"not a video")
    assert any("duration cannot be read" in item for item in problems(tmp_path, "--media"))


@pytest.mark.ac("AC-FEAT-009-01")
def test_the_size_limits_of_the_mp4_and_the_gif(tmp_path: Path) -> None:
    make_media(tmp_path)
    make_mp4(tmp_path / "docs/media/demo.mp4", 130, padding=25 * 1024 * 1024)
    make_gif(tmp_path / "docs/media/demo.gif", padding=10 * 1024 * 1024)
    found = problems(tmp_path, "--media")
    assert any("demo.mp4 is larger than 25 MB" in item for item in found)
    assert any("demo.gif is larger than 10 MB" in item for item in found)


@pytest.mark.ac("AC-FEAT-009-03")
def test_a_missing_screenshot_a_wrong_format_a_wrong_size_and_a_heavy_file_fail(
    tmp_path: Path,
) -> None:
    make_media(tmp_path)
    shots = tmp_path / "docs/media/screenshots"
    (shots / "05-ai-dispatcher-trace.png").unlink()
    (shots / "01-login.png").write_bytes(b"\xff\xd8 a jpeg, not a png")
    make_png(shots / "02-fleet.png", 1280, 800)
    make_png(shots / "03-driver-form.png", padding=1024 * 1024)
    found = problems(tmp_path, "--media")
    assert any("05-ai-dispatcher-trace.png is missing" in item for item in found)
    assert any("01-login.png is not a PNG" in item for item in found)
    assert any("02-fleet.png is 1280 x 800" in item for item in found)
    assert any("03-driver-form.png is larger than 1 MB" in item for item in found)
    assert len(found) == 4


DEMO_ROW = "| Demo video (`docs/media/demo.mp4` / `.gif`) and screenshots | {status} |\n"


def readme_with_demo(root: Path, section: str, status: str) -> None:
    readme = root / "README.md"
    change(readme, "## 8. Demo\n\n- text\n", f"## 8. Demo\n\n{section}\n")
    readme.write_text(readme.read_text() + DEMO_ROW.format(status=status))


@pytest.mark.ac("AC-FEAT-009-04")
def test_readme_demo_section_with_media_needs_an_inline_image_a_video_link_and_a_done_row(
    tmp_path: Path,
) -> None:
    root = make_root(tmp_path)
    make_media(root)
    good = "![The optimizer and a plan](docs/media/demo.gif)\n\n[Full video](docs/media/demo.mp4)\n"
    readme_with_demo(root, good, "\u2705 done")
    assert problems(root, "--readme") == []


@pytest.mark.ac("AC-FEAT-009-04")
def test_readme_demo_section_problems_are_each_reported(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    make_media(root)
    # No inline image, no video link and a row that still says planned.
    readme_with_demo(root, "Some words only.", "planned")
    found = problems(root, "--readme")
    assert any("no inline image from docs/media" in item for item in found)
    assert any("does not link docs/media/demo.mp4" in item for item in found)
    assert any("not marked done" in item for item in found)

    root = make_root(tmp_path / "second")
    make_media(root)
    readme_with_demo(
        root, "![](docs/media/demo.gif)\n![x](docs/media/missing.gif)\n", "\u2705 done"
    )
    found = problems(root, "--readme")
    assert any("has no alt text" in item for item in found)
    assert any("'docs/media/missing.gif' does not exist" in item for item in found)


@pytest.mark.ac("AC-FEAT-009-04")
def test_a_done_row_without_media_fails_and_a_planned_row_without_media_passes(
    tmp_path: Path,
) -> None:
    root = make_root(tmp_path)
    readme_with_demo(root, "Planned.", "\u2705 done")
    assert any("marked done, but no media exists" in item for item in problems(root, "--readme"))
    root = make_root(tmp_path / "second")
    readme_with_demo(root, "Planned.", "planned")
    assert problems(root, "--readme") == []
