"""Unit tests for model training helpers (build_models, evaluate_model)."""

import numpy as np

from app.ml.train import build_models, evaluate_model


class TestBuildModels:
    def test_all_five_algorithms_present(self) -> None:
        models = build_models(seed=1)
        expected = {
            "logistic_regression",
            "random_forest",
            "xgboost",
            "lightgbm",
            "catboost",
        }
        assert set(models) == expected

    def test_models_are_fittable(self) -> None:
        """Every model can fit a tiny dataset (API contract check)."""
        rng = np.random.default_rng(3)
        X = rng.normal(size=(30, 4))
        y = (X[:, 0] > 0).astype(int)
        for _name, model in build_models(seed=1).items():
            model.fit(X, y)
            assert model.predict(X).shape == (30,)


class TestEvaluateModel:
    def test_returns_metric_dict(self) -> None:
        from sklearn.linear_model import LogisticRegression

        rng = np.random.default_rng(5)
        X = rng.normal(size=(50, 3))
        y = (X[:, 0] > 0).astype(int)
        model = LogisticRegression().fit(X, y)

        metrics = evaluate_model(model, X, y)
        assert set(metrics) == {"accuracy", "precision", "recall", "f1_score", "roc_auc"}
        for value in metrics.values():
            assert 0.0 <= value <= 1.0

    def test_perfect_model_metrics(self) -> None:
        """A perfect classifier scores 1.0 on all metrics."""
        from sklearn.linear_model import LogisticRegression

        X = np.array([[1.0], [2.0], [3.0], [10.0], [11.0], [12.0]])
        y = np.array([0, 0, 0, 1, 1, 1])
        model = LogisticRegression().fit(X, y)

        metrics = evaluate_model(model, X, y)
        assert metrics["accuracy"] == 1.0
        assert metrics["f1_score"] == 1.0
        assert metrics["roc_auc"] == 1.0
