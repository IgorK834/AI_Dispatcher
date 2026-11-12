"""Manual freight CRUD HTTP adapters."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from routepilot.freight.domain.models import (
    FreightOfferCreate,
    FreightOfferUpdate,
    FreightOfferView,
)
from routepilot.freight.service.offers import FreightService
from routepilot.shared.auth import Principal
from routepilot.shared.pagination import Page


class OfferQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, alias_generator=to_camel)
    limit: int = Field(default=50, ge=1, le=100)
    cursor: str | None = None
    source: str | None = None
    status: Literal["open", "assigned", "expired", "withdrawn"] | None = None
    origin_country: str | None = None
    destination_country: str | None = None
    origin_city: str | None = None
    destination_city: str | None = None
    pickup_from: datetime | None = None
    pickup_to: datetime | None = None
    max_weight_kg: int | None = Field(default=None, ge=1)
    max_pallets: int | None = Field(default=None, ge=1)
    min_completeness: float | None = Field(default=None, ge=0, le=1)
    has_price: bool | None = None


def create_freight_router(
    service: FreightService, require_user: Callable[..., Principal]
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/freight-offers", tags=["freight"])
    user = Depends(require_user)

    @router.get("", response_model=Page[FreightOfferView])
    def offers(
        query: Annotated[OfferQuery, Query()], principal: Principal = user
    ) -> Page[FreightOfferView]:
        return service.list_offers(**query.model_dump())

    @router.post("", status_code=201, response_model=FreightOfferView)
    def create_offer(
        body: FreightOfferCreate, response: Response, principal: Principal = user
    ) -> FreightOfferView:
        offer = service.create_offer(body, str(principal.id))
        response.headers["Location"] = f"/api/v1/freight-offers/{offer.id}"
        return offer

    @router.get("/{offer_id}", response_model=FreightOfferView)
    def offer(offer_id: UUID, principal: Principal = user) -> FreightOfferView:
        return service.get_offer(offer_id)

    @router.patch("/{offer_id}", response_model=FreightOfferView)
    def update_offer(
        offer_id: UUID, body: FreightOfferUpdate, principal: Principal = user
    ) -> FreightOfferView:
        return service.update_offer(offer_id, body, str(principal.id))

    @router.delete("/{offer_id}", status_code=204)
    def delete_offer(offer_id: UUID, principal: Principal = user) -> Response:
        service.delete_offer(offer_id, str(principal.id))
        return Response(status_code=204)

    return router
