"""Unit tests for the dataset profiling module."""

import pandas as pd
import pytest

from app.warehouse.profiling import (
    profile_dataframe,
)


def make_mixed_df() -> pd.DataFrame:
    """A DataFrame with numeric, categorical, and missing values."""
    return pd.DataFrame(
        {
            "age": [25, 30, 35, 40, None, 45],
            "tenure": [1, 2, 3, 4, 5, 6],
            "gender": ["Male", "Female", "Male", "Female", "Male", "Female"],
            "segment": ["A", "B", "A", "B", "A", None],
            "score": [10.5, 20.0, 15.5, None, 12.0, 18.0],
        }
    )


class TestProfileDataframe:
    def test_shape_and_split(self) -> None:
        report = profile_dataframe(make_mixed_df(), "TEST_V1")
        assert report.dataset_id == "TEST_V1"
        assert report.rows == 6
        assert report.columns == 5
        # numeric: age, tenure, score; categorical: gender, segment
        assert len(report.numeric) == 3
        assert len(report.categorical) == 2

    def test_numeric_stats_values(self) -> None:
        report = profile_dataframe(make_mixed_df(), "TEST_V1")
        tenure = next(s for s in report.numeric if s.column == "tenure")
        assert tenure.min == 1.0
        assert tenure.max == 6.0
        assert tenure.mean == 3.5
        assert tenure.missing == 0
        assert tenure.unique == 6
        assert len(tenure.histogram) > 0

    def test_numeric_missing_counted(self) -> None:
        report = profile_dataframe(make_mixed_df(), "TEST_V1")
        age = next(s for s in report.numeric if s.column == "age")
        score = next(s for s in report.numeric if s.column == "score")
        assert age.missing == 1
        assert age.missing_ratio == pytest.approx(1 / 6, abs=0.01)
        assert score.missing == 1

    def test_categorical_top_values(self) -> None:
        report = profile_dataframe(make_mixed_df(), "TEST_V1")
        gender = next(s for s in report.categorical if s.column == "gender")
        assert gender.unique == 2
        assert gender.missing == 0
        # top values sorted by frequency desc
        assert gender.top_values[0]["value"] == "Male"
        assert gender.top_values[0]["count"] == 3

    def test_categorical_missing(self) -> None:
        report = profile_dataframe(make_mixed_df(), "TEST_V1")
        segment = next(s for s in report.categorical if s.column == "segment")
        assert segment.missing == 1
        assert segment.unique == 2

    def test_to_dict_json_serializable(self) -> None:
        """Report serializes to plain dict (JSON-safe)."""
        import json

        report = profile_dataframe(make_mixed_df(), "TEST_V1")
        d = report.to_dict()
        json.dumps(d)  # must not raise

    def test_empty_df(self) -> None:
        report = profile_dataframe(pd.DataFrame({"a": []}), "EMPTY")
        assert report.rows == 0
        assert len(report.numeric) == 1
        assert report.numeric[0].mean is None

    def test_constant_column_histogram(self) -> None:
        """A constant column yields a single-bucket histogram, not zero."""
        df = pd.DataFrame({"const": [5, 5, 5, 5]})
        report = profile_dataframe(df, "CONST")
        assert report.numeric[0].min == 5.0
        assert report.numeric[0].max == 5.0
        assert len(report.numeric[0].histogram) == 1


class TestNumericStats:
    def test_histogram_buckets_sum_to_count(self) -> None:
        df = pd.DataFrame({"x": list(range(100))})
        report = profile_dataframe(df, "HIST")
        hist = report.numeric[0].histogram
        assert len(hist) == 10
        assert sum(b["count"] for b in hist) == 100
