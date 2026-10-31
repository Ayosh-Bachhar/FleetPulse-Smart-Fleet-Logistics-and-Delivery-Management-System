"""Create an authorized FleetPulse staff/driver account.

Run from backend/:
    .\\.venv\\Scripts\\python.exe -m scripts.seed_users
"""

import asyncio
from getpass import getpass

from pydantic import EmailStr, TypeAdapter, ValidationError
from pymongo.errors import DuplicateKeyError

from app.core.security import hash_password
from app.database.connection import (
    connect_to_database,
    close_database_connection,
)
from app.models.user import User, Role


async def create_staff_user():
    print("\nFleetPulse - Create Staff/Driver Account\n")

    role_input = input(
        "Role (admin/dispatcher/driver): "
    ).strip().lower()

    if role_input not in ("admin", "dispatcher", "driver"):
        print("Invalid role.")
        return

    full_name = input("Full name: ").strip()
    email_input = input("Email: ").strip().lower()
    password = getpass("Password: ")

    if not 2 <= len(full_name) <= 100:
        print("Name must contain 2-100 characters.")
        return

    try:
        email = str(
            TypeAdapter(EmailStr).validate_python(email_input)
        )
    except ValidationError:
        print("Invalid email address.")
        return

    if len(password) < 8:
        print("Password must contain at least 8 characters.")
        return

    if len(password.encode("utf-8")) > 72:
        print("Password must not exceed 72 UTF-8 bytes.")
        return

    await connect_to_database()

    try:
        existing = await User.find_one(
            User.email == email
        )

        if existing:
            print("Account already exists. No changes made.")
            return

        new_user = User(
            full_name=full_name,
            email=email,
            password_hash=hash_password(password),
            role=Role(role_input),
            is_active=True,
        )

        try:
            await new_user.insert()
        except DuplicateKeyError:
            print("Account already exists.")
            return

        print(f"\n{role_input.title()} account created.")
        print("You can now log in to FleetPulse.")

    finally:
        await close_database_connection()


if __name__ == "__main__":
    asyncio.run(create_staff_user())