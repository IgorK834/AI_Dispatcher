"""Idempotent import through the provider port and the shared mapper (FEAT-002 FR-23, FR-24)."""

import copy
import hashlib
import json
import re
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from sqlalchemy import MetaData, Table, func, select, text
from sqlalchemy.engine import Engine

from routepilot.bootstrap import DemoDataService
from routepilot.fleet.service import FleetService
from routepilot.freight.domain.models import FreightSearchQuery, RawOfferRecord
from routepilot.freight.generator import generate_offers
from routepilot.freight.service import ImportService
from routepilot.identity.service import IdentityService
from routepilot.integrations.timocom.mapper import TimocomV3Mapper
from routepilot.integrations.timocom.mock import MockFreightProvider
from routepilot.shared.clock import FixedClock
from routepilot.shared.config import Settings
from routepilot.shared.db.engine import make_engine, migration_config

CLOCK = FixedClock(datetime(2026, 11, 16, 6, 0, tzinfo=UTC))


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    url = f"sqlite:///{tmp_path / 'import.db'}"
    command.upgrade(migration_config(url), "head")
    db = make_engine(url)
    yield db
    db.dispose()


@pytest.fixture
def generated() -> tuple[dict[str, Any], dict[str, Any]]:
    return generate_offers(20261109, date(2026, 11, 16))


def service(engine: Engine) -> ImportService:
    return ImportService(engine, CLOCK, TimocomV3Mapper())


def counts(engine: Engine, *names: str) -> dict[str, int]:
    metadata = MetaData()
    with engine.connect() as connection:
        return {
            name: connection.scalar(
                select(func.count()).select_from(Table(name, metadata, autoload_with=engine))
            )
            or 0
            for name in names
        }


REVENUE_SQL = "SELECT revenue_amount_minor, version FROM freight_offers WHERE source_offer_id = :i"
TABLES = ("freight_offers", "freight_stops", "raw_freight_records")


class ListProvider:
    """Any list of raw payloads behind the provider port."""

    name = "mock_timocom_v3"

    def __init__(self, payloads: list[dict[str, Any]], enrichment: dict[str, Any]) -> None:
        self.payloads, self.enrichment = payloads, enrichment

    def search(self, query: FreightSearchQuery) -> Iterator[RawOfferRecord]:
        for payload in self.payloads:
            yield RawOfferRecord(
                source=self.name,
                source_offer_id=payload["id"],
                payload=payload,
                fetched_at=CLOCK.now(),
                enrichment=self.enrichment.get(payload["id"], {}),
            )

    def lookup(self, source_offer_ids: list[str]) -> list[RawOfferRecord]:
        return []


@pytest.mark.ac("AC-FEAT-002-13")
def test_importing_twice_creates_nothing_the_second_time(
    engine: Engine, generated: tuple[dict[str, Any], dict[str, Any]]
) -> None:
    provider = MockFreightProvider(*generated, CLOCK.now())
    importer = service(engine)

    first = importer.run(provider)
    after_first = counts(engine, *TABLES)
    second = importer.run(provider)

    assert first.counts == {"imported": 150, "updated": 0, "unchanged": 0, "failed": 0}
    assert second.counts == {"imported": 0, "updated": 0, "unchanged": 150, "failed": 0}
    assert (
        after_first
        == counts(engine, *TABLES)
        == {
            "freight_offers": 150,
            "freight_stops": 300,
            "raw_freight_records": 150,
        }
    )
    assert counts(engine, "import_batches") == {"import_batches": 2}
    assert first.id != second.id
    assert first.status == second.status == "completed" and first.source == "mock_timocom_v3"


@pytest.mark.ac("AC-FEAT-002-13")
def test_the_hash_is_computed_over_canonical_json_not_over_key_order(
    engine: Engine, generated: tuple[dict[str, Any], dict[str, Any]]
) -> None:
    payload, enrichment = generated
    importer = service(engine)
    importer.run(MockFreightProvider(payload, enrichment, CLOCK.now()))
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT source_offer_id, payload, payload_sha256 FROM raw_freight_records")
        ).all()
    by_id = {row.source_offer_id: row for row in rows}
    for offer in payload["payload"][:20]:
        canonical = json.dumps(offer, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        assert by_id[offer["id"]].payload_sha256 == hashlib.sha256(canonical.encode()).hexdigest()
    # The same content with reversed key order is still "unchanged".
    reordered = {
        "meta": payload["meta"],
        "payload": [dict(reversed(list(o.items()))) for o in payload["payload"]],
    }
    again = importer.run(MockFreightProvider(reordered, enrichment, CLOCK.now()))
    assert again.counts["unchanged"] == 150 and again.counts["imported"] == 0


@pytest.mark.ac("AC-FEAT-002-14")
def test_a_changed_price_adds_a_raw_record_and_updates_the_offer(
    engine: Engine, generated: tuple[dict[str, Any], dict[str, Any]]
) -> None:
    payload, enrichment = generated
    importer = service(engine)
    importer.run(MockFreightProvider(payload, enrichment, CLOCK.now()))
    target = next(o for o in payload["payload"] if "price" in o)
    with engine.connect() as connection:
        before = connection.execute(
            text(REVENUE_SQL),
            {"i": target["id"]},
        ).one()

    changed = copy.deepcopy(payload)
    edited = next(o for o in changed["payload"] if o["id"] == target["id"])
    edited["price"]["amount"] += 17
    batch = importer.run(MockFreightProvider(changed, enrichment, CLOCK.now()))

    assert batch.counts == {"imported": 0, "updated": 1, "unchanged": 149, "failed": 0}
    with engine.connect() as connection:
        after = connection.execute(
            text(REVENUE_SQL),
            {"i": target["id"]},
        ).one()
        raw = connection.execute(
            text("SELECT payload_sha256 FROM raw_freight_records WHERE source_offer_id = :i"),
            {"i": target["id"]},
        ).all()
    assert after.revenue_amount_minor == before.revenue_amount_minor + 1700
    assert after.version == before.version + 1
    assert len({r.payload_sha256 for r in raw}) == len(raw) == 2  # both payloads are kept
    assert counts(engine, *TABLES) == {  # no duplicate offer, no duplicate stops
        "freight_offers": 150,
        "freight_stops": 300,
        "raw_freight_records": 151,
    }


@pytest.mark.ac("AC-FEAT-002-14")
def test_a_record_that_fails_mapping_is_counted_and_creates_nothing(
    engine: Engine, generated: tuple[dict[str, Any], dict[str, Any]]
) -> None:
    payload, enrichment = generated
    broken = copy.deepcopy(payload["payload"][0])
    broken["id"] = "MOCK-999999"
    broken["loadingPlaces"] = broken["loadingPlaces"][:1]  # one loading place
    wrong_weight = copy.deepcopy(payload["payload"][1])
    wrong_weight["id"] = "MOCK-999998"
    wrong_weight["weight_t"] = "heavy"
    provider = ListProvider([broken, wrong_weight, *payload["payload"][2:12]], enrichment)

    batch = service(engine).run(provider)

    assert batch.counts == {"imported": 10, "updated": 0, "unchanged": 0, "failed": 2}
    with engine.connect() as connection:
        ids = {r[0] for r in connection.execute(text("SELECT source_offer_id FROM freight_offers"))}
        raw_ids = {
            r[0]
            for r in connection.execute(text("SELECT source_offer_id FROM raw_freight_records"))
        }
    assert not ids & {"MOCK-999999", "MOCK-999998"}
    assert not raw_ids & {"MOCK-999999", "MOCK-999998"}  # a failure is never stored as an offer
    assert counts(engine, *TABLES) == {
        "freight_offers": 10,
        "freight_stops": 20,
        "raw_freight_records": 10,
    }


@pytest.mark.ac("AC-FEAT-002-14")
def test_a_duplicate_id_inside_one_payload_fails_the_second_record(
    engine: Engine, generated: tuple[dict[str, Any], dict[str, Any]]
) -> None:
    # FEAT-002 §8: the second record with the same id in one payload is a MappingFailure
    # (DUPLICATE_IN_BATCH); the first one is imported normally.
    payload, enrichment = generated
    first = payload["payload"][0]
    other_content = copy.deepcopy(first)
    other_content["freightDescription"] = "A later record with the same id"
    same_content = copy.deepcopy(payload["payload"][1])
    provider = ListProvider(
        [first, other_content, payload["payload"][1], same_content, payload["payload"][2]],
        enrichment,
    )

    batch = service(engine).run(provider)

    assert batch.counts == {"imported": 3, "updated": 0, "unchanged": 0, "failed": 2}
    assert counts(engine, *TABLES) == {
        "freight_offers": 3,
        "freight_stops": 6,
        "raw_freight_records": 3,
    }
    with engine.connect() as connection:
        stored = connection.execute(
            text("SELECT payload_sha256 FROM raw_freight_records WHERE source_offer_id = :i"),
            {"i": first["id"]},
        ).all()
    assert len(stored) == 1  # the later duplicate did not overwrite or add a payload


@pytest.mark.ac("AC-FEAT-002-14")
def test_the_same_id_in_a_later_batch_is_an_update_not_a_duplicate(
    engine: Engine, generated: tuple[dict[str, Any], dict[str, Any]]
) -> None:
    payload, enrichment = generated
    first = payload["payload"][0]
    edited = copy.deepcopy(first)
    edited["freightDescription"] = "Edited synthetic description"
    importer = service(engine)
    importer.run(ListProvider([first], enrichment))
    batch = importer.run(ListProvider([edited], enrichment))
    assert batch.counts == {"imported": 0, "updated": 1, "unchanged": 0, "failed": 0}


@pytest.mark.ac("AC-FEAT-002-14")
def test_imported_offers_carry_source_status_and_retention(
    engine: Engine, generated: tuple[dict[str, Any], dict[str, Any]]
) -> None:
    payload, enrichment = generated
    service(engine).run(MockFreightProvider(payload, enrichment, CLOCK.now()))
    latest = {
        o["id"]: max(p["latestLoadingDate"] for p in o["loadingPlaces"]) for o in payload["payload"]
    }
    with engine.connect() as connection:
        offers = connection.execute(
            text(
                "SELECT source_offer_id, source, status, is_synthetic, retention_until "
                "FROM freight_offers"
            )
        ).all()
        raw = connection.execute(
            text("SELECT source_offer_id, retention_until FROM raw_freight_records")
        ).all()
    assert len(offers) == 150
    for offer in offers:
        assert (offer.source, offer.status, bool(offer.is_synthetic)) == (
            "mock_timocom_v3",
            "open",
            True,
        )
        # latest loading date + 1 day (FR-24): the retention ends on the day after it
        due = date.fromisoformat(latest[offer.source_offer_id]) + timedelta(days=1)
        assert str(offer.retention_until)[:10] == due.isoformat()
    assert {r.source_offer_id: str(r.retention_until)[:10] for r in raw} == {
        o.source_offer_id: str(o.retention_until)[:10] for o in offers
    }


@pytest.mark.ac("AC-FEAT-002-18")
def test_a_seeded_database_is_entirely_synthetic_and_free_of_real_looking_contacts(
    tmp_path: Path,
) -> None:
    url = f"sqlite:///{tmp_path / 'seeded.db'}"
    command.upgrade(migration_config(url), "head")
    engine = make_engine(url)
    settings = Settings(_env_file=None, app_env="test", secret_key="s" * 64,
                        mock_seed=20261109, mock_reference_date="2026-11-16")  # fmt: skip
    identity = IdentityService(engine, settings, CLOCK)
    DemoDataService(
        engine,
        CLOCK,
        settings,
        FleetService(engine, CLOCK, identity.audit),
        ImportService(engine, CLOCK, TimocomV3Mapper(), identity.audit),
        identity.audit,
    ).ensure_seed()
    with engine.connect() as connection:
        for name in (
            "drivers",
            "vehicles",
            "raw_freight_records",
            "freight_offers",
            "cost_profiles",
        ):
            marked = Table(name, MetaData(), autoload_with=engine)
            total = connection.scalar(select(func.count()).select_from(marked))
            other = connection.scalar(
                select(func.count()).select_from(marked).where(marked.c.is_synthetic.is_not(True))
            )
            assert total and other == 0, f"{name}: not every row is synthetic"
        # driver_states has no is_synthetic column (FEAT-001 §6.1): its rows are marked by
        # `source` and belong to synthetic drivers.
        states = connection.execute(
            text(
                "SELECT s.source, d.is_synthetic FROM driver_states s "
                "JOIN drivers d ON d.id = s.driver_id"
            )
        ).all()
        assert len(states) == 5 and all(
            (source, bool(flag)) == ("generated_mock", True) for source, flag in states
        )
        sources = {
            r[0] for r in connection.execute(text("SELECT DISTINCT source FROM freight_offers"))
        }
        assert sources == {"mock_timocom_v3"}
        offer_ids = [
            r[0] for r in connection.execute(text("SELECT source_offer_id FROM freight_offers"))
        ]
        assert len(offer_ids) == 150 and all(i.startswith("MOCK-") for i in offer_ids)

        # No real-looking e-mail address or phone number anywhere in the demo data.
        texts = [r[0] or "" for r in connection.execute(text("SELECT name FROM drivers"))]
        texts += [r[0] or "" for r in connection.execute(text("SELECT phone FROM drivers"))]
        texts += [
            f"{r[0]} {r[1]}"
            for r in connection.execute(
                text("SELECT description, public_remark FROM freight_offers")
            )
        ]
        texts += [r[0] for r in connection.execute(text("SELECT payload FROM raw_freight_records"))]
        phones = [r[0] for r in connection.execute(text("SELECT phone FROM drivers"))]
    blob = "\n".join(texts)
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", blob), "an e-mail address was generated"
    assert all(re.fullmatch(r"\+00-000-000-00\d", phone) for phone in phones)
    stripped = re.sub(r"\d{4}-\d\d-\d\d(T[\d:.+Z-]+)?", "", blob)  # dates are not phone numbers
    stripped = stripped.replace("+00-000-000-00", "")
    assert not re.search(r"(?<![\d.])\+?\d[\d ()-]{8,}\d", stripped), "a phone-like number found"
    engine.dispose()
