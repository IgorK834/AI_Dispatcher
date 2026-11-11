"""Authentication API contracts."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from routepilot.shared.auth import Principal


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)
    captcha_token: str = Field(alias="captchaToken", min_length=1, max_length=2048)


class UserView(BaseModel):
    id: UUID
    email: str
    role: Literal["admin", "dispatcher", "demo"]
    locale: Literal["en", "pl"]


class LoginBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    user: UserView
    csrf_token: str = Field(alias="csrfToken")


@dataclass(frozen=True)
class LoginResult:
    principal: Principal
    user: UserView
    token: str
    csrf_token: str
