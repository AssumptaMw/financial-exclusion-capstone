import numpy as np
import pandas as pd
import pytest
from scipy.sparse import issparse
from sklearn.preprocessing import OneHotEncoder

from src.data.feature_engineering import (
    MODELING_COLUMNS,
    PREDICTOR_COLUMNS,
    TARGET_COLUMN,
    build_modeling_dataset,
)
from src.data.preprocessing import (
    CATEGORICAL_FEATURES,
    _coerce_numeric,
    build_preprocessor,
    split_modeling_data,
)


def make_modeling_data(row_count=40):
    labels = ["formal only"] * 36 + ["informal only"] * 2 + ["excluded"] * 2
    adult_data = {
        "A18": [18 + index % 60 for index in range(row_count)],
        "Sex": ["Female" if index % 2 else "Male" for index in range(row_count)],
        "A20": ["95" if index == 0 else "Secondary completed " for index in range(row_count)],
        "county": ["Nairobi City" if index % 2 else "Meru" for index in range(row_count)],
        "A08": ["Urban" if index % 2 else "Rural" for index in range(row_count)],
        "B3A__2": [index % 2 for index in range(row_count)],
        "B3A__4": [(index + 1) % 2 for index in range(row_count)],
        "B3Ii": ["1000" if index % 3 else "#NULL!" for index in range(row_count)],
        "ID_card": ["Has ID" if index % 2 else "No ID" for index in range(row_count)],
        "S1": ["Own phone" if index % 2 else "#NULL!" for index in range(row_count)],
        "S2__1": ["0" if index % 2 else "1" for index in range(row_count)],
        "S3": ["Daily" if index % 2 else "Never" for index in range(row_count)],
        "S4": ["#NULL!" if index % 2 else "At home" for index in range(row_count)],
        "A24i": ["No difficulty"] * row_count,
        "A24ii": ["No difficulty"] * row_count,
        "A24iii": ["No difficulty"] * row_count,
        "A24iv": ["No difficulty"] * row_count,
        "A24v": ["No difficulty"] * row_count,
        "A24vi": ["No difficulty"] * row_count,
        "Overall_Access_fnl": labels[:row_count],
        "Access_fnl": ["Excluded"] * row_count,
        "indWeight": [1.0] * row_count,
        "A07": list(range(row_count)),
    }
    return build_modeling_dataset(pd.DataFrame(adult_data))


def test_preprocessor_imputes_education_95_without_modifying_input():
    modeling_data = make_modeling_data()
    X_train = modeling_data.loc[:29, PREDICTOR_COLUMNS]
    preprocessor = build_preprocessor()

    transformed = preprocessor.fit_transform(X_train)
    transformed_values = transformed.data if issparse(transformed) else transformed

    assert np.isfinite(transformed_values).all()
    categorical = preprocessor.named_steps["preprocessor"].named_transformers_[
        "categorical"
    ]
    encoder = categorical.named_steps["onehot"]
    assert isinstance(encoder, OneHotEncoder)
    county_position = CATEGORICAL_FEATURES.index("county")
    a20_position = CATEGORICAL_FEATURES.index("A20")
    s1_position = CATEGORICAL_FEATURES.index("S1")
    assert "#NULL!" in encoder.categories_[s1_position]
    assert "95" not in encoder.categories_[a20_position]
    assert X_train.loc[0, "A20"] == "95"
    assert categorical.named_steps["imputer"].statistics_[a20_position] == (
        "Secondary completed "
    )
    assert set(encoder.categories_[county_position]) == {"Meru", "Nairobi City"}


def test_income_numeric_conversion_handles_errors_and_field_specific_special_codes():
    raw = pd.DataFrame(
        {"A18": [18, 30, 45, 50, 60], "B3Ii": ["1000", "#NULL!", "98", "99", "250.5"]}
    )

    converted = _coerce_numeric(raw)

    assert converted["B3Ii"].iloc[[0, 4]].tolist() == [1000.0, 250.5]
    assert converted["B3Ii"].iloc[1:4].isna().all()
    assert raw["B3Ii"].tolist() == ["1000", "#NULL!", "98", "99", "250.5"]


def test_income_imputer_fits_training_median_only():
    data = make_modeling_data()
    X_train = data.iloc[:30].loc[:, PREDICTOR_COLUMNS].copy()
    X_test = data.iloc[30:31].loc[:, PREDICTOR_COLUMNS].copy()
    X_train.loc[:, "B3Ii"] = ["100" if i % 2 else "300" for i in range(len(X_train))]
    X_train.iloc[0, X_train.columns.get_loc("B3Ii")] = "#NULL!"
    X_test.loc[:, "B3Ii"] = "900000"
    preprocessor = build_preprocessor()

    preprocessor.fit(X_train)
    preprocessor.transform(X_test)
    imputer = preprocessor.named_steps["preprocessor"].named_transformers_[
        "numeric"
    ].named_steps["imputer"]

    assert imputer.statistics_[1] == 100
    assert X_train.iloc[0]["B3Ii"] == "#NULL!"


def test_unseen_categories_are_ignored_and_not_learned_from_holdout():
    modeling_data = make_modeling_data()
    X_train = modeling_data.iloc[:30].loc[:, PREDICTOR_COLUMNS].copy()
    X_test = modeling_data.iloc[30:31].loc[:, PREDICTOR_COLUMNS].copy()
    X_test.loc[:, "county"] = "Holdout-only County"
    X_test.loc[:, "A20"] = "Holdout-only education"
    preprocessor = build_preprocessor()

    train_transformed = preprocessor.fit_transform(X_train)
    test_transformed = preprocessor.transform(X_test)
    categorical = preprocessor.named_steps["preprocessor"].named_transformers_[
        "categorical"
    ]
    encoder = categorical.named_steps["onehot"]
    categories = [category for values in encoder.categories_ for category in values]

    assert test_transformed.shape[1] == train_transformed.shape[1]
    assert "Holdout-only County" not in categories
    assert "Holdout-only education" not in categories


def test_split_is_reproducible_stratified_and_excludes_metadata_from_features():
    modeling_data = make_modeling_data()

    first = split_modeling_data(modeling_data, test_size=0.25, random_state=17)
    second = split_modeling_data(modeling_data, test_size=0.25, random_state=17)
    X_train, X_test, y_train, y_test = first
    X_train_again, X_test_again, y_train_again, y_test_again = second

    pd.testing.assert_frame_equal(X_train, X_train_again)
    pd.testing.assert_frame_equal(X_test, X_test_again)
    pd.testing.assert_series_equal(y_train, y_train_again)
    pd.testing.assert_series_equal(y_test, y_test_again)
    assert tuple(X_train.columns) == PREDICTOR_COLUMNS
    assert tuple(X_test.columns) == PREDICTOR_COLUMNS
    assert TARGET_COLUMN not in X_train
    assert "indWeight" not in X_train and "A07" not in X_train
    assert "S2__1" not in X_train and "S4" not in X_train
    assert set(y_train.unique()) == {0, 1}
    assert set(y_test.unique()) == {0, 1}
    assert len(X_test) == 10
    assert len(modeling_data.columns) == len(MODELING_COLUMNS)


@pytest.mark.parametrize("column", ["S2__1", "S4"])
def test_preprocessor_rejects_excluded_review_fields(column):
    X = make_modeling_data().loc[:, PREDICTOR_COLUMNS].copy()
    X[column] = "1"
    with pytest.raises(ValueError, match=f"unexpected=.*{column}"):
        build_preprocessor().fit(X)
