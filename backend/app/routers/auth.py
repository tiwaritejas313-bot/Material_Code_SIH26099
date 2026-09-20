from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.auth import CurrentUser, Role, create_access_token, get_current_user, hash_password, require_role, verify_password
from app.db import get_database

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: Role

    @field_validator("username")
    @classmethod
    def username_format(cls, v: str) -> str:
        v = v.strip().lower()
        if len(v) < 3:
            raise ValueError("username must be at least 3 characters")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("password must be at least 8 characters")
        return v


@router.post("/login")
async def login(req: LoginRequest):
    db = get_database()
    user = await db.users.find_one({"username": req.username.strip().lower()})
    if not user or not user.get("active", True) or not verify_password(req.password, user["password_hash"]):
        # Same message either way -- don't reveal whether the username exists.
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    token = create_access_token(user["username"], user["role"])
    return {"access_token": token, "token_type": "bearer", "username": user["username"], "role": user["role"]}


@router.get("/me")
async def me(user: CurrentUser = Depends(get_current_user)):
    return user


@router.post("/users")
async def create_user(req: CreateUserRequest, _admin: CurrentUser = Depends(require_role("admin"))):
    """Admin-only. Deliberately the only user-management capability here --
    no self-registration, no password reset -- per the explicit instruction
    to keep this system simple rather than build a full identity platform."""
    db = get_database()
    existing = await db.users.find_one({"username": req.username})
    if existing:
        raise HTTPException(status_code=409, detail=f"Username '{req.username}' already exists")

    user_doc = {
        "username": req.username,
        "password_hash": hash_password(req.password),
        "role": req.role,
        "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(user_doc)
    return {"username": req.username, "role": req.role, "active": True}


@router.get("/users")
async def list_users(_admin: CurrentUser = Depends(require_role("admin"))):
    db = get_database()
    users = []
    async for u in db.users.find({}, {"password_hash": 0}):
        u["_id"] = str(u["_id"])
        users.append(u)
    return {"items": users}
