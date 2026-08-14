"""Train all models, register the best (by ROC-AUC) in the Model Registry,
and promote it to production.

Usage:
    uv run python -m app.ml.deploy
"""

import asyncio
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ml.registry import promote_model, register_model  # noqa: E402
from app.ml.train import train_and_evaluate  # noqa: E402


async def main() -> None:
    from app.infrastructure.database.session import engine

    records = await train_and_evaluate(engine)

    # Rank by ROC-AUC, then F1
    best = max(records, key=lambda r: (r["metrics"]["roc_auc"], r["metrics"]["f1_score"]))
    print(f"Best model: {best['model_name']} (ROC-AUC={best['metrics']['roc_auc']:.4f})")

    registered = await register_model(
        engine,
        model_name=best["model_name"],
        algorithm=best["algorithm"],
        model=best["model"],
        metrics=best["metrics"],
        dataset_id=best["dataset_id"],
        feature_version=best["feature_version"],
        random_seed=best["random_seed"],
        training_time_sec=best["training_time_sec"],
    )
    print(
        f"Registered: {registered['model_name']} {registered['model_version']} (id={registered['model_id']})"
    )

    promoted = await promote_model(engine, registered["model_id"])
    print(f"Promoted to production: {promoted}")

    production = await get_production(engine)
    print(f"Production model: {production['model_name']} {production['model_version']}")
    await engine.dispose()


async def get_production(engine: Any) -> dict[str, Any]:
    from app.ml.registry import get_production_model

    result = await get_production_model(engine)
    if result is None:
        raise RuntimeError("No production model")
    return result


if __name__ == "__main__":
    asyncio.run(main())
