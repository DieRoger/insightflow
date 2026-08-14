# InsightFlow — Deployment Guide

Version 1.0 · Status: **Living** · Target: DevOps + Developers

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Local Development](#2-local-development)
3. [Docker Compose](#3-docker-compose)
4. [Environment Variables](#4-environment-variables)
5. [Database Setup](#5-database-setup)
6. [CI/CD Pipeline](#6-cicd-pipeline)
7. [Production Deployment](#7-production-deployment)
8. [Monitoring & Alerting](#8-monitoring--alerting)
9. [Backup & Recovery](#9-backup--recovery)
10. [Security Hardening](#10-security-hardening)

---

# 1. Architecture Overview

## 1.1 MVP Deployment Topology

```
┌──────────────────────────────────────────────────┐
│                   Docker Host                      │
│                                                    │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Next.js   │  │ FastAPI   │  │ Celery Worker │  │
│  │ :3000     │  │ :8000     │  │               │  │
│  └─────┬─────┘  └─────┬─────┘  └───────┬───────┘  │
│        │              │               │           │
│  ┌─────┴──────────────┴───────────────┴───────┐  │
│  │              PostgreSQL :5432               │  │
│  └────────────────────────────────────────────┘  │
│  ┌──────────┐  ┌──────────┐                     │
│  │ Redis     │  │ MinIO     │                    │
│  │ :6379     │  │ :9000     │                    │
│  └──────────┘  └──────────┘                     │
│                                                    │
└──────────────────────────────────────────────────┘
```

## 1.2 Service Ports

| Service | Port | Purpose |
|---------|:----:|---------|
| Frontend (Next.js) | 3000 | User-facing web application |
| Backend (FastAPI) | 8000 | REST API + WebSocket |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache + Celery broker |
| MinIO | 9000 | Object storage (S3 API) |
| MinIO Console | 9001 | MinIO web UI |

---

# 2. Local Development

## 2.1 Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.12+ | `python --version` |
| Node.js | 22+ | `node --version` |
| Docker | 28+ | `docker --version` |
| uv | latest | `uv --version` |

## 2.2 Quick Start

```bash
# Clone and enter project
git clone <repo-url> insightflow
cd insightflow

# Backend setup
cd backend
cp .env.example .env
uv sync
alembic upgrade head
python scripts/seed_dim_time.py
python scripts/generate_mock_data.py --seed 42 --customers 10000  # Small for dev
python scripts/run_etl.py

# Frontend setup
cd ../frontend
cp .env.local.example .env.local
npm install
npm run dev

# Visit http://localhost:3000
```

## 2.3 Backend Dev Commands

```bash
cd backend

# Start API server (hot reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest tests/ -v --cov=app --cov-report=term

# Run lint + type check
ruff check . && ruff format --check . && mypy app/

# Run architecture check
python scripts/check_architecture.py

# Generate mock data
python scripts/generate_mock_data.py --seed 42 --customers 1000000

# Run ETL
python scripts/run_etl.py --input-dir data/mock/

# Create migration
alembic revision --autogenerate -m "add_new_table"

# Apply migrations
alembic upgrade head
```

## 2.4 Frontend Dev Commands

```bash
cd frontend

# Dev server
npm run dev

# Lint
npm run lint

# Type check
npx tsc --noEmit

# Tests
npm test

# Build
npm run build
```

---

# 3. Docker Compose

## 3.1 File: `docker/docker-compose.yml`

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: insightflow
      POSTGRES_PASSWORD: ${DB_PASSWORD:-insightflow_dev}
      POSTGRES_DB: insightflow
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U insightflow"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_USER:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_PASSWORD:-minioadmin}
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data

  backend:
    build:
      context: ../backend
      dockerfile: Dockerfile
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://insightflow:${DB_PASSWORD:-insightflow_dev}@postgres:5432/insightflow
      REDIS_URL: redis://redis:6379/0
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: ${MINIO_USER:-minioadmin}
      MINIO_SECRET_KEY: ${MINIO_PASSWORD:-minioadmin}
      LLM_PROVIDER: ${LLM_PROVIDER:-openai}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  worker:
    build:
      context: ../backend
      dockerfile: Dockerfile
    command: celery -A app.infrastructure.scheduler.celery_app worker --loglevel=info
    environment:
      DATABASE_URL: postgresql+asyncpg://insightflow:${DB_PASSWORD:-insightflow_dev}@postgres:5432/insightflow
      REDIS_URL: redis://redis:6379/0
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: ${MINIO_USER:-minioadmin}
      MINIO_SECRET_KEY: ${MINIO_PASSWORD:-minioadmin}
    depends_on:
      - postgres
      - redis

  frontend:
    build:
      context: ../frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000/api/v1
    depends_on:
      - backend

volumes:
  postgres_data:
  minio_data:
```

## 3.2 Usage

```bash
# Start all services
cd docker
docker compose up -d

# View logs
docker compose logs -f backend

# Stop all services
docker compose down

# Reset (delete volumes)
docker compose down -v
```

## 3.3 Backend Dockerfile

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml requirements.lock ./
RUN pip install uv && uv sync --frozen

# Copy application code
COPY . .

# Run
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 3.4 Frontend Dockerfile

```dockerfile
# frontend/Dockerfile
FROM node:22-alpine AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./
COPY --from=builder /app/node_modules ./node_modules

EXPOSE 3000
CMD ["npm", "start"]
```

---

# 4. Environment Variables

## 4.1 Backend (`backend/.env.example`)

```bash
# Application
APP_NAME=InsightFlow
APP_VERSION=1.0.0
DEBUG=false
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql+asyncpg://insightflow:changeme@localhost:5432/insightflow
DATABASE_POOL_SIZE=20
DATABASE_POOL_OVERFLOW=10

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_TTL=300

# MinIO (Object Storage)
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_REPORTS=insightflow-reports
MINIO_BUCKET_MODELS=insightflow-models
MINIO_SECURE=false

# LLM Provider
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
LLM_FAST_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
# DEEPSEEK_API_KEY=sk-...
# DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
# VLLM_ENDPOINT=http://localhost:8080/v1

# Auth
JWT_SECRET=change-me-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=24

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# CORS
CORS_ORIGINS=http://localhost:3000
```

## 4.2 Frontend (`frontend/.env.local.example`)

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
NEXT_PUBLIC_APP_NAME=InsightFlow
```

---

# 5. Database Setup

## 5.1 Initial Setup

```bash
# 1. Create database (if not using Docker)
createdb insightflow

# 2. Run migrations
cd backend
alembic upgrade head

# 3. Seed reference data
python scripts/seed_dim_time.py       # dim_time: 2020–2030
python scripts/seed_registries.py     # metric_registry (50 rows), feature_registry (45 rows)

# 4. Generate mock data (for dev/test)
python scripts/generate_mock_data.py --seed 42 --customers 1000000

# 5. Run ETL
python scripts/run_etl.py --input-dir data/mock/

# 6. Refresh materialized views
python scripts/refresh_semantic_views.py
```

## 5.2 Migrations

```bash
# Create new migration after model changes
alembic revision --autogenerate -m "description_of_change"

# Review the generated migration file!
# Apply
alembic upgrade head

# Rollback one version
alembic downgrade -1

# Show current version
alembic current
```

---

# 6. CI/CD Pipeline

## 6.1 Pipeline Stages

```
Push to develop
    │
    ▼
┌─────────────┐
│ Lint & Type │  ← ruff, mypy, eslint, tsc
└──────┬──────┘
       ▼
┌─────────────┐
│ Architecture│  ← scripts/check_architecture.py
└──────┬──────┘
       ▼
┌─────────────┐
│ Unit Tests  │  ← pytest, npm test
└──────┬──────┘
       ▼
┌─────────────┐
│ Integration │  ← pytest integration (with test DB)
└──────┬──────┘
       ▼
┌─────────────┐
│ Build Image │  ← docker build
└──────┬──────┘
       ▼
    Merge to develop ✅
```

## 6.2 Merge to Main

```
develop → PR to main
    │
    ▼
All develop checks pass
    │
    ▼
Deploy to staging
    │
    ▼
Smoke tests pass
    │
    ▼
Merge to main → Tag release → Deploy to production
```

## 6.3 Tagging

```bash
# Tag format: v{major}.{minor}.{patch}
git tag v1.0.0
git push origin v1.0.0
```

---

# 7. Production Deployment

## 7.1 MVP: Single VM

```bash
# On production VM
git clone <repo-url> /opt/insightflow
cd /opt/insightflow/docker

# Set production env vars
export DB_PASSWORD=<strong-password>
export JWT_SECRET=<random-64-char>
export OPENAI_API_KEY=sk-...
export CORS_ORIGINS=https://insightflow.example.com

# Start
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

**Production overrides** (`docker-compose.prod.yml`):
- PostgreSQL: no exposed port (internal only)
- MinIO: no console port exposed
- Backend: `--workers 4` on uvicorn
- Frontend: behind nginx reverse proxy
- All services: `restart: always`

## 7.2 Phase 3: Kubernetes

```yaml
# Future: k8s/backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: insightflow-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: insightflow-backend
  template:
    metadata:
      labels:
        app: insightflow-backend
    spec:
      containers:
        - name: backend
          image: insightflow/backend:v1.0.0
          ports:
            - containerPort: 8000
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: insightflow-secrets
                  key: database_url
          resources:
            requests:
              cpu: "500m"
              memory: "512Mi"
            limits:
              cpu: "2"
              memory: "2Gi"
          livenessProbe:
            httpGet:
              path: /api/v1/system/health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
```

---

# 8. Monitoring & Alerting

## 8.1 Metrics Exported

| Metric | Source | Format |
|--------|--------|--------|
| Request count, latency, error rate | FastAPI middleware | Prometheus `/metrics` |
| Database query latency | SQLAlchemy events | Prometheus |
| Celery task duration, success rate | Celery signals | Prometheus |
| LLM token usage, latency | LLM provider adapter | Prometheus |
| AI workflow success rate | LangGraph hooks | Prometheus |

## 8.2 Prometheus Metrics Example

```
# HELP insightflow_request_latency_seconds Request latency
# TYPE insightflow_request_latency_seconds histogram
insightflow_request_latency_seconds_bucket{endpoint="/api/v1/copilot/chat",le="5"} 120
insightflow_request_latency_seconds_bucket{endpoint="/api/v1/copilot/chat",le="10"} 350
insightflow_request_latency_seconds_bucket{endpoint="/api/v1/copilot/chat",le="15"} 480

# HELP insightflow_ai_tokens_total Total LLM tokens consumed
# TYPE insightflow_ai_tokens_total counter
insightflow_ai_tokens_total{agent="planner",type="prompt"} 125000
insightflow_ai_tokens_total{agent="planner",type="completion"} 48000
```

## 8.3 Alert Rules

| Alert | Condition | Severity | Channel |
|-------|-----------|----------|---------|
| API error rate > 1% | `rate(errors[5m]) > 0.01` | Critical | PagerDuty |
| API P95 latency > 2s | `histogram_quantile(0.95, latency) > 2` | Warning | Slack |
| AI Copilot P95 > 20s | `histogram_quantile(0.95, copilot_latency) > 20` | Warning | Slack |
| Database connection pool exhausted | `pool_available < 2` | Critical | PagerDuty |
| Celery queue backlog > 100 | `queue_size > 100` | Warning | Slack |
| Disk usage > 85% | `disk_used_pct > 85` | Warning | Slack |

---

# 9. Backup & Recovery

## 9.1 Backup Strategy

| Data | Method | Frequency | Retention |
|------|--------|-----------|-----------|
| PostgreSQL | `pg_dump` | Nightly | 30 days |
| PostgreSQL WAL | Archive | Continuous | 7 days |
| MinIO (reports) | `mc mirror` | Nightly | 30 days |
| MinIO (models) | `mc mirror` | Per training | 90 days |

## 9.2 Backup Script

```bash
#!/bin/bash
# scripts/backup.sh

BACKUP_DIR="/backups/insightflow"
DATE=$(date +%Y%m%d_%H%M%S)

# PostgreSQL
pg_dump -h localhost -U insightflow -Fc insightflow \
    > "$BACKUP_DIR/postgres_$DATE.dump"

# MinIO reports
mc mirror minio/insightflow-reports "$BACKUP_DIR/reports_$DATE/"

# Cleanup old backups (30 days)
find "$BACKUP_DIR" -name "*.dump" -mtime +30 -delete
```

## 9.3 Recovery

```bash
# PostgreSQL restore
pg_restore -h localhost -U insightflow -d insightflow \
    --clean --if-exists "$BACKUP_DIR/postgres_20260801_020000.dump"

# MinIO restore
mc mirror "$BACKUP_DIR/reports_20260801_020000/" minio/insightflow-reports/
```

## 9.4 RPO / RTO

| Metric | Target | Method |
|--------|:------:|--------|
| RPO (data loss window) | < 24 hours | Nightly pg_dump |
| RTO (time to recover) | < 4 hours | Restore from backup + replay WAL |

---

# 10. Security Hardening

## 10.1 Checklist

- [ ] All secrets in environment variables (never in code or config files)
- [ ] PostgreSQL: strong password, no public port binding
- [ ] Redis: password-protected (`requirepass` in config)
- [ ] MinIO: strong access/secret keys, bucket policies restrict public access
- [ ] JWT: 256-bit secret, 24h expiry
- [ ] HTTPS: TLS termination at reverse proxy (nginx / cloud LB)
- [ ] CORS: restricted to known origins
- [ ] Rate limiting: enabled on all public endpoints
- [ ] SQL: parameterized queries only (enforced by AR-012)
- [ ] AI: SQL Sandbox active (enforced by AR-043)
- [ ] AI: Prompt injection guard active (enforced by AR-101)
- [ ] AI: PII filter active before LLM context assembly (enforced by AR-102)

## 10.2 Security Headers (nginx)

```nginx
add_header X-Content-Type-Options "nosniff";
add_header X-Frame-Options "DENY";
add_header X-XSS-Protection "1; mode=block";
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';";
```

---

# Document Governance

This document is **Living** — updated as infrastructure evolves. The Docker Compose configuration is **committed** for MVP. Kubernetes and production hardening apply to Phase 3.
