"""Silver loader — transform raw.* (Bronze) into warehouse.* (Silver).

Per 03_DATABASE.md §5: validates, deduplicates, resolves keys, and loads
the Star Schema. Dimension tables are upserted; fact tables are loaded
with FK references to dimension surrogate keys.

Pipeline:
  raw_customer → dim_customer, dim_package, dim_region
  raw_usage    → fact_usage_daily
  raw_billing  → fact_billing
  raw_network  → fact_network
  raw_service  → fact_service
  raw_campaign → fact_campaign
"""

import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.logging import get_logger

logger = get_logger(__name__)

CHUNK = 5000


async def _fetch_customer_map(engine: AsyncEngine) -> dict[str, int]:
    """Build source_customer_id → surrogate customer_id map."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT source_customer_id, customer_id FROM warehouse.dim_customer")
        )
        rows = result.fetchall()
    return {r[0]: r[1] for r in rows}


async def load_dimensions(engine: AsyncEngine) -> None:
    """Load dim_customer, dim_package, dim_region from raw_customer."""
    started = time.perf_counter()

    # --- dim_package: distinct packages ---
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO warehouse.dim_package
                    (source_package_id, package_name, package_type, monthly_price)
                SELECT DISTINCT
                    package_id, package_name,
                    CASE
                        WHEN package_name LIKE '%Premium%' OR package_name LIKE '%Pro%' THEN 'premium'
                        WHEN package_name LIKE '%Family%' THEN 'family'
                        WHEN package_name LIKE '%Bundle%' THEN 'bundle'
                        WHEN package_name LIKE '%Data%' THEN 'data_only'
                        ELSE 'voice_only'
                    END,
                    0
                FROM raw.raw_customer
                ON CONFLICT (source_package_id) DO NOTHING
                """
            )
        )
        await conn.execute(
            text(
                """
                UPDATE warehouse.dim_package dp
                SET monthly_price = COALESCE(
                    (SELECT MAX(fb.package_price) FROM raw.raw_billing fb
                     JOIN warehouse.dim_customer dc ON fb.customer_id = dc.source_customer_id
                     WHERE dc.package_id = dp.package_id), dp.monthly_price)
                WHERE dp.monthly_price = 0
                """
            )
        )

    # --- dim_region: distinct city/province → region mapping ---
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO warehouse.dim_region (region_name, province, city)
                SELECT
                    CASE
                        WHEN province IN ('Shanghai','Jiangsu','Zhejiang') THEN 'East'
                        WHEN province = 'Guangdong' THEN 'South'
                        WHEN province IN ('Beijing','Hebei') THEN 'North'
                        WHEN province IN ('Sichuan','Chongqing','Yunnan') THEN 'West'
                        ELSE 'Central'
                    END,
                    province,
                    city
                FROM (SELECT DISTINCT city, province FROM raw.raw_customer) d
                ON CONFLICT DO NOTHING
                """
            )
        )

    # --- dim_customer: full snapshot from raw_customer ---
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO warehouse.dim_customer
                    (source_customer_id, gender, age, city, province, region_id,
                     join_date, contract_type, package_id, status, lifecycle_stage)
                SELECT
                    rc.customer_id,
                    NULLIF(rc.gender, ''),
                    NULLIF(rc.age::int, NULL),
                    NULLIF(rc.city, ''),
                    NULLIF(rc.province, ''),
                    dr.region_id,
                    rc.join_date::date,
                    rc.contract_type,
                    dp.package_id,
                    rc.status,
                    CASE WHEN rc.status = 'churned' THEN 'churned'
                         WHEN CURRENT_DATE - rc.join_date::date <= 90 THEN 'new'
                         ELSE 'active' END
                FROM raw.raw_customer rc
                LEFT JOIN warehouse.dim_package dp ON rc.package_id = dp.source_package_id
                LEFT JOIN warehouse.dim_region dr
                    ON dr.city = rc.city AND dr.province = rc.province
                ON CONFLICT (source_customer_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    gender = EXCLUDED.gender,
                    package_id = EXCLUDED.package_id,
                    updated_at = now()
                """
            )
        )

    elapsed = time.perf_counter() - started
    logger.info("etl_silver_dimensions_complete", duration_sec=round(elapsed, 2))


async def load_facts(engine: AsyncEngine) -> None:
    """Load all fact tables from raw.* using resolved dimension keys."""
    started = time.perf_counter()

    # fact_usage_daily
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO warehouse.fact_usage_daily
                    (customer_id, package_id, region_id, date_id, voice_minutes, sms_count,
                     data_usage_mb, roaming_usage_mb, peak_usage_mb, international_minutes)
                SELECT
                    dc.customer_id, dp.package_id, dc.region_id, dt.date_id,
                    ru.voice_minutes,
                    ru.sms_count,
                    ru.data_usage_mb,
                    ru.roaming_usage_mb,
                    ru.peak_usage_mb,
                    ru.international_minutes
                FROM raw.raw_usage ru
                JOIN warehouse.dim_customer dc ON ru.customer_id = dc.source_customer_id
                JOIN warehouse.dim_package dp ON dc.package_id = dp.package_id
                JOIN warehouse.dim_time dt ON ru.usage_date::date = dt.full_date
                """
            )
        )

    # fact_billing
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO warehouse.fact_billing
                    (customer_id, package_id, date_id, billing_month, monthly_fee,
                     discount_amount, net_revenue, payment_status, overdue_days, package_price)
                SELECT
                    dc.customer_id, dp.package_id, dt.date_id, rb.billing_month::date,
                    rb.monthly_fee,
                    COALESCE(rb.discount_amount, 0),
                    rb.monthly_fee - COALESCE(rb.discount_amount, 0),
                    rb.payment_status,
                    COALESCE(rb.overdue_days, 0),
                    rb.package_price
                FROM raw.raw_billing rb
                JOIN warehouse.dim_customer dc ON rb.customer_id = dc.source_customer_id
                JOIN warehouse.dim_package dp ON dc.package_id = dp.package_id
                JOIN warehouse.dim_time dt ON rb.billing_month::date = dt.full_date
                """
            )
        )

    # fact_network
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO warehouse.fact_network
                    (customer_id, region_id, date_id, latency_ms, signal_strength,
                     drop_rate, packet_loss, coverage_score)
                SELECT
                    dc.customer_id, dc.region_id, dt.date_id,
                    rn.latency_ms,
                    rn.signal_strength,
                    rn.drop_rate,
                    rn.packet_loss,
                    rn.coverage_score
                FROM raw.raw_network rn
                JOIN warehouse.dim_customer dc ON rn.customer_id = dc.source_customer_id
                JOIN warehouse.dim_time dt ON rn.measurement_date::date = dt.full_date
                """
            )
        )

    # fact_service
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO warehouse.fact_service
                    (customer_id, date_id, ticket_count, complaint_type,
                     waiting_time_min, resolution_time_min, csat_score, escalation_count)
                SELECT
                    dc.customer_id, dt.date_id, rs.ticket_count,
                    NULLIF(rs.complaint_type, ''),
                    rs.waiting_time_min,
                    rs.resolution_time_min,
                    rs.csat_score,
                    COALESCE(rs.escalation_count, 0)
                FROM raw.raw_service rs
                JOIN warehouse.dim_customer dc ON rs.customer_id = dc.source_customer_id
                JOIN warehouse.dim_time dt ON rs.ticket_date::date = dt.full_date
                """
            )
        )

    # fact_campaign
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO warehouse.fact_campaign
                    (customer_id, campaign_id, date_id, promotion_type,
                     coupon_used, converted, channel, campaign_cost)
                SELECT
                    dc.customer_id, rc.campaign_id, dt.date_id,
                    NULLIF(rc.promotion_type, ''),
                    rc.coupon_used,
                    rc.converted,
                    NULLIF(rc.channel, ''),
                    rc.campaign_cost
                FROM raw.raw_campaign rc
                JOIN warehouse.dim_customer dc ON rc.customer_id = dc.source_customer_id
                JOIN warehouse.dim_time dt ON rc.campaign_date::date = dt.full_date
                """
            )
        )

    elapsed = time.perf_counter() - started
    logger.info("etl_silver_facts_complete", duration_sec=round(elapsed, 2))


async def refresh_semantic_views(engine: AsyncEngine) -> None:
    """Refresh materialized views concurrently."""
    async with engine.begin() as conn:
        await conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY semantic.kpi_arpu"))
        await conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY semantic.kpi_revenue"))
    logger.info("semantic_views_refreshed")
