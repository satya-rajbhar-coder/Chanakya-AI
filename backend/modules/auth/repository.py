from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from .models import RefreshToken


class RefreshTokenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, token: RefreshToken) -> RefreshToken:
        self.db.add(token)
        return token

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)

        return self.db.scalar(stmt)

    def revoke(self, token: RefreshToken, now: datetime) -> None:
        token.revoked_at = now

    def revoke_all_for_user(self, user_id: UUID, now: datetime) -> None:
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        self.db.execute(stmt)

    def delete_expired(self, now: datetime) -> int:
        stmt = delete(RefreshToken).where(RefreshToken.expires_at <= now)

        result = self.db.execute(stmt)
        return result.rowcount or 0
