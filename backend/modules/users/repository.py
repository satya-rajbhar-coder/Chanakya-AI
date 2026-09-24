from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, user: User) -> User:
        self.db.add(user)
        return user

    def get_by_id(self, user_id: UUID) -> User | None:
        stmt = select(User).where(User.id == user_id)
        return self.db.scalar(stmt)

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return self.db.scalar(stmt)

    def delete(self, user: User) -> None:
        self.db.delete(user)
