"""Churn prediction service — online + batch prediction with explanations.

Per 05_API_SPEC §8: online predict returns risk score, level, top factors,
confidence; batch predict is async (202 + task_id).
"""

import json
import sys
import uuid
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.logging import get_logger  # noqa: E402
from app.ml.dataset import FEATURE_COLUMNS  # noqa: E402
from app.ml.explain import explain_prediction  # noqa: E402
from app.ml.registry import get_production_model  # noqa: E402

logger = get_logger(__name__)

HIGH_THRESHOLD = 0.7
MEDIUM_THRESHOLD = 0.3


def classify_risk(score: float) -> str:
    """Map a probability to LOW/MEDIUM/HIGH (matches core constants)."""
    if score >= HIGH_THRESHOLD:
        return "HIGH"
    if score >= MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


async def predict_customer(engine: AsyncEngine, source_customer_id: str) -> dict[str, Any] | None:
    """Online prediction for a single customer (05_API_SPEC §8.2)."""
    production = await get_production_model(engine)
    if production is None:
        raise RuntimeError("No production churn model registered")

    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT cf.customer_id FROM feature_store.customer_features cf "
                "JOIN warehouse.dim_customer dc ON cf.customer_id = dc.customer_id "
                "WHERE dc.source_customer_id = :sid LIMIT 1"
            ),
            {"sid": source_customer_id},
        )
        row = result.fetchone()
        if row is None:
            return None
        customer_id = row[0]

        # Features for this customer
        feat_cols = ", ".join(FEATURE_COLUMNS)
        feat_result = await conn.execute(
            text(
                f"SELECT {feat_cols} FROM feature_store.customer_features WHERE customer_id = :cid"
            ),
            {"cid": customer_id},
        )
        feat_row = feat_result.fetchone()
        if feat_row is None:
            return None
        features = np.array([float(v) if v is not None else 0.0 for v in feat_row])

    model = production["model"]
    probability = float(model.predict_proba(features.reshape(1, -1))[0][1])

    # Background sample for SHAP: draw a representative set from the
    # feature store so explanations reflect population-level baselines.
    X_background = await _load_background(engine, sample_size=100)

    explanation = explain_prediction(model, X_background, features)

    prediction = {
        "prediction_id": f"pred_{uuid.uuid4().hex[:10]}",
        "customer_id": source_customer_id,
        "risk_score": round(probability, 4),
        "risk_level": classify_risk(probability),
        "top_positive_factors": explanation["top_positive_factors"],
        "top_negative_factors": explanation["top_negative_factors"],
        "confidence": round(min(0.5 + probability, 0.95), 4),
        "model_version": production["model_version"],
        "shap_available": True,
    }
    await _persist_prediction(engine, customer_id, production, prediction)
    return prediction


async def _load_background(engine: AsyncEngine, sample_size: int = 100) -> np.ndarray:
    """Load a random background sample of features for SHAP baselines."""
    feat_cols = ", ".join(FEATURE_COLUMNS)
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                f"SELECT {feat_cols} FROM feature_store.customer_features "
                "WHERE feature_version = 'v1.0.0' ORDER BY random() LIMIT :limit"
            ),
            {"limit": sample_size},
        )
        rows = result.fetchall()
    if not rows:
        return np.zeros((1, len(FEATURE_COLUMNS)))
    return np.array([[float(v) if v is not None else 0.0 for v in row] for row in rows])


async def _persist_prediction(
    engine: AsyncEngine, customer_id: int, production: dict[str, Any], prediction: dict[str, Any]
) -> None:
    """Store the prediction in ml.prediction_registry for auditability."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO ml.prediction_registry (
                    customer_id, model_id, feature_version, risk_score, risk_level,
                    top_positive_factors, top_negative_factors, confidence,
                    prediction_type
                ) VALUES (
                    :customer_id, :model_id, :feature_version, :risk_score, :risk_level,
                    :positive, :negative, :confidence, 'online'
                )
                """
            ),
            {
                "customer_id": customer_id,
                "model_id": production["model_id"],
                "feature_version": production.get("feature_version", "v1.0.0"),
                "risk_score": prediction["risk_score"],
                "risk_level": prediction["risk_level"],
                "positive": json.dumps(prediction["top_positive_factors"]),
                "negative": json.dumps(prediction["top_negative_factors"]),
                "confidence": prediction["confidence"],
            },
        )


async def predict_batch(engine: AsyncEngine) -> int:
    """Batch prediction for all customers. Returns count processed."""
    production = await get_production_model(engine)
    if production is None:
        raise RuntimeError("No production churn model registered")
    model = production["model"]

    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                f"SELECT customer_id, {', '.join(FEATURE_COLUMNS)} "
                "FROM feature_store.customer_features WHERE feature_version = 'v1.0.0'"
            )
        )
        rows = result.fetchall()

    count = 0
    for row in rows:
        customer_id = row[0]
        features = np.array([float(v) if v is not None else 0.0 for v in row[1:]])
        probability = float(model.predict_proba(features.reshape(1, -1))[0][1])
        risk_level = classify_risk(probability)
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO ml.prediction_registry (
                        customer_id, model_id, feature_version, risk_score,
                        risk_level, confidence, prediction_type
                    ) VALUES (:cid, :mid, 'v1.0.0', :score, :level, :conf, 'batch')
                    """
                ),
                {
                    "cid": customer_id,
                    "mid": production["model_id"],
                    "score": round(probability, 4),
                    "level": risk_level,
                    "conf": round(min(0.5 + probability, 0.95), 4),
                },
            )
        count += 1

    logger.info("batch_prediction_complete", count=count, model=production["model_version"])
    return count
