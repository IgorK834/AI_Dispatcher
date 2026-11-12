"""AC-FEAT-003-14 profile selection examples."""

import pytest

from routepilot.compliance.profiles import choose_profile


@pytest.mark.ac("AC-FEAT-003-14")
def test_profile_choice_uses_every_country_in_the_plan() -> None:
    assert choose_profile({"PL"}, "PL").profile_id == "pl_domestic_employee_v1"
    assert choose_profile({"PL", "DE"}, "PL").profile_id == "eu561_van_international_v1"
    assert choose_profile({"CZ", "PL"}, "PL").profile_id == "eu561_van_international_v1"


@pytest.mark.ac("AC-FEAT-003-14")
def test_unresolved_start_country_is_foreign() -> None:
    assert choose_profile(None, "PL").profile_id == "eu561_van_international_v1"
