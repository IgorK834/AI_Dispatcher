"""FEAT-006 FR-23/FR-26 supporting checks: policy parsing, test-only fakes, AI-enabled rule.

All model ids here are fake placeholders; no provider is contacted (OQ-006-01).
"""

import json
from typing import Any

import pytest
from pydantic import ValidationError

from routepilot.agents import models as models_module
from routepilot.agents.models import ModelPolicy, ModelRegistry, ProviderFailure, Role
from routepilot.shared.config import Settings
from tests.agents.fakes import ScriptedModel

ROLES: tuple[Role, ...] = (
    "dispatcher",
    "freight_scout",
    "fleet_compliance",
    "route_planner",
    "explainer",
)


def settings(**values: Any) -> Settings:
    # Keys default to empty so a developer's environment variables cannot change the result.
    keys = {"google_api_key": "", "anthropic_api_key": "", "openai_api_key": ""}
    return Settings(app_env="test", _env_file=None, **{**keys, **values})


@pytest.mark.parametrize(
    "raw",
    [
        "{not json",
        '{"unknown_role": {"model": "google_genai:m"}}',
        '{"dispatcher": {"model": "no-provider"}}',
        '{"dispatcher": {"model": ":only-model"}}',
        '{"dispatcher": {"model": "google_genai:"}}',
        '{"dispatcher": {"model": "google_genai:m", "maxTokens": 0}}',
        '{"dispatcher": {"model": "google_genai:m", "timeoutS": 0}}',
        '{"dispatcher": {"model": "google_genai:m", "extra": 1}}',
        '{"dispatcher": {"model": "google_genai:m", "params": {"max_tokens": 9}}}',
        '{"dispatcher": {"model": "google_genai:m", "params": {"api_key": "x"}}}',
        '{"dispatcher": {"model": "google_genai:m", "params": {"max_retries": 5}}}',
        '{"fallback": {}}',
    ],
)
def test_policy_parsing_errors_are_rejected(raw: str) -> None:
    with pytest.raises(ValidationError):
        ModelPolicy.parse(raw)


def test_policy_resolves_role_default_and_fallback_entries() -> None:
    policy = ModelPolicy.parse(
        json.dumps(
            {
                "dispatcher": {"model": "google_genai:alpha", "maxTokens": 50, "timeoutS": 7},
                "default": {"model": "anthropic:beta"},
                "fallback": {"model": "openai:gamma"},
            }
        )
    )
    dispatcher = policy.for_role("dispatcher")
    assert (dispatcher.model, dispatcher.max_tokens, dispatcher.timeout_s) == (
        "google_genai:alpha",
        50,
        7,
    )
    # Roles that are not listed use the default entry.
    assert {policy.for_role(role).model for role in ROLES[1:]} == {"anthropic:beta"}
    assert policy.fallback is not None and policy.fallback.model == "openai:gamma"


def test_empty_policy_resolves_no_role() -> None:
    policy = ModelPolicy.parse("")
    assert policy.fallback is None
    for role in ROLES:
        with pytest.raises(ValueError, match="No model configured"):
            policy.for_role(role)


@pytest.mark.parametrize("app_env", ["local", "demo", "production"])
def test_fake_models_and_factories_are_rejected_outside_test_env(app_env: str) -> None:
    fake_policy = ModelPolicy.model_validate({"default": {"model": "fake:script"}})
    # model_construct skips the demo/production secret checks and reads no environment or .env.
    outside = Settings.model_construct(app_env=app_env)
    with pytest.raises(ValueError, match="test-only"):
        ModelRegistry(outside, fake_policy)
    real_policy = ModelPolicy.model_validate({"default": {"model": "google_genai:m"}})
    with pytest.raises(ValueError, match="test-only"):
        ModelRegistry(outside, real_policy, {"google_genai:m": lambda: ScriptedModel(script=[])})
    # The same policy and registration are accepted only with APP_ENV=test.
    registry = ModelRegistry(
        settings(), fake_policy, {"fake:script": lambda: ScriptedModel(script=[])}
    )
    assert registry.enabled


@pytest.mark.parametrize(
    ("policy", "keys", "enabled"),
    [
        ({"dispatcher": {"model": "google_genai:m"}}, {}, False),
        ({"dispatcher": {"model": "google_genai:m"}}, {"google_api_key": "k"}, True),
        ({"dispatcher": {"model": "anthropic:m"}}, {"google_api_key": "k"}, False),
        ({"dispatcher": {"model": "anthropic:m"}}, {"anthropic_api_key": "k"}, True),
        ({"dispatcher": {"model": "openai:m"}}, {"openai_api_key": "k"}, True),
        ({"default": {"model": "openai:m"}}, {"openai_api_key": "k"}, True),
        # Only the Dispatcher decides: other roles may point at a provider without a key.
        (
            {"dispatcher": {"model": "openai:m"}, "route_planner": {"model": "anthropic:m"}},
            {"openai_api_key": "k"},
            True,
        ),
        # No Dispatcher and no default: nothing resolves, so AI is off even with keys set.
        ({"route_planner": {"model": "openai:m"}}, {"openai_api_key": "k"}, False),
        ({}, {"openai_api_key": "k", "google_api_key": "k"}, False),
    ],
)
def test_ai_is_enabled_only_when_dispatcher_resolves_to_a_provider_with_a_key(
    policy: dict[str, Any], keys: dict[str, str], enabled: bool
) -> None:
    registry = ModelRegistry(settings(**keys), ModelPolicy.model_validate(policy))
    assert registry.enabled is enabled


def test_registry_reads_the_policy_from_the_environment_setting() -> None:
    raw = json.dumps({"default": {"model": "google_genai:m"}})
    registry = ModelRegistry(settings(agent_model_policy=raw, google_api_key="k"))
    assert registry.enabled
    assert not ModelRegistry(settings(agent_model_policy=raw, google_api_key="")).enabled


def test_build_chat_model_refuses_without_a_key_and_passes_policy_limits_with_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[tuple[str, dict[str, Any]]] = []

    def fake_init(model: str, **params: Any) -> ScriptedModel:
        captured.append((model, params))
        return ScriptedModel(script=[])

    monkeypatch.setattr(models_module, "init_chat_model", fake_init)
    policy = ModelPolicy.model_validate(
        {
            "dispatcher": {
                "model": "google_genai:alpha",
                "params": {"temperature": 0},
                "maxTokens": 40,
                "timeoutS": 9,
            },
            "route_planner": {"model": "anthropic:beta", "maxTokens": 30},
        }
    )
    with pytest.raises(ProviderFailure, match="AI_UNAVAILABLE"):
        ModelRegistry(settings(), policy).build_chat_model(policy.for_role("dispatcher"))
    assert captured == []

    registry = ModelRegistry(settings(google_api_key="g", anthropic_api_key="a"), policy)
    registry.build_chat_model(policy.for_role("dispatcher"))
    registry.build_chat_model(policy.for_role("route_planner"))
    (google_model, google), (anthropic_model, anthropic) = captured
    assert (google_model, anthropic_model) == ("alpha", "beta")
    assert google["model_provider"] == "google_genai" and anthropic["model_provider"] == "anthropic"
    # The policy owns the output cap, timeout and retries; the key comes from settings only.
    assert (google["max_tokens"], google["timeout"], google["api_key"]) == (40, 9, "g")
    assert google["temperature"] == 0
    # google-genai counts the first request as an attempt, so one means no retry.
    assert google["max_retries"] == 1 and anthropic["max_retries"] == 0
    assert anthropic["api_key"] == "a" and anthropic["max_tokens"] == 30
