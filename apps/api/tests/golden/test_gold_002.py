"""Exact assertions from specs/golden/GOLD-002.md section 4."""

import pytest

from .test_assertions import assert_golden


@pytest.mark.ac("AC-FEAT-003-31")
def test_gold_002() -> None:
    assert_golden(2)
