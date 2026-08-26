"""
config.py
=========
Configuration for the authentication system. All values are read from the
environment with a development-only fallback -- exactly the same pattern
`app/database.py` already uses for `DATABASE_URL`.

`JWT_SECRET_KEY` MUST be overridden via the environment in any non-development
deployment. The bundled default exists only so the app and test suite can run
out of the box locally; it is not a production secret.
"""

from __future__ import annotations

import os

JWT_SECRET_KEY: str = os.getenv(
    "JWT_SECRET_KEY",
    "dev-only-insecure-secret-key-override-with-JWT_SECRET_KEY-env-var",
)
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRES_MINUTES: int = int(os.getenv("JWT_EXPIRES_MINUTES", "480"))
