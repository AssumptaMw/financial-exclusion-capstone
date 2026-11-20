import json

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.data.feature_engineering import (
    DESIGN_COLUMNS,
    MODELING_COLUMNS,
    MODEL_METADATA_KEY,
    PREDICTOR_COLUMNS,
    REVIEW_COLUMNS,
    TARGET_COLUMN,
    TRACEABILITY_COLUMNS,
    build_modeling_dataset,
    create_modeling_dataset,
)
from src.data.prepare_data import PREPARATION_METADATA_KEY


def make_adult_data(labels=("formal only", "informal only", "excluded")):
    count = len(labels)
    values = {
        "A18": [18 + index for index in range(count)],
        "Sex": ["Female"] * count,
        "A20": [
            "95" if index == 0 else "Secondary completed "
            for index in range(count)
        ],
        "county": ["Nairobi City"] * count,
        "A08": ["Urban"] * count,
        "B3A__2": [1] * count,
        "B3A__4": [0] * count,
        "B3Ii": ["1000", "#NULL!", "3000"][:count],
        "ID_card": ["Has ID"] * count,
        "S1": ["I own a mobile"] * count,
        "S2__1": ["0", "1", "#NULL!"][:count],
        "S3": ["Daily"] * count,
        "S4": ["#NULL!", "At home", "At work"][:count],
        "A24i": ["No difficulty"] * count,
        "A24ii": ["No difficulty"] * count,
        "A24iii": ["No difficulty"] * count,
        "A24iv": ["No difficulty"] * count,
        "A24v": ["No difficulty"] * count,
        "A24vi": ["No difficulty"] * count,
        "Overall_Access_fnl": list(labels),
        "Access_fnl": ["Formal Prudential"] * count,
        "indWeight": [1.0] * count,
        "A07": list(range(count)),
    }
    if count > 3:
        values["B3Ii"] = ["1000" if index % 2 == 0 else "#NULL!" for index in range(count)]
        values["S2__1"] = ["0" if index % 2 == 0 else "1" for index in range(count)]
        values["S4"] = ["#NULL!" if index % 2 == 0 else "At home" for index in range(count)]
    return pd.DataFrame(values)


@pytest.mark.parametrize(
    ("label", "expected"),
    [("formal only", 0), ("informal only", 0), ("excluded", 1)],
)
def test_target_uses_exact_overall_access_labels(label, expected):
    source = make_adult_data((label,))

    result = build_modeling_dataset(source)

    assert result[TARGET_COLUMN].tolist() == [expected]
    assert result["Overall_Access_fnl"].tolist() == [label]
    assert result["Access_fnl"].tolist() == ["Formal Prudential"]
    assert source["Overall_Access_fnl"].tolist() == [label]


def test_unexpected_or_missing_target_categories_are_rejected():
    for label in ("Excluded", "excluded ", None):
        source = make_adult_data((label,))
        with pytest.raises(ValueError, match="Unrecognized or missing Overall_Access_fnl"):
            build_modeling_dataset(source)


def test_modeling_dataset_excludes_leakage_and_survey_fields_from_predictors():
    source = make_adult_data(("formal only", "excluded"))
    source["mobile_money_usage"] = [0, 1]
    source["formal_service_use"] = [1, 0]

    result = build_modeling_dataset(source)

    assert tuple(result.columns) == MODELING_COLUMNS
    assert len(PREDICTOR_COLUMNS) == 17
    assert set(TRACEABILITY_COLUMNS).issubset(result.columns)
    assert set(DESIGN_COLUMNS).issubset(result.columns)
    assert set(REVIEW_COLUMNS).issubset(result.columns)
    assert not (set(PREDICTOR_COLUMNS) & set(REVIEW_COLUMNS))
    assert result["S2__1"].tolist() == ["0", "1"]
    assert result["S4"].tolist() == ["#NULL!", "At home"]
    assert "mobile_money_usage" not in result.columns
    assert "formal_service_use" not in result.columns
    assert not (set(PREDICTOR_COLUMNS) & set(TRACEABILITY_COLUMNS + DESIGN_COLUMNS))
    assert result["financial_exclusion_status"].tolist() == [0, 1]


def test_modeling_dataset_writer_preserves_provenance_and_row_count(tmp_path):
    source = tmp_path / "adults.parquet"
    destination = tmp_path / "modeling.parquet"
    preparation = {"target_constructed": False, "retained_adults": 3}
    adult_data = make_adult_data()
    table = pa.Table.from_pandas(adult_data, preserve_index=False)
    pq.write_table(
        table.replace_schema_metadata(
            {PREPARATION_METADATA_KEY: json.dumps(preparation).encode()}
        ),
        source,
    )

    metadata = create_modeling_dataset(source, destination)
    result = pq.read_table(destination)

    assert result.num_rows == 3
    assert result.column_names == list(MODELING_COLUMNS)
    assert metadata["target_counts"] == {
        "0_financially_included": 2,
        "1_financially_excluded": 1,
    }
    assert metadata["provider_classification_method_independently_verified"] is False
    assert metadata["excluded_review_columns"] == ["S2__1", "S4"]
    assert MODEL_METADATA_KEY in (result.schema.metadata or {})
