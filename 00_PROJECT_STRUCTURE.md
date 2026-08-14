# InsightFlow — Project Structure

Version 1.0 · Status: **Frozen** · Target Audience: Human + AI Coding Assistants

---

## Purpose

This document is the **authoritative map** of the InsightFlow repository. It answers one question for every developer and AI coding assistant:

> "Where should this code go?"

Before creating any file, check this document. If a module doesn't fit the defined structure, it probably doesn't belong in the codebase — or the structure needs an ADR update.

---

# 1. Repository Map

```
insightflow/
│
├── 00_PROJECT_STRUCTURE.md          ← THIS FILE
├── 01_PRD.md                        ← Product Requirements Document
├── 02_ARCHITECTURE.md               ← System Architecture
├── 03_DATABASE.md                   ← Database Design & Schema
├── 08_ARCHITECTURE_RULES.md         ← Enforceable Architecture Rules
│
├── backend/                         ← FastAPI monolith (Phase 1–2)
│   ├── app/
│   │   ├── api/                     ← HTTP layer only
│   │   ├── application/             ← Use case orchestration
│   │   ├── domain/                  ← Business rules (zero deps)
│   │   ├── infrastructure/          ← IO, persistence, external services
│   │   ├── ai/                      ← AI Copilot agents & prompts
│   │   ├── warehouse/               ← ETL pipelines
│   │   ├── feature_store/           ← Feature generation
│   │   ├── ml/                      ← Model training, evaluation, registry
│   │   ├── schemas/                 ← Pydantic API schemas
│   │   ├── core/                    ← Config, exceptions, constants
│   │   └── conftest.py              ← Shared test fixtures
│   ├── alembic/                     ← Database migrations
│   │   ├── versions/                ← Migration scripts
│   │   └── env.py
│   ├── scripts/                     ← Dev & ops utilities
│   │   ├── check_architecture.py    ← Architecture rule checker
│   │   ├── seed_dim_time.py         ← Time dimension seeder
│   │   ├── generate_mock_data.py    ← Telecom data simulator
│   │   └── run_etl.py               ← ETL entry point
│   ├── tests/
│   │   ├── unit/                    ← Per-module unit tests
│   │   ├── integration/             ← Cross-module integration tests
│   │   ├── api/                     ← HTTP endpoint tests
│   │   ├── ai/                      ← Prompt regression tests
│   │   │   └── golden/              ← Golden datasets for AI eval
│   │   └── conftest.py
│   ├── data/                        ← Local dev data (gitignored)
│   │   ├── raw/                     ← Sample CSV/Parquet files
│   │   └── duckdb/                  ← DuckDB persistent files
│   ├── pyproject.toml
│   ├── requirements.lock
│   └── Dockerfile
│
├── frontend/                        ← Next.js 15 application
│   ├── app/                         ← App Router pages
│   │   ├── (dashboard)/             ← Authenticated layout group
│   │   │   ├── overview/            ← Dashboard home
│   │   │   ├── customers/           ← Customer 360
│   │   │   ├── analytics/           ← KPI analytics
│   │   │   ├── churn/               ← Churn analysis
│   │   │   ├── recommendations/     ← Decision center
│   │   │   ├── reports/             ← Report viewer
│   │   │   ├── copilot/             ← AI Copilot chat
│   │   │   └── settings/            ← User preferences
│   │   ├── layout.tsx               ← Root layout
│   │   └── page.tsx                 ← Landing / login
│   ├── components/                  ← Shared UI components
│   │   ├── ui/                      ← shadcn/ui primitives
│   │   ├── charts/                  ← Chart wrappers (ECharts)
│   │   ├── tables/                  ← DataTable (TanStack)
│   │   ├── layout/                  ← Sidebar, Header, Shell
│   │   └── shared/                  ← MetricCard, InsightPanel, etc.
│   ├── features/                    ← Feature-specific components
│   │   ├── dashboard/
│   │   ├── customer-360/
│   │   ├── analytics/
│   │   ├── churn/
│   │   ├── copilot/
│   │   └── reports/
│   ├── hooks/                       ← Custom React hooks
│   ├── lib/                         ← Utility functions
│   ├── services/                    ← API client layer
│   │   ├── api.ts                   ← Axios/fetch wrapper
│   │   ├── analytics.ts
│   │   ├── customers.ts
│   │   ├── copilot.ts
│   │   └── reports.ts
│   ├── stores/                      ← Zustand stores (UI state only)
│   ├── types/                       ← Shared TypeScript types
│   ├── styles/                      ← Global styles
│   ├── public/                      ← Static assets
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── next.config.ts
│   └── Dockerfile
│
├── docker/                          ← Docker Compose & infra configs
│   ├── docker-compose.yml           ← Local dev environment
│   ├── docker-compose.prod.yml      ← Production override
│   ├── postgres/
│   │   └── init.sql                 ← Initial DB setup
│   └── minio/
│       └── init-buckets.sh          ← Bucket creation script
│
├── .github/
│   └── workflows/
│       └── quality.yml              ← CI quality gates
│
├── .pre-commit-config.yaml          ← Pre-commit hooks
├── .gitignore
├── .cursorrules                     ← AI coding assistant rules
└── README.md
```

---

# 2. Backend Directory Responsibilities

## 2.1 `app/api/` — HTTP Layer

**Owns**: HTTP concerns. Nothing else.

| Subdirectory | Purpose | May Import |
|-------------|---------|------------|
| `routers/` | One file per resource group | `app/application/`, `app/schemas/` |
| `dependencies/` | FastAPI `Depends()` factories | `app/application/`, `app/infrastructure/` |
| `middleware/` | Request ID, logging, error handler | `app/core/` |

**Must NOT**:
- Contain business logic (L0)
- Access database directly (L0)
- Import from `app/domain/` directly (use application services)

---

## 2.2 `app/application/` — Use Case Orchestration

**Owns**: Workflow coordination between domain services.

| Subdirectory | Responsibility |
|-------------|----------------|
| `analytics/` | KPI computation orchestration |
| `churn/` | Churn prediction workflow |
| `reports/` | Report generation orchestration |
| `copilot/` | AI Copilot workflow orchestration |
| `recommendation/` | Recommendation ranking |

**May Import**: `app/domain/` (interfaces), `app/infrastructure/` (interfaces only)
**Must NOT**: Import `app/api/`, execute SQL, call LLM directly

---

## 2.3 `app/domain/` — Business Rules

**Owns**: Entities, value objects, domain services, domain events.

| Subdirectory | Contents |
|-------------|----------|
| `customer/` | Customer aggregate, CustomerService |
| `package/` | Package entity |
| `billing/` | BillingRecord, RevenueCalculator |
| `network/` | NetworkMetric value object |
| `marketing/` | Campaign, CampaignResponse |
| `analytics/` | Insight, Evidence, MetricDefinition |
| `decision/` | Decision, Recommendation |
| `report/` | Report aggregate |
| `shared/` | BaseEntity, DomainEvent, ValueObject |

**Must NOT**: Import anything from `fastapi`, `sqlalchemy`, `redis`, `pydantic`, `langgraph`, `celery` (L0).

---

## 2.4 `app/infrastructure/` — IO & External Services

**Owns**: Implementations of domain interfaces.

| Subdirectory | Responsibility |
|-------------|----------------|
| `database/` | SQLAlchemy engine, session, ORM models |
| `repositories/` | Implementation of domain repository interfaces |
| `redis/` | Cache client, queue broker |
| `storage/` | MinIO adapter for reports/artifacts |
| `llm/` | LLM provider adapter (OpenAI/DeepSeek/Qwen) |
| `scheduler/` | Celery app & task definitions |

**May Import**: `app/domain/` (implements interfaces)
**Must NOT**: Contain business rules (L0)

---

## 2.5 `app/ai/` — AI Copilot Agents

**Owns**: Agent implementations, prompt registry, workflow graph.

| Subdirectory | Responsibility |
|-------------|----------------|
| `planner/` | Query Planner Agent |
| `sql/` | SQL Agent (generation + sandbox validation) |
| `analytics/` | Analytics Agent |
| `retrieval/` | Evidence Retrieval Agent |
| `decision/` | Decision Intelligence Agent |
| `writer/` | Report Writer Agent |
| `reviewer/` | Reviewer Agent |
| `prompts/` | Versioned prompt YAML files |
| `workflow.py` | LangGraph StateGraph definition |

**May Import**: `app/infrastructure/llm/`, `app/domain/`
**Must NOT**: Contain SQL execution (delegates to infrastructure)

---

## 2.6 `app/warehouse/` — ETL Pipelines

**Owns**: Data validation, cleaning, transformation, loading.

| File | Responsibility |
|------|---------------|
| `validator.py` | Schema validation, business rules |
| `loader.py` | Bronze → Silver loading |
| `quality.py` | Data quality reports |

**May Import**: `app/infrastructure/database/`
**Must NOT**: Contain business logic beyond data validation

---

## 2.7 `app/feature_store/` — Feature Engineering

**Owns**: Feature generation, versioning, registry.

**May Import**: `app/infrastructure/database/`
**Must NOT**: Be imported by analytics or API code

---

## 2.8 `app/ml/` — Machine Learning

**Owns**: Model training, evaluation, registry, prediction execution.

| File | Responsibility |
|------|---------------|
| `train.py` | Model training pipeline |
| `evaluate.py` | Evaluation report generation |
| `registry.py` | Model Registry CRUD |
| `predict.py` | Batch & online prediction |
| `explain.py` | SHAP explanation generation |
| `monitor.py` | Drift detection |

**May Import**: `app/feature_store/`, `app/infrastructure/storage/`
**Must NOT**: Be imported by analytics or API code directly

---

## 2.9 `app/schemas/` — API Schemas

**Owns**: Pydantic models for request/response serialization.

| File Convention | Purpose |
|----------------|---------|
| `{resource}_request.py` | POST/PUT request bodies |
| `{resource}_response.py` | GET/POST response bodies |
| `common.py` | Shared schemas (pagination, error envelope) |

---

## 2.10 `app/core/` — Configuration

**Owns**: App config, exception classes, constants.

| File | Purpose |
|------|---------|
| `config.py` | pydantic-settings, env var loading |
| `exceptions.py` | Typed exception hierarchy |
| `constants.py` | Business constants (risk thresholds, etc.) |

---

# 3. Frontend Directory Responsibilities

## 3.1 `app/` — Next.js App Router

Routes follow Next.js file-system routing. Each route folder contains:

```
{route}/
├── page.tsx          ← Page component (server component by default)
├── layout.tsx        ← Optional layout wrapper
├── loading.tsx       ← Skeleton/loading state
├── error.tsx         ← Error boundary
└── not-found.tsx     ← 404 state
```

## 3.2 `components/` — Shared Components

| Directory | Contents | Examples |
|-----------|----------|----------|
| `ui/` | shadcn/ui primitives | Button, Input, Card, Badge, Dialog |
| `charts/` | ECharts wrappers | LineChart, BarChart, Heatmap, FunnelChart |
| `tables/` | TanStack Table wrappers | DataTable (sort, filter, paginate) |
| `layout/` | App shell | Sidebar, Header, Shell, Breadcrumb |
| `shared/` | Domain-agnostic components | MetricCard, InsightPanel, ConfidenceBadge, EvidencePanel |

## 3.3 `features/` — Feature Components

One folder per business feature. Each feature owns its own components, hooks, and types:

```
features/dashboard/
├── components/
│   ├── RevenueOverview.tsx
│   ├── ChurnTrendChart.tsx
│   ├── PackageDistribution.tsx
│   ├── RegionalMap.tsx
│   ├── AnomalyAlerts.tsx
│   └── AIInsightCard.tsx
├── hooks/
│   └── useDashboardData.ts
└── types.ts
```

**Rule**: Feature components may import from `components/` and `hooks/`. They must NOT import from other feature folders (cross-feature coupling).

## 3.4 `services/` — API Client

One file per backend resource group. Every API call passes through this layer.

```typescript
// services/analytics.ts
export const analyticsService = {
    getKPIs: (params: KPIFilters) => api.get('/analytics/kpi', { params }),
    getTrend: (params: TrendParams) => api.get('/analytics/trend', { params }),
    getAnomalies: () => api.get('/analytics/anomaly'),
};
```

**Rule**: Components must NOT call `fetch()` or `axios` directly. Always use the service layer.

## 3.5 `stores/` — Zustand Stores

UI state only (sidebar open, theme, filter selections). Server data is managed by TanStack Query — never duplicated in Zustand.

---

# 4. Dependency Rules (Import Map)

### Allowed Dependencies

```
frontend/app/          → frontend/features/      → frontend/components/
frontend/features/     → frontend/services/       → backend API
frontend/features/     → frontend/hooks/
frontend/components/   → frontend/components/ui/

backend/app/api/       → backend/app/application/
backend/app/api/       → backend/app/schemas/

backend/app/application/ → backend/app/domain/       (interfaces)
backend/app/application/ → backend/app/infrastructure/ (interfaces only)

backend/app/domain/      → (NOTHING external — zero deps)

backend/app/infrastructure/ → backend/app/domain/     (implements interfaces)

backend/app/ai/         → backend/app/infrastructure/llm/
backend/app/ai/         → backend/app/domain/

backend/app/warehouse/  → backend/app/infrastructure/database/
backend/app/feature_store/ → backend/app/infrastructure/database/
backend/app/ml/         → backend/app/feature_store/
```

### Forbidden Dependencies (L0)

```
❌ domain/        → fastapi, sqlalchemy, redis, pydantic, langgraph, celery
❌ application/   → api/
❌ api/routers/   → infrastructure/database/ (use Depends + repository)
❌ features/A/    → features/B/ (cross-feature import)
❌ frontend/      → backend/app/ (only through services/ → HTTP API)
❌ infrastructure/ → application/ (circular dependency)
```

---

# 5. Module Boundaries

Each of these modules is designed to become an independently deployable service in Phase 3. To enable this:

| Module | Future Service | Internal-only API |
|--------|---------------|-------------------|
| `analytics/` | Analytics Service | Insight objects |
| `ml/` | ML Service | Predictions + explanations |
| `copilot/` | AI Copilot Service | Workflow execution |
| `report/` | Report Service | Report generation |
| `warehouse/` | Data Platform | Curated datasets |

**Current (MVP) rule**: Modules are directories in a monolith. They communicate via direct Python imports. **Future rule**: Modules become services. They communicate via HTTP/gRPC. All inter-module communication today must use DTOs (not ORM objects) to make this split mechanical rather than architectural.

---

# 6. Creating a New Module

### New Backend Domain Module

```
app/domain/{name}/
├── __init__.py
├── entity.py              ← Domain entity / aggregate
├── value_objects.py       ← Value objects (if any)
├── service.py             ← Domain service (business rules)
├── events.py              ← Domain events (if any)
└── interfaces.py          ← Repository/service interfaces
```

### New Backend Feature (Application + API)

```
app/application/{name}/
├── __init__.py
└── {name}_service.py

app/api/routers/{name}.py
app/schemas/{name}_request.py
app/schemas/{name}_response.py

tests/unit/application/test_{name}_service.py
tests/api/test_{name}_api.py
```

### New Frontend Feature

```
frontend/features/{name}/
├── components/
│   └── {Name}Page.tsx
├── hooks/
│   └── use{Name}Data.ts
├── types.ts
└── index.ts               ← Public exports
```

---

# 7. Naming Conventions

### Files & Directories

| Element | Convention | Example |
|---------|-----------|---------|
| Directories | `snake_case` | `feature_store/`, `customer_360/` |
| Python modules | `snake_case` | `churn_service.py` |
| React components | `PascalCase` | `RevenueChart.tsx` |
| TypeScript utilities | `camelCase` | `formatCurrency.ts` |
| Test files | `test_{module}.py` | `test_churn_service.py` |

### Python

| Element | Convention | Example |
|---------|-----------|---------|
| Classes | `PascalCase` | `ChurnPredictionService` |
| Functions | `snake_case` | `predict_churn()` |
| Constants | `UPPER_CASE` | `MAX_REVIEW_RETRIES` |
| Private members | `_prefix` | `_classify_risk()` |
| Boolean variables | `is_` / `has_` / `can_` | `is_at_risk` |

### TypeScript

| Element | Convention | Example |
|---------|-----------|---------|
| Components | `PascalCase` | `CustomerList` |
| Hooks | `use` prefix | `useCustomerData` |
| Services | `camelCase` + `Service` | `analyticsService` |
| Types/Interfaces | `PascalCase` | `ChurnPrediction` |
| Constants | `UPPER_CASE` | `API_BASE_URL` |

---

# 8. File Size Limits

| File Type | Soft Limit | Hard Limit | Action if Exceeded |
|-----------|-----------|------------|-------------------|
| Python module | 300 lines | 500 lines | Split into sub-modules |
| React component | 200 lines | 350 lines | Extract sub-components |
| Service class | 200 lines | 300 lines | Split responsibilities |
| Repository class | 150 lines | 250 lines | Split by entity |
| Prompt YAML | N/A | 100 lines | Simplify or split into chain |

---

# 9. Configuration

All configuration is environment-variable-driven. No hardcoded values.

| File | Framework | Purpose |
|------|-----------|---------|
| `backend/app/core/config.py` | `pydantic-settings` | Backend config from env vars |
| `backend/.env.example` | — | Documented env var template |
| `frontend/.env.local.example` | — | Frontend env var template |
| `docker/.env` | — | Docker Compose variables |

**Forbidden**: `config.ini`, `settings.json`, hardcoded URLs, hardcoded secrets.

---

# 10. Quick Reference for AI Coding Assistants

```
When generating code for InsightFlow:

1. New API endpoint?
   → app/api/routers/{resource}.py         (router only)
   → app/application/{domain}/             (service)
   → app/schemas/{resource}_request.py     (request schema)
   → app/schemas/{resource}_response.py    (response schema)
   → tests/api/test_{resource}_api.py      (test)

2. New business rule?
   → app/domain/{module}/service.py        (domain logic)
   → tests/unit/domain/test_{module}.py    (unit test)

3. New database query?
   → app/infrastructure/repositories/      (implementation)
   → app/domain/{module}/interfaces.py     (interface first!)

4. New AI agent capability?
   → app/ai/{agent}/                       (agent logic)
   → app/ai/prompts/{agent}/v1__*.yaml     (versioned prompt)
   → tests/ai/golden/                      (golden dataset)

5. New frontend page?
   → frontend/app/(dashboard)/{route}/page.tsx
   → frontend/features/{feature}/components/
   → frontend/services/{resource}.ts

6. Before committing:
   → python scripts/check_architecture.py  (must pass)
   → ruff check . && ruff format --check .
   → mypy app/
   → pytest --cov=app --cov-fail-under=80
```

---

# Document Freeze

This document defines the **canonical project structure** for InsightFlow Version 1.0.

Changes to the directory layout, module boundaries, or dependency rules require an ADR. AI coding assistants must read this document before generating any file — placing code in the wrong directory is an L1 violation (AR-001).
