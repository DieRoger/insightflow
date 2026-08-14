# InsightFlow — Decision Tree

Version 1.0 · Purpose: Guide all contributors (human + AI) to put code in the right place.

---

## How to Use

Start at the top. Answer each question. Follow the branch. This tree covers **every code placement decision** in InsightFlow.

---

# 1. Backend Code Placement

```
I need to add new code to the backend.
        │
        ▼
Is it handling HTTP requests/responses?
        │
    YES ───► app/api/
        │    ├── Router logic only (validate → call service → return)
        │    ├── Use Depends() for service injection
        │    └── NEVER: business logic, SQL, model training
        │
    NO
        │
        ▼
Is it coordinating a workflow across multiple domain services?
        │
    YES ───► app/application/
        │    ├── One service class per use case
        │    ├── Constructor injection of repositories + domain services
        │    └── NEVER: raw SQL, HTTP calls, LLM calls directly
        │
    NO
        │
        ▼
Is it a business rule, entity, or domain concept?
        │
    YES ───► app/domain/
        │    ├── Entities → dataclasses (zero framework imports)
        │    ├── Value objects → dataclasses or Pydantic BaseModel
        │    ├── Domain services → stateless functions/methods
        │    ├── Interfaces → ABCs for repositories
        │    └── NEVER: import fastapi, sqlalchemy, redis, langgraph, celery
        │
    NO
        │
        ▼
Is it accessing a database, external API, file system, or LLM?
        │
    YES ───► app/infrastructure/
        │    ├── Repositories → implement domain interfaces
        │    ├── LLM adapters → implement LLMProvider ABC
        │    ├── Storage → MinIO, Redis clients
        │    └── NEVER: business rules, workflow orchestration
        │
    NO
        │
        ▼
Is it related to the AI Copilot (agents, prompts, workflows)?
        │
    YES ───► app/ai/
        │    ├── agents/ → one file per agent
        │    ├── prompts/ → versioned YAML files
        │    ├── workflow.py → LangGraph StateGraph
        │    └── NEVER: raw SQL execution, database access (use infrastructure)
        │
    NO
        │
        ▼
Is it data ingestion or ETL?
        │
    YES ───► app/warehouse/
        │    ├── validator.py → data quality rules
        │    ├── loader.py → Bronze → Silver loading
        │    └── NEVER: business metrics, KPI calculations
        │
    NO
        │
        ▼
Is it feature engineering or ML model code?
        │
    YES ───► app/feature_store/ (features) or app/ml/ (models)
        │    └── NEVER: expose directly to API layer
        │
    NO
        │
        ▼
Is it a Pydantic schema for API serialization?
        │
    YES ───► app/schemas/
        │    ├── {resource}_request.py
        │    ├── {resource}_response.py
        │    └── NEVER: business logic, database access
        │
    NO
        │
        ▼
Is it configuration, constants, or base exceptions?
        │
    YES ───► app/core/
        │    ├── config.py → pydantic-settings
        │    ├── exceptions.py → typed exception hierarchy
        │    └── constants.py → named constants (no magic numbers)
        │
    NO
        │
        ▼
    🤔 Ask in the PR. Something doesn't fit the architecture.
```

---

# 2. Frontend Code Placement

```
I need to add new code to the frontend.
        │
        ▼
Is it a full page (a route)?
        │
    YES ───► app/(dashboard)/{route}/page.tsx
        │    ├── Imports feature components from features/
        │    └── NEVER: business logic, KPI calculations
        │
    NO
        │
        ▼
Is it a reusable component used by multiple features?
        │
    YES ───► components/
        │    ├── ui/ → shadcn/ui primitives (Button, Card)
        │    ├── charts/ → ECharts wrappers (LineChart, BarChart)
        │    ├── tables/ → DataTable (TanStack Table)
        │    ├── layout/ → Sidebar, Header, Shell
        │    └── shared/ → MetricCard, ConfidenceBadge, EvidenceCard
        │
    NO
        │
        ▼
Is it specific to one feature/page?
        │
    YES ───► features/{feature}/
        │    ├── components/ → feature-specific components
        │    ├── hooks/ → feature-specific hooks
        │    ├── types.ts → feature-specific types
        │    └── NEVER: import from other feature folders
        │
    NO
        │
        ▼
Is it an API call wrapper?
        │
    YES ───► services/{resource}.ts
        │    └── NEVER: call fetch() or axios directly in components
        │
    NO
        │
        ▼
Is it global UI state (sidebar, theme)?
        │
    YES ───► stores/ (Zustand)
        │    └── NEVER: duplicate server data here (use TanStack Query)
        │
    NO
        │
        ▼
Is it a shared TypeScript type?
        │
    YES ───► types/
        │
    NO
        │
        ▼
Is it a utility function?
        │
    YES ───► lib/
        │
    NO
        │
        ▼
    🤔 Ask in the PR.
```

---

# 3. Database Decision Tree

```
I need to add or change a database table/column.
        │
        ▼
Is this raw source data?
        │
    YES ───► schema: raw
        │    ├── Name: raw_{source}
        │    ├── Append-only (no UPDATE/DELETE)
        │    └── Include: import_batch_id, imported_at, source_filename
        │
    NO
        │
        ▼
Is this cleaned, normalized analytical data?
        │
    YES ───► schema: warehouse
        │    ├── Fact tables: fact_{entity}
        │    ├── Dimension tables: dim_{entity}
        │    ├── Use surrogate integer PKs
        │    └── FK references to dimension tables
        │
    NO
        │
        ▼
Is this an ML feature?
        │
    YES ───► schema: feature_store
        │    ├── Tables: customer_features, churn_features, package_features
        │    ├── Every feature must have a registry entry
        │    └── NEVER: accessed by analytics or dashboard
        │
    NO
        │
        ▼
Is this a pre-computed KPI for dashboards?
        │
    YES ───► schema: semantic
        │    ├── Materialized views: kpi_{name}
        │    ├── Always has UNIQUE index for CONCURRENT refresh
        │    └── NEVER: write raw SQL against semantic views in services
        │
    NO
        │
        ▼
Is this ML metadata (models, predictions)?
        │
    YES ───► schema: ml
        │    ├── Tables: model_registry, prediction_registry
        │    └── NEVER: business logic in these tables
        │
    NO
        │
        ▼
    🤔 Does it need a new schema? Write an ADR.
```

---

# 4. AI Agent Decision Tree

```
I need to add or modify an AI Agent.
        │
        ▼
Does a new agent type need to be created?
        │
    YES ───► Check 08_ARCHITECTURE_RULES.md AR-044 first.
        │    ├── Must be a single, well-defined responsibility
        │    ├── Must communicate via typed objects (no raw prompt passing)
        │    ├── Must implement Agent[TInput, TOutput] contract
        │    └── Requires ADR if adding a new agent to the DAG
        │
    NO
        │
        ▼
Is it a prompt change?
        │
    YES ───► app/ai/prompts/{agent}/v{N}__{description}.yaml
        │    ├── Bump version number
        │    ├── Run prompt regression tests
        │    ├── Compare evaluation scores with previous version
        │    └── NEVER: deploy without evaluation
        │
    NO
        │
        ▼
Is it a new evaluation metric or test case?
        │
    YES ───► tests/ai/golden/{agent}/
        │    ├── Add case_NNN_question.txt + case_NNN_expected.json
        │    └── Run pytest tests/ai/test_prompts/ to verify
        │
    NO
        │
        ▼
Is it a guardrail or safety change?
        │
    YES ───► app/ai/guardrails.py
        │    ├── InputGuardrail: user input sanitization
        │    ├── OutputGuardrail: schema validation + hallucination check
        │    ├── PIIFilter: strip sensitive data before LLM
        │    └── NEVER: weaken security without ADR
        │
    NO
        │
        ▼
    🤔 Check 07_AI_DESIGN.md for existing agent specs.
```

---

# 5. When to Write an ADR

```
I'm about to make a decision.
        │
        ▼
Does it violate an L0 or L1 rule in 08_ARCHITECTURE_RULES.md?
        │
    YES ───► ADR REQUIRED. Use 13_ADR/TEMPLATE.md.
        │
    NO
        │
        ▼
Does it change a Frozen document (00–12)?
        │
    YES ───► ADR REQUIRED.
        │
    NO
        │
        ▼
Does it introduce a new technology, library, or pattern?
        │
    YES ───► ADR RECOMMENDED. Document: Context, Alternatives, Trade-offs.
        │
    NO
        │
        ▼
Does it affect multiple modules or teams?
        │
    YES ───► ADR RECOMMENDED.
        │
    NO
        │
        ▼
    ✅ Proceed. No ADR needed.
```

---

# 6. Quick Reference: "I want to..."

| I want to... | Go to... | Create file... |
|-------------|----------|----------------|
| Add a new API endpoint | `app/api/routers/` | `{resource}.py` |
| Add business logic | `app/domain/{module}/` | `service.py` |
| Add a database query | `app/infrastructure/repositories/` | `{entity}_repository.py` |
| Add an AI prompt | `app/ai/prompts/{agent}/` | `v{N}__{desc}.yaml` |
| Add a frontend page | `app/(dashboard)/{route}/` | `page.tsx` |
| Add a reusable component | `components/shared/` | `{Name}.tsx` |
| Add a feature component | `features/{feature}/components/` | `{Name}.tsx` |
| Add an API client | `services/` | `{resource}.ts` |
| Add a test | `tests/{unit\|integration\|api\|ai}/` | `test_{name}.py` |
| Add a migration | `alembic/versions/` | `{timestamp}_{desc}.py` |
