"""
dependencies.py
================
FastAPI dependencies enforcing the two-principal-type authentication model.

`get_current_officer` / `get_current_citizen` are what routes actually
depend on. Neither trusts anything the client sends outside the signed JWT
-- not a header, not a body field, not a role string. The token's own
`principal_type` claim (set at issuance, see `tokens.create_access_token`)
is the only source of truth for whether a caller is an officer or a
citizen, and the principal is re-loaded from the database on every request
so a deactivated officer's existing token stops working immediately.

    401 -- no token, or the token is missing/malformed/expired/badly signed
    403 -- the token is valid but belongs to the wrong principal type, or
           the principal it names is inactive/deleted
"""

from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..dependencies import get_db
from ..models import Citizen, Officer
from .tokens import PRINCIPAL_TYPE_CITIZEN, PRINCIPAL_TYPE_OFFICER, InvalidTokenError, TokenPayload, decode_access_token

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> TokenPayload:
    """Decode and validate the bearer token. Does not check principal type."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        return decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_current_officer(
    principal: TokenPayload = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> Officer:
    """
    Require an authenticated, active officer.

    A well-formed, validly-signed citizen token reaches here too (any bearer
    token passes `get_current_principal`) and is correctly rejected with 403
    -- the token is legitimate, it just does not authorize this route.
    """
    if principal.principal_type != PRINCIPAL_TYPE_OFFICER:
        raise HTTPException(status_code=403, detail="Officer authentication required")

    officer = db.query(Officer).filter(Officer.id == principal.principal_id).first()

    if officer is None or not officer.is_active:
        raise HTTPException(status_code=403, detail="Officer authentication required")

    return officer


def get_current_citizen(
    principal: TokenPayload = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> Citizen:
    """Require an authenticated, active citizen. Mirrors get_current_officer."""
    if principal.principal_type != PRINCIPAL_TYPE_CITIZEN:
        raise HTTPException(status_code=403, detail="Citizen authentication required")

    citizen = db.query(Citizen).filter(Citizen.id == principal.principal_id).first()

    if citizen is None or not citizen.is_active:
        raise HTTPException(status_code=403, detail="Citizen authentication required")

    return citizen
