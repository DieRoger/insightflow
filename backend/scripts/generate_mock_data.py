"""Telecom mock data generator — produces the six InsightFlow datasets.

Datasets follow 04_DATASET_SPEC.md §4–§9 column contracts and §12
distribution parameters. Output is deterministic given a fixed seed.

Usage:
    uv run python scripts/generate_mock_data.py --seed 42 --customers 1000000
    uv run python scripts/generate_mock_data.py --seed 42 --customers 1000 --days 30
"""

import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# --- Distribution parameters (04_DATASET_SPEC.md §12.2) ---------------------

REGIONS = [
    ("East", 0.25, "T1"),
    ("South", 0.22, "T1"),
    ("North", 0.18, "T1"),
    ("West", 0.20, "T2"),
    ("Central", 0.15, "T2"),
]

PACKAGES = [
    ("PKG-BASIC-001", "Basic Voice", "voice_only", 19.00, 2.0, 100, 50, 0.20),
    ("PKG-DATA-003", "Data Saver", "data_only", 29.00, 30.0, 0, 0, 0.25),
    ("PKG-STANDARD-004", "Standard Bundle", "bundle", 59.00, 60.0, 300, 100, 0.30),
    ("PKG-PREMIUM-001", "Premium Unlimited", "premium", 99.00, 100.0, 1000, 500, 0.15),
    ("PKG-FAMILY-002", "Family Share", "family", 79.00, 80.0, 500, 200, 0.07),
    ("PKG-BUSINESS-005", "Business Pro", "business", 129.00, 200.0, 2000, 1000, 0.03),
]

CITIES = {
    "East": [("Shanghai", "T1"), ("Suzhou", "T2"), ("Hangzhou", "T1")],
    "South": [("Guangzhou", "T1"), ("Shenzhen", "T1"), ("Foshan", "T2")],
    "North": [("Beijing", "T1"), ("Tianjin", "T1"), ("Shijiazhuang", "T2")],
    "West": [("Chengdu", "T1"), ("Chongqing", "T1"), ("Kunming", "T2")],
    "Central": [("Wuhan", "T1"), ("Changsha", "T2"), ("Zhengzhou", "T2")],
}

PROVINCES = {
    "East": "Shanghai/Jiangsu/Zhejiang",
    "South": "Guangdong",
    "North": "Beijing/Hebei",
    "West": "Sichuan/Chongqing/Yunnan",
    "Central": "Hubei/Hunan/Henan",
}

CAMPAIGN_IDS = ["CAMP-SPRING-2026", "CAMP-SUMMER-2026", "CAMP-LOYALTY-Q1", "CAMP-RETENTION-Q2"]
PROMOTION_TYPES = ["discount", "bundle_upgrade", "free_trial", "loyalty_reward"]
PROMOTION_WEIGHTS = [0.40, 0.25, 0.20, 0.15]
CHANNELS = ["sms", "app_push", "email", "call_center"]
CHANNEL_WEIGHTS = [0.40, 0.30, 0.25, 0.05]
CHANNEL_COST = {"sms": 0.05, "app_push": 0.01, "email": 0.02, "call_center": 2.00}


def generate_customers(rng: np.random.Generator, n: int) -> pd.DataFrame:
    """Generate the customer master dataset (04_DATASET_SPEC.md §4)."""
    # Region assignment by population share
    region_shares = np.array([r[1] for r in REGIONS])
    region_idx = rng.choice(len(REGIONS), size=n, p=region_shares)

    # City within region
    cities = []
    provinces = []
    for idx in region_idx:
        city, _ = CITIES[REGIONS[idx][0]][rng.integers(0, len(CITIES[REGIONS[idx][0]]))]
        cities.append(city)
        provinces.append(PROVINCES[REGIONS[idx][0]].split("/")[0])

    # Gender: 52/47/1
    gender = rng.choice(["Male", "Female", "Other"], size=n, p=[0.52, 0.47, 0.01])
    # Age: normal clipped to [18, 90]
    age = np.clip(rng.normal(38, 14, n).astype(int), 18, 90).astype(object)
    age[rng.random(n) < 0.03] = None  # 3% missing age

    # Join date: uniform over last 5 years
    end = date(2026, 7, 31)
    start = end - timedelta(days=5 * 365)
    join_days = rng.integers(0, (end - start).days, size=n)
    join_date = [start + timedelta(days=int(d)) for d in join_days]

    # Contract type: postpaid 60 / prepaid 35 / hybrid 5
    contract = rng.choice(["postpaid", "prepaid", "hybrid"], size=n, p=[0.60, 0.35, 0.05])

    # Package
    pkg_weights = np.array([p[6] for p in PACKAGES], dtype=float)
    pkg_weights = pkg_weights / pkg_weights.sum()
    pkg_idx = rng.choice(len(PACKAGES), size=n, p=pkg_weights)
    package_ids = [PACKAGES[i][0] for i in pkg_idx]
    package_names = [PACKAGES[i][1] for i in pkg_idx]

    # Status: active 85 / suspended 3 / churned 12 (churned biased to longer tenure)
    status = np.array(["active"] * n)
    churn_mask = rng.random(n) < 0.12
    suspended_mask = (~churn_mask) & (rng.random(n) < 0.03)
    status[churn_mask] = "churned"
    status[suspended_mask] = "suspended"

    df = pd.DataFrame(
        {
            "customer_id": [f"CUST-{i:08d}" for i in range(n)],
            "gender": gender,
            "age": age,
            "city": cities,
            "province": provinces,
            "join_date": join_date,
            "contract_type": contract,
            "package_id": package_ids,
            "package_name": package_names,
            "status": status,
        }
    )
    return df


def generate_usage(
    rng: np.random.Generator,
    customers: pd.DataFrame,
    days: int,
) -> pd.DataFrame:
    """Generate daily usage records (04_DATASET_SPEC.md §5).

    Only customers with activity appear. ~85% of active customers have
    usage each day; log-normal data volumes.
    """
    end = date(2026, 7, 31)
    records = []

    active = customers[customers["status"] == "active"]
    n_active = len(active)

    for day_offset in range(days):
        usage_date = end - timedelta(days=day_offset)
        # ~85% active customers use data each day
        active_mask = rng.random(n_active) < 0.85
        users = active[active_mask]

        n = len(users)
        if n == 0:
            continue

        # Log-normal data: median ~500MB, heavy tail
        data_mb = np.exp(rng.normal(np.log(500), 1.0, n)).astype(float)
        data_mb = np.clip(data_mb, 1, 20000)

        voice = np.exp(rng.normal(np.log(25), 0.9, n)).astype(float)
        voice = np.clip(voice, 0, 600)

        sms = rng.poisson(2, n)
        peak = (data_mb * rng.uniform(0.55, 0.75, n)).astype(float)

        roaming = np.where(rng.random(n) < 0.05, rng.uniform(10, 500, n), 0.0)
        intl = np.where(rng.random(n) < 0.02, rng.uniform(1, 60, n), 0.0)

        df = pd.DataFrame(
            {
                "customer_id": users["customer_id"].values,
                "usage_date": usage_date,
                "voice_minutes": np.round(voice, 2),
                "sms_count": sms,
                "data_usage_mb": np.round(data_mb, 2),
                "roaming_usage_mb": np.round(roaming, 2),
                "peak_usage_mb": np.round(peak, 2),
                "international_minutes": np.round(intl, 2),
            }
        )
        records.append(df)

    return pd.concat(records, ignore_index=True)


def generate_billing(
    rng: np.random.Generator, customers: pd.DataFrame, months: int
) -> pd.DataFrame:
    """Generate monthly billing records (04_DATASET_SPEC.md §6)."""
    # All active/suspended customers get billing rows
    billable = customers[customers["status"] != "churned"]
    records = []

    for m in range(months):
        # billing month = first day of month, going back
        month_date = date(2026, 7, 1) - timedelta(days=m * 31)
        month_date = month_date.replace(day=1)

        n = len(billable)
        rows = pd.DataFrame(
            {
                "customer_id": billable["customer_id"].values,
                "billing_month": month_date,
            }
        )
        rows["monthly_fee"] = billable.apply(
            lambda r: next(p[3] for p in PACKAGES if p[0] == r["package_id"]), axis=1
        )
        rows["package_price"] = rows["monthly_fee"]
        rows["discount_amount"] = np.where(rng.random(n) < 0.30, rng.uniform(2, 20, n), 0.0).astype(
            float
        )
        rows["discount_amount"] = np.minimum(rows["discount_amount"], rows["monthly_fee"] * 0.5)

        pay = rng.random(n)
        rows["payment_status"] = np.where(
            pay < 0.85, "paid", np.where(pay < 0.95, "pending", "overdue")
        )
        rows["overdue_days"] = np.where(
            rows["payment_status"] == "overdue", rng.integers(1, 60, n), 0
        )
        rows["payment_method"] = rng.choice(
            ["credit_card", "wallet", "bank_transfer", "cash"], size=n, p=[0.45, 0.30, 0.20, 0.05]
        )
        records.append(rows)

    return pd.concat(records, ignore_index=True)


def generate_network(rng: np.random.Generator, customers: pd.DataFrame, days: int) -> pd.DataFrame:
    """Generate network quality records (04_DATASET_SPEC.md §7).

    Regional variation: East best, West worst.
    """
    end = date(2026, 7, 31)
    records = []
    active = customers[customers["status"] == "active"]

    # Latency by region
    region_latency = {"East": 28, "South": 32, "North": 25, "West": 45, "Central": 35}
    region_coverage = {"East": 92, "South": 88, "North": 90, "West": 78, "Central": 85}

    for day_offset in range(days):
        mdate = end - timedelta(days=day_offset)
        n = len(active)
        # ~70% of active customers have measurements each day
        mask = rng.random(n) < 0.70
        users = active[mask]
        n = len(users)

        lat_base = np.array(
            [
                region_latency[r]
                for r in users["province"].map(
                    lambda p: next(k for k, v in PROVINCES.items() if p in v)
                )
            ]
        )
        latency = np.abs(rng.normal(0, 1, n) * 5 + lat_base).astype(float)

        cov_base = np.array(
            [
                region_coverage[r]
                for r in users["province"].map(
                    lambda p: next(k for k, v in PROVINCES.items() if p in v)
                )
            ]
        )
        coverage = np.clip(rng.normal(0, 1, n) * 5 + cov_base, 50, 98).astype(float)

        drop = np.where(rng.random(n) < 0.80, 0.0, rng.beta(2, 12, n)).astype(float)
        packet_loss = np.where(rng.random(n) < 0.90, 0.0, rng.beta(1.5, 20, n)).astype(float)
        signal = np.clip(rng.normal(85, 8, n), 40, 99).astype(float)

        df = pd.DataFrame(
            {
                "customer_id": users["customer_id"].values,
                "measurement_date": mdate,
                "latency_ms": np.round(latency, 2),
                "signal_strength": np.round(signal, 2),
                "drop_rate": np.round(drop, 4),
                "packet_loss": np.round(packet_loss, 4),
                "coverage_score": np.round(coverage, 2),
            }
        )
        records.append(df)

    return pd.concat(records, ignore_index=True)


def generate_service(rng: np.random.Generator, customers: pd.DataFrame, days: int) -> pd.DataFrame:
    """Generate service tickets (04_DATASET_SPEC.md §8). Sparse — Poisson λ≈0.05/day."""
    end = date(2026, 7, 31)
    records = []
    active = customers[customers["status"] == "active"]

    complaint_types = ["billing", "network", "service", "other"]
    complaint_weights = [0.40, 0.30, 0.25, 0.05]

    for day_offset in range(days):
        tdate = end - timedelta(days=day_offset)
        n = len(active)
        # ~5% of customers have a ticket on any given day
        ticket_mask = rng.random(n) < 0.05
        users = active[ticket_mask]
        n = len(users)
        if n == 0:
            continue

        ticket_count = rng.poisson(1.2, n).clip(1, 5)
        complaint = rng.choice(complaint_types, size=n, p=complaint_weights)
        waiting = np.round(np.exp(rng.normal(np.log(10), 0.7, n)), 2)
        resolution = np.round(np.exp(rng.normal(np.log(60), 0.9, n)), 2)
        csat = rng.choice([5, 4, 3, 2, 1], size=n, p=[0.35, 0.30, 0.20, 0.10, 0.05])
        csat_series = pd.Series(csat, dtype="Int64")
        csat_series[rng.random(n) < 0.30] = pd.NA  # 30% no survey → empty in CSV
        escalation = np.where(rng.random(n) < 0.10, rng.integers(1, 4, n), 0)

        df = pd.DataFrame(
            {
                "customer_id": users["customer_id"].values,
                "ticket_date": tdate,
                "ticket_count": ticket_count,
                "complaint_type": complaint,
                "waiting_time_min": waiting,
                "resolution_time_min": resolution,
                "csat_score": csat_series,
                "escalation_count": escalation,
            }
        )
        records.append(df)

    return pd.concat(records, ignore_index=True)


def generate_campaign(
    rng: np.random.Generator, customers: pd.DataFrame, weeks: int
) -> pd.DataFrame:
    """Generate campaign touches (04_DATASET_SPEC.md §9). Weekly, ~25% of active customers."""
    records = []
    active = customers[customers["status"] == "active"]

    for w in range(weeks):
        cdate = date(2026, 7, 27) - timedelta(weeks=w)
        n = len(active)
        touch_mask = rng.random(n) < 0.25
        users = active[touch_mask]
        n = len(users)

        campaign_id = rng.choice(CAMPAIGN_IDS, size=n)
        promotion = rng.choice(PROMOTION_TYPES, size=n, p=PROMOTION_WEIGHTS)
        channel = rng.choice(CHANNELS, size=n, p=CHANNEL_WEIGHTS)
        coupon = rng.random(n) < 0.25
        converted = rng.random(n) < 0.08
        cost = np.array([CHANNEL_COST[c] for c in channel])

        df = pd.DataFrame(
            {
                "customer_id": users["customer_id"].values,
                "campaign_id": campaign_id,
                "campaign_date": cdate,
                "promotion_type": promotion,
                "coupon_used": coupon,
                "converted": converted,
                "channel": channel,
                "campaign_cost": cost,
            }
        )
        records.append(df)

    return pd.concat(records, ignore_index=True)


def write_csv(df: pd.DataFrame, path: Path) -> None:
    """Write dataframe to CSV with the dataset spec conventions."""
    df.to_csv(path, index=False, date_format="%Y-%m-%d")
    print(f"  {path.name}: {len(df):,} rows, {path.stat().st_size / 1024 / 1024:.1f} MB")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate InsightFlow mock datasets")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (reproducibility)")
    parser.add_argument("--customers", type=int, default=10000, help="Number of customers")
    parser.add_argument("--days", type=int, default=90, help="Usage/network/service history days")
    parser.add_argument("--months", type=int, default=12, help="Billing history months")
    parser.add_argument("--weeks", type=int, default=12, help="Campaign history weeks")
    parser.add_argument("--output-dir", type=str, default="data/mock", help="Output directory")
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating {args.customers:,} customers (seed={args.seed})...")

    customers = generate_customers(rng, args.customers)
    write_csv(customers, out_dir / "customer.csv")

    print(f"Generating usage ({args.days} days)...")
    usage = generate_usage(rng, customers, args.days)
    write_csv(usage, out_dir / "usage.csv")

    print(f"Generating billing ({args.months} months)...")
    billing = generate_billing(rng, customers, args.months)
    write_csv(billing, out_dir / "billing.csv")

    print(f"Generating network ({args.days} days)...")
    network = generate_network(rng, customers, args.days)
    write_csv(network, out_dir / "network.csv")

    print(f"Generating service ({args.days} days)...")
    service = generate_service(rng, customers, args.days)
    write_csv(service, out_dir / "service.csv")

    print(f"Generating campaign ({args.weeks} weeks)...")
    campaign = generate_campaign(rng, customers, args.weeks)
    write_csv(campaign, out_dir / "campaign.csv")

    print(f"Done. Output in {out_dir}")


if __name__ == "__main__":
    main()
