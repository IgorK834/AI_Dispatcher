"""MockFreightProvider: offline search over the generated payload (FEAT-002 FR-22)."""

from datetime import UTC, date, datetime
from typing import Any

import pytest

from routepilot.freight.domain.models import FreightSearchQuery
from routepilot.freight.generator import generate_offers
from routepilot.freight.ports import FreightProvider
from routepilot.integrations.timocom.mock import MockFreightProvider

FETCHED = datetime(2026, 11, 16, 6, 0, tzinfo=UTC)
VAN = "VEHICLE_UP_TO_3_5_T"


@pytest.fixture(scope="module")
def generated() -> tuple[dict[str, Any], dict[str, Any]]:
    return generate_offers(20261109, date(2026, 11, 16))


@pytest.fixture
def provider(generated: tuple[dict[str, Any], dict[str, Any]]) -> MockFreightProvider:
    return MockFreightProvider(*generated, FETCHED)


def ids(provider: MockFreightProvider, **query: Any) -> list[str]:
    return [r.source_offer_id for r in provider.search(FreightSearchQuery(**query))]


@pytest.mark.ac("AC-FEAT-002-20")
def test_search_for_the_van_type_and_an_origin_area_yields_only_matching_records(
    provider: MockFreightProvider,
    generated: tuple[dict[str, Any], dict[str, Any]],
    no_network: list[str],
) -> None:
    payload, _ = generated
    records = list(provider.search(FreightSearchQuery(vehicle_type=VAN, origin="PL")))
    expected = {
        o["id"]
        for o in payload["payload"]
        if VAN in o["vehicleProperties"]["type"]
        and o["loadingPlaces"][0]["address"]["country"] == "PL"
    }
    assert records and {r.source_offer_id for r in records} == expected
    assert len(records) < 150  # the area really filters
    for record in records:
        assert record.source == "mock_timocom_v3" and record.fetched_at == FETCHED
        assert record.payload["loadingPlaces"][0]["address"]["country"] == "PL"
        assert VAN in record.payload["vehicleProperties"]["type"]
    assert provider.lookup(["MOCK-000001", "anything"]) == []
    assert provider.lookup([]) == []
    assert no_network == []  # no socket was opened, nor a name looked up


@pytest.mark.ac("AC-FEAT-002-20")
def test_an_origin_city_a_radius_and_the_other_filters_combine(
    provider: MockFreightProvider, generated: tuple[dict[str, Any], dict[str, Any]]
) -> None:
    payload, _ = generated
    offers = {o["id"]: o for o in payload["payload"]}
    in_katowice = ids(provider, origin="katowice")
    assert in_katowice
    assert all(offers[i]["loadingPlaces"][0]["address"]["city"] == "Katowice" for i in in_katowice)

    near = set(ids(provider, origin="Katowice", radius_km=120))
    assert set(in_katowice) <= near and len(near) > len(in_katowice)  # neighbours within 120 km

    heavy = ids(provider, max_weight_kg=300)
    assert heavy and all(offers[i]["weight_t"] * 1000 <= 300 for i in heavy)
    assert set(ids(provider, origin="PL", max_weight_kg=300)) <= set(heavy)

    monday = datetime(2026, 11, 16, tzinfo=UTC)
    early = ids(provider, loading_from=monday, loading_to=monday)
    assert early and all(
        offers[i]["loadingPlaces"][0]["earliestLoadingDate"]
        <= "2026-11-16"
        <= offers[i]["loadingPlaces"][0]["latestLoadingDate"]
        for i in early
    )
    assert set(ids(provider)) == set(offers)  # an empty query returns all van offers

    nowhere = ids(provider, destination="Atlantis")
    assert nowhere == []


@pytest.mark.ac("AC-FEAT-002-20")
def test_another_vehicle_type_yields_nothing_and_search_is_repeatable(
    provider: MockFreightProvider,
) -> None:
    assert ids(provider, vehicle_type="VEHICLE_UP_TO_12_T") == []
    first = ids(provider, origin="PL")
    assert first == ids(provider, origin="PL")  # a lazy iterator, but a stable order


@pytest.mark.ac("AC-FEAT-002-20")
def test_the_provider_satisfies_the_port_and_declares_what_it_can_do(
    provider: MockFreightProvider,
) -> None:
    port: FreightProvider = provider
    assert port.name == "mock_timocom_v3"
    capabilities = provider.capabilities()
    assert capabilities.search is True and capabilities.lookup is False
