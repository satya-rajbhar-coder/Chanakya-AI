"""Run once on the server: uv run python -m scripts.create_admin admin@company.com"""
import getpass
import os
import sys

from sqlalchemy import inspect, select

# Import routers once so every ORM model is registered before the User mapper
# resolves its string relationships (Conversation, Message, Document, ...).
import api.router  # noqa: F401
from core.security import hash_password
from database.session import SessionLocal, engine
from modules.users.models import User


def check_schema() -> None:
    inspector = inspect(engine)
    missing = [
        ".".join(pair)
        for table, columns in {
            "users": {"role", "is_active"},
            "clients": {"database_name", "client_identifier"},
            "documents": {"client_id"},
        }.items()
        if inspector.has_table(table)
        for pair in [(table, column) for column in (columns - {c["name"] for c in inspector.get_columns(table)})]
    ]
    if missing:
        raise SystemExit(
            "The database is missing required columns: " + ", ".join(missing)
            + "\nRun the one-time PostgreSQL migration first: scripts/002_client_migration.sql"
        )


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m scripts.create_admin admin@company.com")
    check_schema()
    email = sys.argv[1].strip().lower()
    if "@" not in email:
        raise SystemExit("A valid email is required")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.role == "admin")):
            raise SystemExit("An admin already exists. Manage users from the admin panel.")
        if db.scalar(select(User).where(User.email == email)):
            raise SystemExit("Email already exists; use a new company admin address.")
        # Automation: CREATE_ADMIN_PASSWORD / CREATE_ADMIN_NAME avoid getpass hanging
        # when run from scripts; interactive terminals still prompt as before.
        password = os.environ.get("CREATE_ADMIN_PASSWORD") or getpass.getpass("New admin password (12+ characters): ")
        if len(password) < 8:
            raise SystemExit("Password is too short")
        name = (os.environ.get("CREATE_ADMIN_NAME") or input("Admin name: ")).strip()
        if not name:
            raise SystemExit("Name is required")
        db.add(User(name=name, email=email, role="admin", hashed_password=hash_password(password)))
        db.commit()
    print("Company admin created. Sign in via /login.")


if __name__ == "__main__":
    main()