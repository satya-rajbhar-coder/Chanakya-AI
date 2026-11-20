import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.security import hash_password
from modules.admin.repository import AdminRepository
from modules.admin.schemas import ROLE_HIERARCHY
from modules.analysis.registry import get_all_database_names, get_engine
from modules.auth.repository import RefreshTokenRepository
from modules.auth.services import AuthService
from modules.documents.services import DocumentService
from modules.users.models import User

logger = logging.getLogger(__name__)


# Role hierarchy: lowest to highest authority (only 5 roles)
ROLE_HIERARCHY: dict[str, int] = {
    "karyakarta": 1,
    "corporator": 2,
    "aamdar": 3,
    "khasdar": 4,
    "admin": 5,
}

VALID_ROLES = frozenset(ROLE_HIERARCHY.keys())


def _account(repo: AdminRepository, user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "hierarchy_level": ROLE_HIERARCHY.get(user.role),
        "is_active": user.is_active,
        "party_name": user.party_name,
        "corporation": user.corporation,
        "ward_no": user.ward_no,
        "assembly_no": user.assembly_no,
        "parliamentary_constituency": user.parliamentary_constituency,
    }


def _get_user(repo: AdminRepository, user_id: UUID) -> User:
    user = repo.get_user(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


def _validate_database(database_name: str) -> None:
    """Validate that a database is reachable and has tables."""
    try:
        engine = get_engine(database_name)

        if not inspect(engine).get_table_names():
            raise LookupError("Database has no tables")

    except Exception as exc:
        logger.warning(
            "Database check failed for %s",
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


# ---------------------------------------------------------------------------
# User service (admin side)
# ---------------------------------------------------------------------------


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
            role=data.get("role", "karyakarta"),
            party_name=data.get("party_name"),
            corporation=data.get("corporation"),
            ward_no=data.get("ward_no"),
            assembly_no=data.get("assembly_no"),
            parliamentary_constituency=data.get("parliamentary_constituency"),
        )

        # Handle database assignment using database_name directly
        database_name = data.get("database_name")

        if database_name:
            available_dbs = get_all_database_names()
            if database_name not in available_dbs:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Database '{database_name}' not found in available databases",
                )

            _validate_database(database_name)

        repo.commit()

        return _account(repo, user)

    except Exception:
        repo.rollback()
        raise


def update_user(db: Session, user_id: UUID, data: dict, admin_id: UUID):
    repo = AdminRepository(db)
    user = _get_user(repo, user_id)
    admin = _get_user(repo, admin_id)

    if user.role == "admin" and user.id != admin_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin accounts must be managed on the server",
        )

    # Role hierarchy: an admin cannot promote a user to a role equal to or
    # higher than their own level.
    if data.get("role") is not None:
        new_role = data["role"]
        if new_role not in ROLE_HIERARCHY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role '{new_role}'",
            )
        admin_level = ROLE_HIERARCHY.get(admin.role, 0)
        new_level = ROLE_HIERARCHY[new_role]
        if new_level >= admin_level and user.id != admin_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot assign a role at or above your own level",
            )
        user.role = new_role
        user.hierarchy_level = new_level

    if data.get("name") is not None:
        user.name = data["name"]

    if data.get("password") is not None:
        user.hashed_password = hash_password(data["password"])

    if data.get("party_name") is not None:
        user.party_name = data["party_name"]

    if data.get("corporation") is not None:
        user.corporation = data["corporation"]

    if data.get("ward_no") is not None:
        user.ward_no = data["ward_no"]

    if data.get("assembly_no") is not None:
        user.assembly_no = data["assembly_no"]

    if data.get("parliamentary_constituency") is not None:
        user.parliamentary_constituency = data["parliamentary_constituency"]

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

    # Handle database assignment update via database_name
    if data.get("database_name") is not None:
        database_name = data["database_name"]
        if database_name:
            available_dbs = get_all_database_names()
            if database_name not in available_dbs:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Database '{database_name}' not found in available databases",
                )

            _validate_database(database_name)

    repo.commit()

    return _account(repo, user)


def delete_user(
    db: Session, user_id: UUID, admin_id: UUID, confirm: bool = False
) -> None:
    repo = AdminRepository(db)
    user = _get_user(repo, user_id)

    if user.role == "admin" and user.id != admin_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin accounts must be managed on the server",
        )

    if user.id == admin_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself",
        )

    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deletion requires confirmation. Set confirm=true to proceed.",
        )

    try:
        repo.db.delete(user)
        repo.commit()
    except Exception:
        repo.rollback()
        raise


def deactivate_user(db: Session, user_id: UUID, admin_id: UUID) -> dict:
    """Deactivate a user instead of deleting them."""
    repo = AdminRepository(db)
    user = _get_user(repo, user_id)
    admin = _get_user(repo, admin_id)

    if user.role == "admin" and user.id != admin_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin accounts must be managed on the server",
        )

    if user.id == admin_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate yourself",
        )

    user.is_active = False
    RefreshTokenRepository(db).revoke_all_for_user(
        user.id,
        datetime.now(UTC),
    )

    repo.commit()

    return _account(repo, user)


# ---------------------------------------------------------------------------
# Assignment service
# ---------------------------------------------------------------------------


def assign_user(db: Session, user_id: UUID, database_name: str | None = None):
    """Assign a user to a database."""
    repo = AdminRepository(db)
    user = _get_user(repo, user_id)

    if user.role not in ("karyakarta", "corporator", "aamdar", "khasdar", "admin"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only political roles and admin receive assignments",
        )

    try:
        if database_name:
            available_dbs = get_all_database_names()
            if database_name not in available_dbs:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Database '{database_name}' not found in available databases",
                )

            _validate_database(database_name)

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


def get_available_databases(db: Session):
    """Get all available databases from the analysis DB URL template with assignment status."""
    return AdminRepository(db).get_available_databases()