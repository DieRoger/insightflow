"""SHAP-based prediction explainability.

Every prediction must expose top contributing factors (AR-038,
02_ARCHITECTURE.md §10). Uses a background sample for tree SHAP.
"""

import sys
from pathlib import Path
from typing import Any

import numpy as np
import shap

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ml.dataset import FEATURE_COLUMNS  # noqa: E402


def explain_prediction(
    model: Any,
    X_background: np.ndarray,
    features_row: np.ndarray,
    feature_names: list[str] | None = None,
) -> dict[str, Any]:
    """Compute SHAP values for a single prediction.

    Returns { top_positive_factors, top_negative_factors, base_value }.
    """
    names = feature_names or FEATURE_COLUMNS
    if len(features_row) != len(names):
        features_row = features_row[: len(names)]

    try:
        explainer = shap.TreeExplainer(model, X_background)
    except Exception:
        # Fallback for non-tree models (linear SHAP)
        explainer = shap.Explainer(model, X_background)

    shap_values = explainer.shap_values(features_row.reshape(1, -1))
    if isinstance(shap_values, list):
        shap_values = shap_values[1]  # binary: class 1
    values = np.asarray(shap_values).flatten()

    # Feature values for reference
    paired = sorted(
        zip(names, values, features_row, strict=False),
        key=lambda t: t[1],
        reverse=True,
    )
    top_positive = [
        {
            "feature": name,
            "contribution": round(float(val), 4),
            "feature_value": _round_scalar(fvalue),
        }
        for name, val, fvalue in paired[:5]
        if val > 0
    ]
    top_negative = [
        {
            "feature": name,
            "contribution": round(float(val), 4),
            "feature_value": _round_scalar(fvalue),
        }
        for name, val, fvalue in reversed(paired[-5:])
        if val < 0
    ]

    return {
        "top_positive_factors": top_positive,
        "top_negative_factors": top_negative,
        "base_value": round(float(np.asarray(shap_values).flatten().mean()), 4),
    }


def _round_scalar(value: Any) -> float:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return 0.0
