from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.analysis.models import Client, UserClient
from modules.users.models import User


class AdminRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_clients(self) -> list[Client]:
        return list(self.db.scalars(select(Client).order_by(Client.code)).all())

    def get_client(self, client_id: UUID) -> Client | None:
        return self.db.get(Client, client_id)

    def get_client_by_database_name(self, database_name: str) -> UUID | None:
        return self.db.scalar(
            select(Client.id).where(Client.database_name == database_name)
        )

    def get_client_by_identifier(self, identifier: str) -> UUID | None:
        return self.db.scalar(
            select(Client.id).where(Client.client_identifier == identifier)
        )

    def create_client(self, data: dict) -> Client:
        client = Client(**data)
        self.db.add(client)
        return client

    def list_users(self) -> list[User]:
        return list(self.db.scalars(select(User).order_by(User.email)).all())

    def get_user(self, user_id: UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_user_client_ids(self, user_id: UUID) -> list[UUID]:
        return list(
            self.db.scalars(
                select(UserClient.client_id).where(UserClient.user_id == user_id)
            ).all()
        )

    def get_assignments(self, user_id: UUID) -> list[UserClient]:
        return list(
            self.db.scalars(
                select(UserClient).where(UserClient.user_id == user_id)
            ).all()
        )

    def get_existing_client_ids(self, client_ids: set[UUID]) -> set[UUID]:
        if not client_ids:
            return set()

        return set(
            self.db.scalars(select(Client.id).where(Client.id.in_(client_ids))).all()
        )

    def add_assignment(self, user_id: UUID, client_id: UUID) -> None:
        self.db.add(
            UserClient(
                user_id=user_id,
                client_id=client_id,
            )
        )

    def delete_assignment(self, assignment: UserClient) -> None:
        self.db.delete(assignment)

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, instance) -> None:
        self.db.refresh(instance)
