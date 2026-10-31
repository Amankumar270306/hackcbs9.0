from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Any, Dict, Optional, Tuple
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
import jwt

from app.config import settings

# Argon2id password hasher
ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
)


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against an Argon2id hash."""
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError):
        return False
    except Exception:
        return False


def create_access_token(
    subject: str,
    claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate a signed JWT access token."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4()),
        "type": "access",
    }
    if claims:
        payload.update(claims)

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "access":
            raise jwt.InvalidTokenError("Token is not an access token")
        return payload
    except jwt.PyJWTError as exc:
        raise exc


def hash_token(raw_token: str) -> str:
    """Compute deterministic SHA-256 hash for secure refresh token lookup."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_refresh_token(expires_days: Optional[int] = None) -> Tuple[str, str, str, datetime]:
    """
    Generate a cryptographically random refresh token.
    Returns: (raw_token, token_hash, jti, expires_at)
    """
    if expires_days is None:
        expires_days = settings.REFRESH_TOKEN_EXPIRE_DAYS

    raw_token = secrets.token_urlsafe(64)
    token_hash = hash_token(raw_token)
    jti = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)

    return raw_token, token_hash, jti, expires_at
