"""Integration test for the full ML pipeline (dataset → train → deploy).

Runs against the real feature store + registry in PostgreSQL. Models train
quickly on the mock dataset (~10s total).
"""

import pytest

from app.infrastructure.database.session import engine
from app.ml.dataset import build_churn_dataset
from app.ml.registry import get_production_model

pytestmark = pytest.mark.integration


class TestMLPipeline:
    async def test_build_dataset_returns_splits(self) -> None:
        """Dataset construction yields labeled, stratified splits."""
        dataset = await build_churn_dataset(engine)
        assert dataset.n_samples > 100
        assert dataset.churn_rate > 0.01
        assert len(dataset.X_train) + len(dataset.X_val) + len(dataset.X_test) == dataset.n_samples
        # Feature columns match the expected set
        assert set(dataset.X_train.columns) == set(
            [
                "tenure_days",
                "customer_age",
                "contract_duration_months",
                "is_postpaid",
                "is_prepaid",
                "avg_daily_data_mb",
                "avg_daily_voice_min",
                "weekend_usage_ratio",
                "night_usage_ratio",
                "peak_usage_ratio",
                "roaming_ratio",
                "international_ratio",
                "arpu",
                "revenue_trend",
                "discount_ratio",
                "payment_delay_avg",
                "overdue_count",
                "drop_rate_avg",
                "latency_avg_ms",
                "coverage_score_avg",
                "complaint_frequency",
                "network_complaint_ratio",
                "billing_complaint_ratio",
                "avg_resolution_time_min",
                "avg_waiting_time_min",
                "csat_avg",
                "escalation_frequency",
                "promotion_response_rate",
                "days_since_last_complaint",
                "days_since_last_campaign",
                "is_heavy_user",
                "is_premium",
            ]
        )

    async def test_production_model_loaded_and_predicts(self) -> None:
        """The deployed production model loads and makes predictions."""
        production = await get_production_model(engine)
        assert production is not None
        model = production["model"]
        # Predict on a random 5-row feature sample
        dataset = await build_churn_dataset(engine)
        sample = dataset.X_test.head(5).to_numpy()
        probabilities = model.predict_proba(sample)[:, 1]
        assert len(probabilities) == 5
        assert all(0.0 <= p <= 1.0 for p in probabilities)

    async def test_train_evaluate_register_cycle(self) -> None:
        """Full train → evaluate → register → promote cycle works."""
        from sqlalchemy import text

        from app.ml.registry import promote_model, register_model
        from app.ml.train import train_and_evaluate

        records = await train_and_evaluate(engine)
        assert len(records) >= 4  # at least 4 algorithms (catboost may vary)
        best = max(records, key=lambda r: (r["metrics"]["roc_auc"], r["metrics"]["f1_score"]))

        registered = await register_model(
            engine,
            model_name=f"churn_cycle_{best['algorithm']}",
            algorithm=best["algorithm"],
            model=best["model"],
            metrics=best["metrics"],
            dataset_id=best["dataset_id"],
            feature_version=best["feature_version"],
            random_seed=best["random_seed"],
            training_time_sec=best["training_time_sec"],
        )
        assert registered["model_id"] > 0
        promoted = await promote_model(engine, registered["model_id"])
        assert promoted is True

        # Restore the original production model (churn_cycle_* is a temp model)
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE ml.model_registry SET status = 'production', promoted_at = now() "
                    "WHERE model_name = 'churn_logistic_regression' AND model_version LIKE 'v2026%' "
                    "AND model_id <> :temp_id"
                ),
                {"temp_id": registered["model_id"]},
            )
            await conn.execute(
                text("DELETE FROM ml.model_registry WHERE model_id = :temp_id"),
                {"temp_id": registered["model_id"]},
            )
