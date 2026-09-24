from fastapi import Response

from .config import settings

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"

# The refresh cookie used to be scoped to /api/auth. The Next.js middleware
# needs to see it (to silently renew an expired access token), so it is now
# scoped to "/". The legacy path is still cleared on logout.
LEGACY_REFRESH_PATH = "/api/auth"


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        ACCESS_COOKIE, access_token,
        httponly=True, secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE, refresh_token,
        httponly=True, secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=LEGACY_REFRESH_PATH)
