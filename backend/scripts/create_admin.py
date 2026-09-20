"""
Bootstrap the first admin account. This is the ONLY way to create a user
before one admin exists (POST /auth/users requires an admin token already).

Usage: python scripts/create_admin.py <username> <password>
"""
import asyncio
import getpass
import pathlib
import sys
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from app.auth import hash_password
from app.config import settings


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/create_admin.py <username> [password]")
        print("(if password is omitted, you'll be prompted so it never lands in shell history)")
        sys.exit(1)

    username = sys.argv[1].strip().lower()
    password = sys.argv[2] if len(sys.argv) > 2 else getpass.getpass("Password: ")
    if len(password) < 8:
        print("Password must be at least 8 characters.")
        sys.exit(1)

    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]

    existing = await db.users.find_one({"username": username})
    if existing:
        print(f"User '{username}' already exists (role: {existing['role']}). Not overwriting.")
        client.close()
        return

    await db.users.insert_one({
        "username": username,
        "password_hash": hash_password(password),
        "role": "admin",
        "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    print(f"Admin user '{username}' created.")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
