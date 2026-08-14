"""Unit tests for ML module logic (risk classification, explain rounding)."""

import numpy as np

from app.ml.explain import _round_scalar
from app.ml.predict import classify_risk


class TestClassifyRisk:
    def test_high_threshold(self) -> None:
        assert classify_risk(0.91) == "HIGH"
        assert classify_risk(0.7) == "HIGH"

    def test_medium_band(self) -> None:
        assert classify_risk(0.45) == "MEDIUM"
        assert classify_risk(0.3) == "MEDIUM"

    def test_low_band(self) -> None:
        assert classify_risk(0.12) == "LOW"
        assert classify_risk(0.0) == "LOW"


class TestRoundScalar:
    def test_float_rounding(self) -> None:
        assert _round_scalar(3.14159) == 3.1416

    def test_none_value(self) -> None:
        assert _round_scalar(None) == 0.0

    def test_non_numeric(self) -> None:
        assert _round_scalar("abc") == 0.0


class TestExplainPrediction:
    def test_linear_explainer_returns_factors(self) -> None:
        """SHAP on a fitted linear model yields top factors."""
        from sklearn.linear_model import LogisticRegression

        from app.ml.explain import explain_prediction

        rng = np.random.default_rng(7)
        X = rng.normal(size=(50, 5))
        y = (X[:, 0] + X[:, 1] > 0).astype(int)
        model = LogisticRegression().fit(X, y)

        result = explain_prediction(
            model,
            X_background=X[:20],
            features_row=X[0],
            feature_names=["f0", "f1", "f2", "f3", "f4"],
        )
        assert "top_positive_factors" in result
        assert "top_negative_factors" in result
        assert isinstance(result["base_value"], float)

    def test_tree_explainer_returns_factors(self) -> None:
        """SHAP on a fitted tree model yields top factors."""
        from sklearn.ensemble import RandomForestClassifier

        from app.ml.explain import explain_prediction

        rng = np.random.default_rng(7)
        X = rng.normal(size=(50, 5))
        y = (X[:, 0] > 0).astype(int)
        model = RandomForestClassifier(n_estimators=5, random_state=1).fit(X, y)

        result = explain_prediction(
            model,
            X_background=X[:20],
            features_row=X[1],
            feature_names=["f0", "f1", "f2", "f3", "f4"],
        )
        assert isinstance(result["base_value"], float)

    def test_feature_value_rounding(self) -> None:
        """Feature values are rounded to 4 decimals."""
        from sklearn.linear_model import LogisticRegression

        from app.ml.explain import explain_prediction

        X = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]])
        y = np.array([0, 0, 1, 1])
        model = LogisticRegression().fit(X, y)

        result = explain_prediction(
            model,
            X_background=X,
            features_row=X[0],
            feature_names=["a", "b"],
        )
        for factor in result["top_positive_factors"] + result["top_negative_factors"]:
            assert isinstance(factor["contribution"], float)
            assert isinstance(factor["feature_value"], float)
