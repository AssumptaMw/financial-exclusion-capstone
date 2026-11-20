import json

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.data.eda import grouped_exclusion, quality_summary, run_eda
from src.data.feature_engineering import (
    MODEL_METADATA_KEY,
    MODELING_COLUMNS,
    PREDICTOR_COLUMNS,
    TARGET_COLUMN,
)


def test_grouped_exclusion_uses_group_denominators_and_preserves_nulls():
    groups = pd.Series(["a", "a", "b", None], index=[1, 2, 3, 4])
    target = pd.Series([1, 0, 1, 0], index=groups.index)

    summary = grouped_exclusion(groups, target)

    assert summary.loc["a", "respondents"] == 2
    assert summary.loc["a", "excluded"] == 1
    assert summary.loc["a", "excluded_pct"] == 50
    assert summary.loc["b", "excluded_pct"] == 100
    assert summary.loc["<null>", "respondents"] == 1
    with pytest.raises(ValueError, match="indices must match"):
        grouped_exclusion(groups, target.reset_index(drop=True))


def test_grouped_exclusion_does_not_overflow_int8_target():
    groups = pd.Series(["county"] * 438)
    target = pd.Series([1] * 42 + [0] * 396, dtype="int8")

    summary = grouped_exclusion(groups, target)

    assert summary.loc["county", "excluded"] == 42
    assert summary.loc["county", "excluded_pct"] == pytest.approx(100 * 42 / 438)


def test_quality_summary_distinguishes_null_blank_error_and_field_specific_codes():
    X = pd.DataFrame({column: ["a", "b", "c"] for column in PREDICTOR_COLUMNS})
    X["A20"] = ["95", None, ""]
    X["B3Ii"] = ["#NULL!", "98", "100"]
    X["A24i"] = ["#NULL!", "99", "No"]

    quality = quality_summary(X)

    assert quality.loc["A20", ["null", "blank", "excel_error", "special_or_unresolved"]].tolist() == [1, 1, 0, 1]
    assert quality.loc["B3Ii", ["null", "blank", "excel_error", "special_or_unresolved"]].tolist() == [0, 0, 1, 1]
    assert quality.loc["A24i", "special_or_unresolved"] == 0
    with pytest.raises(ValueError, match="approved predictors"):
        quality_summary(X.assign(S4="not approved"))


def test_run_eda_uses_training_only_and_preserves_modeling_input(tmp_path):
    rows = 40
    data = {
        column: [f"{column}-{index % 2}" for index in range(rows)]
        for column in MODELING_COLUMNS
    }
    data["A18"] = [20 + index % 50 for index in range(rows)]
    data["B3Ii"] = ["1000" if index % 3 else "#NULL!" for index in range(rows)]
    data["B3A__2"] = [index % 2 for index in range(rows)]
    data["B3A__4"] = [(index + 1) % 2 for index in range(rows)]
    data[TARGET_COLUMN] = [0] * 30 + [1] * 10
    source = tmp_path / "modeling.parquet"
    table = pa.Table.from_pandas(pd.DataFrame(data), preserve_index=False)
    metadata = {MODEL_METADATA_KEY: json.dumps({"predictors": list(PREDICTOR_COLUMNS)}).encode()}
    pq.write_table(table.replace_schema_metadata(metadata), source)
    original = source.read_bytes()
    report = tmp_path / "results" / "eda_report.md"
    figures = tmp_path / "figures"

    results = run_eda(source, report, figures)

    assert results["training_rows"] == 32
    assert results["class_counts"] == {0: 24, 1: 8}
    assert source.read_bytes() == original
    assert report.is_file()
    text = report.read_text(encoding="utf-8")
    assert "only training rows are summarized" in text
    assert "unweighted" in text
    assert "## All categorical predictors versus the target" in text
    assert all(f"### `{column}`" in text for column in PREDICTOR_COLUMNS if column not in ("A18", "B3Ii"))
    assert len(results["figures"]) == 6
    assert all(path.is_file() and path.stat().st_size > 0 for path in results["figures"])


def test_run_eda_rejects_nonapproved_predictor_provenance(tmp_path):
    source = tmp_path / "modeling.parquet"
    table = pa.table({"value": [1]})
    pq.write_table(
        table.replace_schema_metadata({MODEL_METADATA_KEY: b'{"predictors": ["S4"]}'}),
        source,
    )

    with pytest.raises(ValueError, match="approved feature list"):
        run_eda(source, tmp_path / "report.md", tmp_path / "figures")
