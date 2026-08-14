"""create feature store, registries, and semantic layer

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _exec(sql: str) -> None:
    """Execute a multi-statement DDL script statement by statement."""
    for stmt in sql.split(";"):
        if stmt.strip():
            op.execute(stmt)


FEATURE_STORE_DDL = """
CREATE TABLE feature_store.feature_registry (
    feature_id SERIAL PRIMARY KEY,
    feature_name VARCHAR(100) NOT NULL UNIQUE,
    feature_table VARCHAR(50) NOT NULL,
    description TEXT,
    formula TEXT,
    data_source VARCHAR(200),
    data_type VARCHAR(20),
    refresh_cron VARCHAR(50),
    version VARCHAR(20) NOT NULL,
    owner VARCHAR(100),
    is_deprecated BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE feature_store.customer_features (
    customer_id INTEGER PRIMARY KEY,
    feature_version VARCHAR(20) NOT NULL,
    generated_at TIMESTAMPTZ DEFAULT now(),
    tenure_days INTEGER,
    customer_age INTEGER,
    contract_duration_months INTEGER,
    is_postpaid BOOLEAN,
    is_prepaid BOOLEAN,
    avg_daily_data_mb DECIMAL(10,2),
    avg_daily_voice_min DECIMAL(8,2),
    data_usage_trend DECIMAL(6,4),
    voice_usage_trend DECIMAL(6,4),
    weekend_usage_ratio DECIMAL(5,4),
    night_usage_ratio DECIMAL(5,4),
    peak_usage_ratio DECIMAL(5,4),
    roaming_ratio DECIMAL(5,4),
    international_ratio DECIMAL(5,4),
    arpu DECIMAL(10,2),
    revenue_trend DECIMAL(6,4),
    discount_ratio DECIMAL(5,4),
    payment_delay_avg DECIMAL(6,2),
    overdue_count INTEGER,
    drop_rate_avg DECIMAL(5,4),
    drop_rate_trend DECIMAL(6,4),
    latency_avg_ms DECIMAL(8,2),
    latency_trend DECIMAL(6,4),
    coverage_score_avg DECIMAL(5,2),
    signal_stability DECIMAL(5,4),
    network_quality_index DECIMAL(5,2),
    complaint_frequency DECIMAL(6,4),
    complaint_trend DECIMAL(6,4),
    network_complaint_ratio DECIMAL(5,4),
    billing_complaint_ratio DECIMAL(5,4),
    avg_resolution_time_min DECIMAL(8,2),
    avg_waiting_time_min DECIMAL(8,2),
    csat_avg DECIMAL(4,2),
    csat_trend DECIMAL(6,4),
    escalation_frequency DECIMAL(6,4),
    package_upgrade_count INTEGER,
    package_downgrade_count INTEGER,
    promotion_response_rate DECIMAL(5,4),
    recharge_frequency DECIMAL(6,2),
    data_quota_utilization DECIMAL(5,4),
    days_since_last_complaint INTEGER,
    days_since_last_campaign INTEGER,
    is_heavy_user BOOLEAN,
    is_premium BOOLEAN
);
CREATE INDEX idx_cf_version ON feature_store.customer_features(feature_version);
CREATE INDEX idx_cf_arpu ON feature_store.customer_features(arpu);
CREATE INDEX idx_cf_tenure ON feature_store.customer_features(tenure_days);

CREATE TABLE feature_store.churn_features (
    customer_id INTEGER PRIMARY KEY,
    feature_version VARCHAR(20) NOT NULL,
    generated_at TIMESTAMPTZ DEFAULT now(),
    is_churn BOOLEAN,
    churn_window_end DATE,
    usage_decline_velocity DECIMAL(6,4),
    revenue_decline_velocity DECIMAL(6,4),
    complaint_spike_indicator BOOLEAN,
    network_degradation_score DECIMAL(5,4),
    payment_risk_score DECIMAL(5,4),
    inactivity_risk DECIMAL(5,4),
    downgrade_recent BOOLEAN,
    retention_campaign_eligible BOOLEAN
);
CREATE INDEX idx_chf_version ON feature_store.churn_features(feature_version);

CREATE TABLE feature_store.package_features (
    package_id INTEGER PRIMARY KEY,
    feature_version VARCHAR(20) NOT NULL,
    generated_at TIMESTAMPTZ DEFAULT now(),
    subscriber_count INTEGER,
    avg_tenure_days DECIMAL(8,2),
    churn_rate DECIMAL(5,4),
    avg_arpu DECIMAL(10,2),
    upgrade_from_rate DECIMAL(5,4),
    downgrade_to_rate DECIMAL(5,4),
    avg_csat DECIMAL(4,2),
    price_to_quota_ratio DECIMAL(8,4)
);
CREATE INDEX idx_pf_version ON feature_store.package_features(feature_version);
"""

REGISTRY_DDL = """
CREATE TABLE semantic.metric_registry (
    metric_id SERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(50) NOT NULL,
    business_definition TEXT NOT NULL,
    formula TEXT NOT NULL,
    unit VARCHAR(30),
    data_source VARCHAR(200),
    materialized_view VARCHAR(100),
    refresh_cron VARCHAR(50),
    owner VARCHAR(100),
    version VARCHAR(20) NOT NULL,
    is_deprecated BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE ml.model_registry (
    model_id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(20) NOT NULL,
    model_type VARCHAR(30) NOT NULL,
    algorithm VARCHAR(50),
    artifact_path VARCHAR(500),
    training_dataset_id VARCHAR(100),
    feature_version VARCHAR(20),
    evaluation_report JSONB,
    hyperparameters JSONB,
    random_seed INTEGER,
    training_time_sec INTEGER,
    framework_version VARCHAR(30),
    status VARCHAR(20) DEFAULT 'development',
    promoted_at TIMESTAMPTZ,
    promoted_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(model_name, model_version)
);

CREATE TABLE ml.prediction_registry (
    prediction_id BIGSERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    model_id INTEGER,
    feature_version VARCHAR(20),
    risk_score DECIMAL(5,4),
    risk_level VARCHAR(10),
    top_positive_factors JSONB,
    top_negative_factors JSONB,
    confidence DECIMAL(5,4),
    shap_values JSONB,
    prediction_type VARCHAR(10),
    predicted_at TIMESTAMPTZ DEFAULT now(),
    observation_window DATERANGE
);
CREATE INDEX idx_pred_customer ON ml.prediction_registry(customer_id, predicted_at DESC);
CREATE INDEX idx_pred_model ON ml.prediction_registry(model_id, predicted_at);
CREATE INDEX idx_pred_risk ON ml.prediction_registry(risk_level, predicted_at);
"""

SEMANTIC_VIEW_DDL = """
CREATE MATERIALIZED VIEW semantic.kpi_arpu AS
SELECT
    dt.year,
    dt.month,
    dr.region_name,
    dp.package_name,
    SUM(fb.net_revenue) / NULLIF(COUNT(DISTINCT fb.customer_id), 0) AS arpu,
    COUNT(DISTINCT fb.customer_id) AS customer_count,
    SUM(fb.net_revenue) AS total_revenue
FROM warehouse.fact_billing fb
JOIN warehouse.dim_time dt ON fb.date_id = dt.date_id
JOIN warehouse.dim_customer dc ON fb.customer_id = dc.customer_id
JOIN warehouse.dim_region dr ON dc.region_id = dr.region_id
JOIN warehouse.dim_package dp ON fb.package_id = dp.package_id
WHERE dc.status = 'active'
GROUP BY dt.year, dt.month, dr.region_name, dp.package_name;
CREATE UNIQUE INDEX idx_kpi_arpu ON semantic.kpi_arpu(year, month, region_name, package_name);

CREATE MATERIALIZED VIEW semantic.kpi_revenue AS
SELECT
    dt.year,
    dt.month,
    SUM(fb.net_revenue) AS mrr,
    SUM(fb.net_revenue) - LAG(SUM(fb.net_revenue)) OVER (ORDER BY dt.year, dt.month) AS mrr_change,
    SUM(fb.discount_amount) AS total_discounts
FROM warehouse.fact_billing fb
JOIN warehouse.dim_time dt ON fb.date_id = dt.date_id
GROUP BY dt.year, dt.month;
CREATE UNIQUE INDEX idx_kpi_revenue ON semantic.kpi_revenue(year, month);
"""


def upgrade() -> None:
    """Create feature store, registries, and semantic materialized views."""
    _exec(FEATURE_STORE_DDL)
    _exec(REGISTRY_DDL)
    _exec(SEMANTIC_VIEW_DDL)


def downgrade() -> None:
    """Drop semantic views and tables (destructive)."""
    op.execute("DROP MATERIALIZED VIEW IF EXISTS semantic.kpi_revenue")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS semantic.kpi_arpu")
    for table in ("prediction_registry", "model_registry"):
        op.execute(f"DROP TABLE IF EXISTS ml.{table}")
    op.execute("DROP TABLE IF EXISTS semantic.metric_registry")
    for table in ("package_features", "churn_features", "customer_features", "feature_registry"):
        op.execute(f"DROP TABLE IF EXISTS feature_store.{table}")
