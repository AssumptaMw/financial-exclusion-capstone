import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC

from src.data.feature_engineering import PREDICTOR_COLUMNS
from src.data.preprocessing import build_model_pipeline, build_preprocessor
from src.models import train
from src.models.estimators import BalancedXGBClassifier
from src.models.evaluate import evaluate_model


def sample_predictors(size=60):
    data = {
        column: [f"{column}-{index % 2}" for index in range(size)]
        for column in PREDICTOR_COLUMNS
    }
    data["A18"] = [20 + index % 40 for index in range(size)]
    data["B3Ii"] = ["#NULL!" if index % 7 == 0 else str(1000 + index * 10) for index in range(size)]
    data["B3A__2"] = [index % 2 for index in range(size)]
    data["B3A__4"] = [(index + 1) % 2 for index in range(size)]
    return pd.DataFrame(data, columns=PREDICTOR_COLUMNS)


class RecordingPreprocessor(BaseEstimator, TransformerMixin):
    fitted_indices = []

    def fit(self, X, y=None):
        self.fitted_indices.append(set(X.index))
        self.delegate_ = build_preprocessor().fit(X, y)
        return self

    def transform(self, X):
        return self.delegate_.transform(X)


def test_cross_validation_fits_preprocessing_within_folds_and_refits_on_training(monkeypatch):
    X = sample_predictors()
    y = pd.Series([int(index % 5 == 0) for index in range(len(X))])
    RecordingPreprocessor.fitted_indices = []
    monkeypatch.setattr(
        train, "build_model_pipeline",
        lambda estimator: Pipeline([("preprocessing", RecordingPreprocessor()), ("estimator", estimator)]),
    )

    selected, model, scores = train.train_candidates(
        X, y, cv_splits=2, forest_trees=3, boosting_rounds=3
    )

    fits = RecordingPreprocessor.fitted_indices
    assert len(fits) == 9
    assert all(len(indices) == 30 and indices < set(X.index) for indices in fits[:8])
    assert fits[-1] == set(X.index)
    assert set(scores) == {"logistic_regression", "random_forest", "xgboost", "svm"}
    assert selected in scores
    assert all(len(result["f1"]["folds"]) == 2 for result in scores.values())
    assert selected == max(scores, key=lambda name: (scores[name]["f1"]["mean"], scores[name]["recall"]["mean"]))


def test_serialized_model_predicts_unseen_categories_and_rejects_leakage(tmp_path):
    X = sample_predictors()
    y = pd.Series([int(index % 5 == 0) for index in range(len(X))])
    selected, model, _ = train.train_candidates(
        X.iloc[:50], y.iloc[:50], cv_splits=2, forest_trees=3, boosting_rounds=3
    )
    holdout = X.iloc[50:].copy()
    holdout.loc[:, "county"] = "Holdout-only county"
    path = tmp_path / "pipeline.joblib"
    joblib.dump(model, path)
    loaded = joblib.load(path)

    assert selected in ("logistic_regression", "random_forest", "xgboost", "svm")
    np.testing.assert_array_equal(model.predict(holdout), loaded.predict(holdout))
    if hasattr(model, "predict_proba"):
        np.testing.assert_allclose(model.predict_proba(holdout), loaded.predict_proba(holdout))
    else:
        np.testing.assert_allclose(model.decision_function(holdout), loaded.decision_function(holdout))
    categories = loaded.named_steps["preprocessing"].named_steps["preprocessor"].named_transformers_["categorical"].named_steps["onehot"].categories_
    assert "Holdout-only county" not in set().union(*(set(values) for values in categories))
    with pytest.raises(ValueError, match="unexpected"):
        loaded.predict(holdout.assign(Overall_Access_fnl="excluded"))


class KnownPredictions:
    classes_ = np.array([0, 1])

    def predict(self, X):
        return np.array([0, 1, 0, 1])

    def predict_proba(self, X):
        probabilities = np.array([0.1, 0.6, 0.4, 0.9])
        return np.column_stack((1 - probabilities, probabilities))


def test_evaluation_metrics_and_figures(tmp_path):
    y = pd.Series([0, 0, 1, 1])
    metrics = evaluate_model(KnownPredictions(), pd.DataFrame({"x": range(4)}), y, tmp_path)

    assert metrics["confusion_matrix"] == [[1, 1], [1, 1]]
    assert metrics["accuracy"] == metrics["precision"] == metrics["recall"] == metrics["f1"] == 0.5
    assert metrics["roc_auc"] == 0.75
    assert metrics["pr_auc_average_precision"] == pytest.approx(5 / 6)
    assert metrics["classification_report"]["excluded"]["support"] == 2
    assert {path.name for path in tmp_path.glob("*.png")} == {
        "model_confusion_matrix.png", "model_roc.png", "model_precision_recall.png"
    }
    with pytest.raises(ValueError, match="both non-null binary classes"):
        evaluate_model(KnownPredictions(), pd.DataFrame({"x": [1]}), pd.Series([1]), tmp_path)


def test_training_rejects_unapproved_predictors():
    X = sample_predictors()
    y = pd.Series([index % 2 for index in range(len(X))])
    with pytest.raises(ValueError, match="approved feature list"):
        train.train_candidates(X.assign(S4="unexpected"), y, cv_splits=2, forest_trees=3)


def test_model_selection_prioritizes_f1_over_recall(monkeypatch):
    X = sample_predictors()
    y = pd.Series([index % 2 for index in range(len(X))])

    def fake_cross_validate(pipeline, *args, **kwargs):
        baseline = pipeline.named_steps["estimator"].__class__.__name__ == "LogisticRegression"
        scores = {f"test_{metric}": np.array([0.5, 0.5]) for metric in train.SCORING}
        scores["test_f1"] = np.array([0.7, 0.7] if baseline else [0.6, 0.6])
        scores["test_recall"] = np.array([0.4, 0.4] if baseline else [0.9, 0.9])
        return scores

    monkeypatch.setattr(train, "cross_validate", fake_cross_validate)
    selected, _, _ = train.train_candidates(X, y, cv_splits=2, forest_trees=3)

    assert selected == "logistic_regression"


def test_xgboost_computes_weight_from_each_fit():
    estimator = BalancedXGBClassifier(n_estimators=2, n_jobs=1, random_state=42)
    X = np.arange(12).reshape(6, 2)

    estimator.fit(X, np.array([0, 0, 0, 0, 1, 1]))
    assert estimator.get_params()["scale_pos_weight"] == 2
    estimator.fit(X, np.array([0, 0, 0, 1, 1, 1]))
    assert estimator.get_params()["scale_pos_weight"] == 1
    with pytest.raises(ValueError, match="both non-null binary"):
        estimator.fit(X, np.zeros(6))


@pytest.mark.parametrize(
    "estimator",
    [BalancedXGBClassifier(n_estimators=2, n_jobs=1, random_state=42),
     SVC(class_weight="balanced", probability=False)],
)
def test_added_models_serialize_as_complete_pipelines(estimator, tmp_path):
    X = sample_predictors()
    y = pd.Series([int(index % 5 == 0) for index in range(len(X))])
    model = build_model_pipeline(estimator).fit(X, y)
    path = tmp_path / "pipeline.joblib"
    joblib.dump(model, path)

    reloaded = joblib.load(path)

    np.testing.assert_array_equal(model.predict(X.iloc[:5]), reloaded.predict(X.iloc[:5]))
    if hasattr(model, "predict_proba"):
        np.testing.assert_allclose(model.predict_proba(X.iloc[:5]), reloaded.predict_proba(X.iloc[:5]))
    else:
        np.testing.assert_allclose(model.decision_function(X.iloc[:5]), reloaded.decision_function(X.iloc[:5]))


class KnownDecisionScores:
    classes_ = np.array([0, 1])

    def predict(self, X):
        return np.array([0, 1, 0, 1])

    def decision_function(self, X):
        return np.array([-0.8, 0.2, -0.2, 0.8])


def test_evaluate_svm_style_decision_scores(tmp_path):
    y = pd.Series([0, 0, 1, 1])
    metrics = evaluate_model(KnownDecisionScores(), pd.DataFrame({"x": range(4)}), y, tmp_path)

    assert metrics["score_type"] == "decision_function"
    assert metrics["threshold"] == 0
    assert metrics["roc_auc"] == 0.75
    assert metrics["pr_auc_average_precision"] == pytest.approx(5 / 6)
