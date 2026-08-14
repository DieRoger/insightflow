"""Canonical Loader — persist adapter canonical output into the warehouse.

Per the data plan §7: canonical tables (customer/subscription/service/billing/
churn) are loaded into the Star Schema with provenance tracking. Each dataset
is loaded independently — never UNIONed.

Mappings:
    customer     → warehouse.dim_customer     (upsert by source_customer_id)
    subscription → warehouse.dim_subscription (upsert by source+dataset)
    billing      → warehouse.fact_billing     (per billing_month)
    churn        → updates dim_customer.status (active/churned)
"""

import sys
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.logging import get_logger  # noqa: E402

logger = get_logger(__name__)


def _bool_map(s: pd.Series) -> pd.Series:
    """Map Yes/No (and True/False) to Python bool.

    Values outside the boolean vocabulary (e.g. 'DSL', 'Fiber optic' in
    internet_service) are preserved unchanged — never coerced to NaN.
    """
    mapping = {"Yes": True, "No": False, "true": True, "false": False}
    results: list[object] = []
    for v in s.tolist():
        if isinstance(v, bool):
            results.append(v)
        elif v in mapping:
            results.append(mapping[v])
        else:
            results.append(v)
    # Return dtype=object so scalar access yields plain Python values
    return pd.Series(results, index=s.index, dtype=object)


def _fill_bool(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Coerce Yes/No string columns to nullable booleans.

    Only columns whose values are ALL within the boolean vocabulary are
    converted. Enum-like columns (e.g. internet_service with 'DSL',
    'Fiber optic', 'No') keep their string values untouched so they can
    be stored in a VARCHAR column.
    """
    bool_vocab = {"Yes", "No", "true", "false"}
    out = df.copy()
    for col in cols:
        if col not in out.columns:
            continue
        values = out[col].dropna().unique()
        if len(values) == 0:
            continue
        # bool dtype columns are already boolean; string columns must be
        # entirely within the vocabulary to be converted
        is_bool_dtype = pd.api.types.is_bool_dtype(out[col])
        if is_bool_dtype or all(v in bool_vocab for v in values):
            out[col] = _bool_map(out[col])
    return out


async def load_canonical(
    engine: AsyncEngine, canonical: dict[str, pd.DataFrame], dataset_id: str
) -> dict[str, int]:
    """Load canonical tables into the warehouse. Returns per-table row counts."""
    counts: dict[str, int] = {}

    # ------------------------------------------------------------------
    # 1. customer → dim_customer (upsert)
    # ------------------------------------------------------------------
    if "customer" in canonical:
        customer = canonical["customer"].copy()
        # churn label drives status
        if "churn" in canonical:
            churn_map = canonical["churn"].set_index("source_customer_id")["is_churn"].to_dict()
            customer["_is_churn"] = customer["source_customer_id"].map(churn_map)
        else:
            customer["_is_churn"] = 0
        customer["status"] = customer["_is_churn"].map({1: "churned", 0: "active"})
        customer["lifecycle_stage"] = customer["status"].map(
            {"churned": "churned", "active": "active"}
        )

        # join_date is NOT NULL — derive from tenure when subscription data exists
        if "subscription" in canonical and not canonical["subscription"].empty:
            tenure_map = (
                canonical["subscription"]
                .set_index("source_customer_id")["tenure_months"]
                .fillna(0)
                .to_dict()
            )
        else:
            tenure_map = {}
        from datetime import timedelta

        customer["join_date"] = customer["source_customer_id"].apply(
            lambda sid: date.today() - timedelta(days=int(tenure_map.get(sid, 0)) * 30)
        )

        # contract_type lives in the subscription table — merge it in
        if "subscription" in canonical and not canonical["subscription"].empty:
            contract_map = (
                canonical["subscription"]
                .dropna(subset=["contract_type"])
                .set_index("source_customer_id")["contract_type"]
                .to_dict()
            )
            customer["contract_type"] = customer["source_customer_id"].map(contract_map)
        elif "contract_type" not in customer.columns:
            customer["contract_type"] = None

        rows = 0
        async with engine.begin() as conn:
            for _, row in customer.iterrows():
                await conn.execute(
                    text(
                        """
                        INSERT INTO warehouse.dim_customer (
                            source_customer_id, gender, contract_type, status,
                            lifecycle_stage, join_date, created_at, updated_at
                        ) VALUES (:sid, :gender, :contract, :status, :lifecycle, :join_date, now(), now())
                        ON CONFLICT (source_customer_id) DO UPDATE SET
                            gender = EXCLUDED.gender,
                            contract_type = COALESCE(EXCLUDED.contract_type, warehouse.dim_customer.contract_type),
                            status = EXCLUDED.status,
                            lifecycle_stage = EXCLUDED.lifecycle_stage,
                            join_date = COALESCE(EXCLUDED.join_date, warehouse.dim_customer.join_date),
                            updated_at = now()
                        """
                    ),
                    {
                        "sid": str(row["source_customer_id"]),
                        "gender": row.get("gender") if pd.notna(row.get("gender")) else None,
                        "contract": row.get("contract_type")
                        if pd.notna(row.get("contract_type"))
                        else None,
                        "status": str(row["status"]),
                        "lifecycle": str(row["lifecycle_stage"]),
                        "join_date": row["join_date"],
                    },
                )
                rows += 1
        counts["customer"] = rows
        logger.info("canonical_customer_loaded", dataset=dataset_id, rows=rows)

    # ------------------------------------------------------------------
    # 2. subscription → dim_subscription (upsert by source + dataset)
    # ------------------------------------------------------------------
    if "subscription" in canonical:
        sub = canonical["subscription"].copy()
        # merge service booleans if present
        if "service" in canonical and not canonical["service"].empty:
            svc = canonical["service"].copy()
            svc = _fill_bool(svc, [c for c in svc.columns if c != "source_customer_id"])
            sub = sub.merge(svc, on="source_customer_id", how="left")

        rows = 0
        async with engine.begin() as conn:
            for _, row in sub.iterrows():
                await conn.execute(
                    text(
                        """
                        INSERT INTO warehouse.dim_subscription (
                            source_customer_id, dataset_id, tenure_months, contract_type,
                            is_paperless_billing, payment_method,
                            phone_service, multiple_lines, internet_service,
                            online_security, online_backup, device_protection,
                            tech_support, streaming_tv, streaming_movies
                        ) VALUES (
                            :sid, :dataset_id, :tenure, :contract,
                            :paperless, :payment,
                            :phone, :multi, :internet,
                            :security, :backup, :device,
                            :support, :tv, :movies
                        )
                        ON CONFLICT (source_customer_id, dataset_id) DO UPDATE SET
                            tenure_months = EXCLUDED.tenure_months,
                            contract_type = EXCLUDED.contract_type,
                            is_paperless_billing = EXCLUDED.is_paperless_billing,
                            payment_method = EXCLUDED.payment_method,
                            phone_service = EXCLUDED.phone_service,
                            multiple_lines = EXCLUDED.multiple_lines,
                            internet_service = EXCLUDED.internet_service,
                            online_security = EXCLUDED.online_security,
                            online_backup = EXCLUDED.online_backup,
                            device_protection = EXCLUDED.device_protection,
                            tech_support = EXCLUDED.tech_support,
                            streaming_tv = EXCLUDED.streaming_tv,
                            streaming_movies = EXCLUDED.streaming_movies,
                            loaded_at = now()
                        """
                    ),
                    {
                        "sid": str(row["source_customer_id"]),
                        "dataset_id": dataset_id,
                        "tenure": int(row["tenure_months"])
                        if pd.notna(row.get("tenure_months"))
                        else None,
                        "contract": row.get("contract_type")
                        if pd.notna(row.get("contract_type"))
                        else None,
                        "paperless": bool(row["is_paperless_billing"])
                        if pd.notna(row.get("is_paperless_billing"))
                        else None,
                        "payment": row.get("payment_method")
                        if pd.notna(row.get("payment_method"))
                        else None,
                        "phone": _val_bool(row, "phone_service"),
                        "multi": _val_bool(row, "multiple_lines"),
                        "internet": row.get("internet_service")
                        if pd.notna(row.get("internet_service"))
                        else None,
                        "security": _val_bool(row, "online_security"),
                        "backup": _val_bool(row, "online_backup"),
                        "device": _val_bool(row, "device_protection"),
                        "support": _val_bool(row, "tech_support"),
                        "tv": _val_bool(row, "streaming_tv"),
                        "movies": _val_bool(row, "streaming_movies"),
                    },
                )
                rows += 1
        counts["subscription"] = rows
        logger.info("canonical_subscription_loaded", dataset=dataset_id, rows=rows)

    # ------------------------------------------------------------------
    # 3. billing → fact_billing (per billing_month; needs dim_time + dim_customer)
    # ------------------------------------------------------------------
    if "billing" in canonical and not canonical["billing"].empty:
        billing = canonical["billing"].copy()
        billing_month = date.today().replace(day=1)
        date_id = int(billing_month.strftime("%Y%m%d"))

        # Ensure dim_time row exists for this month
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO warehouse.dim_time (date_id, full_date, year, quarter, month, week, day, day_of_week, day_name, is_weekend, fiscal_year, fiscal_quarter)
                    VALUES (:date_id, :full_date, :year, :quarter, :month, 1, 1, 1, 'Monday', false, :year, :quarter)
                    ON CONFLICT (date_id) DO NOTHING
                    """
                ),
                {
                    "date_id": date_id,
                    "full_date": billing_month,
                    "year": billing_month.year,
                    "quarter": (billing_month.month - 1) // 3 + 1,
                    "month": billing_month.month,
                },
            )

            rows = 0
            # Resolve a package for this dataset (map contract_type → generic package)
            package_result = await conn.execute(
                text(
                    """
                    SELECT package_id FROM warehouse.dim_package
                    WHERE source_package_id = :pkg
                    """
                ),
                {"pkg": f"SRC-{dataset_id}"},
            )
            pkg_row = package_result.fetchone()
            if pkg_row is None:
                pkg_result = await conn.execute(
                    text(
                        """
                        INSERT INTO warehouse.dim_package (
                            source_package_id, package_name, package_type, monthly_price
                        ) VALUES (:pkg, :name, 'external', 0)
                        ON CONFLICT (source_package_id) DO NOTHING
                        RETURNING package_id
                        """
                    ),
                    {"pkg": f"SRC-{dataset_id}", "name": f"Source {dataset_id}"},
                )
                pkg_row = pkg_result.fetchone()
            package_id = int(pkg_row[0]) if pkg_row else None

            for _, row in billing.iterrows():
                sid = str(row["source_customer_id"])
                # Resolve warehouse customer_id
                cid_result = await conn.execute(
                    text(
                        "SELECT customer_id FROM warehouse.dim_customer WHERE source_customer_id = :sid"
                    ),
                    {"sid": sid},
                )
                cid_row = cid_result.fetchone()
                if cid_row is None:
                    continue
                monthly = (
                    float(row["monthly_charges"]) if pd.notna(row.get("monthly_charges")) else 0.0
                )
                # Idempotent: delete existing row for this customer+month, then insert
                await conn.execute(
                    text(
                        "DELETE FROM warehouse.fact_billing WHERE customer_id = :cid AND billing_month = :bm"
                    ),
                    {"cid": int(cid_row[0]), "bm": billing_month},
                )
                await conn.execute(
                    text(
                        """
                        INSERT INTO warehouse.fact_billing (
                            customer_id, package_id, date_id, billing_month,
                            monthly_fee, discount_amount, net_revenue,
                            payment_status, overdue_days, package_price
                        ) VALUES (
                            :cid, :package_id, :date_id, :billing_month,
                            :monthly, 0, :monthly,
                            'paid', 0, :monthly
                        )
                        """
                    ),
                    {
                        "cid": int(cid_row[0]),
                        "package_id": package_id,
                        "date_id": date_id,
                        "billing_month": billing_month,
                        "monthly": monthly,
                    },
                )
                rows += 1
            counts["billing"] = rows
            logger.info("canonical_billing_loaded", dataset=dataset_id, rows=rows)

    return counts


def _val_bool(row: pd.Series, col: str) -> bool | None:
    """Return a nullable bool from a row column.

    Only true boolean semantics (Yes/No/True/False) map to bool; any other
    value (e.g. 'No phone service' in MultipleLines) becomes None rather
    than a non-bool that the DB would reject.
    """
    val = row.get(col)
    if val is None or pd.isna(val):
        return None
    if isinstance(val, bool):
        return val
    mapped = _bool_map(pd.Series([val])).iloc[0]
    # numpy bool (np.False_/np.True_) is not a Python bool — check both
    if mapped is True or mapped is False:
        return bool(mapped)
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio

    from app.infrastructure.database.session import engine

    async def main() -> None:
        from app.warehouse.adapters import IBMTelcoAdapter

        adapter = IBMTelcoAdapter()
        raw = adapter.load_raw(Path("data/raw/ibm_telco_v1/WA_Fn-UseC_-Telco-Customer-Churn.csv"))
        canonical = adapter.to_canonical(raw)
        counts = await load_canonical(engine, canonical, adapter.registry_entry.dataset_id)
        logger.info("canonical_loader_cli_complete", counts=counts)
        await engine.dispose()

    asyncio.run(main())
