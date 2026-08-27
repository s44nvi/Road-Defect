# Alembic - Database Migration Tool

# This directory contains Alembic migrations for the Road Defect Detection database.
# Alembic is a lightweight database migration tool for SQLAlchemy.

## Usage

```bash
# Create a new migration (auto-detect changes)
alembic revision --autogenerate -m "Add new table"

# Apply migrations to database
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

## Migrations

- `versions/001_initial_schema.py` - Initial database schema with defects, observations, officers, repairs
