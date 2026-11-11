"""Fleet HTTP adapters; all roles may edit drivers and vehicles."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field

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
from routepilot.fleet.service.fleet import FleetService
from routepilot.shared.auth import Principal
from routepilot.shared.pagination import Page


class PageQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    limit: int = Field(default=50, ge=1, le=100)
    cursor: str | None = None


class DriverQuery(PageQuery):
    home_city: str | None = Field(default=None, alias="homeCity")
    available_before: datetime | None = Field(default=None, alias="availableBefore")
    has_vehicle: bool | None = Field(default=None, alias="hasVehicle")


class VehicleQuery(PageQuery):
    pallet_places: int | None = Field(default=None, alias="palletPlaces", ge=1, le=12)
    unassigned: bool | None = None


def create_fleet_router(
    service: FleetService,
    require_user: Callable[..., Principal],
    require_admin: Callable[..., Principal],
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["fleet"])
    user = Depends(require_user)
    admin = Depends(require_admin)

    @router.get("/drivers", response_model=Page[DriverView])
    def drivers(
        query: Annotated[DriverQuery, Query()], principal: Principal = user
    ) -> Page[DriverView]:
        return service.list_drivers(**query.model_dump())

    @router.post("/drivers", status_code=201, response_model=DriverView)
    def create_driver(
        body: DriverCreate, response: Response, principal: Principal = user
    ) -> DriverView:
        item = service.create_driver(body, str(principal.id))
        response.headers["Location"] = f"/api/v1/drivers/{item.id}"
        return item

    @router.get("/drivers/{driver_id}", response_model=DriverView)
    def driver(driver_id: UUID, principal: Principal = user) -> DriverView:
        return service.get_driver(driver_id)

    @router.patch("/drivers/{driver_id}", response_model=DriverView)
    def update_driver(
        driver_id: UUID, body: DriverUpdate, principal: Principal = user
    ) -> DriverView:
        return service.update_driver(driver_id, body, str(principal.id))

    @router.delete("/drivers/{driver_id}", status_code=204)
    def delete_driver(driver_id: UUID, principal: Principal = user) -> Response:
        service.delete_driver(driver_id, str(principal.id))
        return Response(status_code=204)

    @router.get("/drivers/{driver_id}/state", response_model=Page[DriverStateView])
    def states(
        driver_id: UUID, query: Annotated[PageQuery, Query()], principal: Principal = user
    ) -> Page[DriverStateView]:
        return service.list_states(driver_id, **query.model_dump())

    @router.post("/drivers/{driver_id}/state", status_code=201, response_model=DriverStateView)
    def state(
        driver_id: UUID, body: DriverStateCreate, response: Response, principal: Principal = user
    ) -> DriverStateView:
        item = service.add_state(driver_id, body, str(principal.id))
        response.headers["Location"] = f"/api/v1/drivers/{driver_id}/state"
        return item

    @router.get("/vehicles", response_model=Page[VehicleView])
    def vehicles(
        query: Annotated[VehicleQuery, Query()], principal: Principal = user
    ) -> Page[VehicleView]:
        return service.list_vehicles(**query.model_dump())

    @router.post("/vehicles", status_code=201, response_model=VehicleView)
    def create_vehicle(
        body: VehicleCreate, response: Response, principal: Principal = user
    ) -> VehicleView:
        item = service.create_vehicle(body, str(principal.id))
        response.headers["Location"] = f"/api/v1/vehicles/{item.id}"
        return item

    @router.get("/vehicles/{vehicle_id}", response_model=VehicleView)
    def vehicle(vehicle_id: UUID, principal: Principal = user) -> VehicleView:
        return service.get_vehicle(vehicle_id)

    @router.patch("/vehicles/{vehicle_id}", response_model=VehicleView)
    def update_vehicle(
        vehicle_id: UUID, body: VehicleUpdate, principal: Principal = user
    ) -> VehicleView:
        return service.update_vehicle(vehicle_id, body, str(principal.id))

    @router.delete("/vehicles/{vehicle_id}", status_code=204)
    def delete_vehicle(vehicle_id: UUID, principal: Principal = user) -> Response:
        service.delete_vehicle(vehicle_id, str(principal.id))
        return Response(status_code=204)

    @router.get("/cost-profiles", response_model=Page[CostProfileView])
    def profiles(
        query: Annotated[PageQuery, Query()], principal: Principal = user
    ) -> Page[CostProfileView]:
        return service.list_cost_profiles(**query.model_dump())

    @router.post("/cost-profiles", status_code=201, response_model=CostProfileView)
    def create_profile(
        body: CostProfileCreate, response: Response, principal: Principal = admin
    ) -> CostProfileView:
        item = service.create_cost_profile(body, str(principal.id))
        response.headers["Location"] = f"/api/v1/cost-profiles/{item.id}"
        return item

    @router.get("/cost-profiles/{profile_id}", response_model=CostProfileView)
    def profile(profile_id: UUID, principal: Principal = user) -> CostProfileView:
        return service.get_cost_profile(profile_id)

    @router.patch("/cost-profiles/{profile_id}", response_model=CostProfileView)
    def update_profile(
        profile_id: UUID, body: CostProfileUpdate, principal: Principal = admin
    ) -> CostProfileView:
        return service.update_cost_profile(profile_id, body, str(principal.id))

    @router.delete("/cost-profiles/{profile_id}", status_code=204)
    def delete_profile(profile_id: UUID, principal: Principal = admin) -> Response:
        service.delete_cost_profile(profile_id, str(principal.id))
        return Response(status_code=204)

    return router
