# ADR-000: Architecture Freeze — Foundational Decisions

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-08-04 |
| **Author** | System Architect |
| **Affected Rules** | All |
| **Supersedes** | — |
| **Superseded By** | — |

---

## Context

InsightFlow is an AI-Native Telecom Decision Intelligence Platform. Before any code is written, the architecture must be frozen to provide a stable foundation for all subsequent development. This ADR records the foundational architectural decisions and their rationale.

---

## Decisions

### D-001: Clean Architecture (Layered)

**Decision**: Adopt a strict 4-layer architecture: API → Application → Domain ← Infrastructure.

**Why**:
- Domain independence enables unit testing business logic without frameworks
- Infrastructure layer can be swapped (e.g., PostgreSQL → ClickHouse) without touching business logic
- AI coding assistants have clear rules: "domain never imports fastapi"

**Alternatives considered**:
- Django MVC: Tight coupling between ORM and business logic. Rejected — incompatible with AI-native async patterns.
- Hexagonal Architecture: Over-engineered for MVP team size. Clean Architecture captures the essential insight (dependency inversion) with less ceremony.

### D-002: Star Schema for Warehouse

**Decision**: Adopt dimensional modeling (Star Schema) with fact and dimension tables.

**Why**:
- Telecom analytics is inherently multidimensional (region × time × package × segment)
- Star Schema queries are simple, fast, and understandable by analysts
- BI tools and AI Copilot can auto-discover dimensions
- Avoids snowflake complexity for MVP

**Alternatives considered**:
- Normalized (3NF): Optimal for writes, terrible for analytical queries. Rejected — InsightFlow is read-heavy.
- Data Vault: Excellent for auditability but requires specialized tooling. Rejected — over-engineered for MVP.

### D-003: LangGraph for AI Copilot Orchestration

**Decision**: Use LangGraph's StateGraph for the 7-agent DAG workflow.

**Why**:
- Built-in state management across agent nodes
- Native checkpointing for workflow traceability and debugging
- Conditional edges for Reviewer retry logic
- Framework-agnostic contract — agents communicate via typed objects, not LangGraph internals
- Can migrate to custom DAG if LangGraph becomes a bottleneck

**Alternatives considered**:
- Custom DAG (hand-rolled): Full control but requires building state management, checkpointing, and observability from scratch. Rejected — reinventing the wheel.
- LangChain Chains: Linear workflows only, no branching. Rejected — Reviewer needs conditional edges.

### D-004: PostgreSQL + DuckDB (Not ClickHouse)

**Decision**: Use PostgreSQL for OLTP + warehouse, DuckDB for local analytical queries. Defer ClickHouse to Phase 3.

**Why**:
- PostgreSQL is the team's operational database — single technology for OLTP and warehouse reduces MVP complexity
- DuckDB provides columnar analytics embedded in Python — no separate server
- 1M customers × 100M records fits comfortably in PostgreSQL with proper indexing
- ClickHouse requires separate operational knowledge, backup strategy, and monitoring

**Alternatives considered**:
- ClickHouse from day 1: Superior analytical performance but adds a second database to manage. Rejected for MVP — migrate when data exceeds PostgreSQL's comfortable range.
- Snowflake/BigQuery: Cloud-only, cost-prohibitive for MVP. Rejected.

### D-005: Repository Pattern

**Decision**: All database access goes through Repository interfaces defined in the domain layer.

**Why**:
- Domain layer defines what data it needs (interface); infrastructure provides how (implementation)
- Swapping PostgreSQL for any other database requires changing repository implementations only
- AI coding assistants have a clear rule: "never write SQL in services"

**Alternatives considered**:
- Active Record (Django ORM style): Models carry their own persistence. Rejected — couples domain to ORM, impossible to unit test without database.
- Raw SQL everywhere: Maximum performance, zero abstraction. Rejected — unmaintainable at scale.

### D-006: Evidence-First AI

**Decision**: Every AI-generated conclusion must reference retrieved evidence. No free-form LLM text without data anchors.

**Why**:
- Telecom executives will not trust AI recommendations without proof
- Evidence anchoring is the primary hallucination mitigation strategy
- Every finding is auditable: "show me the SQL that produced this number"
- Differentiates InsightFlow from generic chatbot products

**Alternatives considered**:
- Free-form LLM responses: Faster to implement but untrustworthy. Rejected — violates product philosophy.
- RAG-only (no structured analytics): Evidence is unstructured text, not metrics. Rejected — cannot answer "what is the ARPU in East Region?"

---

## Trade-offs

| Positive | Negative |
|----------|----------|
| Strict layering prevents architecture erosion | More files/boilerplate than a simple script |
| Repository Pattern enables testing without DB | Additional abstraction layer to maintain |
| Star Schema makes analytics fast and understandable | ETL must transform normalized source data into dimensional model |
| LangGraph provides checkpointing and observability | Framework dependency (mitigated by agent-level contract abstraction) |
| Evidence-first AI builds user trust | Slower response times (must retrieve evidence before generating language) |

---

## Consequences

### Immediate
- All contributors must follow the layered architecture — no shortcuts
- Every new module must go through the Decision Tree (15_DECISION_TREE.md)
- AI-generated code must pass `scripts/check_architecture.py`

### Long-term
- Architecture supports microservice extraction (modules → independent services)
- Database migration path to ClickHouse is architecturally clean (Repository Pattern isolates storage)
- Prompt changes are safe (versioned + regression-tested)
- Evidence chain enables SOC 2 / ISO 27001 audit compliance

---

## Approval

- [x] System Architect
- [x] Tech Lead
