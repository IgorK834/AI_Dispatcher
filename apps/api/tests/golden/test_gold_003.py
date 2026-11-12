"""Exact assertions from specs/golden/GOLD-003.md section 4."""

import pytest

from .test_assertions import assert_golden


@pytest.mark.ac("AC-FEAT-003-32")
def test_gold_003() -> None:
    assert_golden(3)
