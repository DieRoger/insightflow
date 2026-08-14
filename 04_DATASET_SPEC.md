# InsightFlow — Dataset Specification (Input Contract)

Version 1.0 · Status: **Frozen** · Target: ETL, ML, Testing, Demo

---

## Table of Contents

1. [Purpose & Scope](#1-purpose--scope)
2. [File Format Standards](#2-file-format-standards)
3. [Data Source Overview](#3-data-source-overview)
4. [Customer Dataset](#4-customer-dataset)
5. [Usage Dataset](#5-usage-dataset)
6. [Billing Dataset](#6-billing-dataset)
7. [Network Dataset](#7-network-dataset)
8. [Customer Service Dataset](#8-customer-service-dataset)
9. [Marketing Dataset](#9-marketing-dataset)
10. [Cross-Dataset Rules](#10-cross-dataset-rules)
11. [Data Quality Rules](#11-data-quality-rules)
12. [Mock Data Generation Rules](#12-mock-data-generation-rules)
13. [Data Volume Specification](#13-data-volume-specification)
14. [ETL Contract](#14-etl-contract)

---

# 1. Purpose & Scope

## 1.1 Why This Document Exists

InsightFlow ingests data from six external telecom systems. Every downstream component — ETL, Warehouse, Feature Store, ML models, Analytics, AI Copilot, Reports — depends on the shape and quality of this input data.

**Without a frozen input contract:**

- ETL developers guess at column meanings
- ML engineers train on data that doesn't match production
- Test data generators produce unrealistic distributions
- Demo data doesn't exercise edge cases

**With this document frozen:**

- ETL code is generated from the spec
- ML feature engineering assumes known input distributions
- Mock data generators produce contract-compliant test data
- Every stakeholder has a single source of truth for "what data looks like"

## 1.2 What This Document Covers

| Aspect | Covered? |
|--------|:--------:|
| File format (CSV, Parquet) | ✅ |
| Column name, type, required/optional | ✅ |
| Validation rules per column | ✅ |
| Value ranges and distributions | ✅ |
| Missing value handling | ✅ |
| Cross-dataset referential integrity | ✅ |
| Mock data generation parameters | ✅ |
| Expected data volumes | ✅ |
| Update frequency / delivery schedule | ✅ |

## 1.3 Relationship to Other Documents

```
04_DATASET_SPEC.md          ← THIS FILE: "What raw data looks like"
        │
        ▼
03_DATABASE.md              ← "How data is stored after ETL"
        │
        ▼
05_API_SPEC.md              ← "How data is served to clients"
```

---

# 2. File Format Standards

## 2.1 Supported Formats

| Format | Use Case | Notes |
|--------|----------|-------|
| **CSV** (primary) | MVP input | UTF-8, header row required, comma-delimited |
| **Parquet** (future) | Production input | Columnar, compressed, schema-embedded |

## 2.2 CSV Conventions

| Rule | Value |
|------|-------|
| Encoding | UTF-8 (no BOM) |
| Delimiter | `,` (comma) |
| Quote character | `"` (double quote) |
| Escape character | `\` |
| Header row | **Required** — first row must match column names exactly |
| Line endings | `\n` (LF) |
| NULL representation | Empty string (two consecutive delimiters: `,,`) |
| Date format | `YYYY-MM-DD` (ISO 8601 date) |
| Timestamp format | `YYYY-MM-DDTHH:MM:SSZ` (ISO 8601) |
| Boolean | `true` / `false` (lowercase) |
| Decimal | `.` as decimal separator, no thousands separator |

## 2.3 File Naming Convention

```
{domain}_{timestamp}.csv

Examples:
  customer_20260701.csv
  usage_202607_daily.csv
  billing_202607.csv
```

## 2.4 Delivery Schedule

| Dataset | Frequency | Delivery Window | Expected Size |
|---------|-----------|-----------------|---------------|
| Customer | Daily (full refresh) | 01:00–02:00 UTC | ~50 MB |
| Usage | Daily (incremental) | 02:00–03:00 UTC | ~200 MB/day |
| Billing | Monthly | 1st of month, 04:00 UTC | ~30 MB |
| Network | Daily | 02:00–03:00 UTC | ~150 MB/day |
| Service | Daily | 02:00–03:00 UTC | ~10 MB/day |
| Marketing | Weekly | Monday 03:00 UTC | ~5 MB |

---

# 3. Data Source Overview

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Customer   │  │    Usage     │  │   Billing    │
│   (CRM)      │  │  (Network)   │  │  (Finance)   │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       │    ┌────────────┼─────────────────┤
       │    │            │                 │
       ▼    ▼            ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Network    │  │   Service    │  │  Marketing   │
│  (Monitoring)│  │  (Ticketing) │  │  (Campaign)  │
└──────────────┘  └──────────────┘  └──────────────┘
```

**Join key**: `customer_id` is the universal foreign key across all six datasets.

---

# 4. Customer Dataset

### Source System

CRM (Customer Relationship Management)

### File

`customer_YYYYMMDD.csv`

### Description

Customer identity, demographics, contract, and lifecycle status. One row per customer. This is the **master record** — all other datasets reference it.

### Column Definitions

| # | Column | Type | Required | Description | Validation | Example |
|---|--------|------|----------|-------------|------------|---------|
| 1 | `customer_id` | `VARCHAR(50)` | ✅ | Unique customer identifier from CRM | NOT NULL, unique within file, pattern: `CUST-\d{8}` | `CUST-00000001` |
| 2 | `gender` | `VARCHAR(10)` | | Customer gender | `Male`, `Female`, `Other`, or empty | `Male` |
| 3 | `age` | `INTEGER` | | Age at import time | `0 ≤ age ≤ 120`, or empty | `34` |
| 4 | `city` | `VARCHAR(100)` | | City of residence | Non-empty string or empty | `Shanghai` |
| 5 | `province` | `VARCHAR(100)` | | Province / State | Non-empty string or empty | `Shanghai` |
| 6 | `join_date` | `DATE` | ✅ | Subscription start date | `YYYY-MM-DD`, ≤ today | `2024-04-10` |
| 7 | `contract_type` | `VARCHAR(30)` | ✅ | Contract category | `prepaid`, `postpaid`, or `hybrid` | `postpaid` |
| 8 | `package_id` | `VARCHAR(50)` | ✅ | Source system package code | NOT NULL, references package catalog | `PKG-PREMIUM-001` |
| 9 | `package_name` | `VARCHAR(100)` | | Human-readable package name | — | `Premium Unlimited` |
| 10 | `status` | `VARCHAR(20)` | ✅ | Current customer status | `active`, `suspended`, or `churned` | `active` |

### Primary Key

`customer_id` (natural key from source)

### Data Distribution (Expected)

| Column | Distribution |
|--------|-------------|
| `gender` | Male 52%, Female 47%, Other/empty 1% |
| `age` | Normal, μ=38, σ=14, clipped to [18, 90] |
| `contract_type` | postpaid 60%, prepaid 35%, hybrid 5% |
| `status` | active 85%, suspended 3%, churned 12% |
| `join_date` | Uniform over last 5 years, spike in Q4 (holiday promos) |

### Example Rows

```csv
customer_id,gender,age,city,province,join_date,contract_type,package_id,package_name,status
CUST-00000001,Male,34,Shanghai,Shanghai,2024-04-10,postpaid,PKG-PREMIUM-001,Premium Unlimited,active
CUST-00000002,Female,28,Beijing,Beijing,2025-01-15,prepaid,PKG-DATA-003,Data Saver,active
CUST-00000003,Male,45,Guangzhou,Guangdong,2023-06-01,postpaid,PKG-BUSINESS-005,Business Pro,churned
CUST-00000004,Female,,Shenzhen,Guangdong,2026-03-20,hybrid,PKG-FAMILY-002,Family Share,suspended
```

### Missing Value Handling

| Column | Strategy |
|--------|----------|
| `gender` | Leave NULL in warehouse |
| `age` | Leave NULL; feature engineering imputes with median |
| `city` | Leave NULL; region cannot be determined |
| `province` | Leave NULL; region cannot be determined |

---

# 5. Usage Dataset

### Source System

Network usage monitoring / mediation system

### File

`usage_YYYYMMDD.csv` (one file per day, or one file per month with all daily rows)

### Description

Daily communication behavior: voice minutes, SMS, data consumption. One row per customer per day. **Only customers who had activity on that day are present** — no zero-usage rows.

### Column Definitions

| # | Column | Type | Required | Description | Validation | Example |
|---|--------|------|----------|-------------|------------|---------|
| 1 | `customer_id` | `VARCHAR(50)` | ✅ | Customer identifier | Must exist in `customer.csv` (checked at ETL) | `CUST-00000001` |
| 2 | `usage_date` | `DATE` | ✅ | Date of usage record | `YYYY-MM-DD`, ≤ today | `2026-08-01` |
| 3 | `voice_minutes` | `DECIMAL(10,2)` | | Outbound call minutes this day | `≥ 0`, or empty (= 0) | `52.50` |
| 4 | `sms_count` | `INTEGER` | | SMS messages sent this day | `≥ 0`, or empty (= 0) | `3` |
| 5 | `data_usage_mb` | `DECIMAL(12,2)` | | Total mobile data consumed (MB) | `≥ 0`, or empty (= 0) | `2240.50` |
| 6 | `roaming_usage_mb` | `DECIMAL(10,2)` | | Data consumed while roaming (MB) | `≥ 0`, or empty (= 0) | `0.00` |
| 7 | `peak_usage_mb` | `DECIMAL(10,2)` | | Data consumed during peak hours (08:00–22:00) | `≥ 0`, ≤ `data_usage_mb` | `1380.00` |
| 8 | `international_minutes` | `DECIMAL(8,2)` | | International call minutes | `≥ 0`, or empty (= 0) | `0.00` |

### Primary Key

`(customer_id, usage_date)` — composite

### Data Distribution (Expected)

| Column | Distribution |
|--------|-------------|
| `voice_minutes` | Log-normal, μ=30min/day for active users, heavy right tail |
| `sms_count` | Zero-inflated Poisson, λ=2 (most customers send 0–5 SMS/day) |
| `data_usage_mb` | Log-normal, μ=500MB/day, σ large (heavy users at 5GB+/day) |
| `roaming_usage_mb` | 95% zeros, 5% with values 10–500MB |
| `peak_usage_mb` | ~60–70% of `data_usage_mb` |
| `international_minutes` | 98% zeros |

### Seasonality

- Data usage higher on weekends (+15%)
- Voice minutes higher on weekdays
- Major holidays: data +40%, voice +25%

### Example Rows

```csv
customer_id,usage_date,voice_minutes,sms_count,data_usage_mb,roaming_usage_mb,peak_usage_mb,international_minutes
CUST-00000001,2026-08-01,52.50,3,2240.50,0.00,1380.00,0.00
CUST-00000001,2026-08-02,48.00,5,2180.00,0.00,1420.00,0.00
CUST-00000002,2026-08-01,12.00,0,320.50,120.00,180.00,0.00
CUST-00000005,2026-08-01,0.00,1,85.00,0.00,50.00,5.50
```

### Missing Value Handling

| Column | Strategy |
|--------|----------|
| All numeric usage columns | Treat empty as `0` (no usage ≠ missing data) |

---

# 6. Billing Dataset

### Source System

Billing / Finance system

### File

`billing_YYYYMM.csv` (one file per month)

### Description

Monthly billing records: plan fees, discounts, payment status. One row per customer per month. **All active customers have a billing row each month.**

### Column Definitions

| # | Column | Type | Required | Description | Validation | Example |
|---|--------|------|----------|-------------|------------|---------|
| 1 | `customer_id` | `VARCHAR(50)` | ✅ | Customer identifier | Must exist in `customer.csv` | `CUST-00000001` |
| 2 | `billing_month` | `DATE` | ✅ | First day of billing month | `YYYY-MM-01` format | `2026-08-01` |
| 3 | `monthly_fee` | `DECIMAL(10,2)` | ✅ | Base plan fee before discounts | `≥ 0` | `99.00` |
| 4 | `discount_amount` | `DECIMAL(10,2)` | | Discount applied this month | `≥ 0`, ≤ `monthly_fee` | `3.50` |
| 5 | `payment_status` | `VARCHAR(20)` | ✅ | Payment outcome for this month | `paid`, `overdue`, or `pending` | `paid` |
| 6 | `overdue_days` | `INTEGER` | | Days past due (if overdue) | `≥ 0`; 0 if `paid`; must be >0 if `overdue` | `0` |
| 7 | `package_price` | `DECIMAL(10,2)` | ✅ | List price of the package this month | `≥ 0`, should equal `monthly_fee` for non-discounted | `99.00` |
| 8 | `payment_method` | `VARCHAR(30)` | | Payment method | `credit_card`, `bank_transfer`, `wallet`, `cash` | `credit_card` |

### Primary Key

`(customer_id, billing_month)` — composite

### Business Validation Rules

| Rule | Severity |
|------|----------|
| `discount_amount ≤ monthly_fee` | Error — reject row |
| `overdue_days > 0` implies `payment_status = 'overdue'` | Warning — quarantine |
| `payment_status = 'paid'` implies `overdue_days = 0` | Warning — quarantine |
| `monthly_fee` should ≈ `package_price` (within 5%) | Warning — log variance |
| `billing_month` must be the 1st of a month | Error — reject row |

### Data Distribution (Expected)

| Column | Distribution |
|--------|-------------|
| `monthly_fee` | Multi-modal: peaks at $29 (basic), $59 (standard), $99 (premium) |
| `discount_amount` | 70% zero, 30% $2–$20 (promotional), heavy right tail |
| `payment_status` | paid 85%, pending 10%, overdue 5% |
| `overdue_days` | 90% zero, remaining log-normal μ=15 days |
| `payment_method` | credit_card 45%, wallet 30%, bank_transfer 20%, cash 5% |

### Example Rows

```csv
customer_id,billing_month,monthly_fee,discount_amount,payment_status,overdue_days,package_price,payment_method
CUST-00000001,2026-08-01,99.00,3.50,paid,0,99.00,credit_card
CUST-00000002,2026-08-01,29.00,0.00,paid,0,29.00,wallet
CUST-00000006,2026-08-01,59.00,0.00,overdue,22,59.00,bank_transfer
CUST-00000007,2026-08-01,99.00,10.00,pending,0,99.00,credit_card
```

---

# 7. Network Dataset

### Source System

Network monitoring / QoS platform

### File

`network_YYYYMMDD.csv`

### Description

Daily network quality metrics per customer: latency, signal, drop rate, coverage. One row per customer per day. May be sparse — not all customers have measurements every day.

### Column Definitions

| # | Column | Type | Required | Description | Validation | Example |
|---|--------|------|----------|-------------|------------|---------|
| 1 | `customer_id` | `VARCHAR(50)` | ✅ | Customer identifier | Must exist in `customer.csv` | `CUST-00000001` |
| 2 | `measurement_date` | `DATE` | ✅ | Date of measurement | `YYYY-MM-DD` | `2026-08-01` |
| 3 | `latency_ms` | `DECIMAL(8,2)` | | Round-trip network latency (ms) | `0 ≤ latency ≤ 10000` | `28.50` |
| 4 | `signal_strength` | `DECIMAL(5,2)` | | Signal quality (0–100 normalized) | `0 ≤ signal_strength ≤ 100` | `85.00` |
| 5 | `drop_rate` | `DECIMAL(5,4)` | | Call drop probability | `0 ≤ drop_rate ≤ 1` | `0.0050` |
| 6 | `packet_loss` | `DECIMAL(5,4)` | | Packet loss probability | `0 ≤ packet_loss ≤ 1` | `0.0010` |
| 7 | `coverage_score` | `DECIMAL(5,2)` | | Composite coverage quality (0–100) | `0 ≤ coverage_score ≤ 100` | `92.00` |

### Primary Key

`(customer_id, measurement_date)` — composite

### Data Distribution (Expected)

| Column | Distribution | Typical Range |
|--------|-------------|---------------|
| `latency_ms` | Log-normal, μ=35ms | 10–200ms |
| `signal_strength` | Beta-like, peak at 75–95 | 40–98 |
| `drop_rate` | Zero-inflated: 80% at 0, remaining Beta | 0–0.15 |
| `packet_loss` | Zero-inflated: 90% at 0 | 0–0.05 |
| `coverage_score` | Normal-ish, μ=85 | 50–98 |

### Regional Variation

| Region | Latency (avg) | Coverage (avg) | Drop Rate (avg) |
|--------|:------------:|:--------------:|:---------------:|
| East | 28ms | 92 | 0.005 |
| South | 32ms | 88 | 0.008 |
| North | 25ms | 90 | 0.004 |
| West | 45ms | 78 | 0.012 |
| Central | 35ms | 85 | 0.007 |

### Example Rows

```csv
customer_id,measurement_date,latency_ms,signal_strength,drop_rate,packet_loss,coverage_score
CUST-00000001,2026-08-01,28.50,85.00,0.0050,0.0010,92.00
CUST-00000001,2026-08-02,31.20,82.00,0.0080,0.0020,90.00
CUST-00000008,2026-08-01,95.00,52.00,0.0420,0.0180,62.00
```

---

# 8. Customer Service Dataset

### Source System

Customer service ticketing / helpdesk

### File

`service_YYYYMMDD.csv`

### Description

Daily customer service interactions: ticket volume, complaint categories, resolution metrics, CSAT. One row per customer per day with service activity. **Only customers with service activity are present.**

### Column Definitions

| # | Column | Type | Required | Description | Validation | Example |
|---|--------|------|----------|-------------|------------|---------|
| 1 | `customer_id` | `VARCHAR(50)` | ✅ | Customer identifier | Must exist in `customer.csv` | `CUST-00000001` |
| 2 | `ticket_date` | `DATE` | ✅ | Date tickets were opened | `YYYY-MM-DD` | `2026-08-01` |
| 3 | `ticket_count` | `INTEGER` | ✅ | Number of tickets opened this day | `≥ 0` | `1` |
| 4 | `complaint_type` | `VARCHAR(50)` | | Primary complaint category | `billing`, `network`, `service`, `other` | `billing` |
| 5 | `waiting_time_min` | `DECIMAL(8,2)` | | Minutes before first agent response | `≥ 0` | `12.50` |
| 6 | `resolution_time_min` | `DECIMAL(8,2)` | | Minutes until ticket resolved | `≥ 0` | `45.00` |
| 7 | `csat_score` | `INTEGER` | | Post-resolution satisfaction survey (if completed) | `1 ≤ csat_score ≤ 5`, or empty | `4` |
| 8 | `escalation_count` | `INTEGER` | | Number of times ticket was escalated | `≥ 0`, or empty (= 0) | `0` |

### Primary Key

`(customer_id, ticket_date, complaint_type)` — composite (a customer can have multiple complaint types on the same day)

### Business Validation Rules

| Rule | Severity |
|------|----------|
| `resolution_time_min ≥ waiting_time_min` (when both present) | Warning — quarantine |
| `csat_score` outside 1–5 | Error — reject row |
| `ticket_count > 0` | Implicit — rows with `ticket_count = 0` should not exist |

### Data Distribution (Expected)

| Column | Distribution |
|--------|-------------|
| `ticket_count` | Poisson, λ=0.05/day/customer (most customers have 0 tickets most days) |
| `complaint_type` | billing 40%, network 30%, service 25%, other 5% |
| `waiting_time_min` | Log-normal, μ=10min |
| `resolution_time_min` | Log-normal, μ=60min, with long tail (complex cases) |
| `csat_score` | Skewed: 5=35%, 4=30%, 3=20%, 2=10%, 1=5% |
| `escalation_count` | 90% zero, 10% ≥ 1 |

### Example Rows

```csv
customer_id,ticket_date,ticket_count,complaint_type,waiting_time_min,resolution_time_min,csat_score,escalation_count
CUST-00000001,2026-07-15,1,billing,12.50,45.00,4,0
CUST-00000009,2026-08-01,3,network,45.00,180.00,2,1
CUST-00000010,2026-08-01,1,billing,8.00,20.00,5,0
CUST-00000010,2026-08-01,1,network,8.00,35.00,,0
```

---

# 9. Marketing Dataset

### Source System

Marketing automation / campaign platform

### File

`campaign_YYYYMMDD.csv`

### Description

Campaign touchpoints: promotions, coupons, conversion tracking. One row per customer per campaign touch. **Only customers who received a campaign are present.**

### Column Definitions

| # | Column | Type | Required | Description | Validation | Example |
|---|--------|------|----------|-------------|------------|---------|
| 1 | `customer_id` | `VARCHAR(50)` | ✅ | Customer identifier | Must exist in `customer.csv` | `CUST-00000001` |
| 2 | `campaign_id` | `VARCHAR(50)` | ✅ | Campaign identifier from marketing platform | NOT NULL | `CAMP-SPRING-2026` |
| 3 | `campaign_date` | `DATE` | ✅ | Date of campaign touch | `YYYY-MM-DD` | `2026-03-15` |
| 4 | `promotion_type` | `VARCHAR(50)` | | Type of promotion offered | `discount`, `bundle_upgrade`, `free_trial`, `loyalty_reward` | `discount` |
| 5 | `coupon_used` | `BOOLEAN` | | Did customer redeem the coupon? | `true` or `false` | `true` |
| 6 | `converted` | `BOOLEAN` | | Did the touch result in conversion? | `true` or `false` | `false` |
| 7 | `channel` | `VARCHAR(30)` | | Delivery channel | `sms`, `email`, `app_push`, `call_center` | `sms` |
| 8 | `campaign_cost` | `DECIMAL(10,2)` | | Cost attributed to this touch (USD) | `≥ 0` | `0.50` |

### Primary Key

`(customer_id, campaign_id, campaign_date)` — composite

### Data Distribution (Expected)

| Column | Distribution |
|--------|-------------|
| `promotion_type` | discount 40%, bundle_upgrade 25%, free_trial 20%, loyalty_reward 15% |
| `coupon_used` | true 25%, false 75% |
| `converted` | true 8%, false 92% |
| `channel` | sms 40%, app_push 30%, email 25%, call_center 5% |
| `campaign_cost` | sms $0.05, email $0.02, app_push $0.01, call_center $2.00 |

### Example Rows

```csv
customer_id,campaign_id,campaign_date,promotion_type,coupon_used,converted,channel,campaign_cost
CUST-00000001,CAMP-SPRING-2026,2026-03-15,discount,true,false,sms,0.05
CUST-00000002,CAMP-SPRING-2026,2026-03-15,bundle_upgrade,false,true,app_push,0.01
CUST-00000011,CAMP-LOYALTY-Q1,2026-01-20,loyalty_reward,true,true,email,0.02
```

---

# 10. Cross-Dataset Rules

## 10.1 Referential Integrity

| Rule | Enforcement |
|------|-------------|
| Every `customer_id` in `usage.csv` must exist in `customer.csv` | ETL rejects orphans; quarantines rows |
| Every `customer_id` in `billing.csv` must exist in `customer.csv` | ETL rejects orphans |
| Every `customer_id` in `network.csv` must exist in `customer.csv` | ETL rejects orphans |
| Every `customer_id` in `service.csv` must exist in `customer.csv` | ETL rejects orphans |
| Every `customer_id` in `campaign.csv` must exist in `customer.csv` | ETL rejects orphans |

## 10.2 Temporal Integrity

| Rule | Enforcement |
|------|-------------|
| `usage_date`, `measurement_date`, `ticket_date`, `campaign_date` must be ≤ current date | Warning — flag future dates |
| `join_date` in customer must be ≤ `billing_month` | Error — reject billing row |
| `join_date` in customer must be ≤ `usage_date` | Warning — quarantine usage row |
| Billing rows must exist for all active customers each month | Analytics detects gaps |

## 10.3 Logical Consistency

| Rule | Enforcement |
|------|-------------|
| A customer with `status = 'churned'` should not have recent usage rows | Warning — flag anomaly |
| A customer with `payment_status = 'overdue'` for 3+ consecutive months is likely at-risk | Analytics signal |
| High `drop_rate` + high `complaint_type = 'network'` → network quality issue confirmed | ML feature interaction |

---

# 11. Data Quality Rules

## 11.1 File-Level Validation

| Check | Action on Failure |
|-------|-------------------|
| File is readable and not empty | Reject entire file |
| File encoding is valid UTF-8 | Reject entire file |
| Header row matches expected columns (exact names) | Reject entire file |
| At least one data row after header | Warning — accept empty file |
| No duplicate `(customer_id)` in customer file | Reject duplicate rows |
| No duplicate `(customer_id, usage_date)` in usage file | Reject duplicate rows |

## 11.2 Row-Level Validation

| Check | Action on Failure |
|-------|-------------------|
| Required column is NULL/empty | **Reject row** → quarantine |
| Value out of valid range | **Reject row** → quarantine |
| Value violates business rule | **Warning** → accept with flag |
| `customer_id` references non-existent customer | **Reject row** → orphan table |
| Date is in the future | **Warning** → accept with flag |
| Duplicate primary key | **Reject row** → quarantine |

## 11.3 Quarantine Strategy

```
Raw file
    │
    ▼
Validation
    │
    ├── Valid rows ──→ raw.* (Bronze)
    │
    └── Invalid rows ──→ raw_quarantine.*
                          │
                          ├── quarantine_reason
                          ├── original_row (JSON)
                          └── imported_at
```

Quarantined rows are not loaded into the warehouse. They are reviewed weekly and either fixed at source or permanently excluded.

## 11.4 Quality Report

Every ETL run generates:

```json
{
    "batch_id": "etl_20260801_020000",
    "dataset": "customer",
    "file": "customer_20260801.csv",
    "rows_total": 1000000,
    "rows_accepted": 998500,
    "rows_quarantined": 1500,
    "quarantine_reasons": {
        "missing_required_column": 200,
        "value_out_of_range": 800,
        "duplicate_primary_key": 300,
        "orphan_customer_id": 200
    },
    "warnings": 5200,
    "duration_sec": 45.2
}
```

---

# 12. Mock Data Generation Rules

## 12.1 Purpose

The `scripts/generate_mock_data.py` utility must produce datasets that:

1. Match the exact column schema defined in §4–§9
2. Follow the expected distributions defined in each section
3. Exercise edge cases (missing values, boundary values, orphans for testing)
4. Maintain cross-dataset referential integrity
5. Produce deterministic output given a fixed random seed (for reproducible tests)

## 12.2 Generation Parameters

```python
# Conceptual — not implementation
MOCK_CONFIG = {
    "seed": 42,
    "customer_count": 1_000_000,
    "churn_rate_target": 0.12,
    "date_range": ("2023-01-01", "2026-08-01"),
    "output_dir": "data/mock/",
    "format": "csv",

    "regions": {
        "East":    {"population_share": 0.25, "city_tier": "T1"},
        "South":   {"population_share": 0.22, "city_tier": "T1/T2"},
        "North":   {"population_share": 0.18, "city_tier": "T1"},
        "West":    {"population_share": 0.20, "city_tier": "T2/T3"},
        "Central": {"population_share": 0.15, "city_tier": "T2"},
    },

    "packages": [
        {"id": "PKG-BASIC-001",   "name": "Basic Voice",    "price": 19.00, "type": "voice_only", "share": 0.20},
        {"id": "PKG-DATA-003",    "name": "Data Saver",     "price": 29.00, "type": "data_only",  "share": 0.25},
        {"id": "PKG-STANDARD-004","name": "Standard Bundle","price": 59.00, "type": "bundle",      "share": 0.30},
        {"id": "PKG-PREMIUM-001", "name": "Premium Unlimited","price": 99.00,"type": "premium",     "share": 0.15},
        {"id": "PKG-FAMILY-002",  "name": "Family Share",   "price": 79.00, "type": "family",      "share": 0.07},
        {"id": "PKG-BUSINESS-005","name": "Business Pro",   "price": 129.00,"type": "business",    "share": 0.03},
    ],
}
```

## 12.3 Edge Cases to Generate

| Scenario | Purpose |
|----------|---------|
| Customer with NULL gender and NULL age | Test missing value handling |
| Customer with `status = 'churned'` but recent usage rows | Test temporal integrity violation |
| Usage row with `customer_id` not in customer.csv | Test orphan handling |
| Billing row with `discount_amount > monthly_fee` | Test business rule violation |
| Network row with `drop_rate = 1.0` (100% drops) | Test boundary value |
| Service row with `csat_score = 0` | Test range validation |
| Campaign row with all boolean fields empty | Test missing boolean handling |
| File with duplicate `(customer_id, usage_date)` | Test deduplication |
| File with wrong header row | Test schema validation |
| Empty file (header only) | Test edge case handling |

## 12.4 Reproducibility

```bash
# Same seed → same data
python scripts/generate_mock_data.py --seed 42 --customers 1000000

# Different seed → different data, same schema
python scripts/generate_mock_data.py --seed 123 --customers 1000000

# Small dataset for fast tests
python scripts/generate_mock_data.py --seed 42 --customers 1000 --output test_fixtures/
```

---

# 13. Data Volume Specification

## 13.1 MVP Target (1 Million Customers)

| Dataset | Rows | File Size (CSV) | File Size (Parquet) |
|---------|------|:---------------:|:-------------------:|
| Customer | 1,000,000 | ~50 MB | ~15 MB |
| Usage | 90,000,000 (90 days × ~1M) | ~4.5 GB | ~600 MB |
| Billing | 12,000,000 (12 months × 1M) | ~600 MB | ~80 MB |
| Network | 90,000,000 (90 days × 1M) | ~3.6 GB | ~500 MB |
| Service | ~4,500,000 (90 days × 5% active) | ~180 MB | ~25 MB |
| Marketing | ~3,000,000 (12 weeks × ~250K touches) | ~120 MB | ~18 MB |
| **Total** | **~200,500,000 rows** | **~9 GB** | **~1.2 GB** |

## 13.2 Growth Projections

| Phase | Customers | Total Rows | Warehouse Size |
|-------|:---------:|:----------:|:--------------:|
| MVP | 1M | ~200M | ~5 GB |
| V1.5 | 5M | ~1B | ~25 GB |
| V2.0 | 10M | ~2B | ~50 GB |
| Enterprise | 50M+ | ~10B+ | ~250 GB+ |

---

# 14. ETL Contract

## 14.1 What ETL Must Do

```
Input File (CSV)
    │
    ▼
1. Schema Validation     ← Check columns match this spec
    │
    ▼
2. Type Conversion       ← String → int/float/date/bool
    │
    ▼
3. Row Validation        ← Apply rules from §11.2
    │
    ├── Valid   → raw.* (Bronze)
    └── Invalid → raw_quarantine.*
    │
    ▼
4. Deduplication         ← Remove duplicate primary keys
    │
    ▼
5. Key Resolution        ← Map source customer_id → warehouse surrogate key
    │
    ▼
6. Warehouse Loading     ← Insert into warehouse.* (Silver)
    │
    ▼
7. Quality Report        ← Generate JSON report (§11.4)
```

## 14.2 ETL Idempotency

- Running the same ETL job twice with the same input file must produce the same warehouse state.
- Bronze rows are never updated (AR-010).
- Silver rows are upserted by primary key.

## 14.3 ETL Error Handling

| Error Type | Behavior |
|------------|----------|
| File not found | Alert, retry 3× with 5min backoff, then fail |
| Schema mismatch | Reject entire file, alert immediately |
| Row validation failures | Quarantine invalid rows, continue processing valid rows |
| Database connection lost | Retry 3×, then fail with alert |
| Disk full | Fail immediately, alert |

---

# Document Freeze

This document freezes the **input data contract** for InsightFlow Version 1.0.

From this point onward:

- All ETL pipelines must accept data matching the exact column schemas in §4–§9.
- Mock data generators must produce data following the distributions in §12.
- Test fixtures must include the edge cases listed in §12.3.
- Any change to a dataset schema requires an ADR and a new file format version.
- Data providers (simulated or real) must deliver files conforming to this specification.
