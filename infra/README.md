# Infrastructure

Local development dependencies are PostgreSQL/PostGIS, Redis, and S3-compatible object storage. Production deployment can replace these components with managed equivalents without changing application boundaries.

Required operational concerns:

- database migrations and seed data
- object storage lifecycle and evidence retention
- queue retries and dead-letter handling
- structured logs and processing metrics
- secrets supplied through the deployment environment