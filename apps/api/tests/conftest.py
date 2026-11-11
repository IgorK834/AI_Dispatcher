"""Deterministic test configuration; no external services."""

import os

import pytest
from hypothesis import settings

os.environ["APP_ENV"] = "test"
settings.register_profile("dev", max_examples=50, derandomize=True)
settings.register_profile("ci", max_examples=100, derandomize=True)
settings.register_profile("nightly", max_examples=1000, derandomize=True)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Include AC IDs in JUnit so trace.py can associate failures with criteria."""
    for item in items:
        for marker in item.iter_markers(name="ac"):
            item.user_properties.extend(("ac", identifier) for identifier in marker.args)
