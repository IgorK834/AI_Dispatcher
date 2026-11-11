"""RFC 9457 problem responses."""

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field


class Problem(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: str = "about:blank"
    title: str
    status: int
    code: str
    instance: str
    request_id: str = Field(alias="requestId")


def problem(request: Request, status: int, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={
            "type": "about:blank",
            "title": code.replace("_", " ").title(),
            "status": status,
            "code": code,
            "instance": request.url.path,
            "requestId": getattr(request.state, "request_id", ""),
        },
    )
