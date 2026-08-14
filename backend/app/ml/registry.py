"""Model Registry — persistence of trained models and their metadata.

Stores model records in ml.model_registry (03_DATABASE.md §8.2) and
serialized model artifacts on disk (MVP; MinIO in Phase 3).
"""

import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import joblib
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ARTIFACT_DIR = Path(__file__).resolve().parent.parent / "data" / "models"


async def register_model(
    engine: AsyncEngine,
    *,
    model_name: str,
    algorithm: str,
    model: Any,
    metrics: dict[str, Any],
    dataset_id: str,
    feature_version: str,
    hyperparameters: dict[str, Any] | None = None,
    random_seed: int = 42,
    training_time_sec: float = 0.0,
) -> dict[str, Any]:
    """Persist a trained model + metadata to the registry."""
    model_version = f"v{time.strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:4]}"

    # Serialize artifact
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_path = ARTIFACT_DIR / f"{model_name}_{model_version}.joblib"
    joblib.dump(model, artifact_path)
    framework_version = _framework_version(algorithm)

    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                INSERT INTO ml.model_registry (
                    model_name, model_version, model_type, algorithm, artifact_path,
                    training_dataset_id, feature_version, evaluation_report,
                    hyperparameters, random_seed, training_time_sec,
                    framework_version, status
                ) VALUES (
                    :name, :version, 'churn_prediction', :algorithm, :artifact,
                    :dataset_id, :feature_version, :evaluation,
                    :hyperparameters, :seed, :training_sec, :framework, 'development'
                )
                RETURNING model_id
                """
            ),
            {
                "name": model_name,
                "version": model_version,
                "algorithm": algorithm,
                "artifact": str(artifact_path),
                "dataset_id": dataset_id,
                "feature_version": feature_version,
                "evaluation": json.dumps(metrics),
                "hyperparameters": json.dumps(hyperparameters or {}),
                "seed": random_seed,
                "training_sec": int(training_time_sec),
                "framework": framework_version,
            },
        )
        row = result.fetchone()
        if row is not None:
            model_id = int(row[0])

    return {
        "model_id": model_id,
        "model_name": model_name,
        "model_version": model_version,
        "algorithm": algorithm,
        "metrics": metrics,
        "artifact_path": str(artifact_path),
    }


async def promote_model(engine: AsyncEngine, model_id: int) -> bool:
    """Promote a model to production (archives the current production model)."""
    async with engine.begin() as conn:
        # Archive current production model for this type
        await conn.execute(
            text(
                """
                UPDATE ml.model_registry SET status = 'archived'
                WHERE status = 'production' AND model_type = 'churn_prediction'
                """
            )
        )
        result = await conn.execute(
            text(
                """
                UPDATE ml.model_registry SET status = 'production', promoted_at = now()
                WHERE model_id = :id
                RETURNING model_id
                """
            ),
            {"id": model_id},
        )
        return result.fetchone() is not None


async def get_production_model(engine: AsyncEngine) -> dict[str, Any] | None:
    """Load the production churn model + artifact for inference."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT model_id, model_name, model_version, algorithm, artifact_path,
                       feature_version
                FROM ml.model_registry
                WHERE status = 'production' AND model_type = 'churn_prediction'
                ORDER BY promoted_at DESC LIMIT 1
                """
            )
        )
        row = result.fetchone()
    if row is None:
        return None

    model = joblib.load(row[4])
    return {
        "model_id": row[0],
        "model_name": row[1],
        "model_version": row[2],
        "algorithm": row[3],
        "artifact_path": row[4],
        "feature_version": row[5],
        "model": model,
    }


def _framework_version(algorithm: str) -> str:
    """Return the framework version for a given algorithm."""
    versions: dict[str, str] = {
        "logistic_regression": "scikit-learn",
        "random_forest": "scikit-learn",
        "xgboost": "xgboost",
        "lightgbm": "lightgbm",
        "catboost": "catboost",
    }
    return versions.get(algorithm, "unknown")
