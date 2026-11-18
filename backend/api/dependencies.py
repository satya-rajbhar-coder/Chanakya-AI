from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from core.cookies import ACCESS_COOKIE
from core.security import verify_access_token
from database.session import get_db
from modules.admin.schemas import ROLE_HIERARCHY
from modules.users.models import User
from modules.users.services import UserService


def get_current_user(
    access_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
    db: Session = Depends(get_db),
) -> User:
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    try:
        payload = verify_access_token(access_token)
        user_id = UUID(str(payload["sub"]))

        user = UserService(db).get_user_by_id(user_id)
        if not user.is_active:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account disabled")
        return user
    except (HTTPException, ValueError, TypeError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def require_role(min_role: str):
    """Return a dependency that requires the user's role level to be >= min_role level."""
    if min_role not in ROLE_HIERARCHY:
        raise ValueError(f"Unknown role: {min_role}")

    def checker(user: CurrentUser) -> User:
        user_level = ROLE_HIERARCHY.get(user.role, 0)
        min_level = ROLE_HIERARCHY[min_role]
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' is not authorized; requires at least '{min_role}'",
            )
        return user

    return checker


RequireKaryakarta = Annotated[User, Depends(require_role("karyakarta"))]
RequireCorporator = Annotated[User, Depends(require_role("corporator"))]
RequireAamdar = Annotated[User, Depends(require_role("aamdar"))]
RequireKhasdar = Annotated[User, Depends(require_role("khasdar"))]


def user_scope(user: User) -> dict:
    """Return the data scope for a user based on their role and assignments.

    Returns a dict with keys: ward_no, assembly_no, parliamentary_constituency.
    Higher-level roles inherit broader scope.
    """
    scope: dict[str, str | None] = {
        "ward_no": None,
        "assembly_no": None,
        "parliamentary_constituency": None,
    }

    role = user.role
    level = ROLE_HIERARCHY.get(role, 0)

    if role == "admin":
        return scope  # admin sees everything (no filter)

    if level >= ROLE_HIERARCHY["karyakarta"] and user.ward_no:
        scope["ward_no"] = user.ward_no
    if level >= ROLE_HIERARCHY["corporator"] and user.ward_no:
        scope["ward_no"] = user.ward_no
    if level >= ROLE_HIERARCHY["aamdar"] and user.assembly_no:
        scope["assembly_no"] = user.assembly_no
    if level >= ROLE_HIERARCHY["khasdar"] and user.parliamentary_constituency:
        scope["parliamentary_constituency"] = user.parliamentary_constituency

    return scope


def get_user_scope(user: CurrentUser) -> dict:
    return user_scope(user)


UserScope = Annotated[dict, Depends(get_user_scope)]
