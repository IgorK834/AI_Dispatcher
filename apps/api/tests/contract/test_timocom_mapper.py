import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from routepilot.freight.domain.models import MappingFailure, NormalizedOffer, RawOfferRecord
from routepilot.integrations.timocom.mapper import TimocomV3Mapper


def raw() -> dict[str, object]:
    data = json.loads(
        (Path(__file__).parents[1] / "fixtures/timocom/find_freight_offers.json").read_text()
    )["example"]["payload"][0]
    # The source example has two LOADING stops (documented in its annotation).
    # This explicit adaptation exercises mapping; the unchanged example must fail.
    data["loadingPlaces"][-1]["loadingType"] = "UNLOADING"
    return data


def mapped(data: dict[str, object]) -> NormalizedOffer | MappingFailure:
    return TimocomV3Mapper().to_domain(
        RawOfferRecord(
            source="mock_timocom_v3",
            source_offer_id=str(data["id"]),
            payload=data,
            fetched_at=datetime(2026, 11, 11, tzinfo=UTC),
        )
    )


@pytest.mark.ac("AC-FEAT-002-09")
def test_official_example_maps_with_explicit_stop_correction() -> None:
    result = mapped(raw())
    assert isinstance(result, NormalizedOffer)
    assert result.revenue and result.revenue.amount_minor == 150
    assert result.weight_kg == 5550 and result.stops[0].lat == 41.98311
    assert result.field_provenance["source_offer_id"] == "source"
    data = raw()
    data["loadingPlaces"][-1]["loadingType"] = "LOADING"
    assert isinstance(mapped(data), MappingFailure)


@pytest.mark.ac("AC-FEAT-002-10")
@pytest.mark.ac("AC-FEAT-002-11")
@pytest.mark.ac("AC-FEAT-002-12")
def test_tolerance_fallback_and_failure() -> None:
    data = copy.deepcopy(raw())
    data["creationDateTime "] = data.pop("creationDateTime")
    data["distance_km"] = 4711
    data.pop("price")
    data["length_m"] = 1.7
    for place in data["loadingPlaces"]:
        place["address"].update(city="Katowice", country="PL", geoCoordinate=None)
        place.update(
            earliestLoadingDate="2026-11-17", latestLoadingDate="2026-11-17", startTime="08:15:22Z"
        )
    result = mapped(data)
    assert isinstance(result, NormalizedOffer)
    assert result.revenue is None and "revenue" in result.missing_fields
    assert result.pallet_count == 5 and result.stops[0].lat == 50.2649
    assert {"TIME_FORMAT_TOLERATED", "KEY_WHITESPACE_TOLERATED", "PALLETS_DERIVED"} <= set(
        result.quality_flags
    )
    assert result.stops[0].window_start == datetime(2026, 11, 17, 7, 15, tzinfo=UTC)
    data["loadingPlaces"][0]["address"].update(city="Unknown Place", country="DE")
    data["loadingPlaces"][0]["startTime"] = "08:00"
    data["loadingPlaces"][0]["endTime"] = None
    result = mapped(data)
    assert isinstance(result, NormalizedOffer) and result.stops[0].lat is None
    assert result.stops[0].window_start.hour == 7 and result.stops[0].timezone == "Europe/Berlin"
    assert (
        "MISSING_COORDINATES" in result.quality_flags
        and "TIME_WINDOW_DAY_ONLY" in result.quality_flags
    )
    data["loadingPlaces"] = []
    assert isinstance(mapped(data), MappingFailure)
