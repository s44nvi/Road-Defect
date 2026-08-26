import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Default target is the local development database. `DATABASE_URL` overrides it
# so the same code can point at a test database (the backend test suite runs
# against a throwaway SQLite file) or at a deployment database, without editing
# this file. Behaviour is unchanged when the variable is unset.
DEFAULT_DATABASE_URL = "postgresql+psycopg2://akshaykumar@localhost:5432/sih_road_defects"

DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

# SQLite needs `check_same_thread=False` to be usable from FastAPI's threadpool;
# it is not a valid argument for any other driver.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()
