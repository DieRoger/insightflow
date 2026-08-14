# InsightFlow — Evaluation Framework

Version 1.0 · Status: **Frozen** · Target: ML Engineers + QA + Stakeholders

---

## Table of Contents

1. [Purpose](#1-purpose)
2. [ML Model Evaluation](#2-ml-model-evaluation)
3. [AI Agent Evaluation](#3-ai-agent-evaluation)
4. [Prompt Regression Testing](#4-prompt-regression-testing)
5. [System Quality Metrics](#5-system-quality-metrics)
6. [Business Outcome Metrics](#6-business-outcome-metrics)
7. [Evaluation Schedule](#7-evaluation-schedule)

---

# 1. Purpose

This document defines **how InsightFlow measures quality**. It covers three domains:

| Domain | What's Evaluated | When |
|--------|-----------------|------|
| **ML Models** | Churn prediction accuracy, segmentation quality | Every training run |
| **AI Agents** | Intent accuracy, SQL validity, hallucination rate | Every prompt change + weekly |
| **System** | Latency, availability, correctness | Continuous (CI + production monitoring) |

Every evaluation produces a **structured report** stored alongside the artifact (model, prompt, or deployment).

---

# 2. ML Model Evaluation

## 2.1 Churn Prediction

### Metrics

| Metric | Formula / Description | Target |
|--------|----------------------|:------:|
| **ROC-AUC** | Area under ROC curve | ≥ 0.85 |
| **PR-AUC** | Area under Precision-Recall curve (better for imbalanced data) | ≥ 0.70 |
| **F1 Score** | Harmonic mean of precision and recall | ≥ 0.80 |
| **Precision** | TP / (TP + FP) | ≥ 0.75 |
| **Recall** | TP / (TP + FN) | ≥ 0.80 |
| **Log Loss** | Cross-entropy loss | ≤ 0.35 |
| **Calibration Error** | |predicted_prob - observed_freq| | ≤ 0.05 |
| **Lift @ 10%** | How many more churners captured vs random, at top 10% risk | ≥ 3.0× |

### Confusion Matrix

Required for every evaluation report:

```
                  Predicted
                  Churn   Not Churn
Actual  Churn      TP      FN
        Not Churn  FP      TN
```

### Evaluation Report Template

```json
{
    "model_name": "churn_xgboost",
    "model_version": "v1.2.0",
    "evaluated_at": "2026-07-15T08:30:00Z",
    "dataset": {
        "dataset_id": "ds_churn_20260715",
        "feature_version": "v1.0.0",
        "total_samples": 800000,
        "churn_rate": 0.12,
        "train_split": 0.70,
        "val_split": 0.15,
        "test_split": 0.15
    },
    "metrics": {
        "roc_auc": 0.91,
        "pr_auc": 0.78,
        "f1_score": 0.84,
        "precision": 0.82,
        "recall": 0.86,
        "log_loss": 0.32,
        "calibration_error": 0.03,
        "lift_at_10pct": 3.8
    },
    "confusion_matrix": {
        "true_positive": 8500,
        "false_positive": 1200,
        "true_negative": 38000,
        "false_negative": 2300
    },
    "threshold_analysis": {
        "optimal_threshold": 0.48,
        "at_threshold_0.3": { "precision": 0.65, "recall": 0.92 },
        "at_threshold_0.5": { "precision": 0.82, "recall": 0.86 },
        "at_threshold_0.7": { "precision": 0.91, "recall": 0.62 }
    }
}
```

### Model Comparison (per training run)

Every training run compares all candidates:

```
Model              ROC-AUC   F1      Train Time   Production?
────────────────────────────────────────────────────────────
Logistic Reg.      0.78      0.71    12s          —
Random Forest      0.85      0.78    180s         —
XGBoost            0.91      0.84    340s         ✅ (promoted)
LightGBM           0.90      0.83    280s         —
CatBoost           0.89      0.82    420s         —
```

### Promotion Gate

A model can be promoted to `production` only when:

- [ ] ROC-AUC ≥ 0.85
- [ ] F1 Score ≥ 0.80
- [ ] Calibration Error ≤ 0.05
- [ ] All metrics ≥ previous production model (no regression)
- [ ] SHAP explanations verified for 100 sample predictions
- [ ] Batch prediction tested on full dataset

## 2.2 Customer Segmentation

### Metrics

| Metric | Description | Target |
|--------|-------------|:------:|
| **Silhouette Score** | Cluster cohesion vs separation | ≥ 0.40 |
| **Davies-Bouldin Index** | Cluster similarity (lower is better) | ≤ 1.50 |
| **Segment Stability** | % customers staying in same segment month-over-month | ≥ 0.85 |
| **Segment Size Balance** | Largest segment / smallest segment | ≤ 5.0 |

---

# 3. AI Agent Evaluation

## 3.1 Per-Agent Metrics

### Query Planner

| Metric | Target | Measurement Method |
|--------|:------:|-------------------|
| Intent accuracy | ≥ 0.90 | Compare against golden labeled intents (100 test cases) |
| Metric selection precision | ≥ 0.85 | Selected ⊆ required / selected |
| Metric selection recall | ≥ 0.90 | Selected ∩ required / required |
| Plan completeness | ≥ 0.90 | All necessary steps identified |

### SQL Generator

| Metric | Target | Measurement Method |
|--------|:------:|-------------------|
| SQL validity (parses) | ≥ 0.98 | `sqlparse` + PostgreSQL `EXPLAIN` dry-run |
| Sandbox pass rate | **1.00** | Must be 100% — zero tolerance |
| Metric alignment | ≥ 0.90 | SQL computes the intended metric |
| Execution time (on test DB) | < 2s | Timed against test database |

### Analytics Agent

| Metric | Target | Measurement Method |
|--------|:------:|-------------------|
| Value accuracy | ≥ 0.98 | Computed vs ground truth from raw data |
| Insight extraction rate | ≥ 0.90 | Insights generated / expected |
| Confidence calibration | ≤ 0.10 | |predicted_confidence − actual_accuracy| |

### Decision Intelligence

| Metric | Target | Measurement Method |
|--------|:------:|-------------------|
| Evidence alignment | ≥ 0.85 | Claims with ≥ 1 evidence ref / total claims |
| Hallucination rate | ≤ 0.02 | Claims not supported by input data |
| Impact reasonableness | ≥ 0.80 | Estimated impact within ±30% of ground truth |
| Recommendation relevance | ≥ 0.85 | Recommendation addresses root cause |

### Report Writer

| Metric | Target | Measurement Method |
|--------|:------:|-------------------|
| Evidence citation rate | **1.00** | Every factual claim must cite evidence |
| Hallucination rate | ≤ 0.01 | Fabricated facts not in source data |
| Readability | Grade 8–12 | Flesch-Kincaid score |
| Section completeness | ≥ 0.90 | All required sections present |

### Reviewer

| Metric | Target | Measurement Method |
|--------|:------:|-------------------|
| False pass rate | ≤ 0.05 | Bad reports incorrectly passed |
| False reject rate | ≤ 0.10 | Good reports incorrectly rejected |
| Retry effectiveness | ≥ 0.70 | Retried reports pass on 2nd attempt |

## 3.2 End-to-End Workflow Evaluation

Weekly evaluation on 50 curated test questions:

| Metric | Target |
|--------|:------:|
| Overall success rate (valid response) | ≥ 0.90 |
| Evidence presence rate | 1.00 |
| Average confidence (across all responses) | ≥ 0.75 |
| Average latency | < 12s |
| P95 latency | < 15s |
| User satisfaction (manual review) | ≥ 4.0/5.0 |

---

# 4. Prompt Regression Testing

## 4.1 Golden Dataset

```
tests/ai/golden/
├── planner/
│   ├── case_001_question.txt          # "Why did churn increase in East Region?"
│   ├── case_001_expected_plan.json    # Ground truth AnalysisPlan
│   ├── case_002_question.txt
│   └── case_002_expected_plan.json
├── sql/
│   ├── case_001_input.json
│   ├── case_001_expected_sql.txt
│   └── ...
├── decision/
│   └── ...
├── writer/
│   └── ...
└── reviewer/
    ├── case_bad_001_input.json        # Should be REJECTED
    └── case_good_001_input.json       # Should be ACCEPTED
```

**Minimum golden dataset size per agent**: 20 cases.

## 4.2 Evaluation Run

```bash
# Run all prompt regression tests
pytest tests/ai/test_prompts/ -v --golden-dir tests/ai/golden/

# Run for a specific agent
pytest tests/ai/test_prompts/test_planner_prompts.py -v

# Run with new prompt version comparison
python scripts/evaluate_prompt.py \
    --agent planner \
    --prompt v3__plan_generation \
    --baseline v2__plan_generation \
    --golden-dir tests/ai/golden/planner/
```

## 4.3 Promotion Criteria

A new prompt version can be promoted from `registered` to `active` only when:

| Agent | Criteria |
|-------|----------|
| Planner | All metrics ≥ baseline; no regression > 0.05 on any metric |
| SQL Generator | Sandbox pass rate = 1.00; SQL validity ≥ baseline |
| Decision | Hallucination rate ≤ baseline; evidence alignment ≥ baseline |
| Writer | Evidence citation rate = 1.00; no regression in completeness |
| Reviewer | False pass rate ≤ baseline; false reject rate ≤ baseline + 0.05 |

---

# 5. System Quality Metrics

## 5.1 Performance

| Metric | Target | Measurement |
|--------|:------:|-------------|
| API response (non-AI) | < 500ms P95 | Prometheus histogram |
| Dashboard load | < 2s | Lighthouse / Web Vitals |
| Analytics query | < 5s P95 | App-level timing |
| AI Copilot response | < 15s P95 | App-level timing |
| Batch prediction (1M) | < 30 min | Task duration |
| Report generation | < 60s | Task duration |

## 5.2 Reliability

| Metric | Target | Measurement |
|--------|:------:|-------------|
| Uptime | 99.5% | Uptime monitor |
| Error rate | < 0.5% of requests | Prometheus |
| AI workflow failure rate | < 5% | App-level tracking |
| Data pipeline success rate | > 99% | ETL quality reports |

## 5.3 Correctness

| Metric | Target | Measurement |
|--------|:------:|-------------|
| KPI consistency | 100% | Same KPI from API, dashboard, and report must match |
| SQL Sandbox evasion | 0 | Security test suite |
| Schema validation pass rate | > 99.9% | API-level metrics |

---

# 6. Business Outcome Metrics

These metrics measure whether InsightFlow is delivering business value (for real deployments, not mock data).

| Metric | Target | Measurement |
|--------|:------:|-------------|
| Churn rate reduction | ≥ 10% vs baseline | A/B test |
| ARPU improvement | ≥ 3% | Quarterly comparison |
| Campaign ROI improvement | ≥ 15% | Campaign attribution |
| Analyst time saved | ≥ 50% | User survey |
| Report generation time | From days to minutes | Time tracking |

**Note**: These metrics apply to production deployments with real telecom data. During MVP, only system metrics (§5) are measured.

---

# 7. Evaluation Schedule

| Evaluation | Frequency | Trigger | Owner |
|------------|-----------|---------|-------|
| ML model evaluation | Per training run | New model trained | ML Engineer |
| Model drift check | Weekly | Cron | ML Engineer |
| Prompt regression | Per prompt change | PR with prompt diff | AI Engineer |
| Agent evaluation (full) | Weekly | Cron | AI Engineer |
| System performance | Continuous | Prometheus alerts | DevOps |
| Business outcomes | Monthly | Calendar | Product Manager |

### Automated Evaluation Pipeline

```yaml
# .github/workflows/evaluation.yml (future addition)
name: Weekly AI Evaluation
on:
  schedule:
    - cron: "0 8 * * 1"  # Every Monday 8:00 UTC

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run prompt regression
        run: pytest tests/ai/test_prompts/ -v --json-report
      - name: Run agent evaluation
        run: python scripts/evaluate_agents.py --output evaluation_report.json
      - name: Compare with last week
        run: python scripts/compare_evaluation.py --current evaluation_report.json --baseline s3://insightflow-evals/latest.json
      - name: Alert if regression
        if: failure()
        run: python scripts/alert_slack.py --message "AI evaluation regression detected"
```

---

# Document Freeze

This document freezes the **evaluation framework** for InsightFlow Version 1.0.

Every model training run, prompt change, and weekly evaluation must follow the protocols defined here. Evaluation reports are stored alongside their artifacts for full auditability. Metrics that fall below target thresholds block promotion to production.
