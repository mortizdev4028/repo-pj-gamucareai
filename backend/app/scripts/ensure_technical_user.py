"""Create or normalise the local technical account after an upgrade."""
from __future__ import annotations

import os
from sqlalchemy import select

from app.core.security import hash_password
from app.database import SessionLocal
from app.models import User

EMAIL = os.getenv("TECHNICAL_USER_EMAIL", "technical@gamucare.local").lower().strip()
PASSWORD = os.getenv("TECHNICAL_INITIAL_PASSWORD", "GamuCare123!")


def main() -> None:
    """Ensure the technical account exists without changing an existing password."""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == EMAIL))
        if user is None:
            user = User(
                email=EMAIL,
                password_hash=hash_password(PASSWORD),
                role="technical",
                is_active=True,
                must_change_password=False,
            )
            db.add(user)
            action = "created"
        else:
            user.role = "technical"
            user.is_active = True
            action = "updated"
        db.commit()
        print(f"technical_user_{action}:{EMAIL}")


if __name__ == "__main__":
    main()
