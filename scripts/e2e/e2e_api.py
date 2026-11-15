"""The API of the Playwright run (FEAT-007 FR-3, OQ-007-04): the real application, with the chat
models switchable between "none" and scripted, so that one stack serves both browser scenarios.

Usage (from `apps/api`, with `APP_ENV=test`): `uv run python ../../scripts/e2e/e2e_api.py PORT`

It is the production composition (`create_app`: database, services, engine, tools, graph and
approval gate). It starts with no chat model at all, exactly like an installation without a model
key, so the "AI is off" path is the real one. The `@ai-fake` spec calls `GET /__e2e/ai/on` to
register the scripted offline models of `evals/` (scenario `approval-driver`: the run reads the
fleet and the offers, optimises one driver and stops at `approval_required`) and `GET /__e2e/ai/off`
to remove them again. `on` also lets the scripted models play their script from the start, because
they remember what they already did. These routes exist only in this test launcher, never in the
application, and the scripted models are accepted only with `APP_ENV=test`.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = "approval-driver"


def main(port: int) -> None:
    for path in (ROOT, ROOT / "apps" / "api"):
        sys.path.insert(0, str(path))
    import uvicorn
    from evals.fakes import offline_registry
    from evals.schema import load_scenarios

    from routepilot.agents.models import ModelPolicy
    from routepilot.main import create_app
    from routepilot.shared.config import Settings

    settings = Settings(_env_file=None)
    if settings.app_env != "test":
        raise SystemExit("The scripted models are accepted only with APP_ENV=test.")
    scenario = next(item for item in load_scenarios(ROOT / "evals") if item.id == SCENARIO)
    registry = offline_registry(settings, scenario)
    scripted = registry.policy
    controller = registry.factories["fake:eval-dispatcher"]().controller
    offers = list(controller["offer_ids"])
    registry.policy = ModelPolicy.parse("")  # no model: the AI is off until a spec switches it on

    app = create_app(settings, model_registry=registry)

    @app.get("/__e2e/ai/on", include_in_schema=False)
    def ai_on() -> dict[str, str]:
        controller.clear()
        controller["offer_ids"] = offers
        registry.policy = scripted
        return {"ai": "on"}

    @app.get("/__e2e/ai/off", include_in_schema=False)
    def ai_off() -> dict[str, str]:
        registry.policy = ModelPolicy.parse("")
        return {"ai": "off"}

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main(int(sys.argv[1]))
