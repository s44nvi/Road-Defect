# API Service

FastAPI service responsible for HTTP boundaries, authentication, validation, domain commands, and read models.

Suggested modules:

```text
app/
  main.py
  api/              Route handlers and dependency wiring
  domain/           Commands, policies, and lifecycle transitions
  models/           SQLAlchemy models and migrations
  schemas/          Pydantic request and response contracts
  repositories/     Persistence adapters
  settings.py
```

Long-running work is published to the worker queue. API responses should return job IDs for asynchronous processing.