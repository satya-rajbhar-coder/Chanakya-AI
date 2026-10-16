import logging
import threading
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.security import hash_password
from modules.admin.repository import AdminRepository
from modules.analysis.catalog import build_catalog
from modules.analysis.registry import get_engine
from modules.auth.repository import RefreshTokenRepository
from modules.auth.services import AuthService
from modules.documents.services import DocumentService
from modules.users.models import User

logger = logging.getLogger(__name__)


def _account(repo: AdminRepository, user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "client_ids": repo.get_user_client_ids(user.id),
    }


def _get_user(repo: AdminRepository, user_id: UUID) -> User:
    user = repo.get_user(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


def _set_assignments(repo: AdminRepository, user: User, client_ids: list[UUID]) -> None:
    wanted = set(client_ids)

    existing = repo.get_existing_client_ids(wanted)

    if existing != wanted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unknown client",
        )

    current = {
        assignment.client_id: assignment for assignment in repo.get_assignments(user.id)
    }

    current_ids = set(current)

    for client_id in current_ids - wanted:
        repo.delete_assignment(current[client_id])

    for client_id in wanted - current_ids:
        repo.add_assignment(user.id, client_id)


def list_clients(db: Session):
    return AdminRepository(db).list_clients()


def create_client(db: Session, data: dict):
    repo = AdminRepository(db)
    database_name = data["database_name"]

    try:
        engine = get_engine(database_name)

        if not inspect(engine).get_table_names():
            raise LookupError("Database has no tables")

    except Exception as exc:
        logger.warning(
            "Client database check failed for %s",
            database_name,
            exc_info=True,
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Could not reach database {database_name} "
                "or it has no tables. Check the host, "
                "credentials and driver in ANALYSIS_DB_URL_TEMPLATE."
            ),
        ) from exc

    if repo.get_client_by_database_name(database_name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A database can only belong to one client",
        )

    if repo.get_client_by_identifier(data["client_identifier"]):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Client identifier already exists",
        )

    client = repo.create_client(data)

    try:
        repo.commit()
        repo.refresh(client)

    except IntegrityError as exc:
        repo.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Client code already exists",
        ) from exc

    threading.Thread(
        target=_build_catalog_safe,
        args=(database_name,),
        daemon=True,
    ).start()

    return client


def update_client(db: Session, client_id: UUID, data: dict):
    repo = AdminRepository(db)
    client = repo.get_client(client_id)

    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )

    for field in ("name", "description", "is_active"):
        if data.get(field) is not None:
            setattr(client, field, data[field])

    repo.commit()
    repo.refresh(client)

    return client


def _build_catalog_safe(database_name: str) -> None:
    try:
        build_catalog(database_name)
    except Exception:
        logger.exception("Catalog build failed for %s", database_name)


def list_users(db: Session):
    repo = AdminRepository(db)

    return [_account(repo, user) for user in repo.list_users()]


def create_user(db: Session, data: dict):
    repo = AdminRepository(db)

    try:
        user = AuthService(db).create_user(
            data["email"],
            data["name"],
            data["password"],
        )

        _set_assignments(repo, user, data["client_ids"])

        repo.commit()

        return _account(repo, user)

    except Exception:
        repo.rollback()
        raise


def update_user(db: Session, user_id: UUID, data: dict, admin_id: UUID):
    repo = AdminRepository(db)
    user = _get_user(repo, user_id)

    if user.role == "admin" and user.id != admin_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin accounts must be managed on the server",
        )

    if data.get("name") is not None:
        user.name = data["name"]

    if data.get("password") is not None:
        user.hashed_password = hash_password(data["password"])

    if data.get("is_active") is not None:
        if user.id == admin_id and not data["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate yourself",
            )

        user.is_active = data["is_active"]

    if data.get("password") is not None or data.get("is_active") is False:
        RefreshTokenRepository(db).revoke_all_for_user(
            user.id,
            datetime.now(UTC),
        )

    repo.commit()

    return _account(repo, user)


def assign_user(db: Session, user_id: UUID, client_ids: list[UUID]):
    repo = AdminRepository(db)
    user = _get_user(repo, user_id)

    if user.role != "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only dashboard users receive assignments",
        )

    try:
        _set_assignments(repo, user, client_ids)
        repo.commit()

        return _account(repo, user)

    except Exception:
        repo.rollback()
        raise


def assign_document(db: Session, document_id: UUID, user_ids: list[UUID]):
    return DocumentService(db).set_assignments(
        document_id,
        user_ids,
    )
