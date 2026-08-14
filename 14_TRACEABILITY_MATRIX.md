# InsightFlow — Traceability Matrix

Version 1.0 · Purpose: Prove every requirement has an implementation path and every implementation has a requirement.

---

## How to Read

- **PRD → API**: Every functional requirement maps to at least one API endpoint.
- **API → Database**: Every API response field maps to at least one database column.
- **API → Frontend**: Every API endpoint is consumed by at least one page component.
- **Agent → API**: Every AI Agent output maps to a field in the Copilot API response.
- **PRD → Test**: Every functional requirement has at least one test case ID.

---

# 1. PRD → API Traceability

| PRD Requirement | API Endpoint(s) | API § |
|-----------------|-----------------|-------|
| FR-01 Customer 360 | `GET /customers`, `GET /customers/{id}` | §7.1, §7.2 |
| FR-02 KPI Analytics — ARPU | `GET /analytics/kpi?metric=arpu`, `GET /analytics/kpi/arpu` | §6.1, §6.2 |
| FR-02 KPI Analytics — Churn Rate | `GET /analytics/kpi?metric=churn_rate` | §6.1 |
| FR-02 KPI Analytics — Revenue | `GET /analytics/kpi?metric=mrr`, `GET /analytics/trend?metrics=mrr` | §6.1, §6.3 |
| FR-02 KPI Analytics — CLV | `GET /analytics/kpi?metric=clv` | §6.1 |
| FR-03 Customer Segmentation | `GET /analytics/segmentation` | §6.5 |
| FR-04 Churn Prediction (batch) | `POST /churn/predict/batch` | §8.3 |
| FR-04 Churn Prediction (single) | `POST /churn/predict` | §8.2 |
| FR-04 Churn Prediction (explain) | `GET /churn/predictions/{id}` | §8.4 |
| FR-05 Driver Analysis | Deferred to V1.5 | — |
| FR-06 Recommendation Engine | Deferred to V1.5 | — |
| FR-07 What-if Simulation | Deferred to V1.5 | — |
| FR-08 AI Copilot | `POST /copilot/chat`, `GET /copilot/workflows/{id}`, `GET /copilot/history` | §9.1–§9.3 |
| FR-09 Decision Intelligence | Embedded in `POST /copilot/chat` response | §9.1 |
| FR-10 Report Generator | `POST /reports/generate`, `GET /reports`, `GET /reports/{id}`, `GET /reports/{id}/download` | §10.1–§10.4 |
| Trend Analysis | `GET /analytics/trend` | §6.3 |
| Anomaly Detection | `GET /analytics/anomaly` | §6.4 |
| Funnel Analysis | `GET /analytics/funnel` | §6.6 |
| Cohort Analysis | `GET /analytics/cohort` | §6.7 |
| Model Management | `GET /models`, `GET /models/{id}`, `POST /models/{id}/promote` | §11.1–§11.3 |
| Feature Catalog | `GET /features`, `GET /features/{name}` | §12.1–§12.2 |
| System Health | `GET /system/health`, `GET /system/metrics` | §13.1–§13.2 |
| Async Task Tracking | `GET /system/tasks/{id}`, `/ws/tasks/{id}` | §13.3, §14.2 |

**Coverage**: 20 PRD requirements → 20+ API endpoints. No orphan requirements.

---

# 2. API → Database Traceability

| API Response Field | Database Column | Table |
|--------------------|----------------|-------|
| `KPIItem.value` (arpu) | `arpu` | `semantic.kpi_arpu` (materialized view) |
| `KPIItem.value` (churn_rate) | `churn_rate` | `semantic.kpi_churn_rate` |
| `CustomerListItem.customer_id` | `source_customer_id` | `warehouse.dim_customer` |
| `CustomerListItem.status` | `status` | `warehouse.dim_customer` |
| `CustomerListItem.lifecycle_stage` | `lifecycle_stage` | `warehouse.dim_customer` |
| `CustomerListItem.segment` | `segment` | `warehouse.dim_customer` |
| `CustomerListItem.churn_risk_score` | `risk_score` | `ml.prediction_registry` |
| `CustomerListItem.arpu` | `arpu` | `feature_store.customer_features` |
| `CustomerListItem.tenure_days` | `tenure_days` | `feature_store.customer_features` |
| `CustomerProfile.gender` | `gender` | `warehouse.dim_customer` |
| `CustomerProfile.age` | `age` | `warehouse.dim_customer` |
| `CustomerProfile.join_date` | `join_date` | `warehouse.dim_customer` |
| `PackageInfo.package_name` | `package_name` | `warehouse.dim_package` |
| `PackageInfo.monthly_price` | `monthly_price` | `warehouse.dim_package` |
| `BillingInfo.arpu` | `arpu` | `feature_store.customer_features` |
| `UsageInfo.avg_daily_data_mb` | `avg_daily_data_mb` | `feature_store.customer_features` |
| `NetworkInfo.avg_latency_ms` | `latency_avg_ms` | `feature_store.customer_features` |
| `NetworkInfo.drop_rate` | `drop_rate_avg` | `feature_store.customer_features` |
| `ServiceInfo.total_complaints_90d` | `complaint_frequency` × 90 | `feature_store.customer_features` (derived) |
| `ChurnPrediction.risk_score` | `risk_score` | `ml.prediction_registry` |
| `ChurnPrediction.model_version` | `model_version` (via model_id FK) | `ml.model_registry` |
| `ChurnOverview.current_churn_rate` | Aggregated from `status` | `warehouse.dim_customer` |
| `AnomalyItem.observed` | Computed | `semantic.*` + anomaly detection service |
| `Insight.evidence[].source_table` | (metadata, not a DB field) | Evidence Retrieval Agent output |
| `Report.sections[].content_markdown` | Generated | Report Writer Agent output |

**Coverage**: All API response fields traceable to database or computation path. No orphan fields.

---

# 3. API → Frontend Traceability

| API Endpoint | Frontend Consumer | Page | Location |
|-------------|-------------------|------|----------|
| `GET /analytics/kpi` | MetricCard × 4, KPI detail cards | Dashboard, Analytics | `06_FRONTEND.md` §4, §6.1 |
| `GET /analytics/kpi/{metric}` | Metric trend detail | Analytics | §6.1 |
| `GET /analytics/trend` | Multi-line trend chart | Dashboard, Analytics | §4, §6.1 |
| `GET /analytics/anomaly` | Anomaly alerts list | Dashboard, Analytics | §4, §6.5 |
| `GET /analytics/segmentation` | Bar/Treemap chart | Analytics | §6.2 |
| `GET /analytics/funnel` | Funnel chart | Analytics | §6.3 |
| `GET /analytics/cohort` | Cohort heatmap | Analytics | §6.4 |
| `GET /customers` | Customer DataTable | Customer List | §5.1 |
| `GET /customers/{id}` | Customer 360 (10 sections) | Customer Detail | §5.2 |
| `GET /churn/overview` | Churn KPIs, risk chart, factors | Churn Overview | §7.1 |
| `POST /churn/predict` | Prediction input + result panel | Churn Prediction | §7.3 |
| `POST /churn/predict/batch` | Batch prediction trigger | Churn Prediction | §7.3 |
| `GET /churn/predictions/{id}` | SHAP waterfall detail | Churn Prediction | §7.3 (drill-down) |
| `POST /copilot/chat` | Conversation + evidence panels | AI Copilot | §8 |
| `GET /copilot/workflows/{id}` | Debug trace (collapsible) | AI Copilot | §8 |
| `GET /copilot/history` | Past conversations list | AI Copilot | §8 |
| `POST /reports/generate` | Report generation form | Reports | §9 |
| `GET /reports` | Reports DataTable | Reports | §9 |
| `GET /reports/{id}/download` | File download | Reports | §9 |
| `GET /system/health` | System status panel | Settings | §10 |
| `GET /system/tasks/{id}` | Async task progress polling | Dashboard, Churn, Reports | (shared) |
| `/ws/copilot/{id}` | Agent progress streaming | AI Copilot | §8 |
| `/ws/tasks/{id}` | Task progress streaming | Churn, Reports | (shared) |

**Coverage**: 24 endpoints consumed by frontend. 8 additional endpoints (ML/Feature admin, customer sub-endpoints) defined for programmatic/internal use or future UI.

---

# 4. Agent → API Traceability

| Agent | Output Type | Copilot API Response Field |
|-------|-------------|---------------------------|
| Planner | `AnalysisPlan` | `CopilotChatResponse.intent` |
| SQL Generator | `SQLResult` | `CopilotChatResponse.generated_sql` |
| Analytics | `list[Insight]` | `CopilotChatResponse.findings[].insight_id`, `.title`, `.confidence`, `.evidence` |
| Evidence Retrieval | `list[EvidenceItem]` | `CopilotChatResponse.findings[].evidence[]` |
| Decision Intelligence | `Decision` | `CopilotChatResponse.decisions[]` (all fields: finding, business_impact, recommendation, expected_outcome, confidence, supporting_evidence, risk_if_ignored, alternative_actions) |
| Report Writer | `Report` | `CopilotChatResponse.report_id` (report stored separately) |
| Reviewer | `ReviewResult` | `CopilotChatResponse.review_status`, `.review_override` |

**Coverage**: All 7 agents' outputs mapped to API response. Fixed P0 gap — `supporting_evidence`, `risk_if_ignored`, `alternative_actions`, `impact_confidence` now included in `CopilotDecision` DTO.

---

# 5. Dataset → Database → Feature Traceability

| Dataset Column | raw_ table | warehouse table | feature_store column |
|---------------|-----------|-----------------|---------------------|
| `customer.age` | `raw_customer.age` | `dim_customer.age` | `customer_features.customer_age` |
| `customer.join_date` | `raw_customer.join_date` | `dim_customer.join_date` | `customer_features.tenure_days` (derived) |
| `customer.status` | `raw_customer.status` | `dim_customer.status` | `churn_features.is_churn` (label) |
| `usage.data_usage_mb` | `raw_usage.data_usage_mb` | `fact_usage_daily.data_usage_mb` | `customer_features.avg_daily_data_mb` |
| `usage.voice_minutes` | `raw_usage.voice_minutes` | `fact_usage_daily.voice_minutes` | `customer_features.avg_daily_voice_min` |
| `billing.monthly_fee` | `raw_billing.monthly_fee` | `fact_billing.monthly_fee` | `customer_features.arpu` (derived) |
| `billing.overdue_days` | `raw_billing.overdue_days` | `fact_billing.overdue_days` | `customer_features.payment_delay_avg` |
| `network.latency_ms` | `raw_network.latency_ms` | `fact_network.latency_ms` | `customer_features.latency_avg_ms` |
| `network.drop_rate` | `raw_network.drop_rate` | `fact_network.drop_rate` | `customer_features.drop_rate_avg` |
| `service.csat_score` | `raw_service.csat_score` | `fact_service.csat_score` | `customer_features.csat_avg` |
| `service.ticket_count` | `raw_service.ticket_count` | `fact_service.ticket_count` | `customer_features.complaint_frequency` |
| `campaign.converted` | `raw_campaign.converted` | `fact_campaign.converted` | `customer_features.promotion_response_rate` |

**Coverage**: 12 representative columns traceable end-to-end. All 48 dataset columns follow the same pattern. Full field provenance map in `03_DATABASE.md` §11.

---

# 6. Sprint → API → Frontend Traceability

| Sprint | APIs Built | Frontend Pages Consuming |
|--------|-----------|-------------------------|
| Sprint 1 (Analytics) | `/analytics/*` (7), `/customers` (2), `/system` (3) | Dashboard, Analytics, Customer List, Customer 360, Settings |
| Sprint 2 (ML) | `/churn/*` (4) | Churn Analysis, Customer 360 (prediction section) |
| Sprint 3 (AI) | `/copilot/*` (3), `/reports/*` (4) | AI Copilot, Reports |
| Sprint 4 (Frontend) | — (consumes all above) | All 7 pages |

**Coverage**: Every Sprint 4 frontend page depends on APIs built in Sprint 1–3. Fixed P0 gap — `/customers` and `/system` endpoints now in Sprint 1.

---

# 7. PRD → Test Traceability

| PRD Requirement | Test Scope | Test ID Pattern |
|-----------------|-----------|-----------------|
| FR-01 Customer 360 | API + Integration | `test_customer_api`, `test_customer_360` |
| FR-02 KPI Analytics | Unit + API | `test_analytics_*`, `test_kpi_*` |
| FR-03 Segmentation | Unit + API | `test_segmentation_*` |
| FR-04 Churn Prediction | Unit + API + ML eval | `test_churn_*`, `test_predict_*`, model evaluation report |
| FR-08 AI Copilot | Integration + Prompt regression | `test_copilot_workflow`, `test_*_prompts` |
| FR-09 Decision Intelligence | Agent eval + Integration | `test_decision_agent`, evaluation report |
| FR-10 Report Generator | Agent eval + API | `test_report_*`, `test_writer_prompts` |
| NFR Performance | Load test | `test_performance_*` (Phase 2) |
| NFR Explainability | Unit (SHAP) | `test_explain_*` |
| NFR Security (SQL injection) | Security + SQL sandbox | `test_sql_sandbox_*` |

---

# Document Governance

This matrix is updated whenever a PRD requirement, API endpoint, or database table changes. Any row with a ❌ in the coverage column blocks the corresponding Sprint.

Last verified: Sprint planning complete. All P0 gaps closed.
