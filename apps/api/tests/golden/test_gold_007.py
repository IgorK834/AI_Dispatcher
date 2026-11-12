"""Exact assertions from specs/golden/GOLD-007.md section 4."""

import pytest

from .test_assertions import assert_golden


@pytest.mark.ac("AC-FEAT-003-36")
def test_gold_007() -> None:
    assert_golden(7)
