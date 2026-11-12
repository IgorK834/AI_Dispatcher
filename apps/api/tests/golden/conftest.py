"""Fixtures shared by the golden tests."""

from collections.abc import Callable

import pytest

from routepilot.optimization.engine import optimize
from routepilot.optimization.engine.models import EngineResult, EngineSnapshot


@pytest.fixture
def run() -> Callable[[EngineSnapshot], tuple[EngineResult, bool]]:
    """Run the production engine twice; returns the result and whether both runs are identical."""

    def runner(source: EngineSnapshot) -> tuple[EngineResult, bool]:
        first = optimize(source)
        return first, optimize(source) == first

    return runner
