"""Unit tests for ETL data validation (04_DATASET_SPEC.md §11)."""

import pandas as pd

from app.warehouse.validator import (
    ValidationResult,
    validate_rows,
    validate_schema,
)


class TestValidateSchema:
    def test_missing_column_rejected(self) -> None:
        """Missing required column must be reported."""
        df = pd.DataFrame({"customer_id": ["CUST-1"], "gender": ["Male"]})
        ok, errors = validate_schema(df, "customer")
        assert ok is False
        assert any("join_date" in e for e in errors)

    def test_valid_schema_passes(self) -> None:
        """Complete customer schema passes."""
        df = pd.DataFrame(
            {
                "customer_id": ["CUST-1"],
                "gender": ["Male"],
                "age": [30],
                "city": ["Shanghai"],
                "province": ["Shanghai"],
                "join_date": ["2024-04-10"],
                "contract_type": ["postpaid"],
                "package_id": ["PKG-1"],
                "package_name": ["Basic"],
                "status": ["active"],
            }
        )
        ok, errors = validate_schema(df, "customer")
        assert ok is True
        assert errors == []


class TestValidateRows:
    def test_valid_row_accepted(self) -> None:
        df = pd.DataFrame(
            {
                "customer_id": ["CUST-1"],
                "join_date": ["2024-04-10"],
                "contract_type": ["postpaid"],
                "package_id": ["PKG-1"],
                "status": ["active"],
            }
        )
        result = validate_rows(df, "customer")
        assert result.rows_accepted == 1
        assert result.rows_quarantined == 0

    def test_invalid_enum_rejected(self) -> None:
        """Unknown status value must be quarantined."""
        df = pd.DataFrame(
            {
                "customer_id": ["CUST-1"],
                "join_date": ["2024-04-10"],
                "contract_type": ["postpaid"],
                "package_id": ["PKG-1"],
                "status": ["inactive_custom"],  # not in {active, suspended, churned}
            }
        )
        result = validate_rows(df, "customer")
        assert result.rows_accepted == 0
        assert result.rows_quarantined == 1
        assert "invalid_enum:status" in result.quarantine_reasons

    def test_missing_required_column_rejected(self) -> None:
        df = pd.DataFrame(
            {
                "customer_id": ["CUST-1"],
                "join_date": [""],  # required but empty
                "contract_type": ["postpaid"],
                "package_id": ["PKG-1"],
                "status": ["active"],
            }
        )
        result = validate_rows(df, "customer")
        assert result.rows_accepted == 0
        assert result.rows_quarantined == 1

    def test_age_out_of_range_rejected(self) -> None:
        df = pd.DataFrame(
            {
                "customer_id": ["CUST-1"],
                "age": ["-5"],  # negative age
                "join_date": ["2024-04-10"],
                "contract_type": ["postpaid"],
                "package_id": ["PKG-1"],
                "status": ["active"],
            }
        )
        result = validate_rows(df, "customer")
        assert result.rows_quarantined == 1
        assert "out_of_range:age" in result.quarantine_reasons

    def test_discount_exceeding_fee_rejected(self) -> None:
        """Billing business rule: discount_amount must not exceed monthly_fee."""
        df = pd.DataFrame(
            {
                "customer_id": ["CUST-1"],
                "billing_month": ["2026-08-01"],
                "monthly_fee": ["50"],
                "discount_amount": ["80"],  # exceeds fee
                "payment_status": ["paid"],
                "package_price": ["50"],
            }
        )
        result = validate_rows(df, "billing")
        assert result.rows_quarantined == 1
        assert "business_rule:discount_exceeds_fee" in result.quarantine_reasons

    def test_csat_out_of_range_rejected(self) -> None:
        df = pd.DataFrame(
            {
                "customer_id": ["CUST-1"],
                "ticket_date": ["2026-08-01"],
                "ticket_count": ["1"],
                "csat_score": ["7"],  # out of 1-5
            }
        )
        result = validate_rows(df, "service")
        assert result.rows_quarantined == 1
        assert "out_of_range:csat_score" in result.quarantine_reasons

    def test_csat_empty_accepted(self) -> None:
        """Empty CSAT (no survey) is valid, not quarantined."""
        df = pd.DataFrame(
            {
                "customer_id": ["CUST-1"],
                "ticket_date": ["2026-08-01"],
                "ticket_count": ["1"],
                "csat_score": [""],
            }
        )
        result = validate_rows(df, "service")
        assert result.rows_accepted == 1

    def test_mixed_valid_invalid_split(self) -> None:
        df = pd.DataFrame(
            {
                "customer_id": ["CUST-1", "CUST-2", "CUST-3"],
                "join_date": ["2024-01-01", "2024-01-02", "2024-01-03"],
                "contract_type": ["postpaid", "prepaid", "unknown_type"],
                "package_id": ["PKG-1", "PKG-2", "PKG-3"],
                "status": ["active", "active", "active"],
            }
        )
        result = validate_rows(df, "customer")
        assert result.rows_accepted == 2
        assert result.rows_quarantined == 1


class TestValidationResult:
    def test_defaults(self) -> None:
        result = ValidationResult(dataset="customer")
        assert result.rows_total == 0
        assert result.rows_accepted == 0
        assert result.rows_quarantined == 0
        assert result.quarantine_reasons == {}
