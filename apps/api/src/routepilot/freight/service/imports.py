"""Idempotent imports retain raw payloads and normalize through an injected mapper."""

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from routepilot.freight.domain.models import FreightSearchQuery, ImportBatchView, MappingFailure
from routepilot.freight.ports import FreightProvider, OfferMapper
from routepilot.freight.repository.models import FreightOffer, ImportBatch, RawFreightRecord
from routepilot.freight.service.offers import offer_values, replace_stops
from routepilot.shared.audit import AuditWriter
from routepilot.shared.clock import Clock


class ImportService:
    def __init__(
        self, engine: Engine, clock: Clock, mapper: OfferMapper, audit: AuditWriter | None = None
    ) -> None:
        self.engine, self.clock, self.mapper, self.audit = engine, clock, mapper, audit

    def run(
        self,
        provider: FreightProvider,
        query: FreightSearchQuery | None = None,
        actor: str = "system",
    ) -> ImportBatchView:
        counts = dict(imported=0, updated=0, unchanged=0, failed=0)
        with Session(self.engine) as session, session.begin():
            batch = ImportBatch(
                source=provider.name, started_at=self.clock.now(), status="running", counts=counts
            )
            session.add(batch)
            session.flush()
            seen: set[str] = set()
            for record in provider.search(query or FreightSearchQuery()):
                if record.source_offer_id in seen:
                    # FEAT-002 §8, DUPLICATE_IN_BATCH: only the first record of an id in one
                    # payload counts; the later one is a mapping failure and stores nothing.
                    counts["failed"] += 1
                    continue
                seen.add(record.source_offer_id)
                digest = hashlib.sha256(
                    json.dumps(
                        record.payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                    ).encode()
                ).hexdigest()
                existing_raw = session.scalar(
                    select(RawFreightRecord).where(
                        RawFreightRecord.source == record.source,
                        RawFreightRecord.source_offer_id == record.source_offer_id,
                        RawFreightRecord.payload_sha256 == digest,
                    )
                )
                if existing_raw is not None:
                    counts["unchanged"] += 1
                    continue
                normalized = self.mapper.to_domain(record)
                if isinstance(normalized, MappingFailure):
                    counts["failed"] += 1
                    continue
                raw = RawFreightRecord(
                    source=record.source,
                    source_offer_id=record.source_offer_id,
                    payload=record.payload,
                    payload_sha256=digest,
                    fetched_at=record.fetched_at,
                    import_batch_id=batch.id,
                    is_synthetic=record.source == "mock_timocom_v3",
                    retention_until=normalized.retention_until,
                )
                session.add(raw)
                session.flush()
                row = session.scalar(
                    select(FreightOffer).where(
                        FreightOffer.source == record.source,
                        FreightOffer.source_offer_id == record.source_offer_id,
                    )
                )
                now = self.clock.now()
                values = offer_values(normalized)
                if row is None:
                    row = FreightOffer(
                        **values,
                        source=record.source,
                        status="open",
                        is_synthetic=record.source == "mock_timocom_v3",
                        raw_record_id=raw.id,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(row)
                    session.flush()
                    counts["imported"] += 1
                else:
                    for key, value in values.items():
                        setattr(row, key, value)
                    row.raw_record_id = raw.id
                    row.version += 1
                    row.updated_at = now
                    counts["updated"] += 1
                replace_stops(session, row.id, normalized.stops)
            batch.counts = counts.copy()
            batch.status = "completed"
            batch.finished_at = self.clock.now()
            if self.audit:
                self.audit.record(
                    actor,
                    "freight.imported",
                    "import_batch",
                    str(batch.id),
                    counts.copy(),
                    transaction=session,
                )
            return ImportBatchView.model_validate(batch)
