"""Unit tests for the data quality layer and IBM Telco adapter."""

import pandas as pd

from app.warehouse.adapters import IBMTelcoAdapter
from app.warehouse.quality import ColumnRule, ConsistencyRule, run_quality_checks


def make_telco_df() -> pd.DataFrame:
    """A small valid IBM Telco-shaped dataframe."""
    return pd.DataFrame(
        {
            "customerID": [f"CUST-{i:04d}" for i in range(10)],
            "gender": ["Male", "Female"] * 5,
            "SeniorCitizen": [0, 1] * 5,
            "Partner": ["Yes", "No"] * 5,
            "Dependents": ["No", "Yes"] * 5,
            "tenure": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "PhoneService": ["Yes"] * 10,
            "MultipleLines": ["No"] * 10,
            "InternetService": ["DSL", "Fiber optic"] * 5,
            "OnlineSecurity": ["No", "Yes"] * 5,
            "OnlineBackup": ["No", "Yes"] * 5,
            "DeviceProtection": ["No", "Yes"] * 5,
            "TechSupport": ["No", "Yes"] * 5,
            "StreamingTV": ["No", "Yes"] * 5,
            "StreamingMovies": ["No", "Yes"] * 5,
            "Contract": ["Month-to-month", "Two year"] * 5,
            "PaperlessBilling": ["Yes", "No"] * 5,
            "PaymentMethod": ["Electronic check", "Credit card (automatic)"] * 5,
            "MonthlyCharges": [20.5 + i for i in range(10)],
            "TotalCharges": [20.5 + i * 30 for i in range(10)],
            "Churn": ["No", "Yes"] * 5,
        }
    )


class TestRunQualityChecks:
    def test_clean_data_scores_100(self) -> None:
        df = make_telco_df()
        report = run_quality_checks(
            df,
            dataset_id="TEST_V1",
            column_rules=[
                ColumnRule("customerID", "required"),
                ColumnRule("gender", "enum", ["Male", "Female"]),
                ColumnRule("tenure", "non_negative"),
            ],
            unique_keys=["customerID"],
        )
        assert report.completeness == 100.0
        assert report.validity == 100.0
        assert report.uniqueness == 100.0
        assert report.overall_score == 100.0
        assert report.rows_valid == len(df)

    def test_missing_required_flagged(self) -> None:
        df = make_telco_df()
        df.loc[2, "customerID"] = None
        report = run_quality_checks(
            df,
            dataset_id="TEST_V1",
            column_rules=[ColumnRule("customerID", "required")],
        )
        assert report.completeness < 100.0
        assert any(i.column == "customerID" and i.rule == "completeness" for i in report.issues)

    def test_invalid_enum_flagged(self) -> None:
        df = make_telco_df()
        df.loc[0, "gender"] = "Unknown"
        report = run_quality_checks(
            df,
            dataset_id="TEST_V1",
            column_rules=[ColumnRule("gender", "enum", ["Male", "Female"])],
        )
        assert report.validity < 100.0
        assert any(i.rule == "validity" for i in report.issues)

    def test_duplicate_keys_flagged(self) -> None:
        df = make_telco_df()
        df.loc[5, "customerID"] = df.loc[0, "customerID"]  # duplicate
        report = run_quality_checks(
            df,
            dataset_id="TEST_V1",
            column_rules=[ColumnRule("customerID", "required")],
            unique_keys=["customerID"],
        )
        assert report.uniqueness < 100.0
        assert any(i.rule == "uniqueness" for i in report.issues)

    def test_consistency_rule_flagged(self) -> None:
        df = make_telco_df()
        df.loc[0, "TotalCharges"] = 0.0  # violates total >= monthly
        report = run_quality_checks(
            df,
            dataset_id="TEST_V1",
            column_rules=[],
            consistency_rules=[
                ConsistencyRule(
                    name="total_gte_monthly",
                    expression="TotalCharges >= MonthlyCharges",
                )
            ],
        )
        assert report.consistency < 100.0
        assert any(i.rule == "consistency" for i in report.issues)

    def test_negative_value_flagged(self) -> None:
        df = make_telco_df()
        df.loc[3, "tenure"] = -5
        report = run_quality_checks(
            df,
            dataset_id="TEST_V1",
            column_rules=[ColumnRule("tenure", "non_negative")],
        )
        assert report.validity < 100.0

    def test_issue_samples_capture_bad_rows(self) -> None:
        df = make_telco_df()
        df.loc[[0, 1], "gender"] = "X"
        report = run_quality_checks(
            df,
            dataset_id="TEST_V1",
            column_rules=[ColumnRule("gender", "enum", ["Male", "Female"])],
        )
        issue = next(i for i in report.issues if i.rule == "validity")
        assert issue.failed_count == 2
        assert len(issue.samples) >= 1


class TestIBMTelcoAdapter:
    def test_load_raw_coerces_total_charges(self) -> None:
        adapter = IBMTelcoAdapter()
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "telco.csv"
            make_telco_df().to_csv(path, index=False)
            df = adapter.load_raw(path)
            assert len(df) == 10
            assert pd.api.types.is_numeric_dtype(df["TotalCharges"])

    def test_to_canonical_mapping(self) -> None:
        adapter = IBMTelcoAdapter()
        df = make_telco_df()
        canonical = adapter.to_canonical(df)

        assert "customer" in canonical
        assert "subscription" in canonical
        assert "service" in canonical
        assert "billing" in canonical
        assert "churn" in canonical
        assert len(canonical["customer"]) == 10
        assert "source_customer_id" in canonical["customer"].columns
        # churn label mapped to 0/1
        assert set(canonical["churn"]["is_churn"]) == {0, 1}

    def test_service_columns_normalized_to_snake_case(self) -> None:
        """Service columns must be canonical snake_case, not source CamelCase.

        Regression for the E1 bug: adapter output used PhoneService etc. while
        the loader expects phone_service — every service column landed NULL.
        """
        from app.warehouse.adapters import SERVICE_MAPPING

        adapter = IBMTelcoAdapter()
        df = make_telco_df()
        canonical = adapter.to_canonical(df)

        svc = canonical["service"]
        expected = ["source_customer_id"] + list(SERVICE_MAPPING.values())
        assert list(svc.columns) == expected
        # Values are preserved (not NULL) after rename
        assert svc["phone_service"].notna().all()
        assert svc["tech_support"].notna().all()
        assert svc["internet_service"].notna().all()

    def test_registry_entry(self) -> None:
        adapter = IBMTelcoAdapter()
        entry = adapter.registry_entry
        assert entry.dataset_id == "IBM_TELCO_V1"
        assert entry.source == "kaggle"
        assert "kaggle.com" in entry.source_url

    def test_quality_rules_complete(self) -> None:
        adapter = IBMTelcoAdapter()
        rules = adapter.quality_column_rules()
        assert any(r.column == "customerID" and r.rule == "required" for r in rules)
        assert any(r.column == "Churn" and r.rule == "enum" for r in rules)
        assert adapter.unique_keys() == ["customerID"]
