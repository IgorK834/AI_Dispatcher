"""The Developer API counts contents only; the exact-count path must not send other fields."""

from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from routepilot.agents.models import ModelPolicy, ModelRegistry
from routepilot.agents.schemas import DispatcherDecision
from routepilot.shared.config import Settings


@pytest.mark.ac("AC-FEAT-006-11")
def test_google_count_sends_contents_only_and_includes_system_and_tool_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(_env_file=None, app_env="test", google_api_key="test-key-not-used")
    policy = ModelPolicy.model_validate(
        {"dispatcher": {"model": "google_genai:test-model", "params": {"thinking_level": "high"}}}
    )
    registry = ModelRegistry(settings, policy)
    model = registry.build_chat_model(policy.for_role("dispatcher"))
    seen: dict[str, Any] = {}

    def count_tokens(**kwargs: Any) -> SimpleNamespace:
        seen.update(kwargs)
        return SimpleNamespace(total_tokens=321)

    assert model.client is not None
    monkeypatch.setattr(model.client.models, "count_tokens", count_tokens)
    bound = model.bind_tools([DispatcherDecision], tool_choice="DispatcherDecision")
    count = registry._count(
        model,
        [SystemMessage("SYSTEM-MARKER"), HumanMessage("question")],
        dict(bound.kwargs),
        live_campaign=True,
    )
    assert count == 321
    assert set(seen) == {"model", "contents"}  # no config: the endpoint rejects it
    text = " ".join(part.text or "" for item in seen["contents"] for part in item.parts)
    assert "SYSTEM-MARKER" in text and "DispatcherDecision" in text
