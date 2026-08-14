# InsightFlow — Implementation Checklist

Version 1.0 · Purpose: Sprint-by-sprint acceptance verification. Check boxes as completed.

---

## Phase 0: Foundation

### Week 1 — Project Setup

- [ ] Monorepo structure created (`backend/`, `frontend/`, `docker/`)
- [ ] Backend: FastAPI scaffold running (`uvicorn app.main:app`)
- [ ] Backend: Core config (`pydantic-settings`), exceptions, logging
- [ ] Database: PostgreSQL Docker container running
- [ ] Database: Alembic initialized, first migration created
- [ ] Database: All schemas created (`raw`, `warehouse`, `feature_store`, `semantic`, `ml`)
- [ ] Database: `dim_time` seeded (2020–2030, ~4,018 rows)
- [ ] Database: `metric_registry` seeded (50 rows)
- [ ] Database: `feature_registry` seeded (45 rows)
- [ ] Docker Compose: All services start (`docker compose up`)
- [ ] CI: Quality gates workflow running
- [ ] CI: Architecture check passes (`python scripts/check_architecture.py`)
- [ ] CI: Lint passes (`ruff check`)
- [ ] CI: Type check passes (`mypy app/`)
- [ ] `.pre-commit-config.yaml` installed and working

### Week 2 — Data Simulation & ETL

- [ ] Mock data generator: `customer.csv` produces valid rows
- [ ] Mock data generator: `usage.csv` produces valid rows
- [ ] Mock data generator: `billing.csv` produces valid rows
- [ ] Mock data generator: `network.csv` produces valid rows
- [ ] Mock data generator: `service.csv` produces valid rows
- [ ] Mock data generator: `campaign.csv` produces valid rows
- [ ] `python scripts/generate_mock_data.py --seed 42 --customers 1000000` runs without error
- [ ] ETL: CSV → `raw.*` loads correctly
- [ ] ETL: Schema validation rejects malformed files
- [ ] ETL: Row validation quarantines invalid rows (check quarantine table non-empty on test data)
- [ ] ETL: `raw.*` → `warehouse.*` with key resolution
- [ ] ETL: Star Schema populated (all fact + dim tables have rows)
- [ ] Data quality report generated with < 1% quarantine rate on generated data

### Phase 0 Gate

- [ ] `docker compose up` starts all 6 services
- [ ] CI is green on `develop` branch
- [ ] 1M mock customers in warehouse
- [ ] All 6 datasets pass validation
- [ ] Phase 0 retrospective complete

---

## Phase 1 — Sprint 1: Analytics Engine + Customer + System APIs

### Week 3 — Domain & KPI Computation

- [ ] Domain: `Insight` value object created (`app/domain/analytics/`)
- [ ] Domain: `Evidence` value object created
- [ ] Domain: `MetricDefinition` value object created
- [ ] Domain: `MetricRegistry` interface defined
- [ ] Infrastructure: `MetricRepository` implemented (PostgreSQL)
- [ ] Application: Revenue KPIs working (ARPU, MRR, Revenue Growth)
- [ ] Application: Customer KPIs working (Active, New, Churned, Retention, CLV)
- [ ] Application: Usage KPIs working (Avg Data, Voice, SMS, Roaming)
- [ ] Application: Network KPIs working (Drop Rate, Latency, Coverage)
- [ ] Application: Service KPIs working (Complaints, CSAT, Resolution Time)
- [ ] Application: Marketing KPIs working (ROI, Conversion, CAC)
- [ ] Application: Trend Analysis working (DoD, WoW, MoM, QoQ, YoY)

### Week 4 — Advanced Analytics + APIs

- [ ] Application: Segmentation Analysis working (by region, package, segment)
- [ ] Application: Funnel Analysis working (lifecycle stages)
- [ ] Application: Cohort Analysis working (retention + revenue)
- [ ] Application: Anomaly Detection working (Z-score, IQR, rolling avg)
- [ ] API: Analytics routers (7 endpoints): `/kpi`, `/kpi/{metric}`, `/trend`, `/anomaly`, `/segmentation`, `/funnel`, `/cohort`
- [ ] API: Customer routers (2 endpoints): `/customers`, `/customers/{id}`
- [ ] API: Customer 360 response includes all 10 sections (profile, package, billing, usage, network, service, prediction, recommendations, timeline)
- [ ] API: System routers (3 endpoints): `/system/health`, `/system/metrics`, `/system/tasks/{id}`
- [ ] Schemas: All Pydantic models match `05_API_SPEC.md`
- [ ] Semantic Layer: `kpi_arpu` materialized view created and refreshable
- [ ] Semantic Layer: `kpi_churn_rate` materialized view created
- [ ] Semantic Layer: `kpi_revenue` materialized view created
- [ ] Tests: Unit tests for all analytics services (coverage ≥ 85%)
- [ ] Tests: Integration tests for analytics + customer + system endpoints
- [ ] Tests: All tests pass (`pytest tests/ -v`)

### Sprint 1 Gate

- [ ] 50 KPIs available and returning values
- [ ] All 12 API endpoints match `05_API_SPEC.md`
- [ ] Trend, segmentation, funnel, cohort, anomaly all functional
- [ ] Customer list with filtering + Customer 360 with 10 sections
- [ ] System health + task polling endpoints working
- [ ] KPI queries < 3s on 1M customer dataset
- [ ] All tests pass, coverage ≥ 80%

---

## Phase 1 — Sprint 2: ML Platform

### Week 5 — Feature Engineering + Model Training

- [ ] Feature Generation: `customer_features` (45 features) computed
- [ ] Feature Generation: `churn_features` with labels (is_churn + observation window)
- [ ] Feature Generation: `package_features` computed
- [ ] Feature Store: Version metadata stored (`feature_registry` populated)
- [ ] Feature Store: Regeneration is deterministic (same seed → same features)
- [ ] Dataset: Train/val/test split with version tracking
- [ ] Dataset: Class balance reported (churn rate in dataset)
- [ ] Model: Logistic Regression trained and evaluated
- [ ] Model: Random Forest trained and evaluated
- [ ] Model: XGBoost trained and evaluated
- [ ] Model: LightGBM trained and evaluated
- [ ] Model: CatBoost trained and evaluated

### Week 6 — Evaluation + Prediction Service

- [ ] Evaluation: Comparison report for all 5 models (ROC-AUC, F1, PR-AUC, Log Loss, Calibration)
- [ ] Evaluation: Confusion matrix for each model
- [ ] Hyperparameter Optimization: Optuna tuned top 2 models
- [ ] Explainability: SHAP values computed for all predictions
- [ ] Explainability: Top contributing factors available per prediction
- [ ] Model Registry: All 5 models registered with metadata
- [ ] Model Registry: Promote/demote workflow functional
- [ ] Prediction: `POST /churn/predict` (online, single customer) → returns risk_score + factors
- [ ] Prediction: `POST /churn/predict/batch` (async) → returns task_id
- [ ] Prediction: `GET /churn/predictions/{id}` → returns SHAP detail
- [ ] API: All 4 churn endpoints match `05_API_SPEC.md` §8
- [ ] Tests: Unit tests for feature generation, model training, prediction (coverage ≥ 80%)

### Sprint 2 Gate

- [ ] 5 algorithms trained and benchmarked
- [ ] Best model: ROC-AUC ≥ 0.85, F1 ≥ 0.80
- [ ] Every prediction includes SHAP + confidence
- [ ] Batch prediction: 1M customers < 30 minutes
- [ ] Model Registry tracks all metadata
- [ ] All tests pass, coverage ≥ 80%

---

## Phase 1 — Sprint 3: AI Copilot + Reports

### Week 7 — Agents

- [ ] LLM Provider: OpenAI adapter working
- [ ] LLM Provider: Mock provider for tests (no API calls)
- [ ] Prompt Registry: All 6 YAML prompts loaded and cached
- [ ] Planner Agent: `question → AnalysisPlan` working
- [ ] Planner Agent: Evaluation ≥ 0.90 intent accuracy on golden dataset
- [ ] SQL Generator Agent: `AnalysisPlan → SQLResult` working
- [ ] SQL Generator Agent: SQL Sandbox rejects all dangerous SQL (100% pass rate)
- [ ] SQL Generator Agent: Evaluation ≥ 0.95 SQL validity
- [ ] Analytics Agent: `SQLResult → Insight[]` working
- [ ] Evidence Retrieval Agent: Returns evidence from 4 data sources
- [ ] Decision Intelligence Agent: `Insight[] + Evidence → Decision` working
- [ ] Decision Intelligence Agent: Evaluation — hallucination rate ≤ 0.02
- [ ] Context Assembly: Dynamic context builder stays under 8K token limit
- [ ] Guardrails: Input sanitization blocks prompt injection
- [ ] Guardrails: PII filter strips sensitive data before LLM

### Week 8 — Workflow + APIs + Evaluation

- [ ] Report Writer Agent: `Decision → Report` with sections + executive summary
- [ ] Report Writer Agent: Evaluation — evidence citation rate = 100%
- [ ] Reviewer Agent: All 6 checks functional
- [ ] Reviewer Agent: Retry ceiling (max 3) enforced
- [ ] Reviewer Agent: Override path delivers with `review_override: true`
- [ ] Workflow Engine: LangGraph DAG (7 nodes) compiles and runs
- [ ] Workflow Engine: SQL + Evidence run in parallel
- [ ] Workflow Engine: Reviewer gate routes correctly (retry vs pass vs override)
- [ ] Workflow Engine: Checkpointer records full trace for debugging
- [ ] API: `POST /copilot/chat` returns complete findings + decisions + evidence
- [ ] API: `GET /copilot/workflows/{id}` returns full agent traces
- [ ] API: `GET /copilot/history` returns paginated past chats
- [ ] API: `POST /reports/generate` returns task_id (async)
- [ ] API: `GET /reports` lists reports with status
- [ ] API: `GET /reports/{id}` returns report metadata
- [ ] API: `GET /reports/{id}/download` returns file
- [ ] WebSocket: `/ws/copilot/{id}` streams agent progress
- [ ] WebSocket: `/ws/tasks/{id}` streams task progress
- [ ] Prompt Evaluation: Golden dataset tests for all 6 prompts
- [ ] Prompt Evaluation: All metrics meet promotion thresholds
- [ ] Integration: End-to-end Copilot workflow test passes

### Sprint 3 Gate

- [ ] AI Copilot answers "Why did churn increase?" with evidence-backed findings
- [ ] SQL Sandbox rejects 100% of dangerous SQL
- [ ] Reviewer retry ceiling works (3 retries → override)
- [ ] Copilot chat latency < 15s P95
- [ ] Every AI output includes confidence + evidence
- [ ] Reports generate with valid Markdown and evidence citations
- [ ] All prompt evaluation scores meet thresholds
- [ ] All tests pass, AI-specific coverage ≥ 90%

---

## Phase 1 — Sprint 4: Frontend & Integration

### Week 9 — Core Pages + Shared Components

- [ ] Frontend scaffold: Next.js 15 + shadcn/ui + Tailwind + ECharts
- [ ] Layout: Shell with Sidebar, Header, Theme toggle
- [ ] Layout: Sidebar navigation (7 items) working with route highlighting
- [ ] Shared: MetricCard component with all 4 states
- [ ] Shared: ConfidenceBadge with 4-level color coding
- [ ] Shared: DataTable with sort, filter, pagination
- [ ] Shared: ErrorState component (message + retry)
- [ ] Shared: EmptyState component (illustration + action)
- [ ] Shared: Skeleton components for loading states
- [ ] API client: `services/api.ts` with auth interceptor and error normalization
- [ ] API client: All service modules (`analytics.ts`, `customers.ts`, `copilot.ts`, etc.)
- [ ] Page: Dashboard — Key Metrics (4 MetricCards)
- [ ] Page: Dashboard — Trend Chart (multi-line)
- [ ] Page: Dashboard — Risk Donut + Anomaly List
- [ ] Page: Dashboard — AI Insights (InsightCard × 3)
- [ ] Page: Analytics — 5 tabs (Overview, Segmentation, Funnel, Cohort, Anomalies)
- [ ] Page: Analytics — Global FilterBar persisted across tabs
- [ ] Page: Customer List — Search + 3 filter dropdowns + DataTable
- [ ] Page: Customer List — Summary stats bar (Total, Active, At-Risk, Churned)
- [ ] Page: Customer 360 — All 10 sections rendering
- [ ] Page: Customer 360 — Churn risk score color-coded
- [ ] Page: Churn Analysis — Overview tab (4 MetricCards + trend + risk donut)
- [ ] Page: Churn Analysis — High-Risk Customers tab (DataTable)
- [ ] Page: Churn Analysis — Prediction tab (input → result panel)

### Week 10 — Copilot + Reports + Polish

- [ ] Page: AI Copilot — Conversation panel + Evidence panel (60/40)
- [ ] Page: AI Copilot — WorkflowProgressBar (7 agent steps)
- [ ] Page: AI Copilot — Finding cards with ConfidenceBadge
- [ ] Page: AI Copilot — Decision cards with recommendation + impact
- [ ] Page: AI Copilot — Evidence panel with source table + SQL
- [ ] Page: AI Copilot — Suggestion chips when empty
- [ ] Page: AI Copilot — Input with char counter + context chips
- [ ] WebSocket: Copilot real-time progress streaming working
- [ ] Page: Reports — Generate form (type, format, parameters)
- [ ] Page: Reports — History DataTable with status badges
- [ ] Page: Reports — Download button functional
- [ ] Page: Settings — Theme toggle (light/dark/system)
- [ ] Page: Settings — System status panel
- [ ] Responsive: Desktop (xl) layout verified on all 7 pages
- [ ] Responsive: Tablet (md) layout verified — sidebar collapsed, 2-col grids
- [ ] Responsive: Mobile (sm) layout verified — hamburger menu, stacked cards
- [ ] Accessibility: Keyboard navigation functional on all pages
- [ ] Accessibility: Screen reader labels on icon buttons
- [ ] Accessibility: Focus indicators visible
- [ ] Accessibility: Color contrast ≥ WCAG AA
- [ ] Accessibility: Charts distinguishable in grayscale
- [ ] Accessibility: `prefers-reduced-motion` respected
- [ ] Integration: Full user flow — Dashboard → Customer → Churn → Copilot → Report → Download
- [ ] All pages match `06_FRONTEND.md` component trees
- [ ] Every async component handles loading, error, empty, success

### Sprint 4 Gate

- [ ] All 7 pages rendering correctly
- [ ] Dashboard load < 2s (Lighthouse)
- [ ] AI Copilot chat works end-to-end
- [ ] Responsive on desktop, tablet, mobile
- [ ] WCAG AA accessibility compliance
- [ ] All integration tests pass

---

## Phase 2: Enhancement (Reference — Not Yet Committed)

- [ ] Recommendation Engine: Package recommendation
- [ ] Recommendation Engine: Retention strategy ranking
- [ ] What-if Simulation: Price elasticity modeling
- [ ] What-if Simulation: Scenario comparison UI
- [ ] Model Monitoring: Data drift detection
- [ ] Model Monitoring: Alert pipeline (Slack/email)
- [ ] PDF Report: WeasyPrint or Playwright rendering
- [ ] RBAC: Role-based middleware
- [ ] Performance: AI Copilot < 10s (parallel optimization)
- [ ] Load test: 100 concurrent users
- [ ] End-to-end tests (Playwright)

## Phase 3: Production (Reference — Not Yet Committed)

- [ ] Multi-tenant data isolation
- [ ] Microservice split (Analytics / ML / AI / Report)
- [ ] API Gateway with rate limiting
- [ ] ClickHouse migration (evaluate)
- [ ] Feature Store: Feast (evaluate)
- [ ] Model Registry: MLflow (evaluate)
- [ ] Kubernetes deployment with Helm charts
- [ ] Disaster recovery: Backup + restore tested
- [ ] SLA 99.5% verified with monitoring

---

## Usage

Copy the relevant sprint section into your Sprint tracking tool. Check boxes as tasks complete. Any unchecked box at Sprint Gate blocks the next Sprint.

**Last updated**: Sprint 1–4 committed. Phase 2–3 directional.
