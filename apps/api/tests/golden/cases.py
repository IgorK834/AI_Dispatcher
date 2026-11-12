"""Entry point for code that wants a golden input by number; the inputs live in fixtures/."""

from importlib import import_module

from routepilot.optimization.engine.models import EngineSnapshot


def case(number: int) -> EngineSnapshot:
    return import_module(f".fixtures.gold_{number:03d}", package=__package__).build()
