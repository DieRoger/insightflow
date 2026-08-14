"""Integration tests for the Model Registry against real PostgreSQL."""

import pytest
from sklearn.linear_model import LogisticRegression

from app.infrastructure.database.session import engine
from app.ml.registry import (
    get_production_model,
    promote_model,
    register_model,
)

pytestmark = pytest.mark.integration

# Model registry test names — cleaned before/after to avoid interference
TEST_MODELS = ("churn_test_model", "churn_archive_test")


@pytest.fixture(autouse=True)
async def clean_test_models():
    """Remove test models and restore the real production model after each test."""
    from sqlalchemy import text

    placeholders = ", ".join(f"'{m}'" for m in TEST_MODELS)
    async with engine.begin() as conn:
        # Remember the real production model before test interference
        result = await conn.execute(
            text(
                "SELECT model_id FROM ml.model_registry "
                "WHERE status = 'production' AND model_type = 'churn_prediction' "
                f"AND model_name NOT IN ({placeholders}) ORDER BY promoted_at DESC LIMIT 1"
            )
        )
        row = result.fetchone()
        production_id = int(row[0]) if row else None

        await conn.execute(
            text(f"DELETE FROM ml.model_registry WHERE model_name IN ({placeholders})")
        )
    yield
    async with engine.begin() as conn:
        await conn.execute(
            text(f"DELETE FROM ml.model_registry WHERE model_name IN ({placeholders})")
        )
        # Restore the real production model so downstream tests still work
        if production_id is not None:
            await conn.execute(
                text(
                    "UPDATE ml.model_registry SET status = 'production', promoted_at = now() "
                    "WHERE model_id = :id AND status <> 'production'"
                ),
                {"id": production_id},
            )


class TestModelRegistry:
    async def test_register_promote_load_cycle(self) -> None:
        """Full registry cycle: register → promote → load."""
        model = LogisticRegression(max_iter=100)

        registered = await register_model(
            engine,
            model_name="churn_test_model",
            algorithm="logistic_regression",
            model=model,
            metrics={"roc_auc": 0.9, "f1_score": 0.8},
            dataset_id="ds_test",
            feature_version="v1.0.0",
            random_seed=42,
            training_time_sec=0.5,
        )
        assert registered["model_name"] == "churn_test_model"
        assert registered["model_version"].startswith("v")
        assert registered["model_id"] > 0
        assert "metrics" in registered

        promoted = await promote_model(engine, registered["model_id"])
        assert promoted is True

        production = await get_production_model(engine)
        assert production is not None
        assert production["model_name"] == "churn_test_model"
        # Loaded artifact is a usable classifier
        assert hasattr(production["model"], "predict")

    async def test_promote_archives_previous(self) -> None:
        """Promoting a new model archives the previous production model."""
        model = LogisticRegression(max_iter=100)
        first = await register_model(
            engine,
            model_name="churn_archive_test",
            algorithm="logistic_regression",
            model=model,
            metrics={"roc_auc": 0.7},
            dataset_id="ds_test",
            feature_version="v1.0.0",
        )
        await promote_model(engine, first["model_id"])

        second = await register_model(
            engine,
            model_name="churn_archive_test",
            algorithm="logistic_regression",
            model=model,
            metrics={"roc_auc": 0.95},
            dataset_id="ds_test",
            feature_version="v1.0.0",
        )
        await promote_model(engine, second["model_id"])

        production = await get_production_model(engine)
        assert production is not None
        assert production["model_id"] == second["model_id"]

    async def test_archiving_test_models_keeps_production(self) -> None:
        """get_production_model falls back to the real model when tests are archived."""
        from sqlalchemy import text

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE ml.model_registry SET status = 'archived' "
                    "WHERE model_type = 'churn_prediction' AND model_name IN ('churn_test_model', 'churn_archive_test')"
                )
            )
        production = await get_production_model(engine)
        # A production model must always be resolvable — the test models being
        # archived must not leave the registry without a production model.
        assert production is not None
