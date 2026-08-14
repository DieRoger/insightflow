"""Churn prediction model training — benchmark 5 algorithms.

Trains Logistic Regression, Random Forest, XGBoost, LightGBM, and
CatBoost on the churn dataset, evaluates each, and persists the best
model to the Model Registry (03_DATABASE.md §8.2).

Usage:
    uv run python -m app.ml.train
"""

import asyncio
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Any, Protocol  # noqa: E402

from catboost import CatBoostClassifier  # noqa: E402
from lightgbm import LGBMClassifier  # noqa: E402

# LightGBM / XGBoost / CatBoost are hard deps (in pyproject.toml)
from xgboost import XGBClassifier  # noqa: E402

from app.ml.dataset import Dataset, build_churn_dataset  # noqa: E402


class Classifier(Protocol):
    """Structural interface for sklearn-compatible classifiers."""

    def fit(self, X: Any, y: Any) -> "Classifier": ...
    def predict(self, X: Any) -> np.ndarray: ...
    def predict_proba(self, X: Any) -> np.ndarray: ...


def build_models(seed: int = 42) -> dict[str, Classifier]:
    """Instantiate the candidate model zoo."""
    models: dict[str, Classifier] = {
        "logistic_regression": LogisticRegression(max_iter=1000, random_state=seed),
        "random_forest": RandomForestClassifier(
            n_estimators=200, max_depth=8, random_state=seed, n_jobs=-1
        ),
    }
    if XGBClassifier is not None:
        models["xgboost"] = XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            random_state=seed,
            eval_metric="logloss",
        )
    if LGBMClassifier is not None:
        models["lightgbm"] = LGBMClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.05, random_state=seed, verbose=-1
        )
    if CatBoostClassifier is not None:
        models["catboost"] = CatBoostClassifier(
            iterations=200, depth=6, learning_rate=0.05, random_state=seed, verbose=False
        )
    return models


def evaluate_model(model: Classifier, X_val: np.ndarray, y_val: np.ndarray) -> dict[str, float]:
    """Evaluate a fitted model on validation data."""
    y_pred = model.predict(X_val)
    y_proba = model.predict_proba(X_val)[:, 1] if hasattr(model, "predict_proba") else y_pred
    return {
        "accuracy": float(accuracy_score(y_val, y_pred)),
        "precision": float(precision_score(y_val, y_pred, zero_division=0)),
        "recall": float(recall_score(y_val, y_pred, zero_division=0)),
        "f1_score": float(f1_score(y_val, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_val, y_proba)),
    }


async def train_and_evaluate(engine: Any) -> list[dict[str, Any]]:
    """Train all models, return per-model evaluation records."""
    from app.core.logging import get_logger

    logger = get_logger(__name__)
    dataset: Dataset = await build_churn_dataset(engine)
    X_train = dataset.X_train.to_numpy()
    y_train = dataset.y_train.to_numpy()
    X_val = dataset.X_val.to_numpy()
    y_val = dataset.y_val.to_numpy()

    records: list[dict[str, Any]] = []
    for name, model in build_models().items():
        started = time.perf_counter()
        logger.info("model_training_start", model=name)
        model.fit(X_train, y_train)
        metrics = evaluate_model(model, X_val, y_val)
        elapsed = time.perf_counter() - started
        logger.info(
            "model_training_complete",
            model=name,
            f1=round(metrics["f1_score"], 4),
            roc_auc=round(metrics["roc_auc"], 4),
            duration_sec=round(elapsed, 2),
        )
        records.append(
            {
                "model_name": f"churn_{name}",
                "algorithm": name,
                "metrics": metrics,
                "training_time_sec": round(elapsed, 2),
                "dataset_id": dataset.dataset_id,
                "feature_version": dataset.feature_version,
                "random_seed": 42,
                "model": model,
            }
        )
    return records


async def main() -> None:
    from app.infrastructure.database.session import engine

    records = await train_and_evaluate(engine)
    print("\n=== Model Benchmark ===")
    print(f"{'Model':<22} {'ROC-AUC':>8} {'F1':>8} {'Prec':>8} {'Rec':>8} {'Time(s)':>8}")
    for r in records:
        m = r["metrics"]
        print(
            f"{r['model_name']:<22} {m['roc_auc']:>8.4f} {m['f1_score']:>8.4f} "
            f"{m['precision']:>8.4f} {m['recall']:>8.4f} {r['training_time_sec']:>8.2f}"
        )
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
