from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.users.models import User


class AdminRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_users(self) -> list[User]:
        return list(self.db.scalars(select(User).order_by(User.email)).all())

    def get_user(self, user_id: UUID) -> User | None:
        return self.db.get(User, user_id)

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, instance) -> None:
        self.db.refresh(instance)

    def get_available_databases(self) -> list[dict]:
        """Get all available databases from the analysis DB URL template with assignment status."""
        from modules.analysis.registry import get_all_database_names

        db_names = get_all_database_names()
        result = []

        for db_name in db_names:
            # Check if any user is assigned to this database
            # In the new system, databases are assigned based on user role fields
            result.append(
                {
                    "name": db_name,
                    "is_assigned": False,  # Simplified - we don't track client assignments anymore
                    "assigned_client_id": None,
                    "assigned_client_name": None,
                }
            )

        return result
