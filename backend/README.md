# Backend

FastAPI application providing authentication, request validation, domain commands, read models, and lifecycle transitions.

## Tech Stack

- **Framework:** FastAPI
- **Server:** Uvicorn
- **Database:** PostgreSQL + SQLAlchemy ORM
- **Async Jobs:** Redis + Celery/Dramatiq
- **Validation:** Pydantic v2
- **Auth:** JWT tokens
- **Python:** 3.9+

## Project Structure

```text
backend/
  app/
    api/              Route handlers and request schemas
    models/           SQLAlchemy ORM models
    services/         Business logic (defect fusion, scoring, tracking)
    db/               Database connections and session management
    workers/          Async job definitions (inference, validation)
    schemas/          Pydantic request/response schemas
    config.py         Environment and app configuration
    main.py           FastAPI application entry point
```

## Key Responsibilities

- **Authentication & Authorization:** JWT-based officer and admin roles
- **Request Validation:** Pydantic schemas for all endpoints
- **Domain Commands:** Evidence upload, verification, repair scheduling
- **Read Models:** Defect list, prioritized queue, repair history
- **Lifecycle Transitions:** State machine for defect → verified → scheduled → repaired → validated
- **Async Processing:** Inference, sensor fusion, clustering run as background jobs

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start development server
python -m uvicorn app.main:app --reload

# Start background workers
celery -A app.workers worker --loglevel=info
```

## Environment Variables

Create `.env`:

```
DATABASE_URL=postgresql://user:password@localhost:5432/road_defects
REDIS_URL=redis://localhost:6379
JWT_SECRET_KEY=your_secret_key_here
ALLOWED_ORIGINS=http://localhost:3000
```

## API Documentation

Once running, visit `http://localhost:8000/docs` (Swagger UI) or `/redoc` (ReDoc).