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
from modules.analysis.models import Client
from modules.analysis.registry import get_all_database_names, get_engine
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
        "hierarchy_level": ROLE_HIERARCHY.get(user.role),
        "is_active": user.is_active,
        "party_name": user.party_name,
        "ward_no": user.ward_no,
        "assembly_no": user.assembly_no,
        "parliamentary_constituency": user.parliamentary_constituency,
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


def _validate_database(database_name: str) -> None:
    """Validate that a client database is reachable and has tables."""
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


# ---------------------------------------------------------------------------
# Client service
# ---------------------------------------------------------------------------


def list_clients(db: Session):
    return AdminRepository(db).list_clients()


def get_available_databases(db: Session):
    """Get all available databases from the analysis DB URL template with assignment status."""
    return AdminRepository(db).get_available_databases()


def create_client(db: Session, data: dict):
    repo = AdminRepository(db)
    database_name = data["database_name"]

    # Validate that the database exists in the analysis DB URL template
    available_dbs = get_all_database_names()
    if database_name not in available_dbs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database '{database_name}' not found in available databases. Available: {', '.join(available_dbs)}",
        )

    _validate_database(database_name)

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

    return client


def update_client(db: Session, client_id: UUID, data: dict):
    repo = AdminRepository(db)
    client = repo.get_client(client_id)

    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )

    # Re-validate database if database_name is being changed
    new_db = data.get("database_name")
    if new_db is not None and new_db != client.database_name:
        available_dbs = get_all_database_names()
        if new_db not in available_dbs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Database '{new_db}' not found in available databases. Available: {', '.join(available_dbs)}",
            )
        _validate_database(new_db)

        if repo.get_client_by_database_name(new_db):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A database can only belong to one client",
            )

    if data.get("client_identifier") is not None:
        new_id = data["client_identifier"]
        if new_id != client.client_identifier and repo.get_client_by_identifier(new_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Client identifier already exists",
            )

    for field in (
        "name",
        "description",
        "is_active",
        "database_name",
        "client_identifier",
    ):
        if data.get(field) is not None:
            setattr(client, field, data[field])

    repo.commit()
    repo.refresh(client)

    return client


def delete_client(db: Session, client_id: UUID) -> None:
    repo = AdminRepository(db)
    client = repo.get_client(client_id)

    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )

    try:
        repo.db.delete(client)
        repo.commit()
    except Exception:
        repo.rollback()
        raise


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
            role=data.get("role", "user"),
            party_name=data.get("party_name"),
            ward_no=data.get("ward_no"),
            assembly_no=data.get("assembly_no"),
            parliamentary_constituency=data.get("parliamentary_constituency"),
        )

        # Handle database_name: create or find client for the database
        client_ids = list(data.get("client_ids", []))
        database_name = data.get("database_name")
        
        if database_name:
            # Check if client already exists for this database
            existing_client = repo.get_client_by_database_name(database_name)
            if existing_client:
                client_ids.append(str(existing_client))
            else:
                # Create a new client for this database
                from modules.analysis.registry import get_all_database_names
                available_dbs = get_all_database_names()
                if database_name not in available_dbs:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Database '{database_name}' not found in available databases",
                    )
                
                _validate_database(database_name)
                
                # Generate client code and identifier from database name
                client_code = database_name.upper().replace("-", "_")[:100]
                client_identifier = database_name.lower().replace("-", "_")[:100]
                
                # Ensure unique code and identifier
                base_code = client_code
                base_identifier = client_identifier
                counter = 1
                while repo.get_client_by_identifier(client_identifier):
                    client_identifier = f"{base_identifier}_{counter}"
                    counter += 1
                counter = 1
                while repo.db.scalar(select(Client.id).where(Client.code == client_code)):
                    client_code = f"{base_code}_{counter}"
                    counter += 1
                
                new_client = repo.create_client({
                    "code": client_code,
                    "name": database_name.replace("_", " ").replace("-", " ").title(),
                    "database_name": database_name,
                    "client_identifier": client_identifier,
                    "description": f"Auto-created for database {database_name}",
                })
                repo.flush()
                client_ids.append(str(new_client.id))

        _set_assignments(repo, user, [UUID(cid) for cid in client_ids])

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

    # Handle client assignments update
    if data.get("client_ids") is not None:
        _set_assignments(repo, user, data["client_ids"])

    repo.commit()

    return _account(repo, user)


def delete_user(db: Session, user_id: UUID, admin_id: UUID, confirm: bool = False) -> None:
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


def assign_user(db: Session, user_id: UUID, client_ids: list[UUID]):
    repo = AdminRepository(db)
    user = _get_user(repo, user_id)

    if user.role not in ("user", "karyakarta", "corporator", "aamdar", "khasdar"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only dashboard and political roles receive assignments",
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
