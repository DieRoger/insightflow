# InsightFlow — API Specification (Contract)

Version 1.0 · Status: **Frozen** · Target: Frontend ↔ Backend Contract

---

## Table of Contents

1. [Design Principles](#1-design-principles)
2. [Authentication](#2-authentication)
3. [Common Objects](#3-common-objects)
4. [Pagination](#4-pagination)
5. [Error Codes](#5-error-codes)
6. [Analytics API](#6-analytics-api)
7. [Customer API](#7-customer-api)
8. [Churn API](#8-churn-api)
9. [Copilot API](#9-copilot-api)
10. [Report API](#10-report-api)
11. [Model API](#11-model-api)
12. [Feature API](#12-feature-api)
13. [System API](#13-system-api)
14. [WebSocket](#14-websocket)
15. [Async Tasks](#15-async-tasks)
16. [API Versioning](#16-api-versioning)
17. [API Lifecycle](#17-api-lifecycle)

---

# 1. Design Principles

| # | Principle | Enforcement |
|---|-----------|-------------|
| P1 | **Every endpoint is a contract.** Frontend and backend agree on the exact shape. | Pydantic schema + TypeScript type in sync |
| P2 | **No ORM objects cross the API boundary.** | Schemas in `app/schemas/`, not `app/infrastructure/` |
| P3 | **Errors are typed, not stringified.** | Every error has a `code`, `message`, optional `details` |
| P4 | **Async operations return immediately.** | `202 Accepted` + `task_id` for any operation > 5 seconds |
| P5 | **Read-only analytics never mutate.** | All GET /analytics/* have zero side effects |
| P6 | **Evidence is mandatory for AI outputs.** | Copilot responses always include evidence references |
| P7 | **Backward compatibility within a major version.** | v1 endpoints may add optional fields but never remove or rename |

---

# 2. Authentication

| Aspect | MVP (V1.0) | Future (V2.0+) |
|--------|------------|----------------|
| Scheme | Bearer JWT | OAuth2 + SSO |
| Header | `Authorization: Bearer <token>` | Same |
| Expiry | 24 hours | Configurable |
| Refresh | Not in MVP | `/api/v1/auth/refresh` |
| Scope | Single-tenant, no roles | RBAC with scopes |

**MVP**: A single JWT secret validates all requests. No per-endpoint permission checks.
**Login endpoint** (future): `POST /api/v1/auth/login` — not in MVP scope.

---

# 3. Common Objects

These types are shared across all endpoints. They are frozen — every endpoint MUST use them.

## 3.1 Response Envelope

### Success

```json
{
    "success": true,
    "data": { },
    "meta": {
        "page": 1,
        "page_size": 20,
        "total": 1523
    },
    "request_id": "req_01J2X5K8N3P7Q9R2"
}
```

**DTO**:

```python
# backend/app/schemas/common.py
from pydantic import BaseModel
from typing import Generic, TypeVar

T = TypeVar("T")

class Meta(BaseModel):
    page: int | None = None
    page_size: int | None = None
    total: int | None = None
    latency_ms: int | None = None

class SuccessResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T
    meta: Meta | None = None
    request_id: str
```

```typescript
// frontend/types/api.ts
interface SuccessResponse<T> {
    success: true;
    data: T;
    meta?: {
        page?: number;
        page_size?: number;
        total?: number;
        latency_ms?: number;
    };
    request_id: string;
}
```

### Error

```json
{
    "success": false,
    "error": {
        "code": "CUSTOMER_NOT_FOUND",
        "message": "Customer with ID CUST-99999 does not exist.",
        "details": null,
        "category": "BUSINESS"
    },
    "request_id": "req_01J2X5K8N3P7Q9R2"
}
```

**DTO**:

```python
class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict | None = None
    category: str  # VALIDATION | BUSINESS | ML | AI | INFRASTRUCTURE | INTERNAL

class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
    request_id: str
```

```typescript
interface ErrorResponse {
    success: false;
    error: {
        code: string;
        message: string;
        details?: Record<string, unknown>;
        category: "VALIDATION" | "BUSINESS" | "ML" | "AI" | "INFRASTRUCTURE" | "INTERNAL";
    };
    request_id: string;
}

type ApiResponse<T> = SuccessResponse<T> | ErrorResponse;
```

---

## 3.2 Common Value Objects

### RiskLevel

```python
from enum import StrEnum

class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
```

```typescript
type RiskLevel = "LOW" | "MEDIUM" | "HIGH";
```

### TimeRange

```python
from datetime import date
from pydantic import BaseModel, model_validator

class TimeRange(BaseModel):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def start_before_end(self):
        if self.start_date > self.end_date:
            raise ValueError("start_date must be before end_date")
        return self
```

```typescript
interface TimeRange {
    start_date: string;  // ISO 8601 date: "2026-01-01"
    end_date: string;
}
```

### SortOrder

```python
class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"
```

### Insight (shared across Analytics, Copilot, Reports)

```python
class EvidenceItem(BaseModel):
    source_table: str
    description: str
    metric: str | None = None
    sql: str | None = None
    sample_size: int | None = None
    confidence: float  # 0.0–1.0
    generated_at: str  # ISO 8601

class Insight(BaseModel):
    insight_id: str
    metric: str
    dimension: str | None = None
    title: str
    value: float | None = None
    baseline: float | None = None
    change_rate: float | None = None
    trend: str | None = None  # "up" | "down" | "stable"
    evidence: list[EvidenceItem]
    confidence: float
    timestamp: str
```

```typescript
interface EvidenceItem {
    source_table: string;
    description: string;
    metric?: string;
    sql?: string;
    sample_size?: number;
    confidence: number;
    generated_at: string;
}

interface Insight {
    insight_id: string;
    metric: string;
    dimension?: string;
    title: string;
    value?: number;
    baseline?: number;
    change_rate?: number;
    trend?: "up" | "down" | "stable";
    evidence: EvidenceItem[];
    confidence: number;
    timestamp: string;
}
```

---

# 4. Pagination

### Request Parameters

| Parameter | Type | Default | Max | Description |
|-----------|------|---------|-----|-------------|
| `page` | `int` | 1 | — | 1-indexed page number |
| `page_size` | `int` | 20 | 100 | Items per page |
| `sort` | `str` | varies | — | Column name |
| `order` | `str` | `desc` | — | `asc` or `desc` |

### Response Meta

```json
{
    "meta": {
        "page": 1,
        "page_size": 20,
        "total": 1523,
        "total_pages": 77
    }
}
```

`total_pages` = `ceil(total / page_size)`. Optional but recommended.

---

# 5. Error Codes

Every error in the system belongs to one of these ranges. No ad-hoc error codes allowed.

### Error Code Registry

| Range | Category | HTTP Status | Description |
|-------|----------|-------------|-------------|
| `VAL_001`–`VAL_099` | Validation | 422 | Invalid request data |
| `BIZ_001`–`BIZ_099` | Business | 409 | Business rule violation |
| `NF_001`–`NF_099` | Not Found | 404 | Resource not found |
| `ML_001`–`ML_099` | ML | 500/503 | Model/prediction errors |
| `AI_001`–`AI_099` | AI | 500/503 | AI Copilot errors |
| `INF_001`–`INF_099` | Infrastructure | 503 | DB/Redis/storage errors |
| `EXT_001`–`EXT_099` | External | 502 | LLM provider or external API errors |
| `AUTH_001`–`AUTH_099` | Authentication | 401/403 | Auth failures |
| `RATE_001`–`RATE_099` | Rate Limit | 429 | Too many requests |
| `INT_001`–`INT_099` | Internal | 500 | Unexpected errors |

### Detailed Error Code Table

| Code | HTTP | Message Template |
|------|------|-----------------|
| `VAL_001` | 422 | Invalid request body: {field} |
| `VAL_002` | 422 | Invalid date range: start_date must be before end_date |
| `VAL_003` | 422 | Invalid page_size: must be between 1 and 100 |
| `VAL_004` | 422 | Invalid sort column: {column} |
| `BIZ_001` | 409 | Report already published |
| `BIZ_002` | 409 | Model is already in production |
| `BIZ_003` | 409 | Duplicate metric definition: {metric_name} |
| `NF_001` | 404 | Customer not found: {customer_id} |
| `NF_002` | 404 | Report not found: {report_id} |
| `NF_003` | 404 | Model not found: {model_id} |
| `NF_004` | 404 | Prediction not found: {prediction_id} |
| `NF_005` | 404 | Workflow not found: {workflow_id} |
| `ML_001` | 500 | Model prediction failed: {reason} |
| `ML_002` | 503 | Model not loaded: {model_name} v{model_version} |
| `ML_003` | 500 | Feature version mismatch: expected {expected}, got {actual} |
| `ML_004` | 500 | SHAP explanation unavailable for this model type |
| `AI_001` | 503 | LLM provider timeout after {seconds}s |
| `AI_002` | 500 | LLM response failed schema validation |
| `AI_003` | 500 | SQL Agent generated forbidden SQL: {keyword} |
| `AI_004` | 500 | AI workflow exceeded max retries |
| `AI_005` | 500 | Prompt version not found: {prompt_id} |
| `AI_006` | 500 | AI output confidence below threshold: {confidence} |
| `INF_001` | 503 | Database unavailable |
| `INF_002` | 503 | Redis unavailable |
| `INF_003` | 503 | Object storage unavailable |
| `INF_004` | 503 | Task queue unavailable |
| `EXT_001` | 502 | LLM provider returned error: {status_code} |
| `EXT_002` | 502 | External API timeout: {service_name} |
| `AUTH_001` | 401 | Missing or invalid authentication token |
| `AUTH_002` | 401 | Token expired |
| `AUTH_003` | 403 | Insufficient permissions |
| `RATE_001` | 429 | Rate limit exceeded. Retry after {seconds}s |
| `INT_001` | 500 | Internal server error |

---

# 6. Analytics API

Base: `/api/v1/analytics`

## 6.1 GET /analytics/kpi

| Attribute | Value |
|-----------|-------|
| **Purpose** | List KPI values with optional filters |
| **Auth** | Required |
| **Rate Limit** | 60 req/min |

**Query Parameters**:

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `metric` | `str` | No | Filter by metric name (e.g., `arpu`, `churn_rate`) |
| `category` | `str` | No | revenue / customer / usage / network / service / marketing |
| `region` | `str` | No | Region name |
| `package` | `str` | No | Package name |
| `time_range` | `str` | No | `last_7d`, `last_30d`, `last_90d`, `this_month`, `last_month` |
| `page` | `int` | No | Default 1 |
| `page_size` | `int` | No | Default 20, max 100 |

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "items": [
            {
                "metric_name": "arpu",
                "category": "revenue",
                "value": 72.15,
                "unit": "USD",
                "previous_value": 68.90,
                "change_rate": 0.047,
                "trend": "up",
                "region": "East",
                "period": "2026-07"
            }
        ]
    },
    "meta": { "page": 1, "page_size": 20, "total": 50 },
    "request_id": "req_xxx"
}
```

**DTO**:

```python
class KPIItem(BaseModel):
    metric_name: str
    category: str
    value: float
    unit: str
    previous_value: float | None = None
    change_rate: float | None = None
    trend: str | None = None
    region: str | None = None
    package: str | None = None
    period: str

class KPIListResponse(BaseModel):
    items: list[KPIItem]
```

**Possible Errors**: `VAL_001`, `VAL_002`, `INF_001`

---

## 6.2 GET /analytics/kpi/{metric}

| Attribute | Value |
|-----------|-------|
| **Purpose** | Trend data for a single metric over time |
| **Auth** | Required |

**Path Parameters**: `metric` — metric name (e.g., `arpu`)

**Query Parameters**:

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `granularity` | `str` | No | `day`, `week`, `month` (default: `month`) |
| `time_range` | `str` | No | `last_30d`, `last_90d`, `last_12m` |
| `region` | `str` | No | Filter by region |

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "metric_name": "arpu",
        "unit": "USD",
        "granularity": "month",
        "series": [
            { "period": "2026-01", "value": 68.50 },
            { "period": "2026-02", "value": 69.10 },
            { "period": "2026-03", "value": 72.15 }
        ],
        "trend": {
            "direction": "up",
            "slope": 1.22,
            "confidence": 0.89
        },
        "anomalies": [
            { "period": "2026-03", "value": 72.15, "expected": 69.80, "z_score": 2.8 }
        ]
    },
    "meta": null,
    "request_id": "req_xxx"
}
```

**DTO**:

```python
class TrendPoint(BaseModel):
    period: str
    value: float

class TrendSummary(BaseModel):
    direction: str
    slope: float
    confidence: float

class AnomalyPoint(BaseModel):
    period: str
    value: float
    expected: float
    z_score: float

class MetricTrendResponse(BaseModel):
    metric_name: str
    unit: str
    granularity: str
    series: list[TrendPoint]
    trend: TrendSummary
    anomalies: list[AnomalyPoint]
```

**Possible Errors**: `NF_001` (metric not in registry), `VAL_002`

---

## 6.3 GET /analytics/trend

| Attribute | Value |
|-----------|-------|
| **Purpose** | Multi-metric trend comparison |
| **Auth** | Required |

**Query Parameters**:

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `metrics` | `str` | Yes | Comma-separated metric names: `arpu,churn_rate,mrr` |
| `time_range` | `str` | No | Default `last_12m` |

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "series": {
            "arpu": [
                { "period": "2026-01", "value": 68.50 },
                { "period": "2026-02", "value": 69.10 }
            ],
            "churn_rate": [
                { "period": "2026-01", "value": 0.032 },
                { "period": "2026-02", "value": 0.029 }
            ]
        }
    },
    "meta": null,
    "request_id": "req_xxx"
}
```

---

## 6.4 GET /analytics/anomaly

| Attribute | Value |
|-----------|-------|
| **Purpose** | List active anomalies across all monitored metrics |
| **Auth** | Required |

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "items": [
            {
                "anomaly_id": "ano_001",
                "metric": "churn_rate",
                "region": "East",
                "observed": 0.052,
                "expected": 0.031,
                "deviation_pct": 67.7,
                "severity": "HIGH",
                "detected_at": "2026-08-01T02:00:00Z"
            }
        ]
    },
    "meta": { "total": 3 },
    "request_id": "req_xxx"
}
```

**DTO**:

```python
class AnomalyItem(BaseModel):
    anomaly_id: str
    metric: str
    region: str | None = None
    observed: float
    expected: float
    deviation_pct: float
    severity: str  # LOW | MEDIUM | HIGH
    detected_at: str
```

---

## 6.5 GET /analytics/segmentation

| Attribute | Value |
|-----------|-------|
| **Purpose** | Segment distribution for a given metric |
| **Auth** | Required |

**Query Parameters**:

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `metric` | `str` | Yes | e.g., `arpu`, `churn_rate` |
| `dimension` | `str` | Yes | `region`, `package`, `segment`, `contract_type` |

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "metric": "arpu",
        "dimension": "region",
        "segments": [
            { "label": "East", "value": 75.20, "count": 245000 },
            { "label": "South", "value": 68.40, "count": 198000 },
            { "label": "North", "value": 82.10, "count": 156000 },
            { "label": "West", "value": 64.30, "count": 210000 },
            { "label": "Central", "value": 70.50, "count": 191000 }
        ]
    },
    "meta": null,
    "request_id": "req_xxx"
}
```

---

## 6.6 GET /analytics/funnel

| Attribute | Value |
|-----------|-------|
| **Purpose** | Customer lifecycle funnel |
| **Auth** | Required |

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "stages": [
            { "stage": "Visitor", "count": 2000000, "pct": 100 },
            { "stage": "Subscriber", "count": 1000000, "pct": 50 },
            { "stage": "Active User", "count": 800000, "pct": 40 },
            { "stage": "Premium User", "count": 200000, "pct": 10 },
            { "stage": "Retained User", "count": 650000, "pct": 32.5 }
        ]
    },
    "meta": null,
    "request_id": "req_xxx"
}
```

---

## 6.7 GET /analytics/cohort

| Attribute | Value |
|-----------|-------|
| **Purpose** | Retention by acquisition cohort |
| **Auth** | Required |

**Query Parameters**:

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `metric` | `str` | No | `retention`, `revenue` (default: `retention`) |

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "metric": "retention",
        "cohorts": [
            {
                "cohort": "2026-01",
                "size": 8500,
                "months": [
                    { "month": 0, "value": 1.0 },
                    { "month": 1, "value": 0.92 },
                    { "month": 3, "value": 0.81 },
                    { "month": 6, "value": 0.73 }
                ]
            }
        ]
    },
    "meta": null,
    "request_id": "req_xxx"
}
```

---

## 6.8 DTO Summary — Analytics

```python
# backend/app/schemas/analytics_response.py

class KPIItem(BaseModel):
    metric_name: str
    category: str
    value: float
    unit: str
    previous_value: float | None = None
    change_rate: float | None = None
    trend: str | None = None
    region: str | None = None
    package: str | None = None
    period: str

class TrendPoint(BaseModel):
    period: str
    value: float

class AnomalyItem(BaseModel):
    anomaly_id: str
    metric: str
    region: str | None = None
    observed: float
    expected: float
    deviation_pct: float
    severity: str
    detected_at: str

class SegmentItem(BaseModel):
    label: str
    value: float
    count: int

class FunnelStage(BaseModel):
    stage: str
    count: int
    pct: float

class CohortData(BaseModel):
    cohort: str
    size: int
    months: list[dict]  # {month: int, value: float}
```

```typescript
// frontend/types/analytics.ts

interface KPIItem {
    metric_name: string;
    category: string;
    value: number;
    unit: string;
    previous_value?: number;
    change_rate?: number;
    trend?: "up" | "down" | "stable";
    region?: string;
    package?: string;
    period: string;
}

type TrendPoint = { period: string; value: number };
type AnomalyItem = {
    anomaly_id: string;
    metric: string;
    region?: string;
    observed: number;
    expected: number;
    deviation_pct: number;
    severity: "LOW" | "MEDIUM" | "HIGH";
    detected_at: string;
};
type SegmentItem = { label: string; value: number; count: number };
type FunnelStage = { stage: string; count: number; pct: number };
```

---

# 7. Customer API

Base: `/api/v1/customers`

## 7.1 GET /customers

| Attribute | Value |
|-----------|-------|
| **Purpose** | List/search customers with pagination and filters |
| **Auth** | Required |

**Query Parameters**:

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | `str` | No | `active`, `churned`, `suspended` |
| `segment` | `str` | No | `premium`, `heavy_user`, `price_sensitive`, `business`, `dormant` |
| `lifecycle_stage` | `str` | No | `new`, `active`, `at_risk`, `churned` |
| `risk_level` | `str` | No | `LOW`, `MEDIUM`, `HIGH` |
| `region` | `str` | No | Region name |
| `package` | `str` | No | Package name |
| `search` | `str` | No | Search by customer_id or name |
| `page` | `int` | No | Default 1 |
| `page_size` | `int` | No | Default 20, max 100 |
| `sort` | `str` | No | `tenure_days`, `arpu`, `clv`, `churn_risk` |
| `order` | `str` | No | `asc`, `desc` |

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "items": [
            {
                "customer_id": "CUST-00001",
                "status": "active",
                "lifecycle_stage": "active",
                "segment": "premium",
                "churn_risk_score": 0.12,
                "risk_level": "LOW",
                "arpu": 95.50,
                "tenure_days": 845,
                "region": "East",
                "package_name": "Premium Unlimited",
                "join_date": "2024-04-10"
            }
        ]
    },
    "meta": { "page": 1, "page_size": 20, "total": 1000000 },
    "request_id": "req_xxx"
}
```

**DTO**:

```python
class CustomerListItem(BaseModel):
    customer_id: str
    status: str
    lifecycle_stage: str
    segment: str | None = None
    churn_risk_score: float | None = None
    risk_level: str | None = None
    arpu: float | None = None
    tenure_days: int
    region: str | None = None
    package_name: str | None = None
    join_date: str
```

---

## 7.2 GET /customers/{customer_id}

| Attribute | Value |
|-----------|-------|
| **Purpose** | Customer 360 profile — complete view |
| **Auth** | Required |

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "profile": {
            "customer_id": "CUST-00001",
            "gender": "Male",
            "age": 34,
            "city": "Shanghai",
            "region": "East",
            "join_date": "2024-04-10",
            "contract_type": "postpaid",
            "status": "active",
            "lifecycle_stage": "active",
            "segment": "premium",
            "tenure_days": 845
        },
        "package": {
            "package_name": "Premium Unlimited",
            "package_type": "premium",
            "monthly_price": 99.00,
            "data_quota_gb": 100,
            "voice_quota_min": null
        },
        "billing": {
            "arpu": 95.50,
            "last_payment_status": "paid",
            "overdue_days": 0,
            "discount_ratio": 0.035,
            "monthly_bills": [
                { "month": "2026-07", "net_revenue": 95.50, "status": "paid" },
                { "month": "2026-06", "net_revenue": 95.50, "status": "paid" }
            ]
        },
        "usage": {
            "avg_daily_data_mb": 2150.5,
            "avg_daily_voice_min": 45.2,
            "data_trend": "up",
            "peak_usage_ratio": 0.62,
            "roaming_usage_mb": 120.0
        },
        "network": {
            "avg_latency_ms": 28.5,
            "drop_rate": 0.005,
            "coverage_score": 92.0
        },
        "service": {
            "total_complaints_90d": 1,
            "avg_csat": 4.5,
            "avg_resolution_time_min": 45.0
        },
        "prediction": {
            "churn_risk_score": 0.12,
            "risk_level": "LOW",
            "top_risk_factors": [],
            "predicted_at": "2026-08-01T02:00:00Z"
        },
        "recommendations": [
            {
                "action": "Offer loyalty reward",
                "expected_retention_lift": 0.02,
                "confidence": 0.85
            }
        ],
        "timeline": [
            { "date": "2026-07-15", "event": "Package upgraded to Premium Unlimited" },
            { "date": "2026-05-10", "event": "Service ticket: billing inquiry" },
            { "date": "2024-04-10", "event": "Customer joined" }
        ]
    },
    "meta": null,
    "request_id": "req_xxx"
}
```

**DTO** — Python:

```python
class CustomerProfile(BaseModel):
    customer_id: str
    gender: str | None = None
    age: int | None = None
    city: str | None = None
    region: str | None = None
    join_date: str
    contract_type: str
    status: str
    lifecycle_stage: str
    segment: str | None = None
    tenure_days: int

class PackageInfo(BaseModel):
    package_name: str
    package_type: str
    monthly_price: float
    data_quota_gb: float | None = None
    voice_quota_min: int | None = None

class BillingInfo(BaseModel):
    arpu: float
    last_payment_status: str
    overdue_days: int
    discount_ratio: float
    monthly_bills: list[dict]

class UsageInfo(BaseModel):
    avg_daily_data_mb: float
    avg_daily_voice_min: float
    data_trend: str | None = None
    peak_usage_ratio: float | None = None
    roaming_usage_mb: float | None = None

class NetworkInfo(BaseModel):
    avg_latency_ms: float | None = None
    drop_rate: float | None = None
    coverage_score: float | None = None

class ServiceInfo(BaseModel):
    total_complaints_90d: int
    avg_csat: float | None = None
    avg_resolution_time_min: float | None = None

class PredictionInfo(BaseModel):
    churn_risk_score: float
    risk_level: str
    top_risk_factors: list[dict]
    predicted_at: str

class RecommendationInfo(BaseModel):
    action: str
    expected_retention_lift: float
    confidence: float

class TimelineEvent(BaseModel):
    date: str
    event: str

class Customer360Response(BaseModel):
    profile: CustomerProfile
    package: PackageInfo
    billing: BillingInfo
    usage: UsageInfo
    network: NetworkInfo
    service: ServiceInfo
    prediction: PredictionInfo | None = None
    recommendations: list[RecommendationInfo]
    timeline: list[TimelineEvent]
```

**DTO** — TypeScript:

```typescript
interface Customer360Response {
    profile: CustomerProfile;
    package: PackageInfo;
    billing: BillingInfo;
    usage: UsageInfo;
    network: NetworkInfo;
    service: ServiceInfo;
    prediction: PredictionInfo | null;
    recommendations: RecommendationInfo[];
    timeline: TimelineEvent[];
}

interface CustomerProfile {
    customer_id: string;
    gender?: string;
    age?: number;
    city?: string;
    region?: string;
    join_date: string;
    contract_type: string;
    status: string;
    lifecycle_stage: string;
    segment?: string;
    tenure_days: number;
}
// ... (all sub-types mirrored from Python DTOs)
```

**Possible Errors**: `NF_001`

---

## 7.3 GET /customers/{customer_id}/usage

| Attribute | Value |
|-----------|-------|
| **Purpose** | Daily usage history for chart rendering |
| **Auth** | Required |

**Query Parameters**: `time_range` (default `last_90d`)

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "customer_id": "CUST-00001",
        "series": [
            { "date": "2026-08-01", "data_usage_mb": 2240.0, "voice_minutes": 52, "sms_count": 3 },
            { "date": "2026-07-31", "data_usage_mb": 2180.5, "voice_minutes": 48, "sms_count": 5 }
        ]
    },
    "meta": { "total": 90 },
    "request_id": "req_xxx"
}
```

---

## 7.4 GET /customers/{customer_id}/billing

| Attribute | Value |
|-----------|-------|
| **Purpose** | Monthly billing history |
| **Auth** | Required |

**Query Parameters**: `time_range` (default `last_12m`)

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "customer_id": "CUST-00001",
        "bills": [
            {
                "billing_month": "2026-07-01",
                "monthly_fee": 99.00,
                "discount_amount": 3.50,
                "net_revenue": 95.50,
                "payment_status": "paid",
                "overdue_days": 0
            }
        ]
    },
    "meta": { "total": 12 },
    "request_id": "req_xxx"
}
```

---

## 7.5 GET /customers/{customer_id}/predictions

| Attribute | Value |
|-----------|-------|
| **Purpose** | Prediction history for a customer |
| **Auth** | Required |

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "customer_id": "CUST-00001",
        "current": {
            "prediction_id": "pred_001",
            "risk_score": 0.12,
            "risk_level": "LOW",
            "top_positive_factors": [],
            "top_negative_factors": [
                { "feature": "tenure_days", "contribution": -0.15 }
            ],
            "confidence": 0.94,
            "model_version": "churn_xgboost_v1.2.0",
            "predicted_at": "2026-08-01T02:00:00Z"
        },
        "history": [
            { "predicted_at": "2026-07-01", "risk_score": 0.15, "risk_level": "LOW" },
            { "predicted_at": "2026-06-01", "risk_score": 0.18, "risk_level": "LOW" }
        ]
    },
    "meta": null,
    "request_id": "req_xxx"
}
```

---

## 7.6 GET /customers/{customer_id}/timeline

| Attribute | Value |
|-----------|-------|
| **Purpose** | Customer journey event timeline |
| **Auth** | Required |

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "customer_id": "CUST-00001",
        "events": [
            { "date": "2026-07-15", "event_type": "package_change", "description": "Upgraded to Premium Unlimited" },
            { "date": "2026-05-10", "event_type": "service_ticket", "description": "Billing inquiry resolved" },
            { "date": "2026-03-01", "event_type": "campaign", "description": "Responded to Spring Promotion" },
            { "date": "2024-04-10", "event_type": "registration", "description": "Customer joined" }
        ]
    },
    "meta": null,
    "request_id": "req_xxx"
}
```

---

# 8. Churn API

Base: `/api/v1/churn`

## 8.1 GET /churn/overview

| Attribute | Value |
|-----------|-------|
| **Purpose** | Churn dashboard overview — rates, trends, risk distribution |
| **Auth** | Required |

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "current_churn_rate": 0.032,
        "previous_churn_rate": 0.029,
        "change_pct": 10.3,
        "trend": "up",
        "risk_distribution": {
            "HIGH": { "count": 45000, "pct": 4.5 },
            "MEDIUM": { "count": 120000, "pct": 12.0 },
            "LOW": { "count": 835000, "pct": 83.5 }
        },
        "top_risk_factors": [
            { "factor": "complaint_frequency", "importance": 0.28 },
            { "factor": "payment_delay_avg", "importance": 0.22 },
            { "factor": "drop_rate_avg", "importance": 0.18 }
        ],
        "churn_by_region": [
            { "region": "East", "churn_rate": 0.041, "count": 10250 },
            { "region": "South", "churn_rate": 0.028, "count": 5544 }
        ],
        "churn_by_segment": [
            { "segment": "price_sensitive", "churn_rate": 0.065, "count": 18000 },
            { "segment": "premium", "churn_rate": 0.018, "count": 3600 }
        ]
    },
    "meta": null,
    "request_id": "req_xxx"
}
```

---

## 8.2 POST /churn/predict

| Attribute | Value |
|-----------|-------|
| **Purpose** | Online churn prediction for a single customer |
| **Auth** | Required |
| **Performance** | < 3 seconds |

**Request**:

```json
{
    "customer_id": "CUST-10025"
}
```

**Validation Rules**:
- `customer_id` must exist in `dim_customer`
- Customer must be `active` or `at_risk` (predicting for churned customers is meaningless)

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "prediction_id": "pred_01J2X6M1N4Q8R3S5",
        "customer_id": "CUST-10025",
        "risk_score": 0.91,
        "risk_level": "HIGH",
        "top_positive_factors": [
            { "feature": "complaint_frequency", "contribution": 0.32, "description": "High complaint frequency (3.2/day)" },
            { "feature": "payment_delay_avg", "contribution": 0.21, "description": "Average payment delay 15 days" }
        ],
        "top_negative_factors": [
            { "feature": "tenure_days", "contribution": -0.08, "description": "Long tenure (845 days)" }
        ],
        "confidence": 0.93,
        "model_version": "churn_xgboost_v1.2.0",
        "shap_available": true
    },
    "meta": { "latency_ms": 1200 },
    "request_id": "req_xxx"
}
```

**DTO**:

```python
# Request
class ChurnPredictRequest(BaseModel):
    customer_id: str

# Response
class FactorContribution(BaseModel):
    feature: str
    contribution: float
    description: str

class ChurnPredictionResponse(BaseModel):
    prediction_id: str
    customer_id: str
    risk_score: float
    risk_level: str
    top_positive_factors: list[FactorContribution]
    top_negative_factors: list[FactorContribution]
    confidence: float
    model_version: str
    shap_available: bool
```

**Possible Errors**: `NF_001`, `BIZ_002` (customer already churned), `ML_001`, `ML_002`

---

## 8.3 POST /churn/predict/batch

| Attribute | Value |
|-----------|-------|
| **Purpose** | Trigger batch prediction for all active customers |
| **Auth** | Required |
| **Mode** | **Async** — returns immediately with `task_id` |

**Request**:

```json
{
    "model_version": "churn_xgboost_v1.2.0",
    "feature_version": "v1.0.0"
}
```

**Response** `202`:

```json
{
    "success": true,
    "data": {
        "task_id": "task_batch_pred_01J2X6M1N4Q8R3S5",
        "status": "PENDING",
        "estimated_duration_sec": 600
    },
    "meta": null,
    "request_id": "req_xxx"
}
```

**Polling**: `GET /api/v1/system/tasks/{task_id}` (see §15)

**Possible Errors**: `ML_002`, `ML_003`, `INF_004`

---

## 8.4 GET /churn/predictions/{prediction_id}

| Attribute | Value |
|-----------|-------|
| **Purpose** | Full prediction detail with SHAP waterfall data |
| **Auth** | Required |

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "prediction_id": "pred_01J2X6M1N4Q8R3S5",
        "customer_id": "CUST-10025",
        "risk_score": 0.91,
        "risk_level": "HIGH",
        "factors": [
            { "feature": "complaint_frequency", "shap_value": 0.32, "feature_value": 3.2 },
            { "feature": "payment_delay_avg", "shap_value": 0.21, "feature_value": 15.0 },
            { "feature": "tenure_days", "shap_value": -0.08, "feature_value": 845.0 }
        ],
        "base_value": 0.28,
        "confidence": 0.93,
        "model_version": "churn_xgboost_v1.2.0",
        "feature_version": "v1.0.0",
        "predicted_at": "2026-08-01T02:00:00Z"
    },
    "meta": null,
    "request_id": "req_xxx"
}
```

**Possible Errors**: `NF_004`, `ML_004`

---

## 8.5 DTO Summary — Churn

```typescript
// frontend/types/churn.ts

interface ChurnOverview {
    current_churn_rate: number;
    previous_churn_rate: number;
    change_pct: number;
    trend: "up" | "down" | "stable";
    risk_distribution: Record<RiskLevel, { count: number; pct: number }>;
    top_risk_factors: { factor: string; importance: number }[];
    churn_by_region: { region: string; churn_rate: number; count: number }[];
    churn_by_segment: { segment: string; churn_rate: number; count: number }[];
}

interface FactorContribution {
    feature: string;
    contribution: number;
    description: string;
}

interface ChurnPrediction {
    prediction_id: string;
    customer_id: string;
    risk_score: number;
    risk_level: RiskLevel;
    top_positive_factors: FactorContribution[];
    top_negative_factors: FactorContribution[];
    confidence: number;
    model_version: string;
    shap_available: boolean;
}

interface SHAPFactor {
    feature: string;
    shap_value: number;
    feature_value: number;
}
```

---

# 9. Copilot API

Base: `/api/v1/copilot`

## 9.1 POST /copilot/chat

| Attribute | Value |
|-----------|-------|
| **Purpose** | Submit a natural language question, receive evidence-backed analysis |
| **Auth** | Required |
| **Performance** | < 15 seconds |
| **Idempotency** | Not idempotent — each call generates a new workflow |

**Request**:

```json
{
    "question": "Why did churn increase in East Region last month?",
    "context": {
        "time_range": "last_month",
        "region": "East",
        "filters": {}
    }
}
```

**Validation Rules**:
- `question` must be 1–500 characters
- `question` is sanitized for prompt injection before reaching LLM
- `context` is optional and used to narrow the analysis scope

**Business Rules**:
- The Copilot runs a 7-agent DAG: Planner → SQL/Analytics/Evidence → Decision → Writer → Reviewer
- Reviewer retries max 3 times; 4th attempt delivers with `review_override: true`
- All findings must reference at least one `EvidenceItem`

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "workflow_id": "wf_01J2X6M1N4Q8R3S5",
        "intent": "churn_root_cause_analysis",
        "question": "Why did churn increase in East Region last month?",
        "findings": [
            {
                "insight_id": "ins_001",
                "title": "Premium customer churn increased 23% MoM in East Region",
                "confidence": 0.92,
                "evidence": [
                    {
                        "source_table": "fact_service",
                        "description": "Complaint volume +28% among premium customers in East Region",
                        "metric": "complaint_frequency",
                        "sample_size": 45210,
                        "confidence": 0.95
                    },
                    {
                        "source_table": "fact_network",
                        "description": "Average latency increased from 35ms to 62ms in East urban clusters",
                        "metric": "latency_avg_ms",
                        "sample_size": 182000,
                        "confidence": 0.91
                    }
                ]
            }
        ],
        "decisions": [
            {
                "decision_id": "dec_001",
                "finding": "Premium customer churn increasing in East Region",
                "business_impact": "Estimated annual revenue loss: $1.8M",
                "recommendation": "Prioritize network optimization in East Region urban clusters",
                "expected_outcome": "Estimated 3-5% churn reduction within 60 days",
                "confidence": 0.87
            }
        ],
        "generated_sql": "SELECT dc.region_id, COUNT(*) ...",
        "report_id": "rpt_01J2X6M1N4Q8R3S5",
        "review_status": "PASSED",
        "review_override": false,
        "agents_executed": 7,
        "total_tokens": 4200
    },
    "meta": {
        "latency_ms": 8200
    },
    "request_id": "req_xxx"
}
```

**DTO**:

```python
# Request
class CopilotContext(BaseModel):
    time_range: str | None = None
    region: str | None = None
    filters: dict = {}

class CopilotChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    context: CopilotContext | None = None

# Response
class CopilotFinding(BaseModel):
    insight_id: str
    title: str
    confidence: float
    evidence: list[EvidenceItem]

class CopilotDecision(BaseModel):
    decision_id: str
    finding: str
    business_impact: str
    impact_confidence: float
    recommendation: str
    expected_outcome: str
    confidence: float
    supporting_evidence: list[str]       # Evidence IDs referenced
    risk_if_ignored: str                 # "Continued churn → $2.5M annual loss"
    alternative_actions: list[str]       # ["Launch campaign", "Offer discount"]

class CopilotChatResponse(BaseModel):
    workflow_id: str
    intent: str
    question: str
    findings: list[CopilotFinding]
    decisions: list[CopilotDecision]
    generated_sql: str | None = None
    report_id: str | None = None
    review_status: str  # PASSED | OVERRIDDEN
    review_override: bool
    agents_executed: int
    total_tokens: int
```

**Possible Errors**: `VAL_001`, `AI_001`, `AI_002`, `AI_003`, `AI_004`, `AI_005`, `AI_006`, `EXT_001`, `INF_001`

**Audit Log**: Every chat call logs: `workflow_id`, `user_question`, `intent`, `agent_traces[]`, `total_tokens`, `latency_ms`, `review_status`

---

## 9.2 GET /copilot/workflows/{workflow_id}

| Attribute | Value |
|-----------|-------|
| **Purpose** | Full trace of a workflow execution (for debugging) |
| **Auth** | Required |

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "workflow_id": "wf_01J2X6M1N4Q8R3S5",
        "status": "COMPLETED",
        "started_at": "2026-08-01T10:30:00Z",
        "completed_at": "2026-08-01T10:30:08Z",
        "total_latency_ms": 8200,
        "agent_traces": [
            {
                "agent": "planner",
                "execution_id": "exec_planner_001",
                "started_at": "2026-08-01T10:30:00.100Z",
                "completed_at": "2026-08-01T10:30:01.500Z",
                "latency_ms": 1400,
                "input_summary": "Why did churn increase...",
                "output_summary": "intent=churn_root_cause_analysis",
                "prompt_version": "v2__plan_generation",
                "model": "gpt-4o",
                "token_usage": { "prompt": 350, "completion": 120 },
                "error": null
            }
        ]
    },
    "meta": null,
    "request_id": "req_xxx"
}
```

**Possible Errors**: `NF_005`

---

## 9.3 GET /copilot/history

| Attribute | Value |
|-----------|-------|
| **Purpose** | Past chat history (paginated) |
| **Auth** | Required |

**Query Parameters**: `page`, `page_size`

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "items": [
            {
                "workflow_id": "wf_01J2X6M1N4Q8R3S5",
                "question": "Why did churn increase in East Region?",
                "intent": "churn_root_cause_analysis",
                "created_at": "2026-08-01T10:30:00Z",
                "findings_count": 1,
                "report_id": "rpt_01J2X6M1N4Q8R3S5"
            }
        ]
    },
    "meta": { "page": 1, "page_size": 20, "total": 45 },
    "request_id": "req_xxx"
}
```

---

# 10. Report API

Base: `/api/v1/reports`

## 10.1 GET /reports

| Attribute | Value |
|-----------|-------|
| **Purpose** | List generated reports |
| **Auth** | Required |

**Query Parameters**: `type` (daily/weekly/monthly/quarterly/executive), `page`, `page_size`

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "items": [
            {
                "report_id": "rpt_01J2X6M1N4Q8R3S5",
                "title": "Weekly Executive Summary — 2026-W31",
                "type": "weekly",
                "format": "markdown",
                "status": "published",
                "generated_at": "2026-08-01T10:30:00Z",
                "size_bytes": 24500,
                "download_url": "/api/v1/reports/rpt_01J2X6M1N4Q8R3S5/download"
            }
        ]
    },
    "meta": { "page": 1, "page_size": 20, "total": 52 },
    "request_id": "req_xxx"
}
```

---

## 10.2 POST /reports/generate

| Attribute | Value |
|-----------|-------|
| **Purpose** | Trigger report generation |
| **Auth** | Required |
| **Mode** | **Async** — returns immediately with `task_id` |

**Request**:

```json
{
    "type": "weekly",
    "format": "markdown",
    "parameters": {
        "week": "2026-W31",
        "regions": ["East", "South"]
    },
    "based_on_workflow": "wf_01J2X6M1N4Q8R3S5"
}
```

**Validation Rules**:
- `type` must be one of: `daily`, `weekly`, `monthly`, `quarterly`, `executive`
- `format` must be one of: `markdown`, `pdf`
- `based_on_workflow` is optional — if provided, the report embeds Copilot findings

**Response** `202`:

```json
{
    "success": true,
    "data": {
        "task_id": "task_rpt_01J2X6M1N4Q8R3S5",
        "status": "PENDING",
        "estimated_duration_sec": 30
    },
    "meta": null,
    "request_id": "req_xxx"
}
```

**Possible Errors**: `VAL_001`, `NF_005` (workflow not found), `BIZ_001`, `INF_004`

---

## 10.3 GET /reports/{report_id}

| Attribute | Value |
|-----------|-------|
| **Purpose** | Report metadata and download URL |
| **Auth** | Required |

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "report_id": "rpt_01J2X6M1N4Q8R3S5",
        "title": "Weekly Executive Summary — 2026-W31",
        "type": "weekly",
        "format": "markdown",
        "status": "published",
        "generated_at": "2026-08-01T10:30:00Z",
        "generated_by": "AI Copilot",
        "sections": [
            { "title": "Executive Summary", "confidence": 0.92 },
            { "title": "Revenue Analysis", "confidence": 0.95 },
            { "title": "Churn Analysis", "confidence": 0.91 },
            { "title": "Recommendations", "confidence": 0.87 }
        ],
        "evidence_count": 12,
        "size_bytes": 24500,
        "download_url": "/api/v1/reports/rpt_01J2X6M1N4Q8R3S5/download"
    },
    "meta": null,
    "request_id": "req_xxx"
}
```

**Possible Errors**: `NF_002`

---

## 10.4 GET /reports/{report_id}/download

| Attribute | Value |
|-----------|-------|
| **Purpose** | Download report file |
| **Auth** | Required |
| **Response** | Binary file stream with `Content-Type: application/octet-stream` |

---

# 11. Model API

Base: `/api/v1/models`

## 11.1 GET /models

| Attribute | Value |
|-----------|-------|
| **Purpose** | List registered ML models |
| **Auth** | Required |

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "items": [
            {
                "model_id": 1,
                "model_name": "churn_xgboost",
                "model_version": "v1.2.0",
                "model_type": "churn_prediction",
                "algorithm": "xgboost",
                "status": "production",
                "metrics": {
                    "roc_auc": 0.91,
                    "f1_score": 0.84,
                    "precision": 0.82,
                    "recall": 0.86
                },
                "trained_at": "2026-07-15T08:00:00Z",
                "feature_version": "v1.0.0"
            }
        ]
    },
    "meta": { "total": 5 },
    "request_id": "req_xxx"
}
```

---

## 11.2 GET /models/{model_id}

| Attribute | Value |
|-----------|-------|
| **Purpose** | Full model detail + evaluation report |
| **Auth** | Required |

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "model_id": 1,
        "model_name": "churn_xgboost",
        "model_version": "v1.2.0",
        "model_type": "churn_prediction",
        "algorithm": "xgboost",
        "status": "production",
        "training_dataset_id": "ds_churn_20260715",
        "feature_version": "v1.0.0",
        "hyperparameters": {
            "max_depth": 6,
            "learning_rate": 0.05,
            "n_estimators": 500,
            "subsample": 0.8
        },
        "evaluation": {
            "roc_auc": 0.91,
            "pr_auc": 0.78,
            "f1_score": 0.84,
            "precision": 0.82,
            "recall": 0.86,
            "log_loss": 0.32,
            "confusion_matrix": {
                "true_positive": 8500,
                "false_positive": 1200,
                "true_negative": 38000,
                "false_negative": 2300
            },
            "calibration_error": 0.03
        },
        "feature_importance": [
            { "feature": "complaint_frequency", "importance": 0.28 },
            { "feature": "payment_delay_avg", "importance": 0.22 }
        ],
        "training_time_sec": 340,
        "framework_version": "xgboost==2.1.0",
        "trained_at": "2026-07-15T08:00:00Z",
        "promoted_at": "2026-07-20T10:00:00Z"
    },
    "meta": null,
    "request_id": "req_xxx"
}
```

**Possible Errors**: `NF_003`

---

## 11.3 POST /models/{model_id}/promote

| Attribute | Value |
|-----------|-------|
| **Purpose** | Promote a model to production |
| **Auth** | Required |

**Request**:

```json
{
    "status": "production"
}
```

**Business Rules**:
- Only one model per `model_type` can be in `production` at a time
- Promoting a new model archives the current production model

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "model_id": 1,
        "model_name": "churn_xgboost",
        "model_version": "v1.2.0",
        "previous_status": "staging",
        "current_status": "production",
        "promoted_at": "2026-08-01T12:00:00Z"
    },
    "meta": null,
    "request_id": "req_xxx"
}
```

**Possible Errors**: `NF_003`, `BIZ_002`

---

# 12. Feature API

Base: `/api/v1/features`

## 12.1 GET /features

| Attribute | Value |
|-----------|-------|
| **Purpose** | List registered features with metadata |
| **Auth** | Required |

**Query Parameters**: `feature_table` (customer_features / churn_features / package_features)

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "items": [
            {
                "feature_name": "arpu",
                "feature_table": "customer_features",
                "description": "Average monthly revenue (6-month rolling)",
                "data_type": "DECIMAL",
                "version": "v1.0.0",
                "owner": "ML Team"
            },
            {
                "feature_name": "complaint_frequency",
                "feature_table": "customer_features",
                "description": "Tickets per day (90-day average)",
                "data_type": "DECIMAL",
                "version": "v1.0.0",
                "owner": "ML Team"
            }
        ]
    },
    "meta": { "total": 45 },
    "request_id": "req_xxx"
}
```

---

## 12.2 GET /features/{feature_name}

| Attribute | Value |
|-----------|-------|
| **Purpose** | Single feature detail with formula and data source |
| **Auth** | Required |

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "feature_name": "complaint_frequency",
        "feature_table": "customer_features",
        "description": "Average number of service tickets per day over the last 90 days",
        "formula": "AVG(fact_service.ticket_count) OVER (last 90 days per customer)",
        "data_source": "warehouse.fact_service",
        "data_type": "DECIMAL(6,4)",
        "refresh_cron": "0 2 * * *",
        "version": "v1.0.0",
        "owner": "ML Team",
        "is_deprecated": false
    },
    "meta": null,
    "request_id": "req_xxx"
}
```

---

# 13. System API

Base: `/api/v1/system`

## 13.1 GET /system/health

| Attribute | Value |
|-----------|-------|
| **Purpose** | Liveness/readiness check |
| **Auth** | None (public) |

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "status": "healthy",
        "version": "1.0.0",
        "uptime_seconds": 345600,
        "checks": {
            "database": "ok",
            "redis": "ok",
            "storage": "ok",
            "llm_provider": "ok"
        }
    },
    "meta": null,
    "request_id": "req_xxx"
}
```

---

## 13.2 GET /system/metrics

| Attribute | Value |
|-----------|-------|
| **Purpose** | Internal observability metrics (Prometheus-compatible) |
| **Auth** | Required |

**Response** `200`:

```json
{
    "success": true,
    "data": {
        "requests_total": 1250000,
        "requests_per_minute": 45.3,
        "avg_latency_ms": 320,
        "p95_latency_ms": 1200,
        "p99_latency_ms": 4500,
        "error_rate": 0.002,
        "ai_tokens_total": 8500000,
        "ai_workflows_total": 12500,
        "active_tasks": 3
    },
    "meta": null,
    "request_id": "req_xxx"
}
```

---

## 13.3 GET /system/tasks/{task_id}

| Attribute | Value |
|-----------|-------|
| **Purpose** | Poll async task status |
| **Auth** | Required |

**Response** `200` (task in progress):

```json
{
    "success": true,
    "data": {
        "task_id": "task_batch_pred_01J2X6M1N4Q8R3S5",
        "task_type": "batch_prediction",
        "status": "RUNNING",
        "progress_pct": 45,
        "started_at": "2026-08-01T10:00:00Z",
        "estimated_completion": "2026-08-01T10:10:00Z"
    },
    "meta": null,
    "request_id": "req_xxx"
}
```

**Response** `200` (task completed):

```json
{
    "success": true,
    "data": {
        "task_id": "task_batch_pred_01J2X6M1N4Q8R3S5",
        "task_type": "batch_prediction",
        "status": "COMPLETED",
        "progress_pct": 100,
        "started_at": "2026-08-01T10:00:00Z",
        "completed_at": "2026-08-01T10:08:30Z",
        "result": {
            "predictions_generated": 950000,
            "high_risk_count": 45000,
            "model_version": "churn_xgboost_v1.2.0"
        }
    },
    "meta": null,
    "request_id": "req_xxx"
}
```

**Task statuses**: `PENDING` → `RUNNING` → `COMPLETED` | `FAILED`

---

# 14. WebSocket

## 14.1 `/ws/copilot/{workflow_id}`

| Attribute | Value |
|-----------|-------|
| **Purpose** | Real-time streaming of AI Copilot progress |
| **Auth** | Required (token in query param: `?token=xxx`) |

**Server → Client messages**:

```json
{ "type": "agent_start", "agent": "planner", "timestamp": "..." }
{ "type": "agent_progress", "agent": "sql", "message": "Generating SQL...", "timestamp": "..." }
{ "type": "agent_complete", "agent": "sql", "latency_ms": 800, "timestamp": "..." }
{ "type": "finding", "data": { "title": "...", "confidence": 0.92 } }
{ "type": "decision", "data": { "recommendation": "...", "confidence": 0.87 } }
{ "type": "workflow_complete", "workflow_id": "...", "report_id": "..." }
{ "type": "error", "agent": "reviewer", "message": "Retrying... (attempt 2/3)" }
```

## 14.2 `/ws/tasks/{task_id}`

| Attribute | Value |
|-----------|-------|
| **Purpose** | Real-time async task progress |
| **Auth** | Required |

**Server → Client messages**:

```json
{ "type": "progress", "task_id": "...", "progress_pct": 45, "message": "Processing batch 45/100" }
{ "type": "complete", "task_id": "...", "result": { } }
{ "type": "error", "task_id": "...", "error": { "code": "ML_003", "message": "..." } }
```

---

# 15. Async Tasks

### Pattern

```
POST /api/v1/{resource}/{action}
    │
    ▼
202 Accepted
    {
        "task_id": "task_xxx",
        "status": "PENDING"
    }
    │
    ▼
Client polls:  GET /api/v1/system/tasks/{task_id}
    │
    ▼
Or WebSocket:  /ws/tasks/{task_id}
```

### Async Endpoints

| Endpoint | Task Type | Est. Duration |
|----------|-----------|---------------|
| `POST /churn/predict/batch` | `batch_prediction` | 5–30 min |
| `POST /reports/generate` | `report_generation` | 10–60 sec |
| (future) `POST /data/import` | `data_import` | 1–30 min |
| (future) `POST /models/train` | `model_training` | 5–60 min |
| (future) `POST /features/refresh` | `feature_refresh` | 1–5 min |

### Polling Best Practices

- Initial interval: 1 second
- Backoff: double after each poll, max 30 seconds
- Timeout: client should stop polling after 10× estimated duration
- WebSocket is preferred when available

---

# 16. API Versioning

### Current Version

All endpoints: `/api/v1/`

### Version Policy

| Action | Allowed in v1.x? |
|--------|:----------------:|
| Add new endpoint | ✅ |
| Add optional field to request | ✅ |
| Add optional field to response | ✅ |
| Add new error code | ✅ |
| Remove endpoint | ❌ (requires v2) |
| Rename field | ❌ (requires v2) |
| Change field type | ❌ (requires v2) |
| Remove field from response | ❌ (requires v2) |
| Change error code meaning | ❌ (requires v2) |

### Deprecation Process

```
v1 endpoint deprecated → Header "Sunset" added → 6-month grace period → Removed in v2
```

---

# 17. API Lifecycle

| Stage | Meaning | Header | Breaking Changes Allowed? |
|-------|---------|--------|:-------------------------:|
| `draft` | Internal development, not deployed | — | Yes |
| `experimental` | Deployed for beta testing | `X-API-Stage: experimental` | Yes |
| `stable` | Production-grade, contract frozen | — | No |
| `deprecated` | Scheduled for removal | `Sunset: <date>` | No |
| `removed` | No longer available | — | N/A |

---

# Document Freeze

This document freezes the **API contract** for InsightFlow Version 1.0.

From this point onward:

- Every API endpoint must match the schema, validation rules, and error codes defined here.
- Frontend code must consume these exact types (TypeScript mirrors frozen).
- Backend code must produce these exact responses (Pydantic models frozen).
- New endpoints added in v1.x must follow the same endpoint template and error code registry.
- Breaking changes require a new major version (`/api/v2/`) with a documented migration path.
- Async operations must use the `202 + task_id + polling` pattern — no blocking endpoints > 5 seconds.
