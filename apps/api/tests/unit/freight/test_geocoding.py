import pytest
from pydantic import ValidationError

from routepilot.freight.generator import CITIES
from routepilot.freight.geocoding import CityTable, city_table, geocode, timezone_for_country


@pytest.mark.ac("AC-FEAT-002-08")
def test_committed_city_schema_and_exact_coordinates() -> None:
    table = CityTable.model_validate(city_table())
    assert len(table.cities) == 39
    assert {
        (city.name, city.country_code, city.lat, city.lon, city.timezone) for city in table.cities
    } == set(CITIES)
    assert geocode("kAtOwIcE", "pl") == (50.2649, 19.0238)
    assert geocode("unknown", "PL") is None
    assert timezone_for_country("DE") == "Europe/Berlin"
    data = city_table().copy()
    data["cities"] = [data["cities"][0], data["cities"][0]]
    with pytest.raises(ValidationError, match="duplicate city/country"):
        CityTable.model_validate(data)
