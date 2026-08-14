# InsightFlow — AI Agent Design

Version 1.0 · Status: **Frozen** · Target: AI/ML Engineers + AI Coding Assistants

---

## Table of Contents

1. [Design Overview](#1-design-overview)
2. [Agent Registry](#2-agent-registry)
3. [Agent: Query Planner](#3-agent-query-planner)
4. [Agent: SQL Generator](#4-agent-sql-generator)
5. [Agent: Analytics](#5-agent-analytics)
6. [Agent: Evidence Retrieval](#6-agent-evidence-retrieval)
7. [Agent: Decision Intelligence](#7-agent-decision-intelligence)
8. [Agent: Report Writer](#8-agent-report-writer)
9. [Agent: Reviewer](#9-agent-reviewer)
10. [Workflow Engine (LangGraph)](#10-workflow-engine-langgraph)
11. [LLM Provider Abstraction](#11-llm-provider-abstraction)
12. [Prompt Registry](#12-prompt-registry)
13. [Evaluation Framework](#13-evaluation-framework)
14. [Context Assembly](#14-context-assembly)
15. [Safety & Guardrails](#15-safety--guardrails)

---

# 1. Design Overview

## 1.1 Agent Topology

```
User Question
      │
      ▼
┌─────────────┐
│   Planner   │  ← Understands intent, builds execution plan
└──────┬──────┘
       │
       ├──────────────────┐
       ▼                  ▼
┌──────────┐      ┌──────────────┐
│SQL Agent │      │Evidence Retr.│  ← These two run IN PARALLEL
└────┬─────┘      └──────┬───────┘
     │                   │
     ▼                   │
┌──────────────┐         │
│Analytics Agt.│         │
└──────┬───────┘         │
       │                 │
       └─────────┬───────┘
                 ▼
       ┌─────────────────┐
       │Decision Intel.  │  ← Synthesizes insights + evidence + ML
       └────────┬────────┘
                ▼
       ┌─────────────────┐
       │ Report Writer   │
       └────────┬────────┘
                ▼
       ┌─────────────────┐
       │   Reviewer      │  ← Validates before delivery
       └────────┬────────┘
                │
        ┌───────┴───────┐
        ▼               ▼
    PASS (deliver)   FAIL (retry ≤3×)
```

## 1.2 Agent Contract

Every agent implements this interface:

```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from pydantic import BaseModel

TInput = TypeVar("TInput", bound=BaseModel)
TOutput = TypeVar("TOutput", bound=BaseModel)

class AgentTrace(BaseModel):
    execution_id: str
    agent_name: str
    started_at: str       # ISO 8601
    completed_at: str
    latency_ms: int
    input_summary: str
    output_summary: str
    prompt_version: str
    model: str
    token_usage: dict     # { "prompt": int, "completion": int }
    retry_count: int
    error: str | None

class AgentResult(BaseModel, Generic[TOutput]):
    data: TOutput | None
    trace: AgentTrace
    success: bool
    error: str | None

class Agent(ABC, Generic[TInput, TOutput]):
    """Base contract for every AI Agent in InsightFlow."""

    agent_name: str
    prompt_version: str
    model: str            # "gpt-4o" | "deepseek-v3" | "qwen-max"
    max_retries: int = 1
    token_budget: int     # Max total tokens per call

    @abstractmethod
    async def execute(
        self,
        input_data: TInput,
        context: "WorkflowContext",
    ) -> AgentResult[TOutput]:
        """Execute this agent's task. Must record full trace."""
        ...

    @abstractmethod
    def input_schema(self) -> type[BaseModel]: ...

    @abstractmethod
    def output_schema(self) -> type[BaseModel]: ...
```

---

# 2. Agent Registry

| Agent | Input | Output | Model | Token Budget | Max Latency |
|-------|-------|--------|-------|:------------:|:-----------:|
| Planner | `str` (user question) | `AnalysisPlan` | gpt-4o | 2,000 | 3s |
| SQL Generator | `AnalysisPlan` | `SQLResult` | gpt-4o | 3,000 | 5s |
| Analytics | `SQLResult` | `list[Insight]` | gpt-4o-mini | 2,000 | 3s |
| Evidence Retrieval | `AnalysisPlan` | `list[Evidence]` | — (no LLM) | 0 | 2s |
| Decision Intelligence | `list[Insight]` + `list[Evidence]` | `Decision` | gpt-4o | 4,000 | 5s |
| Report Writer | `Decision` | `Report` | gpt-4o | 6,000 | 8s |
| Reviewer | `Report` | `ReviewResult` | gpt-4o-mini | 2,000 | 3s |

**Total Token Budget per workflow**: ~19,000 tokens (worst case with retries: ~35,000)

---

# 3. Agent: Query Planner

### Responsibility

Convert natural language into a structured execution plan. The Planner **understands intent** but **never generates SQL** or computes metrics.

### Input

```python
class PlannerInput(BaseModel):
    question: str                    # Raw user question
    context: CopilotContext | None   # Optional: region, time_range filters
```

### Output

```python
class AnalysisStep(BaseModel):
    step_id: str                     # "step_001"
    description: str                 # "Calculate churn rate for East Region"
    required_metrics: list[str]      # ["churn_rate"]
    required_dimensions: list[str]   # ["region", "month"]
    agent: str                       # "sql" | "evidence" | "analytics"

class AnalysisPlan(BaseModel):
    intent: str                      # "churn_root_cause_analysis" | "kpi_trend" | ...
    summary: str                     # 1-sentence: "Analyze churn increase in East Region"
    steps: list[AnalysisStep]
    expected_output_type: str        # "insight" | "report" | "prediction"
    confidence: float                # Planner's confidence in this plan
```

### Prompt Design

```yaml
# Version: v2__plan_generation
system: |
  You are a telecom analytics planner. Your job is to convert business questions
  into structured analysis plans. You do NOT generate SQL or compute metrics.

  Available metrics (from Metric Registry):
  {metric_definitions}

  Available dimensions:
  {dimensions}

  Rules:
  1. Identify the business intent first (churn analysis, revenue analysis, etc.)
  2. List the specific metrics needed to answer the question.
  3. Specify dimensions to slice by (region, segment, time, package).
  4. Break complex questions into sequential steps.
  5. If the question is ambiguous, make reasonable assumptions and note them.
  6. If the question cannot be answered with available metrics, say so.

user: |
  Question: {question}
  Context filters: {context}

  Return a JSON AnalysisPlan with intent, summary, steps, and confidence.
```

### Evaluation

| Metric | Target | How Measured |
|--------|:------:|-------------|
| Intent accuracy | ≥ 0.90 | Compare against golden labeled intents |
| Metric selection precision | ≥ 0.85 | Selected metrics ⊆ required metrics / selected metrics |
| Metric selection recall | ≥ 0.90 | Selected metrics ∩ required / required metrics |
| Plan completeness | ≥ 0.90 | All necessary analysis steps identified |

### Retry & Failure

| Scenario | Behavior |
|----------|----------|
| LLM timeout (>3s) | Retry 1× with same prompt |
| Output fails schema validation | Retry 1× with validation error in prompt |
| Both retries exhausted | Return error to user: "Unable to understand your question. Please rephrase." |
| Confidence < 0.6 | Include in output but flag: `low_confidence: true` |

### Token Budget

| Item | Budget |
|------|:------:|
| System prompt | ~600 tokens |
| Metric definitions | ~500 tokens |
| User question + context | ~200 tokens |
| **Total input** | **~1,300 tokens** |
| Expected output | ~300 tokens |
| **Total** | **~1,600 / 2,000 budget** |

---

# 4. Agent: SQL Generator

### Responsibility

Generate parameterized, read-only SQL from an `AnalysisPlan`. This agent is **the most security-critical** — its output must be sandboxed before execution.

### Input

```python
class SQLGeneratorInput(BaseModel):
    analysis_step: AnalysisStep
    table_schema: str                # Relevant table DDL (from information_schema)
    metric_definitions: str          # Relevant metric formulas
    user_question: str               # Original question (for context)
```

### Output

```python
class SQLResult(BaseModel):
    sql: str                         # Parameterized SELECT statement
    tables_used: list[str]           # ["fact_billing", "dim_customer"]
    parameters: dict[str, str]       # {"$1": "2026-07-01", "$2": "East"}
    explanation: str                 # Human-readable: "This query calculates..."
    confidence: float
    is_safe: bool                    # Set by SQL Sandbox AFTER generation
```

### Prompt Design

```yaml
# Version: v1__sql_generation
system: |
  You are a SQL generator for a telecom analytics platform.
  
  CRITICAL RULES:
  - Generate ONLY SELECT statements.
  - NEVER produce: INSERT, UPDATE, DELETE, DROP, TRUNCATE, ALTER, CREATE, GRANT, REVOKE, EXEC.
  - Use parameterized placeholders ($1, $2, ...) for all literal values.
  - Validate every column name against the provided schema.
  - If a requested metric cannot be computed from available tables, return an error explanation.
  - Use explicit column names, never SELECT *.
  - Include table aliases for readability.

  Available tables:
  {table_schema}

  Metric definitions:
  {metric_definitions}

user: |
  Analysis step: {step_description}
  Required metrics: {required_metrics}
  Dimensions: {required_dimensions}
  Original question: {user_question}

  Return JSON with: sql, tables_used, parameters, explanation, confidence.
```

### SQL Sandbox (Post-Generation Gate)

```python
FORBIDDEN_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE",
    "ALTER", "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
    "MERGE", "REPLACE", "LOAD", "IMPORT",
]

def validate_sql(sql: str) -> tuple[bool, str | None]:
    """
    Returns (is_safe, error_message).
    Must pass before ANY AI-generated SQL touches the database.
    """
    upper = sql.upper()

    # Check forbidden keywords
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf'\b{keyword}\b', upper):
            return False, f"Forbidden keyword detected: {keyword}"

    # Must be a SELECT statement
    if not upper.strip().startswith("SELECT"):
        return False, "SQL must start with SELECT"

    # Basic syntax: must contain FROM
    if "FROM" not in upper:
        return False, "SQL must contain FROM clause"

    # Parameterized check: warn if hardcoded values look suspicious
    if re.search(r"'\d{4}-\d{2}-\d{2}'", sql):  # Hardcoded date literal
        logger.warning("SQL contains hardcoded date literal")

    return True, None
```

### Evaluation

| Metric | Target | How Measured |
|--------|:------:|-------------|
| SQL validity (parses) | ≥ 0.98 | `sqlparse` or PostgreSQL `EXPLAIN` (dry-run) |
| Sandbox pass rate | 1.00 | MUST be 100% — zero tolerance |
| Metric alignment | ≥ 0.90 | Generated SQL computes the correct metric |
| Execution time | < 2s | Run against test database |

### Retry & Failure

| Scenario | Behavior |
|----------|----------|
| Sandbox rejection | **Do NOT retry** — return error immediately. This is a security gate, not a quality issue. |
| SQL parse error | Retry 1× with error message in prompt |
| Execution timeout (>2s) | Retry 1× with query optimization hint |
| Both retries exhausted | Return error: "Could not generate a valid query." |

### Token Budget

| Item | Budget |
|------|:------:|
| System prompt | ~400 tokens |
| Table schema | ~1,000 tokens |
| Metric definitions | ~600 tokens |
| User context | ~300 tokens |
| **Total input** | **~2,300 tokens** |
| Expected output | ~400 tokens |
| **Total** | **~2,700 / 3,000 budget** |

---

# 5. Agent: Analytics

### Responsibility

Transform raw SQL query results into structured `Insight` objects. Performs **statistical calculations only** — never interprets business meaning.

### Input

```python
class AnalyticsInput(BaseModel):
    sql_result: SQLResult
    query_output: list[dict]          # Actual rows from database
    metric_definitions: str
    analysis_step: AnalysisStep
```

### Output

```python
class Insight(BaseModel):
    insight_id: str
    metric: str
    dimension: str | None
    title: str
    value: float | None
    baseline: float | None
    change_rate: float | None
    trend: str | None                # "up" | "down" | "stable"
    evidence: list[EvidenceItem]
    confidence: float
    timestamp: str

class AnalyticsOutput(BaseModel):
    insights: list[Insight]
    summary: str                      # 1-2 sentence statistical summary
```

### Prompt Design

```yaml
# Version: v1__analytics_agent
system: |
  You are a statistical analytics agent. Your job is to transform database query
  results into structured Insight objects.

  Rules:
  1. Calculate change rates, trends, and baselines from the data.
  2. Identify notable patterns (spikes, dips, plateaus).
  3. Compute confidence based on sample size and variance.
  4. NEVER interpret business meaning — that's the Decision Agent's job.
  5. NEVER hallucinate values not present in the query results.
  6. If the query returned empty results, report that honestly.

user: |
  Metric: {metric_name}
  Query results (first 50 rows): {query_output}
  Analysis step: {step_description}

  Return JSON with insights array and statistical summary.
```

### Evaluation

| Metric | Target | How Measured |
|--------|:------:|-------------|
| Insight extraction rate | ≥ 0.90 | Insights generated / expected insights |
| Value accuracy | ≥ 0.98 | Computed values match ground truth from raw data |
| Confidence calibration | ≤ 0.10 | |predicted_confidence - actual_accuracy| |

### Retry & Failure

| Scenario | Behavior |
|----------|----------|
| Empty query results | Return empty insights list + "No data available for this analysis" |
| Schema validation failure | Retry 1× |
| LLM timeout | Retry 1× |

### Token Budget

| Item | Budget |
|------|:------:|
| System prompt | ~300 tokens |
| Query results (truncated to 50 rows) | ~800 tokens |
| Metric definitions | ~400 tokens |
| **Total input** | **~1,500 tokens** |
| Expected output | ~300 tokens |
| **Total** | **~1,800 / 2,000 budget** |

---

# 6. Agent: Evidence Retrieval

### Responsibility

Collect supporting evidence from the warehouse, feature store, and model registry. **This agent does NOT call an LLM** — it is a deterministic data retrieval service.

### Input

```python
class EvidenceRetrievalInput(BaseModel):
    analysis_plan: AnalysisPlan
    metrics: list[str]
    dimensions: list[str]
    time_range: TimeRange | None
```

### Output

```python
class EvidenceItem(BaseModel):
    source_table: str
    description: str
    metric: str | None
    sql: str | None
    sample_size: int | None
    confidence: float
    generated_at: str

class EvidenceRetrievalOutput(BaseModel):
    evidence_items: list[EvidenceItem]
    total_sources: int
```

### Implementation (No LLM)

```python
class EvidenceRetrievalAgent:
    """Deterministic agent — no LLM calls."""

    def __init__(
        self,
        warehouse_repo: WarehouseRepository,
        feature_store: FeatureStoreRepository,
        model_registry: ModelRegistryRepository,
        metric_registry: MetricRegistryRepository,
    ):
        self.warehouse = warehouse_repo
        self.feature_store = feature_store
        self.model_registry = model_registry
        self.metric_registry = metric_registry

    async def execute(
        self,
        input_data: EvidenceRetrievalInput,
        context: WorkflowContext,
    ) -> AgentResult[EvidenceRetrievalOutput]:
        evidence = []

        # 1. Metric definitions
        for metric_name in input_data.metrics:
            metric_def = await self.metric_registry.get(metric_name)
            if metric_def:
                evidence.append(EvidenceItem(
                    source_table=metric_def.data_source,
                    description=f"Metric definition: {metric_def.business_definition}",
                    metric=metric_name,
                    sample_size=None,
                    confidence=1.0,
                    generated_at=now_iso(),
                ))

        # 2. Recent KPI values
        for metric_name in input_data.metrics:
            kpi_data = await self.warehouse.get_recent_kpi(
                metric_name, input_data.time_range
            )
            if kpi_data:
                evidence.append(EvidenceItem(
                    source_table="semantic.kpi_*",
                    description=f"Recent {metric_name} values: {kpi_data}",
                    metric=metric_name,
                    sample_size=kpi_data.get("sample_size"),
                    confidence=0.95,
                    generated_at=now_iso(),
                ))

        # 3. Feature store snapshots (if relevant)
        # 4. Model explanations (if ML predictions involved)

        return AgentResult(
            data=EvidenceRetrievalOutput(
                evidence_items=evidence,
                total_sources=len(evidence),
            ),
            trace=...,
            success=True,
        )
```

### Retry & Failure

| Scenario | Behavior |
|----------|----------|
| Database unavailable | Retry 1×, then return partial evidence with warning |
| Metric not found | Skip that metric, continue |
| All sources failed | Return empty evidence + "Evidence retrieval failed" warning |

---

# 7. Agent: Decision Intelligence

### Responsibility

Synthesize analytics insights, evidence, and ML predictions into business decisions. This is where **interpretation** happens — the Decision Agent answers "so what?"

### Input

```python
class DecisionInput(BaseModel):
    insights: list[Insight]
    evidence: list[EvidenceItem]
    ml_predictions: dict | None       # Optional: churn predictions, segment data
    user_question: str
    business_context: str | None      # Optional: "Q3 retention is a company priority"
```

### Output

```python
class Decision(BaseModel):
    decision_id: str
    finding: str                      # "Premium customer churn increased 23% in East Region"
    business_impact: str              # "Estimated annual revenue loss: $1.8M"
    impact_confidence: float
    recommendation: str               # "Prioritize network optimization in East Region"
    expected_outcome: str             # "3-5% churn reduction within 60 days"
    confidence: float                 # Overall decision confidence
    supporting_evidence: list[str]    # References to evidence IDs
    risk_if_ignored: str              # "Continued churn at current rate → $2.5M annual loss"
    alternative_actions: list[str]    # ["Launch retention campaign", "Offer discount to at-risk"]
```

### Prompt Design

```yaml
# Version: v1__decision_synthesis
system: |
  You are a telecom business decision intelligence agent. You transform analytical
  findings into actionable business recommendations.

  Rules:
  1. Every finding MUST reference specific evidence (cite evidence IDs).
  2. Every recommendation MUST estimate business impact.
  3. If evidence is insufficient, say so — do not fabricate confidence.
  4. Present alternatives when multiple strategies are viable.
  5. Quantify impact in business terms (revenue, churn rate, customer count).
  6. Always include "risk if ignored" to create urgency for action.
  7. Confidence below 0.6 → flag as "Low confidence — human review required."

user: |
  User question: {user_question}
  Business context: {business_context}

  Insights:
  {insights}

  Evidence:
  {evidence}

  ML predictions:
  {ml_predictions}

  Return JSON Decision with finding, business_impact, recommendation, expected_outcome,
  confidence, supporting_evidence, risk_if_ignored, alternative_actions.
```

### Evaluation

| Metric | Target | How Measured |
|--------|:------:|-------------|
| Evidence alignment | ≥ 0.85 | Every claim references ≥ 1 evidence item |
| Impact reasonableness | ≥ 0.80 | Estimated impact within ±30% of ground truth |
| Recommendation relevance | ≥ 0.85 | Recommendation addresses the root cause identified in insights |
| Hallucination rate | ≤ 0.02 | Claims not supported by input data |

### Retry & Failure

| Scenario | Behavior |
|----------|----------|
| Insufficient evidence (< 2 sources) | Flag low confidence, still produce decision |
| LLM timeout | Retry 1× |
| Confidence < 0.6 | Include in output, flag for human review |
| Reviewer rejection (later stage) | Retry with reviewer feedback (max 3× total) |

### Token Budget

| Item | Budget |
|------|:------:|
| System prompt | ~400 tokens |
| Insights (up to 5) | ~800 tokens |
| Evidence (up to 10 items) | ~1,200 tokens |
| ML predictions | ~300 tokens |
| User context | ~200 tokens |
| **Total input** | **~2,900 tokens** |
| Expected output | ~500 tokens |
| **Total** | **~3,400 / 4,000 budget** |

---

# 8. Agent: Report Writer

### Responsibility

Transform a `Decision` into a structured, human-readable business report in Markdown format. PDF rendering is a post-processing step, not part of this agent.

### Input

```python
class WriterInput(BaseModel):
    decision: Decision
    insights: list[Insight]
    evidence: list[EvidenceItem]
    report_type: str                 # "executive" | "weekly" | "monthly" | "daily"
    target_audience: str             # "executive" | "analyst" | "marketing"
    include_charts: bool             # Whether to include chart references
```

### Output

```python
class ReportSection(BaseModel):
    section_id: str
    title: str
    content_markdown: str
    evidence_refs: list[str]
    confidence: float

class Report(BaseModel):
    report_id: str
    title: str
    report_type: str
    generated_at: str
    sections: list[ReportSection]
    executive_summary: str
    total_evidence_count: int
    overall_confidence: float
    review_required: bool
```

### Prompt Design

```yaml
# Version: v1__report_generation
system: |
  You are a business report writer for telecom executives. You transform analytical
  decisions into clear, structured reports.

  Rules:
  1. Start with an executive summary (3–4 sentences max).
  2. Each section must reference specific evidence (cite in footnotes).
  3. Use business language, not technical jargon.
  4. Every claim in the report must be traceable to evidence.
  5. Never invent facts, metrics, or customer data.
  6. Use bullet points for findings, numbered steps for recommendations.
  7. Include a "Confidence Assessment" section explaining uncertainty.

user: |
  Report type: {report_type}
  Target audience: {target_audience}

  Key Decision:
  {decision}

  Supporting Insights:
  {insights}

  Evidence:
  {evidence}

  Return JSON Report with sections and executive_summary.
```

### Evaluation

| Metric | Target | How Measured |
|--------|:------:|-------------|
| Evidence citation rate | 1.00 | Every claim must cite evidence |
| Hallucination rate | ≤ 0.01 | Claims not in source data |
| Readability (Flesch-Kincaid) | Grade 8–12 | Appropriate for business audience |
| Completeness | ≥ 0.90 | All required sections present |

### Retry & Failure

| Scenario | Behavior |
|----------|----------|
| Schema validation failure | Retry 1× |
| Missing required section | Retry 1× with missing section highlighted |
| LLM timeout (>8s) | Retry 1×, then return partial report |

### Token Budget

| Item | Budget |
|------|:------:|
| System prompt | ~400 tokens |
| Decision + Insights + Evidence | ~3,000 tokens |
| **Total input** | **~3,400 tokens** |
| Expected output | ~1,500 tokens (full report) |
| **Total** | **~4,900 / 6,000 budget** |

---

# 9. Agent: Reviewer

### Responsibility

Validate the Report before delivery. Checks for evidence completeness, logical consistency, and confidence thresholds. This is the **last line of defense** before the user sees AI output.

### Input

```python
class ReviewerInput(BaseModel):
    report: Report
    decision: Decision
    insights: list[Insight]
    evidence: list[EvidenceItem]
    retry_count: int                 # Current retry (0, 1, 2, 3)
```

### Output

```python
class ReviewResult(BaseModel):
    passed: bool
    checks: list[ReviewCheck]
    feedback: str | None             # If failed: what needs to change
    overridden: bool                 # True if retry_count >= 3 and we force through
    override_reason: str | None

class ReviewCheck(BaseModel):
    check_name: str                  # "evidence_completeness", "logical_consistency", ...
    passed: bool
    score: float                     # 0.0–1.0
    detail: str
```

### Review Checks

| Check | Description | Threshold | Action on Failure |
|-------|-------------|:---------:|-------------------|
| **Evidence Completeness** | Every claim has ≥ 1 evidence reference | 100% | Return to Writer with missing citations |
| **Logical Consistency** | Findings don't contradict each other | ≥ 0.90 | Return to Decision Agent |
| **Confidence Threshold** | Overall confidence ≥ 0.6 | ≥ 0.60 | Flag as low confidence, still deliver |
| **Metric Consistency** | KPI values match Metric Registry | 100% | Return to Analytics Agent |
| **Citation Validity** | All evidence references exist | 100% | Return to Evidence Retrieval |
| **Schema Compliance** | Report structure matches schema | 100% | Return to Writer |

### Prompt Design

```yaml
# Version: v1__output_validation
system: |
  You are a quality assurance reviewer for AI-generated telecom reports.
  Your job is to find problems, not to be nice.

  Rules:
  1. Check that every factual claim has supporting evidence.
  2. Check for logical contradictions between findings.
  3. Flag any metric value that seems implausible.
  4. Verify that confidence scores are consistent with the quality of evidence.
  5. Be strict — false positives (flagging real issues) are better than false negatives.
  6. If retry_count >= 3, relax standards and pass with override=true.

user: |
  Retry count: {retry_count} (max 3)

  Report:
  {report}

  Decision:
  {decision}

  Insights:
  {insights}

  Evidence:
  {evidence}

  Return JSON ReviewResult with checks array, passed, feedback, overridden.
```

### Retry & Failure

| Scenario | Behavior |
|----------|----------|
| Review fails, retry_count < 3 | Return workflow to Writer or Decision Agent with feedback |
| Review fails, retry_count == 3 | **Force through**: `passed=false, overridden=true` |
| LLM timeout | Retry 1×, then force through with override |

### Override Path

```
retry_count >= MAX_REVIEW_RETRIES (3)
    │
    ▼
Report delivered with:
    ├── review_override: true
    ├── overall_confidence: min(original, 0.5)
    └── Warning in UI: "⚠️ This analysis was auto-published after 3 review attempts.
         Confidence may be lower than indicated. Please verify key findings."
```

### Token Budget

| Item | Budget |
|------|:------:|
| System prompt | ~300 tokens |
| Report + Decision + Insights + Evidence | ~4,000 tokens |
| **Total input** | **~4,300 tokens** |
| Expected output | ~300 tokens |
| **Total** | **~4,600** (Note: exceeds 2,000 budget for gpt-4o-mini → use gpt-4o for retries 2–3) |

---

# 10. Workflow Engine (LangGraph)

### State Definition

```python
from typing import TypedDict

class WorkflowState(TypedDict):
    # Input
    user_question: str
    workflow_id: str

    # Planner
    business_intent: str | None
    analysis_plan: AnalysisPlan | None

    # SQL Agent
    generated_sql: SQLResult | None
    sql_error: str | None

    # Analytics Agent
    insights: list[Insight]

    # Evidence Retrieval
    evidence_items: list[EvidenceItem]

    # Decision Intelligence
    decision: Decision | None

    # Writer
    report: Report | None

    # Reviewer
    review_result: ReviewResult | None
    retry_count: int  # 0–3

    # Tracing
    agent_traces: list[AgentTrace]
    error_log: list[str]
```

### DAG Definition

```python
from langgraph.graph import StateGraph, END

def build_copilot_graph() -> StateGraph:
    workflow = StateGraph(WorkflowState)

    # Add nodes
    workflow.add_node("planner", run_planner)
    workflow.add_node("sql_generator", run_sql_generator)
    workflow.add_node("evidence_retrieval", run_evidence_retrieval)
    workflow.add_node("analytics", run_analytics)
    workflow.add_node("decision_intelligence", run_decision_intelligence)
    workflow.add_node("report_writer", run_report_writer)
    workflow.add_node("reviewer", run_reviewer)

    # Set entry
    workflow.set_entry_point("planner")

    # Edges
    workflow.add_edge("planner", "sql_generator")
    workflow.add_edge("planner", "evidence_retrieval")  # PARALLEL
    workflow.add_edge("sql_generator", "analytics")
    workflow.add_edge("analytics", "decision_intelligence")
    workflow.add_edge("evidence_retrieval", "decision_intelligence")
    workflow.add_edge("decision_intelligence", "report_writer")
    workflow.add_edge("report_writer", "reviewer")

    # Conditional: reviewer gate
    workflow.add_conditional_edges(
        "reviewer",
        decide_after_review,
        {
            "report_writer": "report_writer",       # Retry
            "decision_intelligence": "decision_intelligence",  # Retry from earlier
            END: END,                                # Pass
        },
    )

    return workflow.compile()


def decide_after_review(state: WorkflowState) -> str:
    MAX_RETRIES = 3
    review = state["review_result"]

    if review.passed or review.overridden:
        return END

    state["retry_count"] += 1

    if state["retry_count"] >= MAX_RETRIES:
        # Force through on next reviewer call
        return "report_writer"

    # Route based on which check failed
    for check in review.checks:
        if not check.passed:
            if check.check_name in ("evidence_completeness", "citation_validity"):
                return "decision_intelligence"
            else:
                return "report_writer"

    return "report_writer"  # Default retry
```

### Checkpointer (for debugging)

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
graph = build_copilot_graph().compile(checkpointer=checkpointer)

# Each workflow_id maps to a thread_id in LangGraph
config = {"configurable": {"thread_id": workflow_id}}
result = await graph.ainvoke(initial_state, config)
```

### Observability Hooks

```python
# Every node wraps agent execution with tracing
async def run_planner(state: WorkflowState) -> dict:
    agent = PlannerAgent(...)
    result = await agent.execute(
        PlannerInput(question=state["user_question"]),
        context=state,
    )
    state["agent_traces"].append(result.trace)
    if not result.success:
        state["error_log"].append(f"Planner failed: {result.error}")
    return {"analysis_plan": result.data, "business_intent": result.data.intent}
```

---

# 11. LLM Provider Abstraction

### Interface

```python
from abc import ABC, abstractmethod
from typing import TypeVar

T = TypeVar("T")

class Prompt(BaseModel):
    """Versioned prompt with compiled messages."""
    version: str
    system: str
    user: str
    output_schema: type[BaseModel] | None
    model: str
    temperature: float
    max_tokens: int

class LLMResponse(BaseModel):
    content: str
    model: str
    token_usage: dict
    latency_ms: int

class LLMProvider(ABC):
    """Pluggable LLM backend."""

    @abstractmethod
    async def complete(
        self,
        prompt: Prompt,
    ) -> LLMResponse: ...

    @abstractmethod
    async def complete_structured(
        self,
        prompt: Prompt,
        output_schema: type[T],
    ) -> T: ...
```

### Provider Implementations

```python
# infrastructure/llm/openai_provider.py
class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: str | None = None):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

# infrastructure/llm/deepseek_provider.py
class DeepSeekProvider(LLMProvider):
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
        )

# infrastructure/llm/vllm_provider.py
class VLLMProvider(LLMProvider):
    def __init__(self, endpoint: str):
        self.client = AsyncOpenAI(base_url=endpoint, api_key="not-needed")
```

### Provider Selection

```python
# app/core/config.py
class Settings(BaseSettings):
    llm_provider: str = "openai"     # "openai" | "deepseek" | "qwen" | "vllm"
    llm_model: str = "gpt-4o"
    llm_fast_model: str = "gpt-4o-mini"  # For analytics, reviewer
    openai_api_key: str | None = None
    deepseek_api_key: str | None = None

# Switching provider = changing one env var
```

---

# 12. Prompt Registry

### Storage Layout

```
backend/app/ai/prompts/
├── planner/
│   ├── v1__intent_extraction.yaml
│   └── v2__plan_generation.yaml       ← Active
├── sql/
│   └── v1__sql_generation.yaml        ← Active
├── analytics/
│   └── v1__analytics_agent.yaml       ← Active
├── decision/
│   └── v1__decision_synthesis.yaml    ← Active
├── writer/
│   └── v1__report_generation.yaml     ← Active
└── reviewer/
    └── v1__output_validation.yaml     ← Active
```

### Prompt YAML Schema

```yaml
# v1__sql_generation.yaml
version: "1.0.0"
purpose: "Generate parameterized read-only SQL from AnalysisPlan"
agent: "sql_generator"
model: "gpt-4o"
temperature: 0.0
max_tokens: 3000
json_mode: true
evaluation_score: 0.94
evaluated_at: "2026-07-20"
status: "active"

system: |
  You are a SQL generator...

user: |
  Analysis step: {step_description}
  ...

output_schema:
  type: object
  properties:
    sql: { type: string }
    tables_used: { type: array, items: { type: string } }
    parameters: { type: object }
    explanation: { type: string }
    confidence: { type: number }
  required: [sql, tables_used, confidence]
```

### Prompt Lifecycle

```
Draft → Review → Registered → Active → Deprecated → Archived

Transition rules:
- Draft → Review: Prompt passes manual review
- Review → Registered: Evaluation score ≥ threshold
- Registered → Active: Deployed and serving traffic
- Active → Deprecated: Newer version exists; 30-day grace period
- Deprecated → Archived: No traffic for 30 days
```

### Loading Prompts

```python
class PromptRegistry:
    def __init__(self, prompts_dir: Path):
        self.prompts_dir = prompts_dir
        self._cache: dict[str, Prompt] = {}

    def load(self, prompt_id: str) -> Prompt:
        """Load a prompt by ID: 'planner/v2__plan_generation'"""
        if prompt_id in self._cache:
            return self._cache[prompt_id]

        agent, filename = prompt_id.split("/")
        path = self.prompts_dir / agent / f"{filename}.yaml"

        with open(path) as f:
            raw = yaml.safe_load(f)

        prompt = Prompt(
            version=raw["version"],
            system=raw["system"],
            user=raw["user"],
            output_schema=raw.get("output_schema"),
            model=raw["model"],
            temperature=raw["temperature"],
            max_tokens=raw["max_tokens"],
        )
        self._cache[prompt_id] = prompt
        return prompt
```

---

# 13. Evaluation Framework

### Golden Dataset

```
tests/ai/golden/
├── planner/
│   ├── case_001_question.txt
│   └── case_001_expected_plan.json
├── sql/
│   ├── case_001_input.json
│   └── case_001_expected_sql.txt
├── decision/
│   └── ...
└── reviewer/
    └── case_001_bad_report.json      # Should be REJECTED
    └── case_002_good_report.json     # Should be ACCEPTED
```

### Evaluator Interface

```python
class TestCase(BaseModel):
    case_id: str
    agent: str
    input_data: dict
    expected_output: dict
    evaluation_rules: list[str]    # ["exact_match", "schema_valid", "semantic_similarity"]

class EvaluationReport(BaseModel):
    agent: str
    prompt_version: str
    total_cases: int
    passed: int
    failed: int
    metrics: dict[str, float]      # Per-metric scores
    failures: list[dict]

class PromptEvaluator:
    def __init__(self, llm: LLMProvider, prompt_registry: PromptRegistry):
        self.llm = llm
        self.registry = prompt_registry

    async def evaluate(
        self,
        prompt_id: str,
        test_cases: list[TestCase],
    ) -> EvaluationReport:
        prompt = self.registry.load(prompt_id)
        results = []

        for case in test_cases:
            output = await self.llm.complete_structured(
                prompt.format(**case.input_data),
                output_schema=prompt.output_schema,
            )
            results.append(self._score(case, output))

        return EvaluationReport(
            agent=prompt_id.split("/")[0],
            prompt_version=prompt.version,
            total_cases=len(test_cases),
            passed=sum(1 for r in results if r["passed"]),
            failed=sum(1 for r in results if not r["passed"]),
            metrics=self._aggregate_metrics(results),
            failures=[r for r in results if not r["passed"]],
        )
```

### Evaluation Thresholds by Agent

| Agent | Metric | Promotion Threshold |
|-------|--------|:-------------------:|
| Planner | Intent accuracy | ≥ 0.90 |
| SQL Generator | SQL validity | ≥ 0.95 |
| SQL Generator | Sandbox pass | = 1.00 |
| Decision | Evidence alignment | ≥ 0.85 |
| Decision | Hallucination rate | ≤ 0.02 |
| Writer | Evidence citation rate | = 1.00 |
| Reviewer | False pass rate | ≤ 0.05 |
| Reviewer | False reject rate | ≤ 0.10 |

---

# 14. Context Assembly

### Dynamic Context Builder

```python
class ContextAssembler:
    """Builds the LLM context window from multiple sources.
    Must stay under model's context limit (8K for gpt-4o-mini, 128K for gpt-4o).
    """

    MAX_CONTEXT_TOKENS = 8000

    async def build_context(
        self,
        user_question: str,
        analysis_plan: AnalysisPlan | None = None,
        workflow_state: WorkflowState | None = None,
    ) -> str:
        sources = []

        # 1. Relevant metric definitions (always)
        metrics = await self.metric_registry.search(
            analysis_plan.required_metrics if analysis_plan else []
        )
        sources.append(self._format_metrics(metrics))

        # 2. Relevant table schemas (for SQL Agent)
        if analysis_plan:
            tables = self._extract_tables_from_plan(analysis_plan)
            schemas = await self.warehouse.get_table_schemas(tables)
            sources.append(self._format_schemas(schemas))

        # 3. Recent KPI values (for context)
        if workflow_state:
            recent_kpis = await self.warehouse.get_recent_kpis()
            sources.append(self._format_kpis(recent_kpis))

        # 4. Model explanations (if ML predictions in context)
        # 5. Historical reports (if similar past questions)

        context = "\n\n".join(sources)

        # Truncate to max tokens
        if self._estimate_tokens(context) > self.MAX_CONTEXT_TOKENS:
            context = self._truncate(context, self.MAX_CONTEXT_TOKENS)

        return context
```

### Context Source Priority

| Source | Priority | When Included |
|--------|:--------:|---------------|
| User question | Always | Always |
| Metric definitions | Always | When metrics are in the plan |
| Table schemas | High | SQL Agent only |
| Recent KPI values | Medium | Decision, Writer agents |
| Feature store snapshots | Medium | When ML context needed |
| Historical reports | Low | Writer agent (for style reference) |

---

# 15. Safety & Guardrails

### Input Guardrails

```python
class InputGuardrail:
    """Applied to user input BEFORE it reaches any agent."""

    MAX_QUESTION_LENGTH = 500
    BLOCKED_PATTERNS = [
        r"ignore.*(instruction|prompt|system)",
        r"(drop|delete|truncate|insert|update).*table",
        r"bypass|override.*(rule|check|review)",
    ]

    def sanitize(self, question: str) -> tuple[str, bool]:
        """
        Returns (sanitized_question, is_safe).
        If is_safe=False, the question is blocked entirely.
        """
        # Length check
        if len(question) > self.MAX_QUESTION_LENGTH:
            question = question[:self.MAX_QUESTION_LENGTH]

        # Prompt injection check
        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, question, re.IGNORECASE):
                return "", False

        # Strip delimiters used in prompt injection
        question = question.replace("###", "")
        question = question.replace("---", "")
        question = question.replace('"""', "")

        return question, True
```

### Output Guardrails

```python
class OutputGuardrail:
    """Applied to agent outputs BEFORE they enter the domain layer."""

    def validate_structured_output(
        self,
        raw_output: dict,
        expected_schema: type[BaseModel],
    ) -> BaseModel | None:
        """Validate JSON output against Pydantic schema."""
        try:
            return expected_schema.model_validate(raw_output)
        except ValidationError as e:
            logger.warning("Agent output failed schema validation", errors=e.errors())
            return None

    def check_hallucination_signals(self, output: BaseModel, evidence: list) -> bool:
        """Heuristic checks for hallucinated content."""
        # Check: does output reference tables not in evidence?
        # Check: does output cite metrics not in Metric Registry?
        # Check: does output mention customer IDs not in context?
        ...
```

### PII Filter

```python
class PIIFilter:
    """Strips PII from data before it enters LLM context."""

    PATTERNS = {
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "phone": r'\b\d{10,15}\b',
        "customer_name": r'(?i)\b(customer name|full name):\s*\S+',
    }

    def filter(self, text: str) -> str:
        for label, pattern in self.PATTERNS.items():
            text = re.sub(pattern, f"[REDACTED_{label.upper()}]", text)
        return text
```

---

# Document Freeze

This document freezes the **AI Agent architecture and design** for InsightFlow Version 1.0.

From this point onward:

- Every agent must implement the `Agent[TInput, TOutput]` contract defined in §1.2.
- Every prompt must be a versioned YAML asset in the Prompt Registry (§12).
- The SQL Generator must pass through the SQL Sandbox gate (§4) — no exceptions.
- The Reviewer retry ceiling is 3 (§9) — no exceptions.
- Agent evaluation must use the framework defined in §13 before any prompt version is promoted to `active`.
- Context assembly must stay within the token budget (§14) and filter PII (§15).
