"""create warehouse (Silver) dimension and fact tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _exec(sql: str) -> None:
    """Execute a multi-statement DDL script statement by statement."""
    for stmt in sql.split(";"):
        if stmt.strip():
            op.execute(stmt)


DIMENSION_DDL = """
CREATE TABLE warehouse.dim_time (
    date_id INTEGER PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    year SMALLINT,
    quarter SMALLINT,
    month SMALLINT,
    week SMALLINT,
    day SMALLINT,
    day_of_week SMALLINT,
    day_name VARCHAR(10),
    is_weekend BOOLEAN,
    fiscal_year SMALLINT,
    fiscal_quarter SMALLINT
);

CREATE TABLE warehouse.dim_customer (
    customer_id INTEGER PRIMARY KEY,
    source_customer_id VARCHAR(50) NOT NULL,
    gender VARCHAR(10),
    age INTEGER,
    city VARCHAR(100),
    province VARCHAR(100),
    region_id INTEGER,
    join_date DATE NOT NULL,
    contract_type VARCHAR(30) NOT NULL,
    package_id INTEGER,
    status VARCHAR(20) NOT NULL,
    lifecycle_stage VARCHAR(30) NOT NULL DEFAULT 'new',
    segment VARCHAR(50),
    clv DECIMAL(12,2),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_dim_customer_status ON warehouse.dim_customer(status);
CREATE INDEX idx_dim_customer_segment ON warehouse.dim_customer(segment);
CREATE INDEX idx_dim_customer_lifecycle ON warehouse.dim_customer(lifecycle_stage);
CREATE INDEX idx_dim_customer_source ON warehouse.dim_customer(source_customer_id);

CREATE TABLE warehouse.dim_package (
    package_id INTEGER PRIMARY KEY,
    source_package_id VARCHAR(50) NOT NULL,
    package_name VARCHAR(100) NOT NULL,
    package_type VARCHAR(30) NOT NULL,
    monthly_price DECIMAL(10,2) NOT NULL,
    data_quota_gb DECIMAL(8,2),
    voice_quota_min INTEGER,
    sms_quota INTEGER,
    is_active BOOLEAN DEFAULT true,
    launched_date DATE,
    retired_date DATE
);

CREATE TABLE warehouse.dim_region (
    region_id INTEGER PRIMARY KEY,
    region_name VARCHAR(100) NOT NULL,
    province VARCHAR(100) NOT NULL,
    city VARCHAR(100),
    city_tier VARCHAR(10)
);
"""

FACT_DDL = """
CREATE TABLE warehouse.fact_usage_daily (
    usage_id BIGSERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    package_id INTEGER NOT NULL,
    region_id INTEGER NOT NULL,
    date_id INTEGER NOT NULL,
    voice_minutes DECIMAL(10,2),
    sms_count INTEGER,
    data_usage_mb DECIMAL(12,2),
    roaming_usage_mb DECIMAL(10,2),
    peak_usage_mb DECIMAL(10,2),
    international_minutes DECIMAL(8,2),
    created_at TIMESTAMPTZ DEFAULT now(),
    FOREIGN KEY (customer_id) REFERENCES warehouse.dim_customer(customer_id),
    FOREIGN KEY (package_id) REFERENCES warehouse.dim_package(package_id),
    FOREIGN KEY (region_id) REFERENCES warehouse.dim_region(region_id),
    FOREIGN KEY (date_id) REFERENCES warehouse.dim_time(date_id)
);
CREATE INDEX idx_fud_customer_date ON warehouse.fact_usage_daily(customer_id, date_id);
CREATE INDEX idx_fud_date ON warehouse.fact_usage_daily(date_id);
CREATE INDEX idx_fud_package_date ON warehouse.fact_usage_daily(package_id, date_id);
CREATE INDEX idx_fud_region_date ON warehouse.fact_usage_daily(region_id, date_id);

CREATE TABLE warehouse.fact_billing (
    billing_id BIGSERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    package_id INTEGER NOT NULL,
    date_id INTEGER NOT NULL,
    billing_month DATE NOT NULL,
    monthly_fee DECIMAL(10,2) NOT NULL,
    discount_amount DECIMAL(10,2),
    net_revenue DECIMAL(10,2) NOT NULL,
    payment_status VARCHAR(20) NOT NULL,
    overdue_days INTEGER,
    package_price DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    FOREIGN KEY (customer_id) REFERENCES warehouse.dim_customer(customer_id),
    FOREIGN KEY (package_id) REFERENCES warehouse.dim_package(package_id),
    FOREIGN KEY (date_id) REFERENCES warehouse.dim_time(date_id)
);
CREATE INDEX idx_fb_customer_month ON warehouse.fact_billing(customer_id, billing_month);
CREATE INDEX idx_fb_month ON warehouse.fact_billing(billing_month);
CREATE INDEX idx_fb_status ON warehouse.fact_billing(payment_status, billing_month);

CREATE TABLE warehouse.fact_network (
    network_id BIGSERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    region_id INTEGER NOT NULL,
    date_id INTEGER NOT NULL,
    latency_ms DECIMAL(8,2),
    signal_strength DECIMAL(5,2),
    drop_rate DECIMAL(5,4),
    packet_loss DECIMAL(5,4),
    coverage_score DECIMAL(5,2),
    created_at TIMESTAMPTZ DEFAULT now(),
    FOREIGN KEY (customer_id) REFERENCES warehouse.dim_customer(customer_id),
    FOREIGN KEY (region_id) REFERENCES warehouse.dim_region(region_id),
    FOREIGN KEY (date_id) REFERENCES warehouse.dim_time(date_id)
);
CREATE INDEX idx_fn_customer_date ON warehouse.fact_network(customer_id, date_id);
CREATE INDEX idx_fn_region_date ON warehouse.fact_network(region_id, date_id);

CREATE TABLE warehouse.fact_service (
    service_id BIGSERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    date_id INTEGER NOT NULL,
    ticket_count INTEGER NOT NULL,
    complaint_type VARCHAR(50),
    waiting_time_min DECIMAL(8,2),
    resolution_time_min DECIMAL(8,2),
    csat_score INTEGER,
    escalation_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT now(),
    FOREIGN KEY (customer_id) REFERENCES warehouse.dim_customer(customer_id),
    FOREIGN KEY (date_id) REFERENCES warehouse.dim_time(date_id)
);
CREATE INDEX idx_fs_customer_date ON warehouse.fact_service(customer_id, date_id);
CREATE INDEX idx_fs_type ON warehouse.fact_service(complaint_type, date_id);

CREATE TABLE warehouse.fact_campaign (
    campaign_response_id BIGSERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    campaign_id VARCHAR(50) NOT NULL,
    date_id INTEGER NOT NULL,
    promotion_type VARCHAR(50),
    coupon_used BOOLEAN,
    converted BOOLEAN,
    channel VARCHAR(30),
    campaign_cost DECIMAL(10,2),
    created_at TIMESTAMPTZ DEFAULT now(),
    FOREIGN KEY (customer_id) REFERENCES warehouse.dim_customer(customer_id),
    FOREIGN KEY (date_id) REFERENCES warehouse.dim_time(date_id)
);
CREATE INDEX idx_fc_customer_date ON warehouse.fact_campaign(customer_id, date_id);
CREATE INDEX idx_fc_campaign ON warehouse.fact_campaign(campaign_id, date_id);
CREATE INDEX idx_fc_converted ON warehouse.fact_campaign(converted, date_id);
"""


def upgrade() -> None:
    """Create warehouse dimension and fact tables."""
    _exec(DIMENSION_DDL)
    _exec(FACT_DDL)


def downgrade() -> None:
    """Drop warehouse tables in dependency order."""
    for table in (
        "fact_campaign",
        "fact_service",
        "fact_network",
        "fact_billing",
        "fact_usage_daily",
        "dim_customer",
        "dim_package",
        "dim_region",
        "dim_time",
    ):
        op.execute(f"DROP TABLE IF EXISTS warehouse.{table} CASCADE")
