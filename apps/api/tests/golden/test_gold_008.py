"""Exact assertions from specs/golden/GOLD-008.md section 4."""

import pytest

from .test_assertions import assert_golden


@pytest.mark.ac("AC-FEAT-003-37")
def test_gold_008() -> None:
    assert_golden(8)
