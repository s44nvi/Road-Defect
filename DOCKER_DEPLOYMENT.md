# Docker Deployment Guide

## Prerequisites

- Docker and Docker Compose installed
- Git repository cloned locally
- `.env` file configured (copy from `.env.example`)

## Quick Start

### 1. Set up Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and update the following for production:
```env
POSTGRES_PASSWORD=your-secure-password
MINIO_PASSWORD=your-secure-password
JWT_SECRET_KEY=your-random-secret-key
ENVIRONMENT=production
```

### 2. Start All Services

```bash
docker-compose up -d
```

This will start:
- **PostgreSQL** with PostGIS (port 5432)
- **Redis** (port 6379)
- **MinIO** (ports 9000, 9001)
- **FastAPI Backend** (port 8000)
- **Celery Worker** (background jobs)
- **Next.js Frontend** (port 3000)

### 3. Verify Services

```bash
# Check all containers are running
docker-compose ps

# View logs from all services
docker-compose logs -f

# View logs from specific service
docker-compose logs -f backend
docker-compose logs -f frontend
```

### 4. Access Services

| Service | URL | Credentials |
|---------|-----|-------------|
| Dashboard | http://localhost:3000 | - |
| API Docs | http://localhost:8000/docs | - |
| Redis Commander | http://localhost:8081 | - |
| MinIO Console | http://localhost:9001 | `road-defect` / `change-me-in-production` |

## Common Commands

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f worker
```

### Stop Services

```bash
# Stop all without removing
docker-compose stop

# Stop and remove containers
docker-compose down

# Remove volumes as well (⚠️ deletes data)
docker-compose down -v
```

### Rebuild Services

```bash
# Rebuild all images
docker-compose build

# Rebuild specific service
docker-compose build backend
docker-compose build frontend

# Rebuild and start
docker-compose up --build -d
```

### Run Database Migrations

```bash
docker-compose exec backend alembic upgrade head
```

### Access Database

```bash
docker-compose exec database psql -U road_defect -d road_defect
```

### Run Backend Tests

```bash
docker-compose run --rm backend pytest
```

## Troubleshooting

### Services won't start

1. Check if ports are in use:
   ```bash
   netstat -an | grep LISTEN
   ```

2. Remove stopped containers:
   ```bash
   docker-compose down
   docker system prune
   ```

3. Rebuild images:
   ```bash
   docker-compose build --no-cache
   ```

### Database connection error

```bash
# Check database is healthy
docker-compose ps

# Check database logs
docker-compose logs database

# Restart database
docker-compose restart database
```

### Frontend can't reach backend

1. Check backend is running:
   ```bash
   docker-compose logs backend
   ```

2. Verify environment variable:
   ```bash
   docker-compose exec frontend printenv NEXT_PUBLIC_API_URL
   ```

3. Update `.env`:
   ```env
   NEXT_PUBLIC_API_URL=http://backend:8000
   ```

## Production Deployment

For production deployments to cloud platforms:

### DigitalOcean App Platform

1. Create `app.yaml`:
   ```yaml
   services:
   - name: backend
     github:
       repo: s44nvi/Road-Defect
       branch: main
     build_command: pip install -r requirements.txt
     run_command: uvicorn app.main:app --host 0.0.0.0
     envs:
     - key: ENVIRONMENT
       value: production
     http_port: 8000
   
   - name: frontend
     github:
       repo: s44nvi/Road-Defect
       branch: main
     build_command: npm install && npm run build
     run_command: npm start
     http_port: 3000
   ```

2. Deploy:
   ```bash
   doctl apps create --spec app.yaml
   ```

### AWS ECS/Fargate

1. Create ECR repositories:
   ```bash
   aws ecr create-repository --repository-name road-defect-backend
   aws ecr create-repository --repository-name road-defect-frontend
   ```

2. Push images:
   ```bash
   docker build -t road-defect-backend ./backend
   docker tag road-defect-backend:latest <account>.dkr.ecr.us-east-1.amazonaws.com/road-defect-backend:latest
   docker push <account>.dkr.ecr.us-east-1.amazonaws.com/road-defect-backend:latest
   ```

3. Create ECS task definitions and services

## Security Best Practices

- [ ] Change all default passwords in `.env`
- [ ] Use strong JWT_SECRET_KEY (generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`)
- [ ] Enable HTTPS in production
- [ ] Use AWS Secrets Manager or Azure Key Vault for secrets
- [ ] Regular database backups
- [ ] Monitor resource usage
- [ ] Set up log aggregation
- [ ] Enable database encryption
- [ ] Restrict network access via security groups/firewall

## Performance Optimization

- Adjust replicas in docker-compose for scaling:
  ```bash
  docker-compose up -d --scale worker=3
  ```

- Use managed databases for production (RDS, CloudSQL)
- Set up CDN for frontend assets
- Configure Redis persistence
- Monitor with Prometheus/Grafana
