"""
security.py
============
Password hashing, isolated behind two small functions so the rest of the
backend never touches the underlying library directly.

Uses `bcrypt` directly rather than `passlib` -- passlib is unmaintained and,
as of its last release (1.7.4), is incompatible with modern `bcrypt`
releases (>=4.1) that removed the `__about__` attribute passlib probes for.
`bcrypt` itself is actively maintained and is all a password-hashing helper
actually needs.
"""

from __future__ import annotations

import bcrypt

# bcrypt silently truncates/ignores input beyond 72 bytes; reject long
# passwords explicitly rather than let two different long passwords hash
# identically.
_MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    """Hash a plaintext password for storage. Never store the input itself."""
    encoded = password.encode("utf-8")
    if len(encoded) > _MAX_PASSWORD_BYTES:
        raise ValueError(f"password must be at most {_MAX_PASSWORD_BYTES} bytes")

    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Check a plaintext password against a stored hash. Never raises on mismatch."""
    encoded = password.encode("utf-8")
    if len(encoded) > _MAX_PASSWORD_BYTES:
        return False

    try:
        return bcrypt.checkpw(encoded, password_hash.encode("utf-8"))
    except ValueError:
        # Malformed/foreign hash format -- treat as "does not match", not a crash.
        return False
