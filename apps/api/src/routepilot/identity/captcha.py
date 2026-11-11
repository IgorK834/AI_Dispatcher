"""Server-side Turnstile verification with an injectable HTTP client."""

import httpx

from routepilot.identity.ports import CaptchaResult


class TurnstileVerifier:
    def __init__(self, secret: str, client: httpx.Client | None = None) -> None:
        self.secret = secret
        self.client = client or httpx.Client(timeout=5, trust_env=False)

    def verify(self, token: str, remote_ip: str | None) -> CaptchaResult:
        data = {"secret": self.secret, "response": token}
        if remote_ip:
            data["remoteip"] = remote_ip
        try:
            response = self.client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify", data=data
            )
            if response.status_code != 200:
                return CaptchaResult(False, ["verification-unavailable"])
            payload = response.json()
            return CaptchaResult(
                payload.get("success") is True,
                [str(code) for code in payload.get("error-codes", [])],
            )
        except (httpx.RequestError, ValueError):
            return CaptchaResult(False, ["verification-unavailable"])
