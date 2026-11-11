"""AC-FEAT-000-10: workflow security and gate structure."""

import re
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
