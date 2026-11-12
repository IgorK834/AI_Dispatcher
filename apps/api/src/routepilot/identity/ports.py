"""Captcha verification boundary."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CaptchaResult:
    ok: bool
    error_codes: list[str]


class CaptchaVerifier(Protocol):
    def verify(self, token: str, remote_ip: str | None) -> CaptchaResult: ...
