import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.security import hash_password, verify_password
from modules.auth.repository import RefreshTokenRepository
from rag.service import delete_user_chunks
from .models import User
from .repository import UserRepository
from .schemas import UserUpdate

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = UserRepository(db)

    def get_user_by_id(self, user_id: UUID) -> User:
        user = self.repo.get_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User does not exist"
            )
        return user

    def update_user(self, user_id: UUID, data: UserUpdate) -> User:
        user = self.get_user_by_id(user_id)

        if data.name is not None:
            user.name = data.name

        if data.password is not None:
            if not verify_password(data.current_password or "", user.hashed_password):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Current password is incorrect"
                )
            user.hashed_password = hash_password(data.password)
            RefreshTokenRepository(self.db).revoke_all_for_user(
                user.id, datetime.now(timezone.utc)
            )

        try:
            self.db.commit()
            self.db.refresh(user)
        except Exception:
            self.db.rollback()
            raise
        return user

    def delete_user(self, user_id: UUID) -> None:
        user = self.get_user_by_id(user_id)
        try:
            self.repo.delete(user)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        # Rows are gone (documents cascade); now drop the user's vectors too.
        try:
            delete_user_chunks(user_id)
        except Exception:
            logger.exception("Could not delete vectors for user %s", user_id)
