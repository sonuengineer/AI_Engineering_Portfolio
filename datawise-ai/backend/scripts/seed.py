"""Seed the app database: two orgs (for tenant isolation) and demo users.

Passwords come from DEMO_USER_PASSWORD (placeholder in .env.example -- never a real secret).
Idempotent: existing users get their password reset to the current DEMO_USER_PASSWORD.

    uv run python -m scripts.seed
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.security import hash_password
from app.models import Org, User

DEMO_USERS = [
    ("Acme Retail", "demo@acme.example", "Dana Demo", "admin"),
    ("Acme Retail", "analyst@acme.example", "Alex Analyst", "analyst"),
    ("Globex Corp", "demo@globex.example", "Gary Globex", "admin"),
]


def main() -> None:
    pw_hash = hash_password(get_settings().demo_user_password)
    with get_sessionmaker()() as db:
        orgs: dict[str, Org] = {}
        for org_name, email, full_name, role in DEMO_USERS:
            org = orgs.get(org_name) or db.scalar(select(Org).where(Org.name == org_name))
            if org is None:
                org = Org(name=org_name)
                db.add(org)
                db.flush()
            orgs[org_name] = org
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                db.add(User(org_id=org.id, email=email, full_name=full_name, role=role, password_hash=pw_hash))
            else:
                user.password_hash = pw_hash
        db.commit()
    print("seeded demo users:", ", ".join(u[1] for u in DEMO_USERS))


if __name__ == "__main__":
    main()
