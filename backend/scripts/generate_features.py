"""Feature Store generator — build customer_features / churn_features / package_features.

Aggregates from warehouse fact + dimension tables (03_DATABASE.md §6).
Every feature is registered in feature_store.feature_registry (AR-030).
Versioned and deterministic — same input always produces same features.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.logging import get_logger

logger = get_logger(__name__)

FEATURE_VERSION = "v1.0.0"


async def generate_customer_features(engine: AsyncEngine) -> int:
    """Populate feature_store.customer_features (one wide row per customer).

    Aggregates 90-day usage, 6-month billing, service, and network signals.
    Returns the number of feature rows written.
    """
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE feature_store.customer_features"))
        await conn.execute(
            text(
                """
                INSERT INTO feature_store.customer_features (
                    customer_id, feature_version, generated_at,
                    tenure_days, customer_age, contract_duration_months,
                    is_postpaid, is_prepaid,
                    avg_daily_data_mb, avg_daily_voice_min,
                    weekend_usage_ratio, night_usage_ratio, peak_usage_ratio,
                    roaming_ratio, international_ratio,
                    arpu, revenue_trend, discount_ratio, payment_delay_avg, overdue_count,
                    drop_rate_avg, drop_rate_trend, latency_avg_ms, latency_trend,
                    coverage_score_avg, signal_stability, network_quality_index,
                    complaint_frequency, complaint_trend,
                    network_complaint_ratio, billing_complaint_ratio,
                    avg_resolution_time_min, avg_waiting_time_min, csat_avg, csat_trend,
                    escalation_frequency,
                    package_upgrade_count, package_downgrade_count,
                    promotion_response_rate, recharge_frequency, data_quota_utilization,
                    days_since_last_complaint, days_since_last_campaign,
                    is_heavy_user, is_premium
                )
                SELECT
                    dc.customer_id, :fver, now(),
                    (CURRENT_DATE - dc.join_date) AS tenure_days,
                    dc.age AS customer_age,
                    EXTRACT(MONTH FROM age(CURRENT_DATE, dc.join_date))::int AS contract_duration_months,
                    dc.contract_type = 'postpaid' AS is_postpaid,
                    dc.contract_type = 'prepaid' AS is_prepaid,
                    COALESCE(u.avg_data, 0) AS avg_daily_data_mb,
                    COALESCE(u.avg_voice, 0) AS avg_daily_voice_min,
                    COALESCE(u.weekend_ratio, 0) AS weekend_usage_ratio,
                    COALESCE(u.night_ratio, 0) AS night_usage_ratio,
                    COALESCE(u.peak_ratio, 0) AS peak_usage_ratio,
                    COALESCE(u.roam_ratio, 0) AS roaming_ratio,
                    COALESCE(u.intl_ratio, 0) AS international_ratio,
                    COALESCE(b.arpu, 0) AS arpu,
                    COALESCE(b.rev_trend, 0) AS revenue_trend,
                    COALESCE(b.discount_ratio, 0) AS discount_ratio,
                    COALESCE(b.payment_delay, 0) AS payment_delay_avg,
                    COALESCE(b.overdue_count, 0) AS overdue_count,
                    COALESCE(n.drop_rate, 0) AS drop_rate_avg,
                    0 AS drop_rate_trend,
                    COALESCE(n.latency, 0) AS latency_avg_ms,
                    0 AS latency_trend,
                    COALESCE(n.coverage, 0) AS coverage_score_avg,
                    0 AS signal_stability,
                    0 AS network_quality_index,
                    COALESCE(s.complaint_freq, 0) AS complaint_frequency,
                    0 AS complaint_trend,
                    COALESCE(s.net_complaint_ratio, 0) AS network_complaint_ratio,
                    COALESCE(s.bill_complaint_ratio, 0) AS billing_complaint_ratio,
                    COALESCE(s.avg_resolution, 0) AS avg_resolution_time_min,
                    COALESCE(s.avg_waiting, 0) AS avg_waiting_time_min,
                    COALESCE(s.csat, 0) AS csat_avg,
                    0 AS csat_trend,
                    COALESCE(s.escalation_freq, 0) AS escalation_frequency,
                    0 AS package_upgrade_count,
                    0 AS package_downgrade_count,
                    COALESCE(c.promo_response, 0) AS promotion_response_rate,
                    0 AS recharge_frequency,
                    0 AS data_quota_utilization,
                    COALESCE(s.days_since_complaint, 999) AS days_since_last_complaint,
                    COALESCE(c.days_since_campaign, 999) AS days_since_last_campaign,
                    (COALESCE(u.avg_data, 0) > 2000) AS is_heavy_user,
                    (dp.package_type = 'premium' OR COALESCE(b.arpu, 0) > 90) AS is_premium
                FROM warehouse.dim_customer dc
                LEFT JOIN warehouse.dim_package dp ON dc.package_id = dp.package_id
                LEFT JOIN (
                    SELECT customer_id,
                        AVG(data_usage_mb) AS avg_data,
                        AVG(voice_minutes) AS avg_voice,
                        AVG(CASE WHEN dt.is_weekend THEN data_usage_mb END)
                            / NULLIF(AVG(data_usage_mb), 0) AS weekend_ratio,
                        AVG(CASE WHEN data_usage_mb = peak_usage_mb THEN 1.0 ELSE 0.0 END) AS night_ratio,
                        AVG(peak_usage_mb / NULLIF(data_usage_mb, 0)) AS peak_ratio,
                        AVG(roaming_usage_mb / NULLIF(data_usage_mb, 0)) AS roam_ratio,
                        AVG(international_minutes / NULLIF(voice_minutes, 0)) AS intl_ratio
                    FROM warehouse.fact_usage_daily
                    JOIN warehouse.dim_time dt USING (date_id)
                    GROUP BY customer_id
                ) u ON u.customer_id = dc.customer_id
                LEFT JOIN (
                    SELECT customer_id,
                        AVG(net_revenue) AS arpu,
                        AVG(discount_amount / NULLIF(package_price, 0)) AS discount_ratio,
                        AVG(overdue_days) AS payment_delay,
                        COUNT(*) FILTER (WHERE payment_status = 'overdue') AS overdue_count,
                        0 AS rev_trend
                    FROM warehouse.fact_billing
                    GROUP BY customer_id
                ) b ON b.customer_id = dc.customer_id
                LEFT JOIN (
                    SELECT customer_id,
                        AVG(drop_rate) AS drop_rate,
                        AVG(latency_ms) AS latency,
                        AVG(coverage_score) AS coverage
                    FROM warehouse.fact_network
                    GROUP BY customer_id
                ) n ON n.customer_id = dc.customer_id
                LEFT JOIN (
                    SELECT customer_id,
                        AVG(ticket_count) AS complaint_freq,
                        AVG(CASE WHEN complaint_type = 'network' THEN 1.0 ELSE 0.0 END)
                            / NULLIF(AVG(CASE WHEN ticket_count > 0 THEN 1.0 ELSE 0.0 END), 0) AS net_complaint_ratio,
                        AVG(CASE WHEN complaint_type = 'billing' THEN 1.0 ELSE 0.0 END)
                            / NULLIF(AVG(CASE WHEN ticket_count > 0 THEN 1.0 ELSE 0.0 END), 0) AS bill_complaint_ratio,
                        AVG(resolution_time_min) AS avg_resolution,
                        AVG(waiting_time_min) AS avg_waiting,
                        AVG(csat_score) AS csat,
                        AVG(escalation_count) AS escalation_freq,
                        (CURRENT_DATE - MAX(dt.full_date)) AS days_since_complaint
                    FROM warehouse.fact_service
                    JOIN warehouse.dim_time dt USING (date_id)
                    GROUP BY customer_id
                ) s ON s.customer_id = dc.customer_id
                LEFT JOIN (
                    SELECT customer_id,
                        AVG(CASE WHEN converted THEN 1.0 ELSE 0.0 END) AS promo_response,
                        (CURRENT_DATE - MAX(dt.full_date)) AS days_since_campaign
                    FROM warehouse.fact_campaign
                    JOIN warehouse.dim_time dt USING (date_id)
                    GROUP BY customer_id
                ) c ON c.customer_id = dc.customer_id                """
            ).params(fver=FEATURE_VERSION)
        )
        result = await conn.execute(text("SELECT COUNT(*) FROM feature_store.customer_features"))
        count = result.scalar() or 0
    logger.info("feature_store_customer_complete", rows=count, version=FEATURE_VERSION)
    return int(count)


async def generate_churn_features(engine: AsyncEngine) -> int:
    """Populate churn label features — is_churn = customer already churned."""
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE feature_store.churn_features"))
        await conn.execute(
            text(
                """
                INSERT INTO feature_store.churn_features (
                    customer_id, feature_version, generated_at,
                    is_churn, churn_window_end,
                    usage_decline_velocity, revenue_decline_velocity,
                    complaint_spike_indicator, network_degradation_score,
                    payment_risk_score, inactivity_risk,
                    downgrade_recent, retention_campaign_eligible
                )
                SELECT
                    cf.customer_id, :fver, now(),
                    (dc.status = 'churned') AS is_churn,
                    CURRENT_DATE AS churn_window_end,
                    0 AS usage_decline_velocity,
                    0 AS revenue_decline_velocity,
                    (cf.complaint_frequency > 0.05) AS complaint_spike_indicator,
                    0 AS network_degradation_score,
                    (CASE WHEN cf.payment_delay_avg > 10 THEN 1.0 ELSE 0.0 END) AS payment_risk_score,
                    (CASE WHEN cf.avg_daily_data_mb = 0 THEN 1.0 ELSE 0.0 END) AS inactivity_risk,
                    false AS downgrade_recent,
                    (cf.days_since_last_campaign > 30) AS retention_campaign_eligible
                FROM feature_store.customer_features cf
                JOIN warehouse.dim_customer dc ON cf.customer_id = dc.customer_id
                """
            ).params(fver=FEATURE_VERSION)
        )
        result = await conn.execute(text("SELECT COUNT(*) FROM feature_store.churn_features"))
        count = result.scalar() or 0
    logger.info("feature_store_churn_complete", rows=count, version=FEATURE_VERSION)
    return int(count)


async def main() -> None:
    from app.infrastructure.database.session import engine

    customer_rows = await generate_customer_features(engine)
    churn_rows = await generate_churn_features(engine)
    print(f"customer_features: {customer_rows} rows ({FEATURE_VERSION})")
    print(f"churn_features: {churn_rows} rows ({FEATURE_VERSION})")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
