"""Leakage-safe preprocessing and stratified data splitting."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from src.data.feature_engineering import (
    MODELING_COLUMNS,
    PREDICTOR_COLUMNS,
    TARGET_COLUMN,
)
from src.financial_exclusion.config import RANDOM_SEED

NUMERIC_FEATURES = ("A18", "B3Ii")
CATEGORICAL_FEATURES = tuple(
    column for column in PREDICTOR_COLUMNS if column not in NUMERIC_FEATURES
)


def _validate_predictors(data: Any) -> pd.DataFrame:
    if not isinstance(data, pd.DataFrame):
        raise TypeError("Preprocessing input must be a pandas DataFrame.")
    missing = sorted(set(PREDICTOR_COLUMNS) - set(data.columns))
    unexpected = sorted(set(data.columns) - set(PREDICTOR_COLUMNS))
    if missing or unexpected:
        raise ValueError(
            f"Predictor columns do not match the approved schema; "
            f"missing={missing}, unexpected={unexpected}"
        )
    return data.loc[:, PREDICTOR_COLUMNS]


def _coerce_numeric(data: pd.DataFrame) -> pd.DataFrame:
    """Convert income amounts; preserve questionnaire special codes as missing."""
    numeric = data.apply(pd.to_numeric, errors="coerce")
    numeric["B3Ii"] = numeric["B3Ii"].mask(numeric["B3Ii"].isin([98, 99]))
    return numeric.replace([np.inf, -np.inf], np.nan)


def _prepare_categories(data: pd.DataFrame) -> pd.DataFrame:
    """Treat undocumented A20 code 95 as missing without altering source data."""
    result = data.copy()
    result["A20"] = result["A20"].mask(result["A20"].isin(["95", 95]), np.nan)
    return result


def build_preprocessor() -> Pipeline:
    """Return a transformer pipeline; callers fit it on training data only."""
    numeric_pipeline = Pipeline(
        steps=[
            (
                "to_numeric",
                FunctionTransformer(
                    _coerce_numeric,
                    validate=False,
                    feature_names_out="one-to-one",
                ),
            ),
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        steps=[
            (
                "prepare_categories",
                FunctionTransformer(
                    _prepare_categories,
                    validate=False,
                    feature_names_out="one-to-one",
                ),
            ),
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    transformer = ColumnTransformer(
        transformers=[
            ("numeric", numeric_pipeline, list(NUMERIC_FEATURES)),
            ("categorical", categorical_pipeline, list(CATEGORICAL_FEATURES)),
        ],
        remainder="drop",
    )
    return Pipeline(
        steps=[
            (
                "validate_predictors",
                FunctionTransformer(_validate_predictors, validate=False),
            ),
            ("preprocessor", transformer),
        ]
    )


def build_model_pipeline(estimator: Any) -> Pipeline:
    """Bind the preprocessing steps to an estimator for train-only fitting."""
    return Pipeline(
        steps=[
            ("preprocessing", build_preprocessor()),
            ("estimator", estimator),
        ]
    )


def split_modeling_data(
    modeling_data: pd.DataFrame,
    *,
    test_size: float = 0.2,
    random_state: int = RANDOM_SEED,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Split predictors and target reproducibly, preserving class proportions."""
    missing = sorted(set(MODELING_COLUMNS) - set(modeling_data.columns))
    if missing:
        raise ValueError(f"Modeling dataset is missing required columns: {missing}")
    y = modeling_data[TARGET_COLUMN]
    classes = y.value_counts(dropna=False)
    if y.isna().any() or not set(classes.index).issubset({0, 1}):
        raise ValueError("Target must contain only non-null binary values 0 and 1.")
    if len(classes) != 2 or int(classes.min()) < 2:
        raise ValueError("Stratified splitting requires at least two rows per class.")
    if not isinstance(test_size, (int, float)) or not 0 < test_size < 1:
        raise ValueError("test_size must be a fraction strictly between 0 and 1.")

    X = modeling_data.loc[:, PREDICTOR_COLUMNS]
    return train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
    )
