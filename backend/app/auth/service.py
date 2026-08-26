"""
service.py
==========
Login logic for both principal types. Kept separate from the FastAPI route
handlers in `main.py` so the credential-checking logic is unit-testable and
so `main.py` only has to translate outcomes into HTTP responses.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Citizen, Officer
from .security import verify_password
from .tokens import PRINCIPAL_TYPE_CITIZEN, PRINCIPAL_TYPE_OFFICER, create_access_token


class InvalidCredentialsError(Exception):
    """
    Unknown email, wrong password, or an inactive account.

    Deliberately a single exception/message for all three cases -- the
    caller must not be able to distinguish "email does not exist" from
    "password is wrong" from the HTTP response.
    """


def authenticate_officer(db: Session, email: str, password: str) -> Officer:
    officer = db.query(Officer).filter(Officer.email == email).first()

    if officer is None or not verify_password(password, officer.password_hash):
        raise InvalidCredentialsError("Invalid email or password")

    if not officer.is_active:
        raise InvalidCredentialsError("Invalid email or password")

    return officer


def authenticate_citizen(db: Session, email: str, password: str) -> Citizen:
    citizen = db.query(Citizen).filter(Citizen.email == email).first()

    if citizen is None or not verify_password(password, citizen.password_hash):
        raise InvalidCredentialsError("Invalid email or password")

    if not citizen.is_active:
        raise InvalidCredentialsError("Invalid email or password")

    return citizen


def issue_officer_token(officer: Officer) -> str:
    return create_access_token(officer.id, PRINCIPAL_TYPE_OFFICER)


def issue_citizen_token(citizen: Citizen) -> str:
    return create_access_token(citizen.id, PRINCIPAL_TYPE_CITIZEN)
