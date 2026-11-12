"""Authentication endpoints and injectable permission dependencies."""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from routepilot.identity.service import IdentityService, LoginBody, LoginInput
from routepilot.shared.auth import Principal
from routepilot.shared.config import Settings
from routepilot.shared.errors import DomainError


def require_user(service: IdentityService) -> Callable[[Request], Principal]:
    def dependency(request: Request) -> Principal:
        return service.require_user(request.cookies.get("rp_session"))

    return dependency


def require_role(service: IdentityService, *roles: str) -> Callable[[Request], Principal]:
    def dependency(request: Request) -> Principal:
        principal = service.require_user(request.cookies.get("rp_session"))
        if principal.role not in roles:
            raise DomainError("FORBIDDEN", 403)
        return principal

    return dependency


def create_identity_router(service: IdentityService, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
    user_dependency = require_user(service)

    async def check_login(request: Request) -> None:
        try:
            data = await request.json()
        except ValueError:
            data = {}
        email = data.get("email", "") if isinstance(data, dict) else ""
        service.check_login_rate(
            email if isinstance(email, str) else "", request.client.host if request.client else None
        )
        if request.headers.get("Origin") not in settings.origins:
            raise DomainError("ORIGIN_NOT_ALLOWED", 403)

    @router.get("/captcha-config")
    def captcha_config() -> dict[str, str]:
        return {"provider": "turnstile", "siteKey": settings.turnstile_site_key}

    @router.post("/login", response_model=LoginBody, dependencies=[Depends(check_login)])
    def login(body: LoginInput, request: Request, response: Response) -> LoginBody:
        result = service.login(
            body.email,
            body.password,
            body.captcha_token,
            request.client.host if request.client else None,
            request.headers.get("User-Agent", ""),
            rate_checked=True,
        )
        secure = request.url.scheme == "https"
        response.set_cookie(
            "rp_session", result.token, httponly=True, samesite="lax", secure=secure, path="/"
        )
        response.set_cookie("rp_csrf", result.csrf_token, samesite="lax", secure=secure, path="/")
        return LoginBody(user=result.user, csrfToken=result.csrf_token)

    @router.get("/me", response_model=LoginBody)
    def me(principal: Annotated[Principal, Depends(user_dependency)]) -> LoginBody:
        return LoginBody(
            user=service.public_user(principal.id), csrfToken=service.csrf_token(principal)
        )

    @router.post("/logout", status_code=204)
    def logout(
        request: Request, principal: Annotated[Principal, Depends(user_dependency)]
    ) -> Response:
        service.logout(request.cookies["rp_session"])
        response = Response(status_code=204)
        response.delete_cookie("rp_session", path="/")
        response.delete_cookie("rp_csrf", path="/")
        return response

    return router
