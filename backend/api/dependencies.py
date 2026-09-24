from typing import Annotated
from uuid import UUID
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session
from core.cookies import ACCESS_COOKIE
from core.security import verify_access_token
from database.session import get_db
from modules.users.models import User
from modules.users.services import UserService


def get_current_user(access_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None, db: Session = Depends(get_db)) -> User:
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    try:
        payload = verify_access_token(access_token)
        user_id = UUID(str(payload['sub']))

        return UserService(db).get_user_by_id(user_id)
    except (HTTPException, ValueError, TypeError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )


CurrentUser = Annotated[User, Depends(get_current_user)]
