"""Run once on the server: uv run python -m scripts.create_admin admin@company.com"""

import getpass
import os
import sys

from sqlalchemy import inspect, select

# Import ALL model modules so SQLAlchemy can resolve every string-based
# relationship across the entire ORM registry before any mapper configures.
# Missing any module causes InvalidRequestError on mapper configuration.
import modules.analysis.models  # noqa: F401
import modules.auth.models  # noqa: F401
import modules.conversations.models  # noqa: F401
import modules.documents.models  # noqa: F401
import modules.messages.models  # noqa: F401
import modules.users.models  # noqa: F401
import ai_agent.intelligence.models  # noqa: F401

from core.security import hash_password
from database.session import SessionLocal, engine
from modules.users.models import User


def check_schema() -> None:
    inspector = inspect(engine)
    missing = [
        f"{table}.{column}"
        for table, columns in {
            "users": {"role", "is_active", "corporation"},
        }.items()
        if inspector.has_table(table)
        for column in (columns - {c["name"] for c in inspector.get_columns(table)})
    ]
    if missing:
        raise SystemExit(
            "The database is missing required columns: "
            + ", ".join(missing)
            + "\nRun the database migration first: alembic upgrade head"
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
            raise SystemExit(
                "An admin already exists. Manage users from the admin panel."
            )
        if db.scalar(select(User).where(User.email == email)):
            raise SystemExit("Email already exists; use a new company admin address.")
        password = os.environ.get("CREATE_ADMIN_PASSWORD") or getpass.getpass(
            "New admin password (8+ characters): "
        )
        if len(password) < 8:
            raise SystemExit("Password is too short")
        name = (os.environ.get("CREATE_ADMIN_NAME") or input("Admin name: ")).strip()
        if not name:
            raise SystemExit("Name is required")
        corporation = (
            os.environ.get("CREATE_ADMIN_CORPORATION")
            or input("Corporation / ULB (e.g., KDMC): ")
        ).strip()
        db.add(
            User(
                name=name,
                email=email,
                role="admin",
                corporation=corporation or None,
                hashed_password=hash_password(password),
            )
        )
        db.commit()
    print("Company admin created. Sign in via /login.")


if __name__ == "__main__":
    main()
