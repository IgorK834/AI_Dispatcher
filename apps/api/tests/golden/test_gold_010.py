"""Exact assertions from specs/golden/GOLD-010.md section 4."""

import pytest

from .test_assertions import assert_golden


@pytest.mark.ac("AC-FEAT-003-39")
def test_gold_010() -> None:
    assert_golden(10)
