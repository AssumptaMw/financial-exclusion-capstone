import hashlib
import json

import joblib
import pandas as pd
import pyarrow.parquet as pq
import pytest
from sklearn.base import clone
from sklearn.svm import SVC

from src import pipeline
from src.data.feature_engineering import create_modeling_dataset
from src.data.prepare_data import prepare_data
from src.data.preprocessing import build_model_pipeline, split_modeling_data
from src.models.train import SCORING, load_modeling_data
from test_prepare_data import write_interim


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def configured_pipeline(tmp_path, monkeypatch):
    interim = tmp_path / "source.parquet"
    write_interim(interim, ages=tuple(20 + i % 60 for i in range(80)))
    table = pq.read_table(interim)
    frame = table.to_pandas()
    frame["Overall_Access_fnl"] = ["excluded" if i % 4 == 0 else "formal only" for i in range(len(frame))]
    pq.write_table(table.from_pandas(frame, schema=table.schema, preserve_index=False), interim)
    adult = tmp_path / "reference_adults.parquet"
    reference = tmp_path / "reference_modeling.parquet"
    cleaning = tmp_path / "reference_cleaning.md"
    prepare_data(interim, adult, cleaning)
    with cleaning.open("a", encoding="utf-8") as file:
        file.write("\n## Manual investigation\nPreserve these findings.\n")
    create_modeling_dataset(adult, reference)
    X_train, X_test, y_train, _ = split_modeling_data(load_modeling_data(reference))
    model = build_model_pipeline(SVC(kernel="rbf", class_weight="balanced", random_state=42))
    model.fit(X_train, y_train)
    model_path = tmp_path / "saved_svm.joblib"
    joblib.dump(model, model_path)
    experiment = tmp_path / "experiment.json"
    experiment.write_text(json.dumps({"selected_model": "svm", "dataset_sha256": digest(reference)}))
    shap_provenance = tmp_path / "shap.json"
    shap_provenance.write_text(json.dumps({"model_sha256": digest(model_path), "dataset_sha256": digest(reference)}))

    for name, value in {
        "PARQUET_PATH": interim, "MODELING_DATASET_PATH": reference, "MODEL_PATH": model_path,
        "EXPERIMENT_CONFIG_PATH": experiment, "SHAP_PROVENANCE_PATH": shap_provenance,
        "CLEANING_REPORT_PATH": cleaning,
        "DATA_RUNS": tmp_path / "data_runs", "RESULT_RUNS": tmp_path / "results_runs",
        "FIGURE_RUNS": tmp_path / "figures_runs",
    }.items():
        monkeypatch.setattr(pipeline, name, value)
    return {"interim": interim, "reference": reference, "model": model_path, "cleaning": cleaning,
            "X_train": X_train, "X_test": X_test, "y_train": y_train}


def stub_comparison(monkeypatch, fixture, *, selected="svm", change_model=False):
    saved = joblib.load(fixture["model"])
    calls = []

    def compare(X, y):
        calls.append("comparison")
        pd.testing.assert_frame_equal(X, fixture["X_train"])
        pd.testing.assert_series_equal(y, fixture["y_train"])
        assert set(X.index).isdisjoint(fixture["X_test"].index)
        candidate = clone(saved).fit(X, y)
        if change_model:
            candidate.named_steps["estimator"].intercept_ += 1
        scores = {
            name: {metric: {"folds": [0.5] * 5, "mean": 0.5, "std": 0.0} for metric in SCORING}
            for name in ("logistic_regression", "random_forest", "xgboost", "svm")
        }
        return selected, candidate, scores

    def explain(model_path, dataset_path, results_dir, figures_dir):
        calls.append("explanation")
        assert model_path == fixture["model"]
        assert dataset_path.is_file()
        (results_dir / "shap_report.md").write_text("fixture explanation", encoding="utf-8")
        (figures_dir / "shap_summary.png").write_bytes(b"fixture")

    monkeypatch.setattr(pipeline, "train_candidates", compare)
    monkeypatch.setattr(pipeline, "run_explanations", explain)
    return calls


def test_pipeline_connects_stages_without_overwriting_sources(configured_pipeline, monkeypatch):
    fixture = configured_pipeline
    before = {name: digest(fixture[name]) for name in ("interim", "reference", "model", "cleaning")}
    calls = stub_comparison(monkeypatch, fixture)

    manifest = pipeline.run_pipeline("test-run")

    assert calls == ["comparison", "explanation"]
    assert manifest["adult_rows"] == 80
    assert manifest["training_rows"] == 64 and manifest["test_rows"] == 16
    assert manifest["refitted_svm_and_training_preprocessing_match"]
    assert not manifest["model_artifact_rewritten"]
    assert before == {name: digest(fixture[name]) for name in before}
    results = pipeline.RESULT_RUNS / "test-run"
    figures = pipeline.FIGURE_RUNS / "test-run"
    assert "Preserve these findings." in (results / "data_cleaning_report.md").read_text(encoding="utf-8")
    assert (results / "model_comparison.json").is_file()
    assert (results / "model_evaluation.json").is_file()
    assert (results / "pipeline_manifest.json").is_file()
    assert (results / "shap_report.md").is_file()
    assert (figures / "model_roc.png").is_file()
    report = (results / "model_evaluation_report.md").read_text(encoding="utf-8")
    assert (results / report.split("![ROC curve](", 1)[1].split(")", 1)[0]).is_file()
    with pytest.raises(FileExistsError, match="new run ID"):
        pipeline.run_pipeline("test-run")
    assert before == {name: digest(fixture[name]) for name in before}


@pytest.mark.parametrize("selected,changed", [("random_forest", False), ("svm", True)])
def test_pipeline_stops_before_test_evaluation_if_model_does_not_match(
    configured_pipeline, monkeypatch, selected, changed
):
    calls = stub_comparison(monkeypatch, configured_pipeline, selected=selected, change_model=changed)
    with pytest.raises(ValueError, match="evaluation stopped"):
        pipeline.run_pipeline("mismatch")
    assert calls == ["comparison"]
    assert not (pipeline.RESULT_RUNS / "mismatch" / "model_evaluation.json").exists()
    assert not (pipeline.RESULT_RUNS / "mismatch" / "pipeline_manifest.json").exists()


def test_pipeline_rejects_bad_run_id_and_changed_model(configured_pipeline):
    with pytest.raises(ValueError, match="Run ID"):
        pipeline.run_pipeline("../outside")
    configured_pipeline["model"].write_bytes(b"different model")
    with pytest.raises(ValueError, match="does not match"):
        pipeline.run_pipeline("changed")
    assert not pipeline.DATA_RUNS.exists()
