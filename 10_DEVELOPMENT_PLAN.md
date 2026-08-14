# InsightFlow — Development Plan

Version 1.0 · Status: **Living** · Target: Project Manager + AI Coding Assistants

---

## Table of Contents

1. [Overview](#1-overview)
2. [Phase -1: Engineering Bootstrap](#2-phase--1-engineering-bootstrap)
3. [Phase 0: Foundation](#3-phase-0-foundation)
4. [Phase 1: MVP — Sprint 1](#4-phase-1--sprint-1-analytics-engine)
4. [Phase 1: MVP — Sprint 2](#4-phase-1--sprint-2-ml-platform)
5. [Phase 1: MVP — Sprint 3](#5-phase-1--sprint-3-ai-copilot)
6. [Phase 1: MVP — Sprint 4](#6-phase-1--sprint-4-frontend--integration)
7. [Phase 2: Enhancement](#7-phase-2-enhancement)
8. [Phase 3: Production](#8-phase-3-production)

---

# 1. Overview

## 1.1 Timeline

```
Phase -1: Engineering Bootstrap   Day 1–2       (2 days)
Phase 0: Foundation               Week 1–2      (2 weeks)
Phase 1: MVP                      Week 3–10     (8 weeks, 4 sprints)
Phase 2: Enhancement              Week 11–16    (6 weeks)
Phase 3: Production               Week 17–24    (8 weeks)
```

## 1.2 Sprint Cadence

- Sprint length: **2 weeks**
- Sprint start: Monday
- Sprint review: Friday of week 2
- Retrospective: Friday after review

## 1.3 Definition of Done (per Task)

- [ ] Implementation matches the frozen spec
- [ ] Unit tests pass (coverage ≥ target for layer)
- [ ] Integration tests pass
- [ ] Type checking passes (`mypy` strict / `tsc --noEmit`)
- [ ] Linting passes (`ruff` / `eslint`)
- [ ] Architecture check passes (`python scripts/check_architecture.py`)
- [ ] No L0 or L1 rule violations
- [ ] Documentation updated (if public API changed)

---

# 2. Phase -1: Engineering Bootstrap

**Goal**: Prove the entire toolchain and a minimal end-to-end path works before writing any business code.

**Duration**: 2 days

### Day 1: Toolchain Verification

| Task | Verification |
|------|-------------|
| Docker Compose starts all 6 services | `docker compose up` — PostgreSQL, Redis, MinIO, Backend, Worker, Frontend all healthy |
| PostgreSQL accepts connections | `pg_isready` passes healthcheck |
| Redis responds | `redis-cli ping` → PONG |
| MinIO accessible | Console at `:9001`, S3 API at `:9000` |
| Alembic initializes database | `alembic upgrade head` creates all schemas |
| Backend starts without import errors | `uvicorn app.main:app` — no crash |
| Frontend starts | `npm run dev` — Next.js compiles |
| `scripts/check_architecture.py` runs | Exits 0 (passes on empty project) |
| `ruff check .` passes | No lint errors |
| `mypy app/` passes | No type errors |
| `.pre-commit install` works | Git hooks active |
| CI workflow (`quality.yml`) green | GitHub Actions passes on empty repo |

**Gate**: `make check` exits 0. All 12 items above verified.

### Day 2: Walking Skeleton

Build one single, complete, minimal path through the entire stack:

```
Frontend (TanStack Query)
    │
    ▼
GET /api/v1/system/health
    │
    ▼
FastAPI Router → (no service needed for health)
    │
    ▼
PostgreSQL (SELECT 1 — verify DB connection)
    │
    ▼
JSON Response: { "status": "healthy", "checks": { "database": "ok" } }
    │
    ▼
Frontend Card: "System Online ●"
```

**Deliverables**:

| # | Artifact | Location |
|---|----------|----------|
| 1 | FastAPI app with `/api/v1/system/health` endpoint | `app/api/routers/system.py` |
| 2 | DB health check (actual `SELECT 1`) | Injected into health endpoint |
| 3 | Standard response envelope (`SuccessResponse`, `ErrorResponse`) | `app/schemas/common.py` |
| 4 | Request ID middleware | `app/api/middleware/request_id.py` |
| 5 | Structured logging (structlog) | `app/core/logging.py` |
| 6 | Frontend API client (`services/api.ts`) | `frontend/services/api.ts` |
| 7 | Frontend TanStack Query hook for health | `frontend/hooks/useSystemHealth.ts` |
| 8 | Frontend Settings page with health status card | `frontend/app/(dashboard)/settings/page.tsx` |
| 9 | Docker Compose: all services wired correctly | `docker/docker-compose.yml` |

**Gate**: Open `http://localhost:3000/settings` → see "System Online ●" with green indicator. Full chain verified.

**Why this matters**: If the Walking Skeleton works, every future Sprint just adds more endpoints, services, and pages following the exact same patterns. If it doesn't work, we fix tooling/config issues now — not during Sprint 4 when 30 endpoints are involved.

---

# 3. Phase 0: Foundation

**Goal**: Project scaffolding, development environment, data simulation, CI/CD.

**Duration**: 2 weeks

### Week 1: Project Setup

| Day | Task | Deliverable | Est. |
|-----|------|-------------|:----:|
| 1 | Initialize monorepo structure (`backend/`, `frontend/`, `docker/`) | `00_PROJECT_STRUCTURE.md` implemented | 4h |
| 1 | Backend: FastAPI scaffold, `pyproject.toml`, `uv` lockfile | Running `uvicorn app.main:app` | 4h |
| 2 | Backend: Core config (`pydantic-settings`), exception hierarchy, logging setup | `app/core/` complete | 6h |
| 2 | Database: PostgreSQL Docker container, Alembic init | `alembic/` with first migration | 2h |
| 3 | Database: Run initial migration sequence (create all schemas) | `raw`, `warehouse`, `feature_store`, `semantic`, `ml` schemas exist | 4h |
| 3 | Database: Seed `dim_time` (2020–2030), `metric_registry` (50 rows), `feature_registry` (45 rows) | Seed data in place | 2h |
| 4 | Docker Compose: PostgreSQL + Redis + MinIO + backend | `docker-compose up` works end-to-end | 4h |
| 5 | CI: `.github/workflows/quality.yml`, `.pre-commit-config.yaml` | CI green on empty repo | 4h |

### Week 2: Data Simulation & ETL

| Day | Task | Deliverable | Est. |
|-----|------|-------------|:----:|
| 1 | Mock data generator: Customer dataset | `scripts/generate_mock_data.py` produces valid `customer.csv` | 4h |
| 2 | Mock data generator: Usage, Billing datasets | `usage.csv`, `billing.csv` | 4h |
| 3 | Mock data generator: Network, Service, Marketing datasets | All 6 CSV files generated | 4h |
| 4 | ETL Pipeline: CSV → `raw.*` (Bronze) | Valid rows in `raw.*` tables | 6h |
| 5 | ETL Pipeline: `raw.*` → `warehouse.*` (Silver) with key resolution | Star Schema populated | 6h |

### Phase 0 Acceptance Criteria

- [ ] `docker-compose up` starts all services
- [ ] CI runs architecture check + lint + type check
- [ ] `python scripts/generate_mock_data.py --seed 42 --customers 1000000` produces all 6 CSV files
- [ ] ETL loads 1M customers into warehouse without errors
- [ ] Data quality report shows < 1% quarantine rate on generated data

---

# 3. Phase 1 — Sprint 1: Analytics Engine

**Goal**: 50 standardized KPIs, trend/variance/segmentation analysis, Analytics API.

**Duration**: 2 weeks

### Week 3

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | Domain: `Insight`, `Evidence`, `MetricDefinition` value objects | `app/domain/analytics/` |
| 1 | Domain: `MetricRegistry` interface | `app/domain/analytics/interfaces.py` |
| 2 | Infrastructure: `MetricRepository` (PostgreSQL) | `app/infrastructure/repositories/metric_repository.py` |
| 2 | Feature: Revenue KPIs (ARPU, MRR, Revenue Growth) | `app/application/analytics/revenue.py` |
| 3 | Feature: Customer KPIs (Active, New, Churned, Retention, CLV) | `app/application/analytics/customer.py` |
| 3 | Feature: Usage KPIs (Avg Data, Voice, SMS, Roaming) | `app/application/analytics/usage.py` |
| 4 | Feature: Network & Service KPIs | `app/application/analytics/network.py`, `service.py` |
| 4 | Feature: Marketing KPIs (Campaign ROI, Conversion) | `app/application/analytics/marketing.py` |
| 5 | Feature: Trend Analysis (DoD, WoW, MoM, QoQ, YoY) | `app/application/analytics/trend.py` |

### Week 4

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | Feature: Segmentation Analysis (slice by region/package/segment) | `app/application/analytics/segmentation.py` |
| 1 | Feature: Funnel & Cohort Analysis | `app/application/analytics/funnel.py`, `cohort.py` |
| 2 | Feature: Anomaly Detection (Z-score, IQR, rolling average) | `app/application/analytics/anomaly.py` |
| 3 | API: Analytics routers (7 endpoints) | `app/api/routers/analytics.py` |
| 3 | Schemas: Analytics request/response Pydantic models | `app/schemas/analytics_*.py` |
| 4 | API: Customer routers (2 endpoints: `GET /customers`, `GET /customers/{id}`) | `app/api/routers/customers.py` |
| 4 | API: System routers (3 endpoints: health, metrics, tasks) | `app/api/routers/system.py` |
| 4 | Semantic Layer: Materialized views (`kpi_arpu`, `kpi_churn_rate`, `kpi_revenue`) | `semantic.*` views refreshed nightly |
| 5 | Tests: Unit + Integration + API tests for analytics + customers + system | `tests/` coverage ≥ 80% |

### Sprint 1 Acceptance Criteria

- [ ] 50 KPIs available via API
- [ ] Trend, segmentation, funnel, cohort, anomaly analysis all functional
- [ ] Customer list and Customer 360 detail endpoints functional
- [ ] System health and task polling endpoints functional
- [ ] All analytics + customer + system API endpoints match `05_API_SPEC.md`
- [ ] Common KPI queries complete < 3 seconds on 1M customer dataset

---

# 4. Phase 1 — Sprint 2: ML Platform

**Goal**: Feature Store, Churn Prediction (5 models), SHAP explainability, Model Registry.

**Duration**: 2 weeks

### Week 5

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | Feature Generation: `customer_features` (45 features) | `app/feature_store/generator.py` |
| 1 | Feature Generation: `churn_features` (label construction) | Churn labels with observation windows |
| 2 | Feature Store: Versioning & metadata | `feature_registry` table populated |
| 2 | Dataset Construction: Feature Store → train/test split | `app/ml/dataset.py` |
| 3 | Model Training: Logistic Regression (baseline) | First trained model in registry |
| 3 | Model Training: Random Forest | Comparison against baseline |
| 4 | Model Training: XGBoost | Grid search + cross-validation |
| 4 | Model Training: LightGBM | Grid search + cross-validation |
| 5 | Model Training: CatBoost | Grid search + cross-validation |

### Week 6

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | Model Evaluation: Generate comparison report (ROC-AUC, F1, PR-AUC) | Best model selected |
| 1 | Hyperparameter Optimization: Optuna for top 2 models | Optimized hyperparameters |
| 2 | Explainability: SHAP integration | `app/ml/explain.py` |
| 2 | Model Registry: CRUD, promotion workflow | `app/ml/registry.py` |
| 3 | Prediction Service: Online (`POST /churn/predict`) | Single prediction with SHAP |
| 3 | Prediction Service: Batch (`POST /churn/predict/batch`) | Async batch prediction |
| 4 | API: Churn endpoints (4 endpoints) | `app/api/routers/churn.py` |
| 4 | Schemas: Churn request/response models | `app/schemas/churn_*.py` |
| 5 | Tests: Unit + Integration + API tests for ML | `tests/` coverage ≥ 80% |

### Sprint 2 Acceptance Criteria

- [ ] 5 algorithms trained and benchmarked
- [ ] Production model achieves ROC-AUC ≥ 0.85, F1 ≥ 0.80
- [ ] Every prediction includes SHAP explanation + confidence
- [ ] Batch prediction processes 1M customers < 30 minutes
- [ ] All churn API endpoints match `05_API_SPEC.md` §8

---

# 5. Phase 1 — Sprint 3: AI Copilot

**Goal**: 7-agent LangGraph workflow, Decision Intelligence, Report Generator, Reviewer.

**Duration**: 2 weeks

### Week 7

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | LLM Provider: OpenAI adapter + mock provider for tests | `app/infrastructure/llm/` |
| 1 | Prompt Registry: YAML loader, versioning, cache | `app/ai/prompts/` with all 6 prompt files |
| 2 | Agent: Planner (NLU → AnalysisPlan) | `app/ai/planner/` |
| 2 | Agent: SQL Generator + SQL Sandbox | `app/ai/sql/` with sandbox validation |
| 3 | Agent: Analytics (SQLResult → Insight) | `app/ai/analytics/` |
| 3 | Agent: Evidence Retrieval (no LLM, deterministic) | `app/ai/retrieval/` |
| 4 | Agent: Decision Intelligence | `app/ai/decision/` |
| 4 | Context Assembly: Dynamic context builder | `app/ai/context.py` |
| 5 | Security: Input guardrails, output guardrails, PII filter | `app/ai/guardrails.py` |

### Week 8

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | Agent: Report Writer | `app/ai/writer/` |
| 1 | Agent: Reviewer (6 checks, retry ceiling) | `app/ai/reviewer/` |
| 2 | Workflow Engine: LangGraph StateGraph (7 nodes, conditional edges) | `app/ai/workflow.py` |
| 2 | Checkpointer: MemorySaver for debugging | Workflow traceable by `workflow_id` |
| 3 | API: Copilot endpoints (`POST /chat`, `GET /workflows/{id}`, `GET /history`) | `app/api/routers/copilot.py` |
| 4 | API: Report endpoints (`GET /reports`, `POST /generate`, `GET /{id}/download`) | `app/api/routers/reports.py` |
| 4 | WebSocket: `/ws/copilot/{workflow_id}` for real-time progress | Agent progress streaming |
| 5 | Prompt Evaluation: Golden dataset tests for all 6 prompts | `tests/ai/test_prompts/` |
| 5 | Integration Tests: End-to-end Copilot workflow | `tests/integration/test_copilot_workflow.py` |

### Sprint 3 Acceptance Criteria

- [ ] AI Copilot answers "Why did churn increase?" with evidence-backed findings
- [ ] SQL Sandbox rejects 100% of dangerous SQL
- [ ] Reviewer retries ≤ 3, then overrides with warning
- [ ] Copilot chat latency < 15 seconds (P95)
- [ ] Every AI output includes confidence + evidence
- [ ] Report generation produces valid Markdown with evidence citations

---

# 6. Phase 1 — Sprint 4: Frontend & Integration

**Goal**: Dashboard, Customer 360, Churn Analysis, AI Copilot UI, Report Viewer.

**Duration**: 2 weeks

### Week 9

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | Frontend scaffold: Next.js 15, shadcn/ui, Tailwind, ECharts | Running `npm run dev` |
| 1 | Layout: Shell (Sidebar, Header), Theme toggle | `components/layout/` |
| 2 | Shared components: MetricCard, ConfidenceBadge, DataTable, ErrorState | `components/shared/` |
| 2 | API client layer: `services/api.ts`, all service modules | `services/` complete |
| 3 | Page: Dashboard (4 sections, 12 cards) | `app/(dashboard)/overview/` |
| 3 | Page: Analytics (5 tabs with global filters) | `app/(dashboard)/analytics/` |
| 4 | Page: Customer List (search, filter, DataTable) | `app/(dashboard)/customers/` |
| 4 | Page: Customer 360 Detail (10 sections) | `app/(dashboard)/customers/[id]/` |
| 5 | Page: Churn Analysis (3 tabs) | `app/(dashboard)/churn/` |

### Week 10

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | Page: AI Copilot (dual panel, progress bar, evidence panel) | `app/(dashboard)/copilot/` |
| 1 | WebSocket integration: Copilot real-time progress | `hooks/useCopilotStream.ts` |
| 2 | Page: Reports (generate form, history table) | `app/(dashboard)/reports/` |
| 2 | Page: Settings (theme, preferences, system status) | `app/(dashboard)/settings/` |
| 3 | Integration testing: Full user flows | All pages render without errors |
| 3 | Responsive QA: Desktop, tablet, mobile | Layout adaptations verified |
| 4 | Accessibility audit: Keyboard nav, screen reader, contrast | WCAG AA compliance |
| 5 | Bug fixes + polish | All known issues resolved |

### Sprint 4 Acceptance Criteria

- [ ] All 7 pages match `06_FRONTEND.md` component trees
- [ ] Every async component handles loading, error, empty, success
- [ ] AI Copilot chat works end-to-end with evidence display
- [ ] Dashboard loads < 2 seconds on 1M customer dataset
- [ ] All pages are responsive and keyboard-accessible

---

# 7. Phase 2: Enhancement

**Goal**: Recommendation Engine, Scenario Simulation, Model Monitoring, PDF reports, RBAC.

**Duration**: 6 weeks (3 sprints)

### Sprint 5: Recommendation Engine (2 weeks)

| Task | Deliverable |
|------|-------------|
| Recommendation ranking: business rules + ML predictions | `app/application/recommendation/` |
| Package recommendation: which package to offer | `POST /recommendations/package` |
| Retention recommendation: which strategy to apply | `POST /recommendations/retention` |
| API: Recommendation endpoints | `app/api/routers/recommendations.py` |
| Frontend: Decision Center page | `app/(dashboard)/recommendations/` |

### Sprint 6: Simulation & Monitoring (2 weeks)

| Task | Deliverable |
|------|-------------|
| What-if Simulation engine | `app/application/simulation/` |
| Price elasticity, churn sensitivity modeling | Scenario comparison |
| Model Monitoring: data drift, concept drift, accuracy drift | `app/ml/monitor.py` |
| Monitoring alerts: Slack/email notifications | Alert pipeline |
| PDF Report rendering (WeasyPrint or Playwright) | `GET /reports/{id}/download` returns PDF |

### Sprint 7: Quality & RBAC (2 weeks)

| Task | Deliverable |
|------|-------------|
| Role-Based Access Control (RBAC) | Middleware + role decorators |
| Performance optimization: query tuning, cache strategy | Dashboard < 1.5s, Analytics < 3s |
| AI Copilot parallel agent optimization | Copilot < 10s |
| End-to-end tests (Playwright) | `tests/e2e/` |
| Load testing (Locust) | 100 concurrent users benchmark |

---

# 8. Phase 3: Production

**Goal**: Multi-tenant, microservices, high availability, enterprise deployment.

**Duration**: 8 weeks

### Key Milestones

| Milestone | Description |
|-----------|-------------|
| Multi-tenant data isolation | Schema-per-tenant or row-level security |
| Microservice split | Analytics / ML / AI / Report as independent services |
| API Gateway | Rate limiting, auth, routing |
| ClickHouse migration | For analytical queries > 10M customers |
| Feature Store (Feast) | Independent feature serving |
| Model Registry (MLflow) | Independent model lifecycle |
| Kubernetes deployment | Helm charts, auto-scaling |
| Disaster recovery | Backup strategy, RPO < 1h, RTO < 4h |
| SLA 99.5% | Monitoring, alerting, on-call runbook |

---

# Appendix A: Task Estimation Guide

| Complexity | Example | Est. |
|------------|---------|:----:|
| Trivial | Add a constant, fix a typo | 0.5h |
| Simple | Add a Pydantic schema, add a test case | 2h |
| Medium | Implement a service method + tests | 4h |
| Large | Implement a full endpoint (router + service + repo + tests) | 8h |
| Complex | Implement an AI Agent (prompt + eval + integration) | 16h |

---

# Appendix B: Risk Register

| Risk | Probability | Impact | Mitigation |
|------|:----------:|:------:|------------|
| AI Copilot latency > 15s | High | Medium | Sprint 7 parallel optimization |
| Mock data ≠ production data | High | High | Configurable distributions in generator; real data validation in Phase 3 |
| LLM output quality degradation | Medium | High | Prompt regression tests in CI; prompt versioning |
| PostgreSQL performance at 1M+ | Medium | Medium | Materialized views + DuckDB; ClickHouse migration path |
| Frontend complexity (Copilot UI) | Medium | Medium | Sprint 4 dedicated to Copilot UI; WebSocket for real-time |

---

# Document Governance

This document is **Living** — it is updated as sprints complete and estimates are refined. The Phase 0–1 sprint plans are **committed** for MVP delivery. Phase 2–3 plans are **directional** and subject to adjustment based on MVP learnings.

Updates to sprint scope require Tech Lead approval. Date changes require Project Manager approval. Architecture changes require an ADR.
