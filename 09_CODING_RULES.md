# InsightFlow — Coding Standards

Version 1.0 · Status: **Frozen** · Target: All Contributors (Human + AI)

---

## Table of Contents

1. [General Rules](#1-general-rules)
2. [Python Standards](#2-python-standards)
3. [TypeScript & React Standards](#3-typescript--react-standards)
4. [SQL Standards](#4-sql-standards)
5. [Error Handling](#5-error-handling)
6. [Logging](#6-logging)
7. [Testing](#7-testing)
8. [Documentation](#8-documentation)
9. [Git Workflow](#9-git-workflow)
10. [AI Coding Assistant Rules](#10-ai-coding-assistant-rules)
11. [Code Review Checklist](#11-code-review-checklist)

---

# 1. General Rules

## 1.1 Language & Formatting

| Rule | Enforcement |
|------|-------------|
| Python code: `ruff format` (Black-compatible, 100 char line limit) | CI gate |
| Python lint: `ruff check` (flake8 + isort + pyupgrade rules) | CI gate |
| Python types: `mypy --strict` | CI gate |
| TypeScript: `eslint` + `prettier` (project config) | CI gate |
| TypeScript types: `tsc --noEmit` | CI gate |
| No committed commented-out code | Code review |
| No `TODO` in committed code (use issue tracker) | Code review |

## 1.2 Naming

### Python

| Element | Convention | Example |
|---------|-----------|---------|
| Modules / files | `snake_case` | `churn_service.py` |
| Classes | `PascalCase` | `ChurnPredictionService` |
| Functions / methods | `snake_case` | `predict_churn()` |
| Variables | `snake_case` | `risk_score` |
| Constants | `UPPER_CASE` | `MAX_REVIEW_RETRIES` |
| Private members | `_leading_underscore` | `_classify_risk()` |
| Boolean variables | `is_`, `has_`, `can_` prefix | `is_at_risk`, `has_complained` |

### TypeScript

| Element | Convention | Example |
|---------|-----------|---------|
| Files (components) | `PascalCase` | `CustomerList.tsx` |
| Files (utilities) | `camelCase` | `formatCurrency.ts` |
| Components | `PascalCase` | `CustomerList` |
| Hooks | `use` prefix | `useCustomerData` |
| Functions | `camelCase` | `fetchCustomers` |
| Interfaces / Types | `PascalCase` | `CustomerProfile` |
| Constants | `UPPER_CASE` | `API_BASE_URL` |
| Boolean variables | `is`, `has`, `should` prefix | `isLoading` |

## 1.3 File Size

| File Type | Soft Limit | Hard Limit |
|-----------|:----------:|:----------:|
| Python module | 300 lines | 500 lines |
| React component | 200 lines | 350 lines |
| Service class | 200 lines | 300 lines |
| Repository class | 150 lines | 250 lines |
| Prompt YAML | — | 100 lines |

**Action on exceeding hard limit**: Split into sub-modules. Refactor PR required before feature PR.

## 1.4 Imports

### Python Import Order

```python
# 1. Standard library
import logging
from datetime import date, datetime

# 2. Third-party
from pydantic import BaseModel
from sqlalchemy import select

# 3. Application
from app.domain.customer import Customer
from app.infrastructure.repositories.customer_repository import CustomerRepository
```

**Forbidden**: `from module import *` (wildcard imports), circular imports.

### TypeScript Import Order

```typescript
// 1. React / Next.js
import { useState } from "react";
import { useRouter } from "next/navigation";

// 2. Third-party
import { useQuery } from "@tanstack/react-query";

// 3. Application (absolute paths)
import { MetricCard } from "@/components/shared/MetricCard";
import { analyticsService } from "@/services/analytics";

// 4. Relative (same feature only)
import { useDashboardData } from "./hooks";
```

## 1.5 No Magic Numbers

```python
# ❌ Bad
if customer.risk_score > 0.6:
    send_alert(customer)

# ✅ Good
HIGH_RISK_THRESHOLD = 0.6

if customer.risk_score > HIGH_RISK_THRESHOLD:
    send_alert(customer)
```

Constants belong in `app/core/constants.py` (backend) or `lib/constants.ts` (frontend).

---

# 2. Python Standards

## 2.1 Type Hints

**Every public function and method must have complete type hints.**

```python
# ❌ Bad
def predict_churn(customer_id):
    ...

# ✅ Good
async def predict_churn(self, customer_id: str) -> ChurnPrediction:
    ...
```

**Forbidden**: `Any` in public interfaces. Use `str | None`, `dict[str, float]`, or define a proper type.

## 2.2 Pydantic Models

```python
from pydantic import BaseModel, Field, model_validator

class ChurnPredictionResponse(BaseModel):
    """Churn prediction for a single customer."""

    prediction_id: str = Field(..., description="Unique prediction identifier")
    customer_id: str
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_level: str = Field(pattern=r"^(LOW|MEDIUM|HIGH)$")
    confidence: float = Field(ge=0.0, le=1.0)
    model_version: str

    @model_validator(mode="after")
    def risk_level_matches_score(self) -> "ChurnPredictionResponse":
        if self.risk_score >= 0.7 and self.risk_level != "HIGH":
            raise ValueError("risk_score >= 0.7 must have risk_level='HIGH'")
        return self
```

**Rules**:
- Every Pydantic model must have a docstring.
- Use `Field()` with `description` for non-obvious fields.
- `ge`/`le`/`pattern` constraints are preferred over custom validators.
- `model_validator` for cross-field validation.

## 2.3 Async/Await

```python
# ✅ Correct: async repository call
async def get_customer(self, customer_id: str) -> Customer:
    return await self.repo.get_by_id(customer_id)

# ❌ Bad: sync call in async context without executor
def get_customer(self, customer_id: str) -> Customer:
    return self.repo.get_by_id(customer_id)  # Blocks event loop
```

**Rules**:
- All I/O (database, HTTP, Redis, file) must be `async`.
- CPU-bound work in `await asyncio.to_thread()` or Celery.
- Never `asyncio.run()` inside a running event loop.

## 2.4 Dataclasses vs Pydantic

| Use | When |
|-----|------|
| `pydantic.BaseModel` | API schemas, config, validation, serialization |
| `dataclasses.dataclass` | Domain entities (framework-independent, AR-051) |

```python
# Domain entities use dataclasses (zero framework deps)
from dataclasses import dataclass, field
from datetime import date

@dataclass
class Customer:
    customer_id: str
    status: str
    join_date: date
    lifecycle_stage: str = "new"
    segment: str | None = None
    churn_risk_score: float = 0.0

    def is_at_risk(self, threshold: float = 0.6) -> bool:
        return self.churn_risk_score >= threshold
```

## 2.5 Service Pattern

```python
class ChurnPredictionService:
    """Orchestrates churn prediction for individual customers."""

    def __init__(
        self,
        customer_repo: CustomerRepository,
        feature_store: FeatureStore,
        model_registry: ModelRegistry,
        prediction_repo: PredictionRepository,
    ) -> None:
        self._customer_repo = customer_repo
        self._feature_store = feature_store
        self._model_registry = model_registry
        self._prediction_repo = prediction_repo

    async def predict(self, customer_id: str) -> ChurnPredictionResponse:
        """Predict churn probability for a single customer.

        Args:
            customer_id: Source system customer identifier.

        Returns:
            Prediction with risk score, level, and contributing factors.

        Raises:
            CustomerNotFoundError: If customer_id does not exist.
            ModelNotLoadedError: If no production model is available.
        """
        customer = await self._customer_repo.get_by_id(customer_id)
        if customer is None:
            raise CustomerNotFoundError(customer_id)

        if customer.status == "churned":
            raise BusinessError(
                code="BIZ_002",
                message="Cannot predict for already-churned customer",
            )

        features = await self._feature_store.get_features(customer_id)
        model = await self._model_registry.get_production_model("churn_prediction")
        prediction = await model.predict(features)

        result = ChurnPredictionResponse(
            prediction_id=generate_id("pred"),
            customer_id=customer_id,
            risk_score=prediction.probability,
            risk_level=self._classify_risk(prediction.probability),
            confidence=prediction.confidence,
            model_version=model.version,
        )

        await self._prediction_repo.save(result)
        return result

    def _classify_risk(self, score: float) -> str:
        if score >= 0.7:
            return "HIGH"
        elif score >= 0.3:
            return "MEDIUM"
        return "LOW"
```

**Rules**:
- Constructor injection only — no `new Repository()` inside methods.
- Public methods have docstrings with Args/Returns/Raises.
- Private helpers prefixed with `_`.
- Business exceptions, not generic `Exception`.

## 2.7 Repository Pattern

```python
from abc import ABC, abstractmethod

class CustomerRepository(ABC):
    """Domain-facing interface for customer persistence."""

    @abstractmethod
    async def get_by_id(self, customer_id: str) -> Customer | None:
        """Retrieve a single customer by source ID."""
        ...

    @abstractmethod
    async def search(
        self,
        filters: CustomerFilters,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResult[Customer]:
        """Search customers with pagination and filters."""
        ...

    @abstractmethod
    async def list_high_risk(self, threshold: float, limit: int = 100) -> list[Customer]:
        """List customers above the risk threshold."""
        ...
```

**Rules**:
- Interface defined in `domain/` (ABC, framework-independent).
- Implementation in `infrastructure/repositories/` (SQLAlchemy, PostgreSQL).
- Return domain entities or DTOs — never ORM objects.

---

# 3. TypeScript & React Standards

## 3.1 Component Template

```tsx
// features/dashboard/components/RevenueOverview.tsx

import { useQuery } from "@tanstack/react-query";
import { analyticsService } from "@/services/analytics";
import { MetricCard } from "@/components/shared/MetricCard";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/shared/ErrorState";
import type { KPIItem } from "@/types/analytics";

interface RevenueOverviewProps {
    timeRange: string;
    region?: string;
    onMetricClick?: (metric: string) => void;
}

export function RevenueOverview({ timeRange, region, onMetricClick }: RevenueOverviewProps) {
    const { data, isLoading, error, refetch } = useQuery({
        queryKey: ["analytics", "kpis", { timeRange, region }],
        queryFn: () => analyticsService.getKPIs({ time_range: timeRange, region }),
        staleTime: 60_000,
    });

    if (isLoading) {
        return (
            <div className="grid grid-cols-4 gap-4">
                {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} className="h-[120px] rounded-lg" />
                ))}
            </div>
        );
    }

    if (error) {
        return (
            <ErrorState
                title="Failed to load revenue data"
                message={error.message}
                onRetry={() => refetch()}
            />
        );
    }

    if (!data?.items.length) {
        return (
            <ErrorState
                title="No data available"
                message="Revenue data will appear here once the first dataset is imported."
                variant="empty"
            />
        );
    }

    return (
        <div className="grid grid-cols-4 gap-4">
            {data.items.map((kpi) => (
                <MetricCard
                    key={kpi.metric_name}
                    title={kpi.metric_name.toUpperCase()}
                    value={kpi.value}
                    format={kpi.unit === "USD" ? "currency" : "percentage"}
                    trend={kpi.change_rate ? {
                        direction: kpi.trend as "up" | "down",
                        value: kpi.change_rate,
                        label: "vs last period",
                    } : undefined}
                    onClick={() => onMetricClick?.(kpi.metric_name)}
                />
            ))}
        </div>
    );
}
```

**Rules**:
- **Always** handle: loading, error, empty, success.
- Use `useQuery` for all server data — never `useState` + `useEffect` + `fetch`.
- Export the component as named export (not default).
- Props interface defined above the component.

## 3.2 Custom Hooks

```tsx
// hooks/useCustomerData.ts

interface UseCustomerDataParams {
    customerId: string;
    enabled?: boolean;
}

export function useCustomerData({ customerId, enabled = true }: UseCustomerDataParams) {
    return useQuery({
        queryKey: ["customers", "detail", customerId],
        queryFn: () => customerService.getById(customerId),
        enabled: enabled && !!customerId,
        staleTime: 5 * 60_000,
        retry: 2,
    });
}
```

**Rules**:
- One hook per query (avoid monster hooks).
- `enabled` flag for conditional fetching.
- `staleTime` set appropriately (KPIs: 60s, profiles: 5min, reports: 30min).

## 3.3 API Service Layer

```typescript
// services/api.ts
import axios from "axios";

const api = axios.create({
    baseURL: process.env.NEXT_PUBLIC_API_URL,
    timeout: 30_000,
    headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
    const token = getAuthToken();
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

api.interceptors.response.use(
    (response) => response.data,
    (error) => {
        const apiError: ApiError = {
            code: error.response?.data?.error?.code ?? "INT_001",
            message: error.response?.data?.error?.message ?? "An unexpected error occurred",
            category: error.response?.data?.error?.category ?? "INTERNAL",
            requestId: error.response?.data?.request_id,
        };
        return Promise.reject(apiError);
    },
);

export { api };
```

**Rules**:
- Never call `fetch()` or `axios` directly in components.
- All API calls go through `services/*.ts`.
- Response interceptor normalizes errors into `ApiError` type.

## 3.4 No `any`

```typescript
// ❌ Bad
function processData(data: any): any { ... }

// ✅ Good
function processData(data: CustomerProfile): KPIItem[] { ... }

// ✅ Acceptable (truly dynamic)
function logDebug(data: Record<string, unknown>): void { ... }
```

---

# 4. SQL Standards

## 4.1 Rules

```sql
-- ✅ Good
SELECT
    dc.customer_id,
    dc.status,
    SUM(fb.net_revenue) AS total_revenue
FROM warehouse.dim_customer dc
JOIN warehouse.fact_billing fb ON dc.customer_id = fb.customer_id
WHERE dc.status = :status
  AND fb.billing_month >= :start_month
GROUP BY dc.customer_id, dc.status
ORDER BY total_revenue DESC
LIMIT :limit;

-- ❌ Bad
SELECT * FROM customers WHERE status = 'active';  -- SELECT *
SELECT * FROM customers WHERE id = ' + customer_id;  -- SQL injection
```

| Rule | Enforcement |
|------|-------------|
| Explicit columns (no `SELECT *`) | grep check (L2) |
| Parameterized queries only | grep check (L0) |
| Table aliases for JOINs | Code review |
| `LIMIT` on all queries without `WHERE` on indexed column | Code review |
| No business logic in SQL | Code review |

---

# 5. Error Handling

## 5.1 Exception Hierarchy

```python
# app/core/exceptions.py

class InsightFlowError(Exception):
    """Base exception for all InsightFlow errors."""
    def __init__(self, code: str, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)

class ValidationError(InsightFlowError):
    """Invalid input data."""
    pass

class BusinessError(InsightFlowError):
    """Business rule violation."""
    pass

class NotFoundError(InsightFlowError):
    """Resource not found."""
    pass

class MLError(InsightFlowError):
    """ML pipeline error."""
    pass

class AIError(InsightFlowError):
    """AI Copilot error."""
    pass

class InfrastructureError(InsightFlowError):
    """Database, Redis, storage errors."""
    pass

class ExternalServiceError(InsightFlowError):
    """LLM provider, external API errors."""
    pass
```

## 5.2 Raising Exceptions

```python
# ✅ Good: specific, with error code
if customer is None:
    raise NotFoundError(
        code="NF_001",
        message=f"Customer not found: {customer_id}",
    )

# ❌ Bad: generic exception
if customer is None:
    raise Exception("Customer not found")

# ❌ Bad: swallowing exceptions
try:
    await repo.save(data)
except Exception:
    pass
```

## 5.3 API Error Mapping

```python
# app/api/middleware/error_handler.py

ERROR_MAP = {
    ValidationError: 422,
    BusinessError: 409,
    NotFoundError: 404,
    MLError: 500,
    AIError: 500,
    InfrastructureError: 503,
    ExternalServiceError: 502,
    InsightFlowError: 500,
}

async def error_handler_middleware(request, call_next):
    try:
        return await call_next(request)
    except InsightFlowError as e:
        return JSONResponse(
            status_code=ERROR_MAP.get(type(e), 500),
            content={
                "success": False,
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": e.details,
                    "category": e.__class__.__name__.replace("Error", "").upper(),
                },
                "request_id": request.state.request_id,
            },
        )
```

---

# 6. Logging

## 6.1 Structured Logging

```python
# ✅ Use structlog
import structlog

logger = structlog.get_logger()

async def predict_churn(self, customer_id: str) -> ChurnPredictionResponse:
    logger.info("churn_prediction_started", customer_id=customer_id)

    try:
        result = await self._do_predict(customer_id)
        logger.info(
            "churn_prediction_completed",
            customer_id=customer_id,
            risk_score=result.risk_score,
            latency_ms=elapsed_ms,
        )
        return result
    except Exception as e:
        logger.error(
            "churn_prediction_failed",
            customer_id=customer_id,
            error=str(e),
            exc_info=True,
        )
        raise
```

```python
# ❌ Bad: print() or stdlib logging
print(f"Customer {customer_id} churn score: {score}")
logging.info("Processing customer %s", customer_id)
```

## 6.2 Required Log Fields

| Field | When | Example |
|-------|------|---------|
| `request_id` | Every API request | `req_01J2X5K8N3P7Q9R2` |
| `workflow_id` | Every AI workflow | `wf_01J2X6M1N4Q8R3S5` |
| `customer_id` | Customer-scoped operations | `CUST-00000001` |
| `latency_ms` | Significant operations | `1200` |
| `model_version` | ML predictions | `churn_xgboost_v1.2.0` |
| `prompt_version` | AI agent calls | `v2__plan_generation` |
| `token_usage` | LLM calls | `{"prompt": 350, "completion": 120}` |

---

# 7. Testing

## 7.1 Test Structure

```
tests/
├── unit/
│   ├── domain/
│   │   └── test_customer.py
│   └── application/
│       └── test_churn_service.py
├── integration/
│   └── test_customer_repository.py
├── api/
│   └── test_churn_endpoints.py
├── ai/
│   ├── test_prompts/
│   │   ├── test_planner_prompts.py
│   │   └── test_sql_prompts.py
│   └── golden/
│       ├── planner_case_001_expected.json
│       └── sql_case_001_expected.sql
└── conftest.py
```

## 7.2 Test Naming

```python
# tests/unit/application/test_churn_service.py

class TestChurnPredictionService:
    async def test_predict_returns_high_risk_for_frequent_complainer(self):
        """Customer with high complaint frequency should get HIGH risk."""
        ...

    async def test_predict_raises_not_found_for_unknown_customer(self):
        """Unknown customer ID raises NotFoundError."""
        ...

    async def test_predict_raises_business_error_for_churned_customer(self):
        """Already churned customer cannot be predicted again."""
        ...

    @pytest.mark.parametrize("score,expected_level", [
        (0.91, "HIGH"),
        (0.45, "MEDIUM"),
        (0.12, "LOW"),
        (0.699, "MEDIUM"),
        (0.701, "HIGH"),
    ])
    async def test_classify_risk_boundaries(self, score, expected_level):
        """Risk levels must match defined thresholds."""
        ...
```

## 7.3 Fixtures

```python
# tests/conftest.py

@pytest.fixture
async def db_session():
    """In-memory SQLite session for unit tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine) as session:
        yield session

@pytest.fixture
def mock_llm_provider():
    """Returns a mock LLM that responds with pre-configured outputs."""
    provider = MockLLMProvider()
    provider.set_response("planner", AnalysisPlan(...))
    return provider

@pytest.fixture
def sample_customer():
    return Customer(
        customer_id="CUST-TEST-001",
        status="active",
        join_date=date(2024, 4, 10),
    )
```

## 7.4 Coverage Targets

| Layer | Target |
|-------|:------:|
| Domain | ≥ 90% |
| Application | ≥ 85% |
| Infrastructure | ≥ 80% |
| API | ≥ 80% |
| **Global minimum** | **≥ 80%** |

---

# 8. Documentation

## 8.1 Docstrings (Python)

```python
async def predict_batch(
    self,
    model_version: str,
    feature_version: str,
    max_customers: int | None = None,
) -> BatchPredictionResult:
    """Run churn prediction on all active customers.

    Loads features from the Feature Store, runs the specified model,
    and persists predictions to the prediction registry.

    Args:
        model_version: Model version to use (e.g., 'v1.2.0').
        feature_version: Feature set version (e.g., 'v1.0.0').
        max_customers: If set, limit batch size (for testing).

    Returns:
        BatchPredictionResult with total predictions, high_risk_count,
        and task_id.

    Raises:
        ModelNotLoadedError: If model_version is not found in registry.
        FeatureVersionMismatchError: If model expects different feature version.
    """
```

**Rules**:
- Every public function/method has a docstring.
- Use Google-style (Args/Returns/Raises).
- Describe *why*, not just *what*.

## 8.2 Comments (TypeScript)

```typescript
/**
 * Fetches and formats customer churn risk for display.
 *
 * Risk levels are determined server-side. This hook adds
 * client-side formatting (color, trend arrow, locale).
 *
 * @param customerId - Source system customer ID
 * @param options.refetchInterval - Polling interval in ms (default: 0 = no polling)
 */
export function useChurnPrediction(
    customerId: string,
    options?: { refetchInterval?: number },
) { ... }
```

---

# 9. Git Workflow

## 9.1 Branch Naming

```
feature/<description>     # feature/churn-prediction
fix/<description>         # fix/api-timeout
refactor/<description>    # refactor/repository-pattern
docs/<description>        # docs/api-spec-update
test/<description>        # test/add-churn-e2e
perf/<description>        # perf/query-optimization
chore/<description>       # chore/update-deps
```

## 9.2 Commit Messages

```
feat: add churn prediction API endpoint
fix: handle null CSAT scores in customer profile
refactor: extract risk classification to domain service
docs: freeze API spec v1.0
test: add regression test for SQL injection guard
perf: add index on fact_billing(customer_id, billing_month)
chore: bump fastapi to 0.115.0
```

**Rules**:
- One logical change per commit.
- Imperative mood ("add", not "added").
- No period at end of first line.
- Body explains *why* when non-obvious.

## 9.3 Pull Requests

- Branch from `develop`, merge to `develop`.
- `main` is production — only merged from `develop` via release PR.
- All CI gates must pass before merge (see `.github/workflows/quality.yml`).
- At least one approval required.
- Squash merge preferred.

---

# 10. AI Coding Assistant Rules

When an AI coding assistant (Codex, Claude Code, Cursor, Copilot) generates code for InsightFlow, it must follow these rules **in addition to** all rules above.

## 10.1 Before Writing Code

1. **Read the relevant frozen documents first.** If generating an API endpoint, read `05_API_SPEC.md`. If generating a database migration, read `03_DATABASE.md`.
2. **Check if the change violates any L0 rule** in `08_ARCHITECTURE_RULES.md`. If it does, stop and surface the conflict.
3. **Reuse existing services and components.** Search the codebase before creating new ones.
4. **Follow the directory structure** in `00_PROJECT_STRUCTURE.md`. Do not create files in the wrong directory.

## 10.2 While Writing Code

1. **Generate tests alongside production code.** Every new service gets a test file.
2. **Use the project's existing patterns.** Match the style of neighboring files.
3. **Keep changes scoped.** One feature = one PR. Do not refactor unrelated code.
4. **Use dependency injection.** Never instantiate infrastructure objects inside business logic.
5. **Add type hints.** Every function signature must be fully typed.
6. **Add docstrings.** Every public function must have a docstring.

## 10.3 After Writing Code

1. **Run `scripts/check_architecture.py`.** Fix any violations.
2. **Run `ruff check . && ruff format --check .`.** Fix lint/format issues.
3. **Run `mypy app/`.** Fix type errors.
4. **Run `pytest --cov=app --cov-fail-under=80`.** Ensure tests pass and coverage meets threshold.
5. **Summarize what was changed and why.** Include in the PR description.

## 10.4 What NOT to Do

- ❌ Do not silently bypass architecture rules.
- ❌ Do not duplicate business logic (check Metric Registry before computing a KPI).
- ❌ Do not return ORM objects through API endpoints.
- ❌ Do not place business logic in routers or React components.
- ❌ Do not hardcode configuration values or secrets.
- ❌ Do not use `SELECT *` in SQL queries.
- ❌ Do not use f-string SQL construction.
- ❌ Do not write inline LLM prompts (use Prompt Registry).
- ❌ Do not skip error handling or logging.
- ❌ Do not change frozen document interfaces without an ADR.

---

# 11. Code Review Checklist

Every PR reviewer must verify:

### Architecture Compliance
- [ ] No L0 architecture rules violated (AR-001, AR-003, AR-010, etc.)
- [ ] Business logic is in Domain or Application layer, not routers or components
- [ ] Database access goes through Repositories
- [ ] SQL is parameterized (no f-strings)
- [ ] Domain layer has zero framework imports

### Code Quality
- [ ] Type hints on all public interfaces
- [ ] Docstrings on public functions/methods
- [ ] No `print()` or stdlib `logging` (use `structlog`)
- [ ] No magic numbers (use named constants)
- [ ] No commented-out code
- [ ] No `TODO` without an issue reference
- [ ] No `Any` types unless truly unavoidable

### Testing
- [ ] Unit tests for new domain/application logic
- [ ] Integration tests for new API endpoints
- [ ] Bug fix includes regression test
- [ ] Coverage does not decrease

### AI-Specific (if applicable)
- [ ] New prompts are versioned in `app/ai/prompts/`
- [ ] Prompt version is in `active` status
- [ ] Prompt has evaluation results
- [ ] AI output validation is in place
- [ ] SQL Sandbox is called before AI-generated SQL execution

### Frontend-Specific (if applicable)
- [ ] Component handles loading, error, empty, and success states
- [ ] No KPI computation in components
- [ ] API calls go through service layer (no raw `fetch`)
- [ ] AI outputs show confidence and evidence

---

# Document Freeze

This document freezes the **coding standards** for InsightFlow Version 1.0.

All contributors — human and AI — must follow these standards. Code that violates them will be rejected in review. The rules in this document are designed to produce a codebase that is readable, maintainable, testable, and consistent across hundreds of files and dozens of contributors.
