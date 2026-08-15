"""Integration test: profile the real IBM Telco dataset."""

from pathlib import Path

import pytest

from app.warehouse.adapters import IBMTelcoAdapter
from app.warehouse.profiling import profile_dataframe

pytestmark = pytest.mark.integration


def _ibm_raw():
    raw = Path("data/raw/ibm_telco_v1")
    csvs = sorted(raw.glob("*.csv"))
    if not csvs:
        pytest.skip("IBM Telco raw CSV not downloaded")
    return IBMTelcoAdapter().load_raw(csvs[0])


class TestIBMProfiling:
    def test_ibm_profile_shape_and_missing(self) -> None:
        df = _ibm_raw()
        report = profile_dataframe(df, "IBM_TELCO_V1")
        assert report.rows == 7043
        assert report.columns == 21

        # TotalCharges has 11 known missing values in the IBM dataset
        tc = next(s for s in report.numeric if s.column == "TotalCharges")
        assert tc.missing == 11
        assert tc.missing_ratio == pytest.approx(11 / 7043, abs=0.001)

        # tenure is 0..72 months
        tenure = next(s for s in report.numeric if s.column == "tenure")
        assert tenure.min == 0.0
        assert tenure.max == 72.0

    def test_ibm_categorical_cardinality(self) -> None:
        df = _ibm_raw()
        report = profile_dataframe(df, "IBM_TELCO_V1")

        customer = next(s for s in report.categorical if s.column == "customerID")
        assert customer.unique == 7043  # all unique

        gender = next(s for s in report.categorical if s.column == "gender")
        assert gender.unique == 2
        assert gender.missing == 0

        churn = next(s for s in report.categorical if s.column == "Churn")
        assert churn.unique == 2
        assert churn.top_values[0]["value"] == "No"  # majority not churned
