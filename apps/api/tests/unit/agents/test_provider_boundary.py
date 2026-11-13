"""FR-23: only agents/models.py may import a chat-model provider package (import-linter)."""

import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

API = Path(__file__).resolve().parents[3]
CONTRACT = "provider SDKs only in agents.models"


def lint(root: Path, module: tuple[str, str] | None = None) -> tuple[int, str]:
    """Run lint-imports on a copy of the package, optionally with one extra module added."""
    shutil.copytree(
        API / "src/routepilot", root / "routepilot", ignore=shutil.ignore_patterns("__pycache__")
    )
    shutil.copy(API / "pyproject.toml", root / "pyproject.toml")
    if module is not None:
        (root / "routepilot" / module[0]).write_text(module[1])
    result = subprocess.run(
        [str(API / ".venv/bin/lint-imports"), "--no-cache"],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root)},
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout + result.stderr


def test_contract_exempts_only_the_models_module() -> None:
    contracts = tomllib.loads((API / "pyproject.toml").read_text())["tool"]["importlinter"][
        "contracts"
    ]
    contract = next(item for item in contracts if item["name"] == CONTRACT)
    assert contract["type"] == "forbidden" and contract["source_modules"] == ["routepilot"]
    assert {"langchain_google_genai", "langchain_anthropic", "langchain_openai", "google"} <= set(
        contract["forbidden_modules"]
    )
    # Every exemption names agents.models as the importer; nothing else is allowed through.
    assert contract["ignore_imports"]
    assert all(
        item.startswith("routepilot.agents.models -> ") for item in contract["ignore_imports"]
    )


def test_real_package_keeps_the_contract(tmp_path: Path) -> None:
    code, output = lint(tmp_path)
    assert code == 0, output
    assert f"{CONTRACT} KEPT" in output


@pytest.mark.parametrize(
    ("path", "statement"),
    [
        ("agents/violation.py", "import langchain_openai\n"),
        ("agents/violation.py", "from langchain_anthropic import ChatAnthropic\n"),
        ("agents/violation.py", "from langchain_google_genai import ChatGoogleGenerativeAI\n"),
        ("agents/violation.py", "from google.genai.types import Part\n"),
        # A lazy import inside a function is still an import.
        ("agents/violation.py", "def build() -> None:\n    import langchain_openai\n"),
        ("fleet/violation.py", "import langchain_openai\n"),
    ],
)
def test_any_other_module_importing_a_provider_package_breaks_the_contract(
    tmp_path: Path, path: str, statement: str
) -> None:
    code, output = lint(tmp_path, (path, statement))
    assert code == 1, output
    assert f"{CONTRACT} BROKEN" in output
