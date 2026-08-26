"""
tokens.py
=========
Minimal signed-JWT issuance/verification for the two principal types the
backend recognizes: officers and citizens.

The token's `sub` claim is the principal's database id (as a string, per JWT
convention) and its `principal_type` claim ("officer" | "citizen") is what
lets `get_current_officer` / `get_current_citizen` reject a token that
authenticates a real, valid principal of the WRONG type -- an officer token
must never satisfy a citizen-only dependency and vice versa. The backend
never infers principal type from anything the client sends outside the
signed token itself (not a header, not a body field, not a role string).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

from . import config

PRINCIPAL_TYPE_OFFICER = "officer"
PRINCIPAL_TYPE_CITIZEN = "citizen"


class InvalidTokenError(ValueError):
    """Raised for a missing, malformed, expired, or badly-signed token."""


@dataclass(frozen=True)
class TokenPayload:
    principal_id: int
    principal_type: str


def create_access_token(principal_id: int, principal_type: str) -> str:
    """Issue a signed JWT identifying one principal."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(principal_id),
        "principal_type": principal_type,
        "iat": now,
        "exp": now + timedelta(minutes=config.JWT_EXPIRES_MINUTES),
    }

    return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def decode_access_token(token: str) -> TokenPayload:
    """
    Verify signature + expiry and extract the principal.

    Raises `InvalidTokenError` for anything wrong with the token -- expired,
    bad signature, missing claims -- so callers have one exception type to
    translate into an HTTP 401.
    """
    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    subject = payload.get("sub")
    principal_type = payload.get("principal_type")

    if subject is None or principal_type is None:
        raise InvalidTokenError("token is missing required claims")

    try:
        principal_id = int(subject)
    except (TypeError, ValueError) as exc:
        raise InvalidTokenError("token subject is not a valid principal id") from exc

    return TokenPayload(principal_id=principal_id, principal_type=principal_type)
