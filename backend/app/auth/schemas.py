"""
schemas.py
==========
Pydantic request/response models for `/auth/officer/login` and
`/auth/citizen/login`.

Deliberately separate from `app/schemas.py` (the defect/report contract) so
this module stays a self-contained boundary. `password_hash` never appears
in any of these -- `OfficerPublic`/`CitizenPublic` are explicit allowlists
of the fields safe to return, not the ORM row itself.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class OfficerLoginRequest(BaseModel):
    email: EmailStr
    password: str


class CitizenLoginRequest(BaseModel):
    email: EmailStr
    password: str


class OfficerPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    officer_id: int
    name: str
    email: str
    department: str | None = None


class CitizenPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    citizen_id: int
    name: str
    email: str


class OfficerLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    officer: OfficerPublic


class CitizenLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    citizen: CitizenPublic
