"""Admin CLI: create (or reset) a user in an existing org.

Usage: NEW_USER_PASSWORD=... python -m scripts.create_user --org <slug> --email x@y --role viewer
The password is read from the NEW_USER_PASSWORD environment variable (never from argv, so it does
not end up in shell history or process listings).
"""

from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import select

from app.core.db import session_scope
from app.core.security import hash_password
from app.models import Org, User


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", required=True)
    ap.add_argument("--email", required=True)
    ap.add_argument("--role", choices=["admin", "member", "viewer"], default="viewer")
    ap.add_argument("--name", default="")
    a = ap.parse_args()
    password = os.environ.get("NEW_USER_PASSWORD", "")
    if len(password) < 12:
        sys.exit("Set NEW_USER_PASSWORD (>= 12 characters)")
    with session_scope() as s:
        org = s.scalar(select(Org).where(Org.slug == a.org))
        if org is None:
            sys.exit(f"org {a.org!r} not found")
        user = s.scalar(select(User).where(User.email == a.email.lower()))
        if user is None:
            user = User(org_id=org.id, email=a.email.lower(), display_name=a.name or a.email, role=a.role,
                        password_hash=hash_password(password))
            s.add(user)
        else:
            user.password_hash, user.role = hash_password(password), a.role
        s.commit()
    print(f"user {a.email} ready (role={a.role}, org={a.org})")


if __name__ == "__main__":
    main()
