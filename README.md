# InsightFlow

> **AI-Native Telecom Decision Intelligence Platform**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

InsightFlow transforms telecom operational data into **evidence-driven decisions**. It is not another dashboard — it is an AI-native platform that answers:

- **Why did it happen?** — Driver analysis with reproducible evidence
- **What will happen?** — Churn prediction with SHAP explainability
- **What should we do?** — Business recommendations with confidence scores

## Architecture

```
Raw Data → Warehouse (Star Schema) → Feature Store → Analytics → ML → Decision Intelligence → AI Copilot → Report
```

- **Backend**: FastAPI + Python 3.12, Clean Architecture (domain / application / infrastructure)
- **Data**: PostgreSQL (Bronze/Silver/Gold + Semantic layer), DuckDB-ready
- **ML**: 5 benchmarked churn models (LR / RF / XGBoost / LightGBM / CatBoost), SHAP explanations, Model Registry
- **AI**: 7-agent LangGraph Copilot (planner → SQL → analytics → evidence → decision → writer → reviewer)
- **Quality**: 66 tests, 80%+ coverage, architecture rules enforced by CI

## Quick Start

```bash
# 1. Start infrastructure
cd docker && docker compose up -d postgres redis

# 2. Backend
cd backend
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run python scripts/seed_registries.py
uv run python scripts/generate_mock_data.py --seed 42 --customers 1000
uv run python scripts/run_etl.py --input-dir data/mock
uv run python scripts/generate_features.py
uv run python -m app.ml.deploy
uv run uvicorn app.main:app --port 8000
```

## Documentation

The full engineering contract lives in the repo root:

| Doc | Contents |
|-----|----------|
| `01_PRD.md` | Product requirements |
| `02_ARCHITECTURE.md` | System architecture |
| `03_DATABASE.md` | Database design |
| `04_DATASET_SPEC.md` | Input data contract |
| `05_API_SPEC.md` | API contract |
| `07_AI_DESIGN.md` | AI agent design |
| `08_ARCHITECTURE_RULES.md` | Enforceable architecture rules |

## License

[MIT](LICENSE) © 2026 runjie luo (DieRoger)
