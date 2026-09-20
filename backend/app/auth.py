"""
Production hardening: authentication + 2 fixed roles (admin/viewer).

Deliberately minimal, per the explicit instruction not to build a complicated
permission system: no self-registration, no password reset flow, no email
verification, no OAuth. Just username+password -> JWT, and one decision per
protected route -- "does this action require admin (write) or is read-only
(any authenticated user) enough?"

Originally 3 roles (admin/reviewer/viewer), with reviewer and admin sharing
identical UI capability and differing only in the invisible (no frontend
page yet) user-management endpoint -- collapsed to 2 on request, since that
distinction wasn't earning its keep yet. admin now covers both "does the
material-review work" and "manages who else can."

Why this exists at all (not just generic hardening): the audit trail built
earlier records a "reviewer" name on every decision, but before this, that
name was free-text anyone could type. Without real identity behind it, the
whole governance story -- "who approved this merge" -- was unverifiable. This
closes that gap.
"""
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import settings
from app.db import get_database

Role = Literal["admin", "viewer"]
ROLE_RANK = {"viewer": 0, "admin": 1}

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(username: str, role: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": username, "role": role, "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


class CurrentUser(BaseModel):
    username: str
    role: Role


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired, please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")

    username, role = payload.get("sub"), payload.get("role")
    if not username or role not in ROLE_RANK:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")

    # Re-check against the database, not just the token, so a deactivated/
    # deleted user's still-valid JWT stops working immediately rather than
    # silently trusting whatever role was true when the token was issued.
    db = get_database()
    user = await db.users.find_one({"username": username})
    if not user or not user.get("active", True):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found or deactivated")

    return CurrentUser(username=username, role=user["role"])


def require_role(minimum: Role):
    """Usage: Depends(require_role("admin")) -- viewer is refused, admin proceeds."""
    async def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if ROLE_RANK[user.role] < ROLE_RANK[minimum]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires '{minimum}' role or higher; you are '{user.role}'",
            )
        return user
    return _check
