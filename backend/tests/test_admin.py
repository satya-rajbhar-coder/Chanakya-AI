"""Tests for the admin module."""

import pytest
from unittest.mock import patch
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from pydantic import ValidationError

from database.base import Base
# Import all models to register them with Base.metadata
import api.router  # noqa: F401
import modules.admin.repository  # noqa: F401
import modules.analysis.models  # noqa: F401
import modules.auth.models  # noqa: F401
import modules.conversations.models  # noqa: F401
import modules.documents.models  # noqa: F401
import modules.messages.models  # noqa: F401
import modules.users.models  # noqa: F401

from modules.admin.services import (
    create_client,
    update_client,
    delete_client,
    list_clients,
    create_user,
    update_user,
    delete_user,
    list_users,
    assign_user,
)
from modules.admin.schemas import ClientCreate, AccountCreate, AssignmentsUpdate
from modules.analysis.models import Client, UserClient
from modules.users.models import User
from core.security import hash_password


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


@pytest.fixture
def mock_validate_database():
    """Mock the _validate_database function to avoid database connections."""
    with patch("modules.admin.services._validate_database") as mock:
        yield mock


@pytest.fixture
def admin_user(db_session):
    """Create an admin user for testing."""
    admin = User(
        id=uuid4(),
        name="Admin User",
        email="admin@test.com",
        hashed_password=hash_password("adminpass123"),
        role="admin",
        hierarchy_level=6,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def regular_user(db_session):
    """Create a regular user for testing."""
    user = User(
        id=uuid4(),
        name="Regular User",
        email="user@test.com",
        hashed_password=hash_password("userpass123"),
        role="user",
        hierarchy_level=5,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def karyakarta_user(db_session):
    """Create a karyakarta user for testing."""
    user = User(
        id=uuid4(),
        name="Karyakarta User",
        email="karyakarta@test.com",
        hashed_password=hash_password("karyapass123"),
        role="karyakarta",
        hierarchy_level=1,
        is_active=True,
        ward_no=5,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_client(db_session):
    """Create a test client."""
    client = Client(
        id=uuid4(),
        code="TEST001",
        name="Test Client",
        database_name="test_db",
        client_identifier="test_client",
        description="Test client for testing",
        is_active=True,
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


@pytest.fixture
def admin_user(db_session):
    """Create an admin user for testing."""
    admin = User(
        id=uuid4(),
        name="Admin User",
        email="admin@test.com",
        hashed_password=hash_password("adminpass123"),
        role="admin",
        hierarchy_level=6,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def regular_user(db_session):
    """Create a regular user for testing."""
    user = User(
        id=uuid4(),
        name="Regular User",
        email="user@test.com",
        hashed_password=hash_password("userpass123"),
        role="user",
        hierarchy_level=5,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def karyakarta_user(db_session):
    """Create a karyakarta user for testing."""
    user = User(
        id=uuid4(),
        name="Karyakarta User",
        email="karyakarta@test.com",
        hashed_password=hash_password("karyapass123"),
        role="karyakarta",
        hierarchy_level=1,
        is_active=True,
        ward_no=5,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_client(db_session):
    """Create a test client."""
    client = Client(
        id=uuid4(),
        code="TEST001",
        name="Test Client",
        database_name="test_db",
        client_identifier="test_client",
        description="Test client for testing",
        is_active=True,
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


class TestClientManagement:
    """Tests for client management."""

    def test_create_client(self, db_session, mock_validate_database):
        """Test creating a client."""
        data = {
            "code": "NEW001",
            "name": "New Client",
            "database_name": "new_db",
            "client_identifier": "new_client",
            "description": "New client for testing",
        }
        client = create_client(db_session, data)
        assert client.code == "NEW001"
        assert client.name == "New Client"
        assert client.database_name == "new_db"
        assert client.client_identifier == "new_client"
        assert client.is_active is True
        mock_validate_database.assert_called_once_with("new_db")

    def test_create_client_duplicate_database_name(self, db_session, test_client, mock_validate_database):
        """Test creating a client with duplicate database name fails."""
        data = {
            "code": "NEW002",
            "name": "New Client 2",
            "database_name": test_client.database_name,  # Duplicate
            "client_identifier": "new_client_2",
        }
        with pytest.raises(HTTPException) as exc_info:
            create_client(db_session, data)
        assert exc_info.value.status_code == 409
        assert "database can only belong to one client" in exc_info.value.detail

    def test_create_client_duplicate_identifier(self, db_session, test_client, mock_validate_database):
        """Test creating a client with duplicate identifier fails."""
        data = {
            "code": "NEW003",
            "name": "New Client 3",
            "database_name": "new_db_3",
            "client_identifier": test_client.client_identifier,  # Duplicate
        }
        with pytest.raises(HTTPException) as exc_info:
            create_client(db_session, data)
        assert exc_info.value.status_code == 409
        assert "Client identifier already exists" in exc_info.value.detail

    def test_list_clients(self, db_session, test_client):
        """Test listing clients."""
        clients = list_clients(db_session)
        assert len(clients) == 1
        assert clients[0].id == test_client.id

    def test_update_client(self, db_session, test_client, mock_validate_database):
        """Test updating a client."""
        updated = update_client(db_session, test_client.id, {"name": "Updated Name", "description": "Updated description"})
        assert updated.name == "Updated Name"
        assert updated.description == "Updated description"

    def test_update_client_not_found(self, db_session):
        """Test updating a non-existent client fails."""
        with pytest.raises(HTTPException) as exc_info:
            update_client(db_session, uuid4(), {"name": "Updated"})
        assert exc_info.value.status_code == 404

    def test_delete_client(self, db_session, test_client):
        """Test deleting a client."""
        delete_client(db_session, test_client.id)
        clients = list_clients(db_session)
        assert len(clients) == 0

    def test_delete_client_not_found(self, db_session):
        """Test deleting a non-existent client fails."""
        with pytest.raises(HTTPException) as exc_info:
            delete_client(db_session, uuid4())
        assert exc_info.value.status_code == 404


class TestUserManagement:
    """Tests for user management."""

    def test_list_users(self, db_session, admin_user, regular_user):
        """Test listing users."""
        users = list_users(db_session)
        assert len(users) == 2
        emails = {u["email"] for u in users}
        assert "admin@test.com" in emails
        assert "user@test.com" in emails

    def test_create_user(self, db_session, admin_user):
        """Test creating a user."""
        data = {
            "email": "newuser@test.com",
            "name": "New User",
            "password": "newpass123",
            "role": "user",
            "client_ids": [],
        }
        user = create_user(db_session, data)
        assert user["email"] == "newuser@test.com"
        assert user["name"] == "New User"
        assert user["role"] == "user"

    def test_create_user_duplicate_email(self, db_session, admin_user, regular_user):
        """Test creating a user with duplicate email fails."""
        data = {
            "email": regular_user.email,  # Duplicate
            "name": "New User",
            "password": "newpass123",
            "role": "user",
            "client_ids": [],
        }
        with pytest.raises(HTTPException) as exc_info:
            create_user(db_session, data)
        assert exc_info.value.status_code == 409
        assert "User already exists" in exc_info.value.detail

    def test_update_user(self, db_session, admin_user, regular_user):
        """Test updating a user."""
        updated = update_user(db_session, regular_user.id, {"name": "Updated Name"}, admin_user.id)
        assert updated["name"] == "Updated Name"

    def test_update_user_not_found(self, db_session, admin_user):
        """Test updating a non-existent user fails."""
        with pytest.raises(HTTPException) as exc_info:
            update_user(db_session, uuid4(), {"name": "Updated"}, admin_user.id)
        assert exc_info.value.status_code == 404

    def test_update_user_admin_cannot_modify_other_admin(self, db_session, admin_user):
        """Test that admin cannot modify another admin."""
        # Create another admin
        other_admin = User(
            id=uuid4(),
            name="Other Admin",
            email="otheradmin@test.com",
            hashed_password=hash_password("adminpass123"),
            role="admin",
            hierarchy_level=6,
            is_active=True,
        )
        db_session.add(other_admin)
        db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            update_user(db_session, other_admin.id, {"name": "Hacked"}, admin_user.id)
        assert exc_info.value.status_code == 403
        assert "Admin accounts must be managed on the server" in exc_info.value.detail

    def test_update_user_cannot_promote_above_own_level(self, db_session, admin_user, regular_user):
        """Test that admin cannot promote user to admin level."""
        with pytest.raises(HTTPException) as exc_info:
            update_user(db_session, regular_user.id, {"role": "admin"}, admin_user.id)
        assert exc_info.value.status_code == 403
        assert "Cannot assign a role at or above your own level" in exc_info.value.detail

    def test_delete_user(self, db_session, admin_user, regular_user):
        """Test deleting a user."""
        delete_user(db_session, regular_user.id, admin_user.id)
        users = list_users(db_session)
        assert len(users) == 1
        assert users[0]["email"] == "admin@test.com"

    def test_delete_user_not_found(self, db_session, admin_user):
        """Test deleting a non-existent user fails."""
        with pytest.raises(HTTPException) as exc_info:
            delete_user(db_session, uuid4(), admin_user.id)
        assert exc_info.value.status_code == 404

    def test_delete_user_cannot_delete_self(self, db_session, admin_user):
        """Test that admin cannot delete themselves."""
        with pytest.raises(HTTPException) as exc_info:
            delete_user(db_session, admin_user.id, admin_user.id)
        assert exc_info.value.status_code == 400
        assert "Cannot delete yourself" in exc_info.value.detail

    def test_delete_user_cannot_delete_other_admin(self, db_session, admin_user):
        """Test that admin cannot delete another admin."""
        other_admin = User(
            id=uuid4(),
            name="Other Admin",
            email="otheradmin@test.com",
            hashed_password=hash_password("adminpass123"),
            role="admin",
            hierarchy_level=6,
            is_active=True,
        )
        db_session.add(other_admin)
        db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            delete_user(db_session, other_admin.id, admin_user.id)
        assert exc_info.value.status_code == 403
        assert "Admin accounts must be managed on the server" in exc_info.value.detail


class TestUserAssignment:
    """Tests for user-client assignments."""

    def test_assign_user(self, db_session, admin_user, karyakarta_user, test_client):
        """Test assigning a user to clients."""
        result = assign_user(db_session, karyakarta_user.id, [test_client.id])
        assert test_client.id in result["client_ids"]

    def test_assign_user_multiple_clients(self, db_session, admin_user, karyakarta_user, test_client):
        """Test assigning a user to multiple clients."""
        # Create another client
        client2 = Client(
            id=uuid4(),
            code="TEST002",
            name="Test Client 2",
            database_name="test_db_2",
            client_identifier="test_client_2",
            is_active=True,
        )
        db_session.add(client2)
        db_session.commit()

        result = assign_user(db_session, karyakarta_user.id, [test_client.id, client2.id])
        assert test_client.id in result["client_ids"]
        assert client2.id in result["client_ids"]

    def test_assign_user_unknown_client(self, db_session, admin_user, karyakarta_user):
        """Test assigning a user to unknown client fails."""
        with pytest.raises(HTTPException) as exc_info:
            assign_user(db_session, karyakarta_user.id, [uuid4()])
        assert exc_info.value.status_code == 400
        assert "Unknown client" in exc_info.value.detail

    def test_assign_user_admin_not_allowed(self, db_session, admin_user, test_client):
        """Test that admin users cannot be assigned to clients."""
        with pytest.raises(HTTPException) as exc_info:
            assign_user(db_session, admin_user.id, [test_client.id])
        assert exc_info.value.status_code == 400
        assert "Only dashboard and political roles receive assignments" in exc_info.value.detail

    def test_assign_user_remove_assignment(self, db_session, admin_user, karyakarta_user, test_client):
        """Test removing all assignments from a user."""
        # First assign
        assign_user(db_session, karyakarta_user.id, [test_client.id])
        # Then remove
        result = assign_user(db_session, karyakarta_user.id, [])
        assert result["client_ids"] == []


class TestRoleHierarchy:
    """Tests for role hierarchy validation."""

    def test_karyakarta_requires_ward_no(self):
        """Test that karyakarta role requires ward_no."""
        with pytest.raises(ValidationError) as exc_info:
            AccountCreate(
                name="Test",
                email="test@test.com",
                password="password123",
                role="karyakarta",
            )
        assert "ward_no is required for karyakarta role" in str(exc_info.value)

    def test_corporator_requires_ward_no(self):
        """Test that corporator role requires ward_no."""
        with pytest.raises(ValidationError) as exc_info:
            AccountCreate(
                name="Test",
                email="test@test.com",
                password="password123",
                role="corporator",
            )
        assert "ward_no is required for corporator role" in str(exc_info.value)

    def test_aamdar_requires_assembly_no(self):
        """Test that aamdar role requires assembly_no."""
        with pytest.raises(ValidationError) as exc_info:
            AccountCreate(
                name="Test",
                email="test@test.com",
                password="password123",
                role="aamdar",
            )
        assert "assembly_no is required for aamdar role" in str(exc_info.value)

    def test_khasdar_requires_parliamentary_constituency(self):
        """Test that khasdar role requires parliamentary_constituency."""
        with pytest.raises(ValidationError) as exc_info:
            AccountCreate(
                name="Test",
                email="test@test.com",
                password="password123",
                role="khasdar",
            )
        assert "parliamentary_constituency is required for khasdar role" in str(exc_info.value)

    def test_user_role_no_requirements(self):
        """Test that user role has no special requirements."""
        data = AccountCreate(
            name="Test",
            email="test@test.com",
            password="password123",
            role="user",
        )
        # Should not raise
        assert data.role == "user"

    def test_admin_role_no_requirements(self):
        """Test that admin role has no special requirements."""
        data = AccountCreate(
            name="Test",
            email="test@test.com",
            password="password123",
            role="admin",
        )
        # Should not raise
        assert data.role == "admin"