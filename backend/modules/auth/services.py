from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.config import settings
from core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
    verify_refresh_token,
)
from modules.users.models import User
from modules.users.repository import UserRepository

from .models import RefreshToken
from .repository import RefreshTokenRepository


# Role hierarchy: lowest to highest authority (only 5 roles)
ROLE_HIERARCHY: dict[str, int] = {
    "karyakarta": 1,
    "corporator": 2,
    "aamdar": 3,
    "khasdar": 4,
    "admin": 5,
}

VALID_ROLES = frozenset(ROLE_HIERARCHY.keys())


def _normalize_email(email: str) -> str:
    return email.lower().strip()


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.tokens = RefreshTokenRepository(db)

    def _issue(self, user: User):
        access = create_access_token(data={"sub": str(user.id)})
        refresh = create_refresh_token(data={"sub": str(user.id)})
        now = datetime.now(UTC)
        row = RefreshToken(
            token_hash=hash_token(refresh),
            user_id=user.id,
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.tokens.add(row)
        return access, refresh

    def create_user(
        self,
        email: str,
        name: str,
        password: str,
        role: str = "karyakarta",
        party_name: str | None = None,
        corporation: str | None = None,
        ward_no: int | None = None,
        assembly_no: str | None = None,
        parliamentary_constituency: str | None = None,
    ) -> User:
        email = _normalize_email(email)
        if self.users.get_by_email(email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="User already exists"
            )

        if role not in VALID_ROLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role '{role}'. Must be one of: {', '.join(sorted(VALID_ROLES))}",
            )

        user = User(
            name=name.strip(),
            email=email,
            hashed_password=hash_password(password),
            role=role,
            hierarchy_level=ROLE_HIERARCHY.get(role),
            party_name=party_name,
            corporation=corporation,
            ward_no=ward_no,
            assembly_no=assembly_no,
            parliamentary_constituency=parliamentary_constituency,
        )
        self.users.add(user)
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="User already exists"
            )

        # The admin remains logged in; creating a user never issues a session.
        return user

    def login(self, email: str, password: str) -> tuple[str, str]:
        user = self.users.get_by_email(_normalize_email(email))

        if (
            not user
            or not user.is_active
            or not verify_password(password, user.hashed_password)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user or password",
            )

        self.tokens.delete_expired(datetime.now(UTC))
        tokens = self._issue(user)
        self.db.commit()

        return tokens

    def refresh_token(self, raw_token: str) -> tuple[str, str]:
        invalid = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or expired",
        )
        payload = verify_refresh_token(raw_token)
        now = datetime.now(UTC)
        token_row = self.tokens.get_by_hash(hash_token(raw_token))

        if (
            token_row is None
            or token_row.revoked_at is not None
            or token_row.expires_at <= now
        ):
            raise invalid

        user = self.users.get_by_id(UUID(str(payload["sub"])))
        if user is None or not user.is_active:
            raise invalid

        self.tokens.revoke(token_row, now)
        access, refresh = self._issue(user)
        self.db.commit()

        return access, refresh

    def logout(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        token_hash = hash_token(raw_token)
        token_row = self.tokens.get_by_hash(token_hash)
        if token_row and token_row.revoked_at is None:
            self.tokens.revoke(token_row, datetime.now(UTC))
            self.db.commit()

    def request_password_reset(self, email: str) -> None:
        """Request a password reset for the given email.

        Always succeeds silently to prevent email enumeration attacks.
        In production, this would generate a time-limited reset token
        and send it via email.
        """
        user = self.users.get_by_email(_normalize_email(email))
        if user and user.is_active:
            # Generate a reset token (stored in refresh_tokens table for simplicity)
            # The token can be used to reset the password via a reset-password endpoint
            from core.security import create_access_token
            reset_token = create_access_token(
                data={"sub": str(user.id), "type": "password_reset"},
                expires_delta=timedelta(hours=1),
            )
            # Store the reset token hash for validation
            now = datetime.now(UTC)
            row = RefreshToken(
                token_hash=hash_token(reset_token),
                user_id=user.id,
                expires_at=now + timedelta(hours=1),
            )
            self.tokens.add(row)
            self.db.commit()
            # In production: send email with reset link containing reset_token
