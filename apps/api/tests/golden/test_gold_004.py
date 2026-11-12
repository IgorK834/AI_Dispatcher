"""Exact assertions from specs/golden/GOLD-004.md section 4."""

import pytest

from .test_assertions import assert_golden


@pytest.mark.ac("AC-FEAT-003-33")
def test_gold_004() -> None:
    assert_golden(4)
