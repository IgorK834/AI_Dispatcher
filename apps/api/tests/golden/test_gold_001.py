"""Exact assertions from specs/golden/GOLD-001.md section 4."""

import pytest

from .test_assertions import assert_golden


@pytest.mark.ac("AC-FEAT-003-30")
def test_gold_001() -> None:
    assert_golden(1)
