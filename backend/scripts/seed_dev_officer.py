"""
seed_dev_officer.py
====================
Creates (or updates) exactly one DEVELOPMENT-only municipal officer account
so `POST /auth/officer/login` has something real to authenticate against
locally.

    python -m backend.scripts.seed_dev_officer

Configuration is read entirely from the environment, with a fallback so the
command runs out of the box for local development:

    OFFICER_EMAIL     (default: officer@example.com)
    OFFICER_PASSWORD  (default: dev-officer-password-change-me)
    OFFICER_NAME      (default: Development Officer)
    OFFICER_DEPARTMENT (optional)

The password is hashed with `app.auth.security.hash_password` before it
touches the database -- the plaintext value from the environment is never
persisted. Re-running this script is safe: it upserts by email rather than
inserting a duplicate row, and re-hashes the (possibly changed) password
each time.

This is a development convenience only. It is not how real officer accounts
should be provisioned in a deployed environment.
"""

from __future__ import annotations

import os

from backend.app.auth.security import hash_password
from backend.app.database import SessionLocal
from backend.app.models import Officer

DEFAULT_EMAIL = "officer@example.com"
DEFAULT_PASSWORD = "dev-officer-password-change-me"
DEFAULT_NAME = "Development Officer"


def main() -> None:
    email = os.getenv("OFFICER_EMAIL", DEFAULT_EMAIL)
    password = os.getenv("OFFICER_PASSWORD", DEFAULT_PASSWORD)
    name = os.getenv("OFFICER_NAME", DEFAULT_NAME)
    department = os.getenv("OFFICER_DEPARTMENT")

    db = SessionLocal()

    try:
        officer = db.query(Officer).filter(Officer.email == email).first()

        if officer is None:
            officer = Officer(email=email)
            db.add(officer)
            action = "Created"
        else:
            action = "Updated"

        officer.name = name
        officer.password_hash = hash_password(password)
        officer.department = department
        officer.is_active = True

        db.commit()

        print(f"{action} development officer: {email}")
        if password == DEFAULT_PASSWORD:
            print(
                "WARNING: using the default development password. "
                "Set OFFICER_PASSWORD to override it."
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
