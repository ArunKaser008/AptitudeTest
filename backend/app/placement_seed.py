from __future__ import annotations

import os

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import User
from app.services.placement_auth import hash_password


def main() -> None:
    email = os.getenv("PLATFORM_ADMIN_EMAIL", "").strip().casefold()
    password = os.getenv("PLATFORM_ADMIN_PASSWORD", "")
    name = os.getenv("PLATFORM_ADMIN_NAME", "Platform administrator").strip()
    if not email or len(password) < 12:
        raise SystemExit(
            "Set PLATFORM_ADMIN_EMAIL and a PLATFORM_ADMIN_PASSWORD of at least 12 characters."
        )
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing is not None:
            print(f"Platform admin already exists: {email}")
            return
        user = User(
            email=email,
            password_hash=hash_password(password),
            display_name=name,
            role="platform_admin",
            college_id=None,
            batch_id=None,
            is_active=True,
        )
        db.add(user)
        db.commit()
    print(f"Created platform admin: {email}")


if __name__ == "__main__":
    main()
