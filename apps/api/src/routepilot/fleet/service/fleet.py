"""Fleet use cases shared by the HTTP API, job snapshots and agent tools."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from routepilot.fleet.domain.models import (
    CostProfileCreate,
    CostProfileUpdate,
    CostProfileView,
    DriverCreate,
    DriverStateCreate,
    DriverStateView,
    DriverUpdate,
    DriverView,
    VehicleCreate,
    VehicleUpdate,
    VehicleView,
)
from routepilot.fleet.generator import generate_fleet
from routepilot.fleet.ports import DriverUsageChecker
from routepilot.fleet.repository.models import CostProfile, Driver, DriverState, Vehicle
from routepilot.shared.audit import AuditWriter
from routepilot.shared.clock import Clock
from routepilot.shared.db.base import Base
from routepilot.shared.errors import DomainError
from routepilot.shared.pagination import CursorCodec, Page


def _values(row: Base) -> dict[str, Any]:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


class Identified(Protocol):
    id: UUID


class FleetService:
    def __init__(
        self,
        engine: Engine,
        clock: Clock,
        audit: AuditWriter | None = None,
        usage_checker: DriverUsageChecker | None = None,
        cursor_secret: str | bytes | None = None,
    ) -> None:
        self.engine, self.clock, self.audit = engine, clock, audit
        self.usage_checker = usage_checker
        self.cursors = CursorCodec(cursor_secret)

    def _audit(
        self,
        session: Session,
        actor: str,
        action: str,
        kind: str,
        entity_id: UUID,
        diff: dict[str, Any] | None = None,
    ) -> None:
        if self.audit:
            self.audit.record(actor, action, kind, str(entity_id), diff, transaction=session)

    def _page[T: Identified](
        self, items: list[T], limit: int, cursor: str | None, filters: dict[str, Any]
    ) -> Page[T]:
        if not 1 <= limit <= 100:
            raise DomainError("VALIDATION_ERROR", 422)
        marker = self.cursors.decode(cursor, filters)
        start = 0
        if marker:
            indexes = [i for i, item in enumerate(items) if str(item.id) == marker]
            if not indexes:
                raise DomainError("VALIDATION_ERROR", 422)
            start = indexes[0] + 1
        selected = items[start : start + limit]
        next_cursor = (
            self.cursors.encode(str(selected[-1].id), filters)
            if start + limit < len(items)
            else None
        )
        return Page(items=selected, nextCursor=next_cursor)

    @staticmethod
    def _cost_view(row: CostProfile) -> CostProfileView:
        return CostProfileView.model_validate(_values(row))

    @staticmethod
    def _vehicle_view(row: Vehicle) -> VehicleView:
        data = _values(row)
        for name in ("length", "width", "height"):
            mm = data.pop(f"inner_{name}_mm")
            data[f"inner_{name}_m"] = Decimal(mm) / 1000 if mm is not None else None
        data["fuel"] = {
            "lPer100kmEmptyAt90": Decimal(data.pop("fuel_l_per_100km_empty_x10")) / 10,
            "lPer100kmFullAt90": Decimal(data.pop("fuel_l_per_100km_full_x10")) / 10,
            "speedCurve": data.pop("fuel_speed_curve"),
            "provenance": data.pop("fuel_provenance"),
        }
        return VehicleView.model_validate(data)

    def _driver_view(self, row: Driver, session: Session) -> DriverView:
        data = _values(row)
        data.pop("deleted_at")
        vehicle = session.get(Vehicle, row.vehicle_id) if row.vehicle_id else None
        state = session.scalar(
            select(DriverState)
            .where(DriverState.driver_id == row.id)
            .order_by(DriverState.valid_from.desc(), DriverState.id.desc())
            .limit(1)
        )
        data["vehicle"] = self._vehicle_view(vehicle) if vehicle else None
        data["state"] = DriverStateView.model_validate(state) if state else None
        return DriverView.model_validate(data)

    @staticmethod
    def _driver(session: Session, driver_id: UUID) -> Driver:
        row = session.get(Driver, driver_id)
        if row is None or row.deleted_at is not None:
            raise DomainError("NOT_FOUND", 404)
        return row

    @staticmethod
    def _vehicle(session: Session, vehicle_id: UUID) -> Vehicle:
        row = session.get(Vehicle, vehicle_id)
        if row is None:
            raise DomainError("NOT_FOUND", 404)
        return row

    @staticmethod
    def _cost(session: Session, profile_id: UUID) -> CostProfile:
        row = session.get(CostProfile, profile_id)
        if row is None:
            raise DomainError("NOT_FOUND", 404)
        return row

    def list_drivers(
        self,
        limit: int = 50,
        cursor: str | None = None,
        home_city: str | None = None,
        available_before: datetime | None = None,
        has_vehicle: bool | None = None,
    ) -> Page[DriverView]:
        with Session(self.engine) as session:
            query = select(Driver).where(Driver.deleted_at.is_(None)).order_by(Driver.id)
            if home_city is not None:
                query = query.where(Driver.home_city == home_city)
            if has_vehicle is not None:
                query = query.where(
                    Driver.vehicle_id.is_not(None) if has_vehicle else Driver.vehicle_id.is_(None)
                )
            items = [self._driver_view(row, session) for row in session.scalars(query)]
            if available_before:
                items = [
                    row
                    for row in items
                    if row.state and row.state.available_from <= available_before
                ]
            return self._page(
                items,
                limit,
                cursor,
                {
                    "resource": "drivers",
                    "home_city": home_city,
                    "available_before": available_before,
                    "has_vehicle": has_vehicle,
                },
            )

    def list_active(self, limit: int = 20) -> list[DriverView]:
        if not 1 <= limit <= 20:
            raise DomainError("VALIDATION_ERROR", 422)
        with Session(self.engine) as session:
            rows = session.scalars(
                select(Driver)
                .where(Driver.deleted_at.is_(None))
                .order_by(Driver.created_at, Driver.id)
                .limit(limit)
            )
            return [self._driver_view(row, session) for row in rows]

    def latest_state(self, driver_id: UUID) -> DriverStateView:
        driver = self.get_driver(driver_id)
        if driver.state is None:
            raise DomainError("NOT_FOUND", 404)
        return driver.state

    def has_active_assignment(self, driver_id: UUID) -> bool:
        self.get_driver(driver_id)
        return (
            self.usage_checker is not None
            and self.usage_checker.assignment_usage(driver_id) == "active"
        )

    def get_driver(self, driver_id: UUID) -> DriverView:
        with Session(self.engine) as session:
            return self._driver_view(self._driver(session, driver_id), session)

    def create_driver(self, body: DriverCreate, actor: str) -> DriverView:
        try:
            with Session(self.engine) as session, session.begin():
                if body.vehicle_id:
                    self._vehicle(session, body.vehicle_id)
                now = self.clock.now()
                row = Driver(
                    **body.model_dump(), is_synthetic=False, created_at=now, updated_at=now
                )
                session.add(row)
                session.flush()
                self._audit(
                    session, actor, "driver.created", "driver", row.id, body.model_dump(mode="json")
                )
                return self._driver_view(row, session)
        except IntegrityError:
            raise DomainError("DUPLICATE_RESOURCE", 409) from None

    def update_driver(self, driver_id: UUID, body: DriverUpdate, actor: str) -> DriverView:
        try:
            with Session(self.engine) as session, session.begin():
                row = self._driver(session, driver_id)
                values = body.model_dump(exclude_unset=True, exclude={"version"})
                merged = DriverCreate.model_validate(
                    {
                        **self._driver_view(row, session).model_dump(
                            include=set(DriverCreate.model_fields)
                        ),
                        **values,
                    }
                )
                if merged.vehicle_id:
                    self._vehicle(session, merged.vehicle_id)
                changed = session.execute(
                    update(Driver)
                    .where(Driver.id == driver_id, Driver.version == body.version)
                    .returning(Driver.id)
                    .values(**values, version=body.version + 1, updated_at=self.clock.now())
                )
                if changed.scalar_one_or_none() is None:
                    raise DomainError("VERSION_CONFLICT", 409)
                session.refresh(row)
                self._audit(
                    session,
                    actor,
                    "driver.updated",
                    "driver",
                    row.id,
                    body.model_dump(mode="json", exclude_unset=True),
                )
                return self._driver_view(row, session)
        except IntegrityError:
            raise DomainError("DUPLICATE_RESOURCE", 409) from None
        except ValidationError:
            raise DomainError("VALIDATION_ERROR", 422) from None

    def delete_driver(self, driver_id: UUID, actor: str) -> None:
        usage = self.usage_checker.assignment_usage(driver_id) if self.usage_checker else "none"
        with Session(self.engine) as session, session.begin():
            row = self._driver(session, driver_id)
            if usage == "active":
                raise DomainError("DRIVER_HAS_ACTIVE_ASSIGNMENT", 409)
            if usage == "historical":
                row.deleted_at = self.clock.now()
            else:
                session.delete(row)
            self._audit(session, actor, "driver.deleted", "driver", driver_id)

    def add_state(
        self, driver_id: UUID, body: DriverStateCreate, actor: str, source: str = "user"
    ) -> DriverStateView:
        with Session(self.engine) as session, session.begin():
            self._driver(session, driver_id)
            row = DriverState(
                **body.model_dump(), driver_id=driver_id, valid_from=self.clock.now(), source=source
            )
            session.add(row)
            session.flush()
            self._audit(
                session,
                actor,
                "driver.state_created",
                "driver",
                driver_id,
                body.model_dump(mode="json"),
            )
            return DriverStateView.model_validate(row)

    def list_states(
        self, driver_id: UUID, limit: int = 50, cursor: str | None = None
    ) -> Page[DriverStateView]:
        with Session(self.engine) as session:
            self._driver(session, driver_id)
            rows = session.scalars(
                select(DriverState)
                .where(DriverState.driver_id == driver_id)
                .order_by(DriverState.valid_from.desc(), DriverState.id.desc())
            )
            return self._page(
                [DriverStateView.model_validate(row) for row in rows],
                limit,
                cursor,
                {"resource": "driver_states", "driver_id": str(driver_id)},
            )

    def list_vehicles(
        self,
        limit: int = 50,
        cursor: str | None = None,
        pallet_places: int | None = None,
        unassigned: bool | None = None,
    ) -> Page[VehicleView]:
        with Session(self.engine) as session:
            assigned = set(
                session.scalars(select(Driver.vehicle_id).where(Driver.vehicle_id.is_not(None)))
            )
            rows = session.scalars(select(Vehicle).order_by(Vehicle.id))
            items = [
                self._vehicle_view(row)
                for row in rows
                if (pallet_places is None or row.pallet_places == pallet_places)
                and (unassigned is None or (row.id not in assigned) == unassigned)
            ]
            return self._page(
                items,
                limit,
                cursor,
                {"resource": "vehicles", "pallet_places": pallet_places, "unassigned": unassigned},
            )

    def get_vehicle(self, vehicle_id: UUID) -> VehicleView:
        with Session(self.engine) as session:
            return self._vehicle_view(self._vehicle(session, vehicle_id))

    @staticmethod
    def _vehicle_values(body: VehicleCreate) -> dict[str, Any]:
        data = body.model_dump(
            exclude={"fuel", "inner_length_m", "inner_width_m", "inner_height_m"}
        )
        for name in ("length", "width", "height"):
            value = getattr(body, f"inner_{name}_m")
            data[f"inner_{name}_mm"] = int(value * 1000) if value is not None else None
        data.update(
            fuel_l_per_100km_empty_x10=int(body.fuel.l_per_100km_empty_at90 * 10),
            fuel_l_per_100km_full_x10=int(body.fuel.l_per_100km_full_at90 * 10),
            fuel_speed_curve=body.fuel.speed_curve,
            fuel_provenance="user",
        )
        return data

    def create_vehicle(self, body: VehicleCreate, actor: str) -> VehicleView:
        try:
            with Session(self.engine) as session, session.begin():
                self._cost(session, body.cost_profile_id)
                now = self.clock.now()
                row = Vehicle(
                    **self._vehicle_values(body), is_synthetic=False, created_at=now, updated_at=now
                )
                session.add(row)
                session.flush()
                self._audit(
                    session,
                    actor,
                    "vehicle.created",
                    "vehicle",
                    row.id,
                    body.model_dump(mode="json"),
                )
                return self._vehicle_view(row)
        except IntegrityError:
            raise DomainError("DUPLICATE_RESOURCE", 409) from None

    def update_vehicle(self, vehicle_id: UUID, body: VehicleUpdate, actor: str) -> VehicleView:
        try:
            with Session(self.engine) as session, session.begin():
                row = self._vehicle(session, vehicle_id)
                values = body.model_dump(exclude_unset=True, exclude={"version"})
                base = self._vehicle_view(row).model_dump(include=set(VehicleCreate.model_fields))
                base["fuel"].pop("provenance", None)
                merged = VehicleCreate.model_validate({**base, **values})
                self._cost(session, merged.cost_profile_id)
                changed = session.execute(
                    update(Vehicle)
                    .where(Vehicle.id == vehicle_id, Vehicle.version == body.version)
                    .returning(Vehicle.id)
                    .values(
                        **self._vehicle_values(merged),
                        version=body.version + 1,
                        updated_at=self.clock.now(),
                    )
                )
                if changed.scalar_one_or_none() is None:
                    raise DomainError("VERSION_CONFLICT", 409)
                session.refresh(row)
                self._audit(
                    session,
                    actor,
                    "vehicle.updated",
                    "vehicle",
                    row.id,
                    body.model_dump(mode="json", exclude_unset=True),
                )
                return self._vehicle_view(row)
        except IntegrityError:
            raise DomainError("DUPLICATE_RESOURCE", 409) from None
        except ValidationError:
            raise DomainError("VALIDATION_ERROR", 422) from None

    def delete_vehicle(self, vehicle_id: UUID, actor: str) -> None:
        with Session(self.engine) as session, session.begin():
            row = self._vehicle(session, vehicle_id)
            if session.scalar(select(Driver.id).where(Driver.vehicle_id == vehicle_id).limit(1)):
                raise DomainError("VEHICLE_ASSIGNED_TO_DRIVER", 409)
            session.delete(row)
            self._audit(session, actor, "vehicle.deleted", "vehicle", vehicle_id)

    def list_cost_profiles(
        self, limit: int = 50, cursor: str | None = None
    ) -> Page[CostProfileView]:
        with Session(self.engine) as session:
            items = [
                self._cost_view(row)
                for row in session.scalars(select(CostProfile).order_by(CostProfile.id))
            ]
            return self._page(items, limit, cursor, {"resource": "cost_profiles"})

    def get_cost_profile(self, profile_id: UUID) -> CostProfileView:
        with Session(self.engine) as session:
            return self._cost_view(self._cost(session, profile_id))

    def create_cost_profile(self, body: CostProfileCreate, actor: str) -> CostProfileView:
        try:
            with Session(self.engine) as session, session.begin():
                now = self.clock.now()
                row = CostProfile(
                    **body.model_dump(),
                    provenance={key: "user" for key in type(body).model_fields},
                    is_synthetic=False,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
                session.flush()
                self._audit(
                    session,
                    actor,
                    "cost_profile.created",
                    "cost_profile",
                    row.id,
                    body.model_dump(mode="json"),
                )
                return self._cost_view(row)
        except IntegrityError:
            raise DomainError("DUPLICATE_RESOURCE", 409) from None

    def update_cost_profile(
        self, profile_id: UUID, body: CostProfileUpdate, actor: str
    ) -> CostProfileView:
        try:
            with Session(self.engine) as session, session.begin():
                row = self._cost(session, profile_id)
                values = body.model_dump(exclude_unset=True, exclude={"version"})
                merged = CostProfileCreate.model_validate(
                    {
                        **self._cost_view(row).model_dump(
                            include=set(CostProfileCreate.model_fields)
                        ),
                        **values,
                    }
                )
                changed = session.execute(
                    update(CostProfile)
                    .where(CostProfile.id == profile_id, CostProfile.version == body.version)
                    .returning(CostProfile.id)
                    .values(
                        **merged.model_dump(),
                        version=body.version + 1,
                        updated_at=self.clock.now(),
                        provenance={**row.provenance, **{key: "user" for key in values}},
                    )
                )
                if changed.scalar_one_or_none() is None:
                    raise DomainError("VERSION_CONFLICT", 409)
                session.refresh(row)
                self._audit(
                    session,
                    actor,
                    "cost_profile.updated",
                    "cost_profile",
                    row.id,
                    body.model_dump(mode="json", exclude_unset=True),
                )
                return self._cost_view(row)
        except IntegrityError:
            raise DomainError("DUPLICATE_RESOURCE", 409) from None
        except ValidationError:
            raise DomainError("VALIDATION_ERROR", 422) from None

    def delete_cost_profile(self, profile_id: UUID, actor: str) -> None:
        with Session(self.engine) as session, session.begin():
            row = self._cost(session, profile_id)
            if session.scalar(
                select(Vehicle.id).where(Vehicle.cost_profile_id == profile_id).limit(1)
            ):
                raise DomainError("COST_PROFILE_IN_USE", 409)
            session.delete(row)
            self._audit(session, actor, "cost_profile.deleted", "cost_profile", profile_id)

    def seed(
        self, seed: int, reference_date: date | datetime, actor: str = "system"
    ) -> dict[str, int]:
        snapshot = generate_fleet(
            seed, reference_date.date() if isinstance(reference_date, datetime) else reference_date
        )
        with Session(self.engine) as session, session.begin():
            now = self.clock.now()
            profile_id = uuid5(NAMESPACE_URL, "routepilot:DEMO-DEFAULT")
            costs = snapshot["cost_profile"].copy()
            provenance = costs.pop("provenance")
            costs.pop("is_synthetic")
            profile = session.get(CostProfile, profile_id)
            if profile is None:
                profile = CostProfile(
                    id=profile_id,
                    created_at=now,
                    updated_at=now,
                    is_synthetic=True,
                    provenance=provenance,
                    **costs,
                )
                session.add(profile)
            else:
                for key, value in costs.items():
                    setattr(profile, key, value)
                profile.provenance = provenance
                profile.updated_at = now
            session.flush()
            for item in snapshot["vehicles"]:
                data = {
                    k: v for k, v in item.items() if k not in ("id", "cost_profile", "is_synthetic")
                }
                fuel = data["fuel"].copy()
                fuel.pop("provenance")
                data["fuel"] = fuel
                data["cost_profile_id"] = profile_id
                body = VehicleCreate.model_validate(data)
                values = self._vehicle_values(body)
                values["fuel_provenance"] = "assumption"
                vehicle_id = uuid5(NAMESPACE_URL, "routepilot:" + item["id"])
                row = session.get(Vehicle, vehicle_id)
                if row is None:
                    session.add(
                        Vehicle(
                            id=vehicle_id,
                            **values,
                            is_synthetic=True,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                else:
                    for key, value in values.items():
                        setattr(row, key, value)
                    row.updated_at = now
                session.flush()
            for item in snapshot["drivers"]:
                data = {k: v for k, v in item.items() if k not in ("id", "is_synthetic")}
                data["vehicle_id"] = uuid5(NAMESPACE_URL, "routepilot:" + data["vehicle_id"])
                driver_id = uuid5(NAMESPACE_URL, "routepilot:" + item["id"])
                driver_row = session.get(Driver, driver_id)
                if driver_row is None:
                    session.add(
                        Driver(
                            id=driver_id, **data, is_synthetic=True, created_at=now, updated_at=now
                        )
                    )
                else:
                    for key, value in data.items():
                        setattr(driver_row, key, value)
                    driver_row.updated_at = now
                session.flush()
            for item in snapshot["driver_states"]:
                state_id = uuid5(NAMESPACE_URL, f"routepilot:{seed}:{reference_date}:" + item["id"])
                if session.get(DriverState, state_id) is not None:
                    continue
                data = {
                    k: v
                    for k, v in item.items()
                    if k not in ("id", "driver_id", "source", "is_synthetic")
                }
                state_body = DriverStateCreate.model_validate(data)
                session.add(
                    DriverState(
                        id=state_id,
                        driver_id=uuid5(NAMESPACE_URL, "routepilot:" + item["driver_id"]),
                        **state_body.model_dump(),
                        valid_from=now,
                        source="generated_mock",
                    )
                )
            if self.audit:
                self.audit.record(
                    actor, "fleet.generated", "fleet", diff={"seed": seed}, transaction=session
                )
        return {"drivers": 5, "vehicles": 5, "states": 5}
