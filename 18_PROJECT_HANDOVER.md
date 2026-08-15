# InsightFlow — Project Handover

> 生成日期：2026-08-15
> 作者：Tech Lead
> 目的：作为新 Codex 对话的**唯一上下文**。假设读者完全不了解本项目。

---

# PROJECT_BRIEF

## 一句话介绍

**InsightFlow 是一个 AI-Native 电信行业决策智能平台（Decision Intelligence Platform）**——它不是又一个仪表盘，而是把电信运营数据转化为"有证据支撑的经营决策"的平台。

## 项目目标

回答传统 BI 无法回答的四个问题：

| 问题 | 传统 BI | InsightFlow |
|------|---------|-------------|
| 发生了什么？ | ✅ | ✅ |
| **为什么发生？** | ❌ | ✅（根因分析 + 可复现证据） |
| **将要发生什么？** | ❌ | ✅（流失预测 + SHAP 可解释性） |
| **应该做什么？** | ❌ | ✅（带置信度的建议） |

## 目标用户

- Operations Analyst（运营分析师）— 日常 KPI 监控、流失分析、报告
- Product Manager（产品经理）— 套餐优化、定价策略
- Marketing（市场团队）— 精准营销、Campaign ROI
- Executive（高管）— 每周经营决策摘要

## 核心价值

1. **Evidence First** — 每个结论必须引用可验证证据（SQL/指标/SHAP）
2. **Explainable AI** — 每个预测必须有 SHAP 因素 + 置信度
3. **Decision Instead of Dashboard** — 输出建议而非图表

## 四个最重要的模块

| 模块 | 说明 |
|------|------|
| **数据治理层**（governance） | Dataset Registry、六维质量评分、多数据集 Canonical 映射 |
| **Analytics Engine** | 50+ KPI、趋势、异常检测 |
| **ML Platform** | 5 算法流失预测 + SHAP + Model Registry |
| **AI Copilot**（规划中） | 7-Agent 自然语言分析工作流 |

## 当前版本

`0.1.0`（MVP 阶段，未发布正式版）

## 当前开发阶段

- **阶段一数据科学链路已 100% 完成**：Raw → Profiling → Quality → Canonical → Analytical Dataset
- Sprint 1（Analytics）✅、Sprint 2（ML）✅
- Sprint 3（AI Copilot）未开始
- Frontend 未开始

---

# PROJECT_CONTEXT

## 项目当前状态

**后端完成度高，前端/Agent 未动**。核心数据链路已用真实 Kaggle 数据（IBM Telco 7,043 行）端到端验证。

## 完成了哪些模块

| 模块 | 状态 | 位置 |
|------|:----:|------|
| 17 份工程契约文档 | ✅ | 仓库根 `00_*.md` ~ `17_*.md` |
| FastAPI 后端骨架（Walking Skeleton） | ✅ | `backend/app/` |
| Star Schema 数据层（6 schema / 22 表 / 2 物化视图） | ✅ | `backend/alembic/versions/` |
| 6 数据集 mock 生成器 + ETL | ✅ | `backend/scripts/generate_mock_data.py` `run_etl.py` |
| Analytics Engine（KPI/趋势/异常） | ✅ | `backend/app/application/analytics/` |
| Customer API（列表 + 360 详情） | ✅ | `backend/app/api/routers/customers.py` |
| ML Platform（5 算法/SHAP/Model Registry） | ✅ | `backend/app/ml/` |
| Churn Prediction API | ✅ | `backend/app/api/routers/churn.py` |
| **多数据集治理**（Dataset Registry/质量评分） | ✅ | `backend/alembic/versions/f6a7b8c9d0e1` `backend/app/warehouse/quality.py` |
| **Source Adapter**（IBM Telco） | ✅ | `backend/app/warehouse/adapters.py` |
| **Canonical Loader**（真实数据落库） | ✅ | `backend/app/warehouse/canonical_loader.py` |
| **Dataset Profiling** | ✅ | `backend/app/warehouse/profiling.py` |
| **Analytical Dataset**（BI 宽表） | ✅ | `backend/app/warehouse/analytical.py` |
| CI/CD（GitHub Actions 全绿） | ✅ | `.github/workflows/quality.yml` |
| MIT License + 双语 README | ✅ | 仓库根 |

## 未完成哪些模块

| 模块 | 状态 | 计划位置 |
|------|:----:|---------|
| AI Copilot（7-Agent） | ❌ 未开始 | `backend/app/ai/`（`07_AI_DESIGN.md` 已冻结设计） |
| Report Generator | ❌ 未开始 | `backend/app/application/reports/` |
| Recommendation Engine | ❌ V1.5 | — |
| What-if Simulation | ❌ V1.5 | — |
| Frontend（Next.js） | ❌ 未开始 | `frontend/`（`06_FRONTEND.md` 已冻结设计） |
| Cell2Cell/Nigeria/Churn2020 适配器 | ❌ 未开始 | `adapters.py` 扩展 |

## 当前 Milestone

**阶段一：第一条完整数据科学链路**（已完成全部 5 步）

## 当前 Phase

Phase 1（MVP 开发）中的"数据地基"子阶段刚收官。Sprint 1-2 已完成，Sprint 3 未开始。

## 当前正在开发什么

无活跃开发任务——刚完成 Analytical Dataset（阶段一收官）。

## 下一步是什么

候选（按优先级）：
1. **E2 修复**：`contract_type` 值域统一（见 Known Bugs）
2. **Analytical Dataset 暴露为 API**（Analytics 端点消费真实数据）
3. **Sprint 3：AI Copilot**（7-Agent LangGraph 工作流）

## Known Issues

见下方 **# KNOWN BUGS** 章节。

## Technical Debt

见下方 **# TECHNICAL DEBT** 章节。

## Risk

1. **mock 数据 vs 真实数据差距**：Sprint 1-2 的模型在 mock 数据上训练（ROC-AUC 1.0，过于理想）；真实 IBM 数据尚未用于模型训练
2. **测试数据污染**：integration 测试依赖 `data/raw/ibm_telco_v1/*.csv`，CI 环境无此文件时 `test_ibm_full_roundtrip` 会失败（当前 CI 数据准备步骤未下载 Kaggle 数据）
3. **CI 网络依赖**：CI 需在数据准备步骤下载 Kaggle 数据 + 部署模型（约 2-3 分钟），可能超时
4. **contract_type 双值域**（见 Bugs E2）：IBM 数据与 mock 数据写入同一列，值域混乱，影响未来 Analytics 正确性

---

# CURRENT ARCHITECTURE

## 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                      Users（规划中）                            │
│                        │                                      │
│                 Next.js Web App（未开发）                       │
│                        │                                      │
│                 FastAPI Backend（已实现）                       │
│  ┌──────────┬───────────┬───────────┬────────────────────┐   │
│  │ Analytics │  Churn    │ Customers │   (Copilot 未做)    │   │
│  │  Engine   │  API      │   360     │                     │   │
│  └──────────┴───────────┴───────────┴────────────────────┘   │
│                        │                                      │
│         ┌──────────────┼──────────────┐                       │
│         ▼              ▼              ▼                       │
│  Warehouse        Feature Store    ML Platform                │
│  (Star Schema)    (Gold)           (5 models + SHAP)          │
│         └──────────────┼──────────────┘                       │
│                        ▼                                      │
│                  PostgreSQL / DuckDB                           │
└──────────────────────────────────────────────────────────────┘
```

## 模块划分（backend/app/）

```
backend/app/
├── api/                    # HTTP 层（router/middleware/schemas）
│   ├── routers/
│   │   ├── system.py       # /health /metrics
│   │   ├── analytics.py    # /analytics/kpi /kpi/{m} /anomaly
│   │   ├── customers.py    # /customers /customers/{id}
│   │   └── churn.py        # /churn/predict /predict/batch
│   └── middleware/         # request_id + error handler
├── application/            # 用例编排（无 SQL）
│   └── analytics/analytics_service.py
├── domain/                 # 业务规则（零框架依赖）
│   ├── analytics/          # Insight/Evidence/MetricDefinition
│   └── customer/           # Customer 实体
├── infrastructure/         # IO 实现
│   ├── database/session.py # async engine
│   └── repositories/       # Customer/KPI/Metric repo
├── warehouse/              # 数据链路核心
│   ├── adapters.py         # SourceAdapter + IBMTelcoAdapter
│   ├── quality.py          # 六维质量评分
│   ├── profiling.py        # 描述性统计
│   ├── canonical_loader.py # Canonical → warehouse
│   ├── analytical.py       # BI 宽表
│   ├── bronze_loader.py    # CSV → raw.*
│   ├── silver_loader.py    # raw.* → warehouse
│   └── validator.py        # ETL 规则校验
├── ml/                     # 机器学习
│   ├── dataset.py          # 训练集构建
│   ├── train.py            # 5 算法训练
│   ├── explain.py          # SHAP
│   ├── registry.py         # Model Registry
│   ├── predict.py          # 预测服务
│   └── deploy.py           # 训练→注册→提升
└── schemas/                # Pydantic API 模型
```

## 数据流（两条管线）

**管线 A — 真实 Kaggle 数据（治理型，当前主推）**：
```
Kaggle IBM Telco
  → data/raw/（不可变 + sha256）
  → ingest_dataset.py（registry 注册）
  → profiling.py（数据集画像）
  → quality.py（六维评分，IBM 实测 99.97%）
  → adapters.py（canonical 映射）
  → canonical_loader.py（写入 warehouse）
  → analytical.py（BI 宽表）
```

**管线 B — mock 数据（Sprint 1-2 用）**：
```
generate_mock_data.py（6 数据集）
  → run_etl.py（CSV → raw.* → warehouse.* 星型）
  → generate_features.py（Feature Store）
  → ml/deploy.py（训练模型）
```

## Workflow

**数据质量工作流**（ingest_dataset.py 核心流程）：
```
1. register_dataset（写入 governance.dataset_registry）
2. kaggle 下载 → raw/（sha256 校验）
3. profile_dataframe（画像输出）
4. run_quality_checks（六维评分 + issues）
5. persist_quality_report（写入 governance.quality_report/issue）
6. to_canonical（adapter 输出 5 个 canonical 表）
7. load_canonical（写入 warehouse：dim_customer/dim_subscription/fact_billing）
```

## 数据库

6 个 schema（`backend/alembic/versions/` 8 个迁移）：

| Schema | 内容 | 关键表 |
|--------|------|--------|
| `raw` | 原始数据（append-only） | raw_customer/usage/billing/network/service/campaign |
| `warehouse` | Star Schema | dim_customer/package/region/time + fact_usage/billing/network/service/campaign + dim_subscription |
| `feature_store` | 特征 | customer_features（45 列）/churn_features/package_features + feature_registry |
| `semantic` | KPI 物化视图 | kpi_arpu/kpi_revenue + metric_registry |
| `ml` | 模型元数据 | model_registry/prediction_registry |
| `governance` | 数据治理 | dataset_registry/raw_dataset_file/quality_report/quality_issue |

**关键迁移链**：
```
58d690bcbe1e (空基) → a1b2c3d4e5f6 (raw) → b2c3d4e5f6a7 (warehouse)
→ c3d4e5f6a7b8 (feature/semantic/ml) → d4e5f6a7b8c9 (唯一约束)
→ e5f6a7b8c9d0 (identity) → f6a7b8c9d0e1 (governance) → 0a1b2c3d4e5f (dim_subscription)
```

## Agent

**未实现**。设计已冻结于 `07_AI_DESIGN.md`：7-Agent DAG（Planner → SQL/Analytics/Evidence → Decision → Writer → Reviewer），用 LangGraph StateGraph。

## API（已实现 12 个端点）

```
GET  /api/v1/system/health
GET  /api/v1/system/metrics
GET  /api/v1/analytics/kpi
GET  /api/v1/analytics/kpi/{metric}
GET  /api/v1/analytics/anomaly
GET  /api/v1/customers
GET  /api/v1/customers/{customer_id}
POST /api/v1/churn/predict
POST /api/v1/churn/predict/batch
```

完整契约在 `05_API_SPEC.md`（含 Copilot/Reports/Models/Features 等规划端点）。

## 为什么这样设计

- **Clean Architecture**（domain/application/infrastructure）：AI 生成代码有清晰边界（AR 规则可机器检查）
- **Star Schema**：电信分析天然多维（区域×时间×套餐×分群）
- **多数据集治理**：不 UNION 不同源数据，每个源经独立 adapter 进 canonical schema（数据方案 §2）
- **六维质量评分**：质量是数据集能否加载的门禁，而非事后检查

---

# IMPORTANT DECISIONS

## D-1: Clean Architecture（四层）

- **背景**：AI 生成代码易混乱，需要硬性边界
- **方案**：api → application → domain ← infrastructure；domain 零框架依赖
- **Trade-off**：文件数多、样板代码 vs 可测试性/可替换性
- **影响**：check_architecture.py 9 项自动检查；Sprint 1 曾抓到 20 个违规全修复

## D-2: Star Schema（非 3NF / 非 Data Vault）

- **背景**：电信 BI 查询多维聚合
- **方案**：4 dim + 5 fact + 2 物化视图
- **Trade-off**：ETL 需转换 vs 查询快、易理解
- **影响**：Analytics 查询 < 2s 达标

## D-3: PostgreSQL + DuckDB（非 ClickHouse）

- **背景**：1M 客户 MVP 规模
- **方案**：PG 做 OLTP+仓库，DuckDB 预留本地分析
- **Trade-off**：双存储 vs 免运维；Phase 3 可迁 ClickHouse
- **影响**：仓库层 SQL 全参数化

## D-4: LangGraph（规划，非自定义 DAG）

- **背景**：7-Agent 工作流需要状态管理/检查点
- **方案**：07_AI_DESIGN.md 冻结 LangGraph StateGraph
- **Trade-off**：框架依赖 vs 免自研状态机
- **影响**：Sprint 3 实现时的唯一依赖

## D-5: Repository Pattern

- **背景**：数据库可替换性
- **方案**：所有 SQL 在 repository，服务层零 SQL
- **Trade-off**：抽象层 vs 可测试性
- **影响**：AR-055 强制；Sprint 1 修复 20 违规时确立

## D-6: Evidence-First AI

- **背景**：高管不信任无证据的 AI 建议
- **方案**：每个结论必须引用证据（SQL/sample_size/confidence）
- **Trade-off**：响应慢 vs 可信
- **影响**：Copilot 的 Reviewer Agent 强校验

## D-7: 多数据集治理（不 UNION）

- **背景**：5 个 Kaggle 数据集字段/语义/标签都不同
- **方案**：SourceAdapter 抽象 → 每数据集独立 adapter → canonical schema；dataset_registry 注册
- **Trade-off**：适配器多 vs 数据隔离/可溯源
- **影响**：quality_report 决定数据集可否加载

## D-8: Canonical 边界归一化（E1 修复）

- **背景**：IBM adapter 输出 CamelCase，loader 期望 snake_case → 服务列全 NULL
- **方案**：在 adapter 输出边界用 SERVICE_MAPPING 显式映射（不改 loader、不改 raw）
- **Trade-off**：映射表维护 vs loader 不污染
- **影响**：修复后 9 服务列正确落库（tech_support 5517/7043）

## D-9: mock 数据 + 真实数据双管线

- **背景**：Sprint 1-2 需快速开发，真实数据后期接入
- **方案**：管线 B（mock ETL）用于功能开发，管线 A（真实 Kaggle）用于数据链路
- **Trade-off**：两套管线维护 vs 开发速度
- **影响**：当前模型在 mock 上训练，真实数据待接入模型

---

# CURRENT IMPLEMENTATION

## 已实现模块

| 模块 | 文件 | 说明 |
|------|------|------|
| 数据治理 | `warehouse/quality.py` `adapters.py` `canonical_loader.py` `profiling.py` `analytical.py` | 完整数据链路 |
| Analytics | `application/analytics/` `api/routers/analytics.py` | KPI/趋势/异常 |
| Customer | `api/routers/customers.py` `infrastructure/repositories/customer_repository.py` | 列表+360 |
| ML | `app/ml/` 全部 | 5 算法/SHAP/Registry/预测 |
| ETL | `warehouse/bronze_loader.py` `silver_loader.py` `validator.py` | mock 管线 |
| System | `api/routers/system.py` | health/metrics |

## 已实现 API

见 **# CURRENT ARCHITECTURE → API** 章节（9 个实际端点 + 契约中规划端点）。

## 已实现 Agent

**无**（Copilot 未开始）。

## 已实现测试（100 个）

```
tests/
├── unit/
│   ├── warehouse/test_quality.py        # 质量层 + adapter（13）
│   ├── warehouse/test_validator.py      # ETL 校验（10）
│   ├── warehouse/test_profiling.py      # profiling（9）
│   ├── ml/test_ml_core.py               # 风险分级/SHAP（9）
│   ├── ml/test_model_training.py        # 5 算法（4）
│   └── analytics/test_analytics_service.py # Insight/趋势（12）
├── integration/
│   ├── test_etl_pipeline.py             # mock ETL 全链路（5）
│   ├── test_canonical_loader.py         # canonical 落库（7）
│   ├── test_profiling_ibm.py            # 真实 IBM profiling（2）
│   ├── test_analytical_dataset.py       # BI 宽表（4）
│   ├── test_ml_pipeline.py              # ML 管线（3）
│   ├── test_model_registry.py           # 模型注册（3）
│   ├── test_analytics_api.py            # Analytics API（9）
│   ├── test_churn_api.py                # Churn API（4）
│   └── test_analytical_api.py           # （见下）
└── api/test_system_api.py               # health（5）
```

覆盖率 **81.45%**（门禁 ≥80%）。

## 已实现页面

**无**（Frontend 未开始）。

---

# ROADMAP STATUS

## 已完成的 Roadmap 项

- ✅ Phase -1（Walking Skeleton）
- ✅ Phase 0（数据地基：Star Schema + mock ETL + Feature Store）
- ✅ Sprint 1（Analytics Engine + Customer API）
- ✅ Sprint 2（ML Platform：5 算法 + SHAP + Registry）
- ✅ 阶段一数据链路（Raw → Profiling → Quality → Canonical → Analytical）
- ✅ CI/CD 全绿 + 公开 GitHub（MIT）

## 正在开发的 Roadmap 项

- 无（刚收官阶段一）

## 未来计划

| 版本 | 内容 |
|------|------|
| Sprint 3 | AI Copilot（7-Agent LangGraph）|
| V1.5 | Recommendation Engine、What-if Simulation |
| V2.0 | Knowledge Graph、RAG、多 Agent 协作 |
| V3.0 | 自主决策智能、持续学习、企业部署 |

---

# OPEN QUESTIONS

1. **contract_type 值域如何统一？** IBM（Month-to-month/One year/Two year）vs mock（prepaid/postpaid/hybrid）写入同一列——需 ADR 决策 canonical 枚举（是映射到标准值域，还是加 dataset 维度拆分）
2. **真实数据何时接入模型训练？** 当前模型在 mock 上训练（ROC-AUC 1.0 过于理想），是否在 Sprint 3 前用 IBM 真实数据重训？
3. **Analytical Dataset 是否落库？** 当前按需读取不落库——是否需要 governance 持久化供 API 消费？
4. **Frontend 优先级**：Sprint 3（Copilot 后端）与 Frontend 谁先？
5. **CI 中 Kaggle 数据准备**：是否在 CI 数据准备步骤加入 Kaggle 下载（需 token 注入 secrets）？

---

# KNOWN BUGS

| ID | 严重度 | 描述 | 位置 | 状态 |
|----|:------:|------|------|:----:|
| **E1** | 🔴 已修 | IBM service 列 CamelCase vs snake_case → 全 NULL | adapters.py/canonical_loader.py | ✅ 已修复（`7c4e6fe`） |
| **E2** | 🟡 未修 | `contract_type` 双值域混存（IBM 合同期 vs mock 合约类型） | validator.py:76 vs canonical_loader.py:89 | ⚠️ 待决策 |
| E3 | 🟡 未修 | `status` 值域：spec `{active,suspended,churned}` vs canonical 只映射 `{active,churned}`（suspended 丢失） | canonical_loader.py:60 | ⚠️ |
| E4 | 🟡 未修 | `payment_method` 值域冲突（spec `{credit_card,...}` vs IBM `"Electronic check"`） | spec:299 vs adapters.py:155 | ⚠️ |
| E5 | 🟢 观察 | `service` 语义错位（spec 的 service=客服工单 vs IBM 的 service=订阅服务） | 04_DATASET_SPEC §8 vs adapters.py | ⚠️ 文档级 |
| E6 | 🟢 观察 | 质量报告三套结构互不对应 | spec §11.4 vs governance.quality_report vs run_etl.py | ⚠️ |

**隐藏 bug 提醒**：`_bool_map` 曾返回 numpy bool 导致 `'No' → None`（已修，`np.bool_ is False` 为 False 的坑）；`'No internet service'`（不适用值）正确映射为 None。

---

# TECHNICAL DEBT

| # | 债务 | 说明 |
|---|------|------|
| TD-1 | **两套管线未统一** | 管线 A（真实治理型）与管线 B（mock ETL）并行，`run_etl.py` 不经 quality.py/governance |
| TD-2 | **quarantine 无持久化** | spec §11.3 承诺 raw_quarantine 表，实际仅内存计数丢弃（`bronze_loader.py:144`） |
| TD-3 | **referential integrity 只数 NULL** | `quality.py:228-233` 未真查库，注释 "async resolution" 无实现 |
| TD-4 | **Parquet 无支持** | 仅 CSV（`bronze_loader.py:123`），spec §2.1 标 "future" |
| TD-5 | **registry 字段未填全** | `register_dataset` 不写 record_count/checksum/downloaded_at；raw_dataset_file 的 row/column_count 从未写 |
| TD-6 | **silver fact 非幂等** | `silver_loader.py:143-254` 纯 INSERT，重复运行会重复行（违反 spec §14.2） |
| TD-7 | **测试数据污染** | integration 测试依赖本地 `data/raw/` CSV；CI 需在数据准备步骤处理 |
| TD-8 | **mock 模型未用真实数据** | production 模型在 mock 上训练，ROC-AUC 1.0 不真实 |
| TD-9 | **CI 数据准备缓慢** | 测试前 seed+mock+ETL+features+deploy 约 2-3 分钟 |

---

# ENGINEERING LESSONS

## 最重要的经验

1. **架构规则要可机器检查**：`check_architecture.py` 在 Sprint 1 抓到 20 个真实违规（SQL 在服务层、业务逻辑在 router）——规则文档若不自动执行就是空话
2. **f-string 动态 SQL 的误报处理**：检查器需区分"列名来自常量（安全）"vs"值插值（危险）"，用 `VALUE_CONTEXT_PATTERNS` 精准匹配
3. **asyncpg 的坑**：
   - 不支持多语句执行（DDL 需逐条 `_exec`）
   - DATE 列要 `datetime.date` 对象非字符串
   - `:param::jsonb` 语法报错 → 用 `CAST(:param AS jsonb)`
   - JSON 参数不能含 NaN（`json.dumps` 默认输出 `NaN` 非法 JSON）→ 需 `_clean_nan`
4. **pandas/numpy 的类型坑**：
   - `np.array(["active"]*n)` 默认 U6 dtype，赋 `"churned"`（7 字符）被静默截断 → 必须 `dtype=object`（曾致客户验收率 837 vs 972）
   - `pd.Series([False]).iloc[0]` 返回 `np.False_`，`np.False_ is False` 为 **False** → 布尔判断必须显式 `is True/is False` 或 `bool()` 转换
   - `Series.map()` 对未知值返回 NaN → 需先 `isin()` 过滤再保留原值
5. **ETL 性能陷阱**：列表推导里调用函数每次迭代重算（`_quarantined_indices` 被调 1000 次 → 45s），缓存结果后 0.25s（180 倍提速）
6. **测试间数据隔离**：integration 测试共享数据库，`TRUNCATE` 会破坏其他测试 → 用唯一 sid + fixture 清理 + 恢复 production 模型
7. **pytest 事件循环**：全局 async engine 与 per-function 事件循环冲突 → `asyncio_default_test_loop_scope = "session"`；TestClient 的 portal 循环不兼容 → 用 `httpx.AsyncClient` + ASGITransport
8. **CI 的 uv 用法**：`uv sync` 创建 venv 但命令不在 PATH → 一律 `uv run`
9. **CI 环境差异**：mypy `python_version=3.11` 与 numpy 2.x stub（需 3.12 语法）冲突 → 升到 3.12；`hashFiles('**')` 在 job if 导致 workflow 解析失败 → 改步骤级 `[ -d dir ]` 检查
10. **真实数据总是暴露设计缺陷**：IBM 数据的 `'No internet service'`（不适用值）暴露了布尔列映射的语义漏洞——比 mock 数据（干净）更能验证设计

## 踩坑 Debug 案例

- **E1 三层连环 bug**：列名不匹配（CamelCase）→ 发现 `_fill_bool` 把枚举列（DSL）当布尔转 NaN → 再发现 `np.bool_` 非 Python bool。每修一层暴露下一层，最终在 adapter 边界统一归一化
- **IBM 数据 26.5% 流失率**：与数据集已知分布一致，验证了链路可信度

## 技术选型经验

- **uv**（替代 pip/poetry）：快、锁文件可靠，但 CI 需 `uv run`
- **structlog**（替代 stdlib logging）：结构化 JSON，但 AR-084 需豁免 CLI 演示块
- **httpx.AsyncClient**（替代 TestClient）：async 测试更可靠

---

# BLOG ASSETS

| 主题 | 价值 |
|------|------|
| **"从 45 秒到 0.25 秒：ETL 性能排查"** | 列表推导内函数重算的经典性能陷阱，180 倍提速故事 |
| **"numpy 的 U6 截断陷阱"** | `np.array(["active"]*n)` 静默截断长字符串，数据工程师必踩 |
| **"np.False_ is False 为 False"** | numpy 标量类型陷阱，导致布尔列全 NULL 的 Debug 故事 |
| **"真实数据如何暴露三层隐藏 bug"** | IBM 'No internet service' 值触发的映射语义漏洞 |
| **"AI 生成代码的架构守护：可机器检查的规则"** | check_architecture.py 设计——规则文档如何变成 CI 门禁 |
| **"多数据集不 UNION：Source Adapter 模式"** | 5 个异构 Kaggle 数据集如何统一进 canonical schema |
| **"六维数据质量评分体系"** | completeness/validity/uniqueness/consistency/RI/overall 的设计 |
| **"从 PRD 到 17 份冻结契约再到 100 个测试"** | 完整工程契约驱动开发流程 |

---

# NEXT RECOMMENDED TASK

## 建议：修复 E2（contract_type 值域统一）

### 为什么

1. **E2 是当前唯一 🔴 级残留数据缺陷**——IBM 数据（Month-to-month/One year/Two year）与 mock 数据（prepaid/postpaid/hybrid）写入**同一列** `dim_customer.contract_type`，值域混乱。这直接影响：
   - Analytics 的 contract_type 过滤/分组（当前分组会得到 5 种混合值）
   - 未来模型训练的类别编码
   - 跨数据集对比分析（数据方案的核心价值）
2. **工作量小、影响大**——比开始 Sprint 3（Copilot）更快的胜利，且为后续数据驱动开发清障
3. **符合数据方案演进**——需要 ADR 决策 canonical 枚举，这正是架构演进的正规流程

### 建议方案（需 Tech Lead 决策）

| 方案 | 思路 | 取舍 |
|------|------|------|
| A. 标准化枚举 | 定义 canonical 枚举（如 `monthly/annual/two_year`），adapter 映射 IBM，loader 统一写入 | 分析统一，但 mock 数据需重映射 |
| B. 加 dataset 维度 | `dim_customer` 增加 contract 相关列按数据集拆分 | 保留原始值，但列冗余 |
| C. 仅文档化 | 接受混合值域，在 metric_registry 注明 | 最省事但遗留脏数据 |

**推荐 A**（标准化枚举），配合：
- ADR 记录决策
- adapter 的 contract 映射函数
- mock 生成器同步更新
- 回归测试

### 实施顺序

```
1. ADR-001: contract_type canonical 枚举决策
2. adapters.py: 增加 contract 映射（IBM → canonical）
3. generate_mock_data.py: mock 值域同步
4. canonical_loader.py / silver_loader.py: 统一写入 canonical 值
5. 回归测试 + 全门禁
6. 提交推送
```

---

*本交接文档基于仓库实际状态（commit `d9a9f9d`）生成，所有路径/测试数/覆盖率经核实。*
