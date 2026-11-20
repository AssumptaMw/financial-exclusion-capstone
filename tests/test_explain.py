import numpy as np
import pandas as pd
import pytest
from sklearn.svm import SVC

from src.data.feature_engineering import PREDICTOR_COLUMNS
from src.data.preprocessing import build_model_pipeline
from src.models.explain import (
    explain_samples,
    load_svm,
    select_training_samples,
    synthetic_excluded_profile,
    transformed_feature_mapping,
)
from test_models import sample_predictors


@pytest.fixture
def fitted_svm():
    X = sample_predictors()
    y = pd.Series([int(index % 5 == 0) for index in range(len(X))])
    return build_model_pipeline(SVC(kernel="rbf", class_weight="balanced")).fit(X, y)


def test_training_sample_selection_is_disjoint_and_reproducible():
    X = sample_predictors()
    background, sample = select_training_samples(X, 6, 8, 42)
    again_background, again_sample = select_training_samples(X, 6, 8, 42)

    pd.testing.assert_frame_equal(background, again_background)
    pd.testing.assert_frame_equal(sample, again_sample)
    assert set(background.index).isdisjoint(sample.index)
    assert set(background.index).union(sample.index).issubset(X.index)
    with pytest.raises(ValueError, match="approved predictors"):
        select_training_samples(X.assign(S4="not approved"), 6, 8, 42)
    with pytest.raises(ValueError, match="fit within training data"):
        select_training_samples(X, 40, 40, 42)


def test_feature_mapping_covers_fitted_outputs_without_losing_source(fitted_svm):
    mapping = transformed_feature_mapping(fitted_svm)
    transformer = fitted_svm.named_steps["preprocessing"].named_steps["preprocessor"]

    assert [item["transformed_feature"] for item in mapping] == list(transformer.get_feature_names_out())
    assert set(item["source_variable"] for item in mapping) == set(PREDICTOR_COLUMNS)
    assert any(item["transformed_feature"] == "numeric__missingindicator_B3Ii"
               and item["source_variable"] == "B3Ii" for item in mapping)
    assert all(item["source_variable"] == "B3A__2"
               for item in mapping if item["transformed_feature"].startswith("categorical__B3A__2_"))


def test_kernel_shap_explains_class_one_margin_and_is_reproducible(fitted_svm):
    X = sample_predictors()
    background, samples = select_training_samples(X, 4, 2, 42)

    baseline, values, margins = explain_samples(
        fitted_svm, background, samples, seed=7, coalition_samples=64
    )
    other_baseline, other_values, other_margins = explain_samples(
        fitted_svm, background, samples, seed=7, coalition_samples=64
    )

    assert values.shape == (2, 17)
    np.testing.assert_allclose(margins, fitted_svm.decision_function(samples))
    np.testing.assert_allclose(baseline + values.sum(axis=1), margins)
    assert baseline == other_baseline
    np.testing.assert_allclose(values, other_values)
    np.testing.assert_allclose(margins, other_margins)


def test_load_rejects_missing_pipeline(tmp_path):
    with pytest.raises(FileNotFoundError, match="Fitted SVM pipeline"):
        load_svm(tmp_path / "missing.joblib")


def test_synthetic_local_profile_does_not_match_a_training_record():
    class AlwaysExcluded:
        def predict(self, frame):
            return np.ones(len(frame), dtype=int)

    X = sample_predictors(3)
    X = pd.concat([X.iloc[[0]]] * 3, ignore_index=True)
    X["A18"] = [21, 20, 20]
    X["Sex"] = ["Female", "Male", "Female"]
    X["county"] = ["Meru", "Meru", "Nairobi"]
    profile = synthetic_excluded_profile(AlwaysExcluded(), X)
    assert not X.eq(profile.iloc[0]).all(axis=1).any()

    identical = pd.concat([X.iloc[[0]]] * 3, ignore_index=True)
    with pytest.raises(ValueError, match="matches a training record"):
        synthetic_excluded_profile(AlwaysExcluded(), identical)
