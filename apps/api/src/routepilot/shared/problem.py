"""RFC 9457 problem responses."""

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, JsonValue


class Problem(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: str = "about:blank"
    title: str
    status: int
    code: str
    instance: str
    request_id: str = Field(alias="requestId")
    errors: list[dict[str, JsonValue]] = Field(default_factory=list)


def problem(
    request: Request,
    status: int,
    code: str,
    *,
    errors: list[dict[str, JsonValue]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        headers=headers,
        content={
            "type": "about:blank",
            "title": code.replace("_", " ").title(),
            "status": status,
            "code": code,
            "instance": request.url.path,
            "requestId": getattr(request.state, "request_id", ""),
            "errors": errors or [],
        },
    )
