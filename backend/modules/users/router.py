from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from api.dependencies import CurrentUser
from core.cookies import clear_auth_cookies
from database.session import get_db
from .schemas import UserResponse, UserUpdate
from .services import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
def get_me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
def update_me(data: UserUpdate, current_user: CurrentUser, db: Session = Depends(get_db)) -> UserResponse:
    user = UserService(db).update_user(current_user.id, data)
    return UserResponse.model_validate(user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(response: Response, current_user: CurrentUser, db: Session = Depends(get_db)) -> None:
    UserService(db).delete_user(current_user.id)
    clear_auth_cookies(response)
