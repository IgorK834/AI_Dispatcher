"""Freight Scout tools through the real registry: search_offers, get_offer, offer_quality."""

import json
import re
from datetime import timedelta

import pytest

from routepilot.agents.tools import contracts
from routepilot.freight.service import FreightOfferCreate
from tests.agents.conftest import GeneratedOffers, ToolEnv

SCOUT = "freight_scout"
UNTRUSTED = re.compile(r"<untrusted_text>(.*)</untrusted_text>", re.DOTALL)


def poisoned(env: ToolEnv, offers: GeneratedOffers) -> str:
    source_id = offers.by_tag["PROMPT_INJECTION"][0]
    assert "SUSPICIOUS_TEXT" in next(
        offer.quality_flags
        for offer in env.freight.all_offers()
        if offer.source_offer_id == source_id
    )
    return source_id


@pytest.mark.ac("AC-FEAT-006-26")
def test_search_offers_is_bounded_free_of_text_and_strict(
    tool_env: ToolEnv, generated_offers: GeneratedOffers
) -> None:
    assert len(generated_offers.ids) == 150
    result = tool_env.call(SCOUT, "search_offers", origin_country="PL")
    direct = tool_env.registry.offers.search(origin_country="PL")
    assert len(result["offers"]) == 20 and result["truncated"] is True
    assert result["total_matching"] == direct["total_matching"] > 20, "facts come from the service"
    # No free text: exactly the summary fields, and no remark or description appears anywhere.
    expected = set(contracts.OfferSummary.model_fields)
    assert all(set(offer) == expected for offer in result["offers"])
    dump = json.dumps(result).lower()
    for offer in tool_env.freight.all_offers():
        for text in (offer.description, offer.public_remark):
            assert not text or text.lower() not in dump
    assert "ignore previous instructions" not in dump
    # The suspicious flag is part of the summary and set only for flagged offers.
    flagged = tool_env.call(SCOUT, "search_offers", origin_country="PL", limit=20)
    assert all(isinstance(offer["suspicious"], bool) for offer in flagged["offers"])
    # An explicit limit is honoured and a result that fits is not truncated.
    few = tool_env.call(SCOUT, "search_offers", origin_country="PL", limit=3)
    assert len(few["offers"]) == 3 and few["truncated"] is True
    assert tool_env.call(SCOUT, "search_offers", origin_city="Nowhere At All")["offers"] == []


@pytest.mark.ac("AC-FEAT-006-26")
@pytest.mark.parametrize(
    "arguments",
    [
        {"unknown_filter": True},
        {"limit": 21},
        {"limit": 0},
        {"limit": "20"},
        {"radius_km": 501},
        {"max_weight_kg": -1},
    ],
)
def test_search_offers_rejects_extra_or_invalid_input(
    tool_env: ToolEnv, arguments: dict[str, object]
) -> None:
    result = tool_env.call(SCOUT, "search_offers", **arguments)
    assert result["error"]["code"] == "VALIDATION_ERROR", arguments


@pytest.mark.ac("AC-FEAT-006-26")
def test_search_offers_unknown_driver_reference_is_not_found(tool_env: ToolEnv) -> None:
    assert tool_env.call(SCOUT, "search_offers", near_driver_ref="D9")["error"]["code"] == (
        "NOT_FOUND"
    )
    near = tool_env.call(SCOUT, "search_offers", near_driver_ref="D1", radius_km=500)
    assert "error" not in near


@pytest.mark.ac("AC-FEAT-006-27")
def test_get_offer_returns_detail_with_provenance_and_quoted_untrusted_text(
    tool_env: ToolEnv, generated_offers: GeneratedOffers
) -> None:
    source_id = poisoned(tool_env, generated_offers)
    detail = tool_env.call(SCOUT, "get_offer", offer_id=source_id)
    assert "error" not in detail
    assert detail["offer_id"] == source_id and detail["suspicious"] is True
    assert detail["provenance"] and all(isinstance(v, str) for v in detail["provenance"].values())
    assert 1 <= len(detail["stops"]) <= 2 and detail["status"] == "open"
    # The remark is quoted external data inside one field of at most 300 characters.
    quoted = detail["untrusted_text"]
    assert len(quoted) <= 300 and UNTRUSTED.fullmatch(quoted)
    remark = next(
        offer.public_remark
        for offer in tool_env.freight.all_offers()
        if offer.source_offer_id == source_id
    )
    assert remark and remark[:40].lower() in quoted.lower()
    outside = json.dumps({key: value for key, value in detail.items() if key != "untrusted_text"})
    assert remark[:40].lower() not in outside.lower(), "free text only in untrusted_text"
    assert set(detail) == set(contracts.OfferDetail.model_fields)
    for name in ("MOCK-999999", "MOCK-12", "not-an-offer"):
        assert tool_env.call(SCOUT, "get_offer", offer_id=name)["error"]["code"] == "NOT_FOUND"
    assert tool_env.call(SCOUT, "get_offer", offer_id=source_id, extra=1)["error"]["code"] == (
        "VALIDATION_ERROR"
    )


@pytest.mark.ac("AC-FEAT-006-27")
def test_get_offer_truncates_long_text_and_hides_private_data(tool_env: ToolEnv) -> None:
    driver, window = tool_env.driver, tool_env.driver.state.available_from
    remark = f"{driver.name} {driver.phone} private@example.test {'Long remark. ' * 30}"
    long_offer = tool_env.freight.create_offer(
        FreightOfferCreate(
            description="Synthetic long remark",
            revenue={"amountMinor": 90000, "currency": "EUR"},
            weight_kg=100,
            pallet_count=1,
            pallet_type="EUR_1200x800",
            required_body_types=["CURTAIN_SIDER"],
            public_remark=remark,
            stops=[
                {
                    "stopType": "LOADING",
                    "city": "Longtext origin",
                    "countryCode": "PL",
                    "lat": 51.0,
                    "lon": 17.0,
                    "windowStart": window,
                    "windowEnd": window + timedelta(hours=8),
                },
                {
                    "stopType": "UNLOADING",
                    "city": "Opole",
                    "countryCode": "PL",
                    "lat": 50.6751,
                    "lon": 17.9213,
                    "windowStart": window + timedelta(hours=1),
                    "windowEnd": window + timedelta(hours=16),
                },
            ],
        ),
        str(tool_env.user),
    )
    assert len(long_offer.public_remark or "") > 300
    found = tool_env.call(SCOUT, "search_offers", origin_city="Longtext origin")
    (summary,) = found["offers"]
    detail = tool_env.call(SCOUT, "get_offer", offer_id=summary["offer_id"])
    assert len(detail["untrusted_text"]) <= 300
    assert "Long remark." in detail["untrusted_text"] and "[email]" in detail["untrusted_text"]
    # Names, phone numbers and e-mail addresses never reach the model, even inside the remark.
    for secret in (driver.name, driver.phone, "private@example.test"):
        assert secret not in json.dumps(detail)


@pytest.mark.ac("AC-FEAT-006-28")
def test_offer_quality_flags_missing_price_and_coordinates_and_passes_complete_offers(
    tool_env: ToolEnv, generated_offers: GeneratedOffers
) -> None:
    window = tool_env.driver.state.available_from
    stops = [
        {
            "stopType": "LOADING",
            "city": "Unknown generated city",
            "countryCode": "PL",
            "windowStart": window,
            "windowEnd": window + timedelta(hours=8),
        },
        {
            "stopType": "UNLOADING",
            "city": "Another unknown city",
            "countryCode": "PL",
            "windowStart": window + timedelta(hours=1),
            "windowEnd": window + timedelta(hours=16),
        },
    ]
    tool_env.freight.create_offer(
        FreightOfferCreate(
            description="Synthetic without coordinates",
            revenue={"amountMinor": 90000, "currency": "EUR"},
            weight_kg=100,
            pallet_count=1,
            pallet_type="EUR_1200x800",
            required_body_types=["CURTAIN_SIDER"],
            stops=stops,
        ),
        str(tool_env.user),
    )
    (no_coordinates,) = tool_env.call(SCOUT, "search_offers", origin_city="Unknown generated city")[
        "offers"
    ]
    no_price = generated_offers.by_tag["NO_PRICE"][0]
    complete = next(
        source_id
        for source_id in generated_offers.ids
        if not {"NO_PRICE", "NO_COORDINATES", "NO_PALLETS"}
        & {tag for tag, ids in generated_offers.by_tag.items() if source_id in ids}
    )
    refs = [no_price, no_coordinates["offer_id"], complete, "MOCK-999999"]
    result = tool_env.call(SCOUT, "offer_quality", offer_ids=refs)
    by_ref = {item["offer_id"]: item for item in result["items"]}
    assert set(by_ref) == set(refs) and len(result["items"]) == 4
    assert by_ref[no_price]["usable_by_engine"] is False
    assert by_ref[no_price]["reason_code"] == "MISSING_REVENUE"
    assert by_ref[no_coordinates["offer_id"]]["usable_by_engine"] is False
    assert by_ref[no_coordinates["offer_id"]]["reason_code"] == "MISSING_COORDINATES"
    assert by_ref[complete]["usable_by_engine"] is True and by_ref[complete]["reason_code"] is None
    assert by_ref["MOCK-999999"]["reason_code"] == "NOT_FOUND", "unknown ids are listed per item"
    too_many = tool_env.call(SCOUT, "offer_quality", offer_ids=[complete] * 21)
    assert too_many["error"]["code"] == "VALIDATION_ERROR"
