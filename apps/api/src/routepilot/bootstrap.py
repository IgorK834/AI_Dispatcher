"""Composition-root demo seed and reset orchestration across module services."""

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import JSON, Column, MetaData, Table, Text, delete, select
from sqlalchemy.engine import Engine

from routepilot.fleet.service import FleetService
from routepilot.freight.generator import generate_offers
from routepilot.freight.service import ImportService
from routepilot.integrations.timocom.mock import MockFreightProvider
from routepilot.shared.audit import AuditWriter
from routepilot.shared.clock import Clock
from routepilot.shared.config import Settings
from routepilot.shared.db.types import UtcDateTime


class GenerateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    seed: int | None = None
    reference_date: date | None = Field(default=None, alias="referenceDate")
    drivers: Literal[5] = 5
    offers: int = Field(default=150, ge=1, le=500)


class DemoDataService:
    def __init__(
        self,
        engine: Engine,
        clock: Clock,
        settings: Settings,
        fleet: FleetService,
        imports: ImportService,
        audit: AuditWriter,
    ) -> None:
        self.engine, self.clock, self.settings = engine, clock, settings
        self.fleet, self.imports, self.audit = fleet, imports, audit
        self.meta = Table(
            "app_meta",
            MetaData(),
            Column("key", Text, primary_key=True),
            Column("value", JSON, nullable=False),
            Column("updated_at", UtcDateTime(), nullable=False),
        )

    def _reference(self) -> date:
        return (
            date.fromisoformat(self.settings.mock_reference_date)
            if self.settings.mock_reference_date
            else self.clock.now().date()
        )

    def ensure_seed(self) -> None:
        with self.engine.connect() as connection:
            existing = connection.scalar(
                select(self.meta.c.value).where(self.meta.c.key == "seed_version")
            )
        if existing is None:
            self.generate(GenerateInput(), "system")

    def generate(self, body: GenerateInput, actor: str) -> dict[str, Any]:
        seed = body.seed if body.seed is not None else self.settings.mock_seed
        reference = body.reference_date or self._reference()
        counts = self.fleet.seed(seed, reference, actor)
        payload, enrichment = generate_offers(seed, reference, body.offers)
        provider = MockFreightProvider(payload, enrichment, self.clock.now())
        batch = self.imports.run(provider, actor=actor)
        value = {
            "version": 1,
            "seed": seed,
            "referenceDate": reference.isoformat(),
            "at": self.clock.now().isoformat(),
        }
        with self.engine.begin() as connection:
            existing = connection.scalar(
                select(self.meta.c.key).where(self.meta.c.key == "seed_version")
            )
            if existing:
                connection.execute(
                    self.meta.update()
                    .where(self.meta.c.key == "seed_version")
                    .values(value=value, updated_at=self.clock.now())
                )
            else:
                connection.execute(
                    self.meta.insert().values(
                        key="seed_version", value=value, updated_at=self.clock.now()
                    )
                )
        self.audit.record(actor, "demo_data.generated", "demo_data", diff=value)
        return {
            "importBatchId": str(batch.id),
            "drivers": counts["drivers"],
            "vehicles": counts["vehicles"],
            "offers": batch.counts,
        }

    def reset(self, actor: str) -> dict[str, Any]:
        # The approved reset restores the complete first-start world. Accounts,
        # their sessions, the signing key and audit history remain available.
        metadata = MetaData()
        names = (
            "assignments",
            "approval_requests",
            "agent_steps",
            "agent_runs",
            "agent_threads",
            "route_explanations",
            "route_stops",
            "route_plans",
            "optimization_jobs",
            "freight_stops",
            "freight_offers",
            "raw_freight_records",
            "import_batches",
            "driver_states",
            "drivers",
            "vehicles",
            "cost_profiles",
            "routing_cache",
        )
        tables = [Table(name, metadata, autoload_with=self.engine) for name in names]
        with self.engine.begin() as connection:
            for table in tables:
                connection.execute(delete(table))
            connection.execute(delete(self.meta).where(self.meta.c.key != "secret_key"))
        result = self.generate(GenerateInput(), actor)
        self.audit.record(actor, "demo_data.reset", "demo_data")
        return result
