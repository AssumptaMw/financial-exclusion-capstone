"""Run the approved stages in isolated, non-overwriting directories."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import shutil
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from scipy import sparse

from src.data.feature_engineering import MODELING_DATASET_PATH, create_modeling_dataset
from src.data.load_data import PARQUET_PATH
from src.data.prepare_data import REPORT_PATH as CLEANING_REPORT_PATH, prepare_data
from src.data.preprocessing import split_modeling_data
from src.financial_exclusion.config import PROCESSED_DATA_DIR, RANDOM_SEED, REPORTS_DIR
from src.models.evaluate import evaluate_model
from src.models.explain import MODEL_PATH, load_svm, run_explanations
from src.models.train import load_modeling_data, train_candidates, write_experiment_results

LOGGER = logging.getLogger(__name__)
EXPERIMENT_CONFIG_PATH = REPORTS_DIR / "results" / "model_experiment_config.json"
SHAP_PROVENANCE_PATH = REPORTS_DIR / "results" / "shap_explanations.json"
DATA_RUNS = PROCESSED_DATA_DIR / "pipeline_runs"
RESULT_RUNS = REPORTS_DIR / "results" / "pipeline_runs"
FIGURE_RUNS = REPORTS_DIR / "figures" / "pipeline_runs"
RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_reference() -> dict[str, str]:
    """Verify that the local model and dataset match the recorded experiment."""
    for path in (
        PARQUET_PATH, MODELING_DATASET_PATH, MODEL_PATH, EXPERIMENT_CONFIG_PATH,
        SHAP_PROVENANCE_PATH, CLEANING_REPORT_PATH,
    ):
        if not path.is_file():
            raise FileNotFoundError(f"Required pipeline input does not exist: {path}")
    model_sha = _sha256(MODEL_PATH)
    dataset_sha = _sha256(MODELING_DATASET_PATH)
    config = json.loads(EXPERIMENT_CONFIG_PATH.read_text(encoding="utf-8"))
    explanation = json.loads(SHAP_PROVENANCE_PATH.read_text(encoding="utf-8"))
    if config.get("selected_model") != "svm" or config.get("dataset_sha256") != dataset_sha:
        raise ValueError("The recorded selected model or training dataset does not match the reference.")
    if explanation.get("model_sha256") != model_sha or explanation.get("dataset_sha256") != dataset_sha:
        raise ValueError("The saved SVM or reference dataset does not match the recorded SHAP provenance.")
    return {
        "model_sha256": model_sha,
        "reference_dataset_sha256": dataset_sha,
        "interim_dataset_sha256": _sha256(PARQUET_PATH),
        "original_cleaning_report_sha256": _sha256(CLEANING_REPORT_PATH),
    }


def _same_values(first, second) -> bool:
    if sparse.issparse(first) or sparse.issparse(second):
        if not sparse.issparse(first) or not sparse.issparse(second) or first.shape != second.shape:
            return False
        return (first != second).nnz == 0
    if isinstance(first, np.ndarray) or isinstance(second, np.ndarray):
        return np.array_equal(first, second)
    return bool(first == second)


def _matches_saved_pipeline(refitted, saved, X_train) -> bool:
    """Compare fitted SVC state and preprocessing outputs without serializing a model."""
    first, second = refitted.named_steps["estimator"], saved.named_steps["estimator"]
    if type(first) is not type(second) or set(vars(first)) != set(vars(second)):
        return False
    if any(not _same_values(vars(first)[key], vars(second)[key]) for key in vars(first)):
        return False
    first_preprocessor = refitted.named_steps["preprocessing"]
    second_preprocessor = saved.named_steps["preprocessing"]
    first_names = first_preprocessor.named_steps["preprocessor"].get_feature_names_out()
    second_names = second_preprocessor.named_steps["preprocessor"].get_feature_names_out()
    if not np.array_equal(first_names, second_names):
        return False
    return _same_values(
        first_preprocessor.transform(X_train), second_preprocessor.transform(X_train)
    )


def run_pipeline(run_id: str) -> dict:
    """Run preparation, training comparison, evaluation and SHAP without replacing inputs."""
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("Run ID must contain 1-64 letters, digits, underscores or hyphens and start with a letter or digit.")
    paths = [DATA_RUNS / run_id, RESULT_RUNS / run_id, FIGURE_RUNS / run_id]
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        raise FileExistsError(f"Run outputs already exist; choose a new run ID: {existing}")
    provenance = _verify_reference()
    saved_model = load_svm(MODEL_PATH)
    for path in paths:
        path.mkdir(parents=True, exist_ok=False)
    data_dir, results_dir, figures_dir = paths
    adult_path = data_dir / "finaccess_adults_unprepared.parquet"
    modeling_path = data_dir / "finaccess_modeling_dataset_6c.parquet"
    cleaning_report = results_dir / "data_cleaning_report.md"

    LOGGER.info("Preparing adult data in isolated run %s", run_id)
    shutil.copyfile(CLEANING_REPORT_PATH, cleaning_report)
    preparation = prepare_data(PARQUET_PATH, adult_path, cleaning_report)
    create_modeling_dataset(adult_path, modeling_path)
    actual = pq.read_table(modeling_path)
    reference = pq.read_table(MODELING_DATASET_PATH)
    if not actual.equals(reference, check_metadata=False):
        raise ValueError("Reconstructed modeling data do not exactly match the approved reference; evaluation stopped.")

    modeling = load_modeling_data(modeling_path)
    X_train, X_test, y_train, y_test = split_modeling_data(modeling)
    LOGGER.info("Comparing the four candidates using training folds only")
    selected, refitted_model, comparison = train_candidates(X_train, y_train)
    if selected != "svm":
        raise ValueError(f"Training-only comparison selected {selected}, not the saved SVM; evaluation stopped.")
    if not _matches_saved_pipeline(refitted_model, saved_model, X_train):
        raise ValueError("The refitted SVM state or training preprocessing outputs differ from the saved model; evaluation stopped.")

    LOGGER.info("Evaluating and explaining the unchanged saved SVM")
    metrics = evaluate_model(saved_model, X_test, y_test, figures_dir)
    write_experiment_results(
        modeling_path, results_dir, figures_dir, len(X_train), len(X_test),
        selected, comparison, metrics,
    )
    run_explanations(MODEL_PATH, modeling_path, results_dir, figures_dir)
    if provenance != _verify_reference():
        raise ValueError("A protected pipeline input changed during execution.")
    manifest = {
        "run_id": run_id,
        "random_seed": RANDOM_SEED,
        "selected_model": selected,
        "model_artifact_rewritten": False,
        "test_partition_previously_evaluated": True,
        "modeling_values_match_reference": True,
        "refitted_svm_and_training_preprocessing_match": True,
        "source_rows": preparation["source_rows"],
        "adult_rows": preparation["retained_adults"],
        "training_rows": len(X_train),
        "test_rows": len(X_test),
        **provenance,
        "run_modeling_dataset_sha256": _sha256(modeling_path),
    }
    (results_dir / "pipeline_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    LOGGER.info("Completed run %s; results in %s", run_id, results_dir)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="New unique run ID; existing outputs are never overwritten.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    LOGGER.setLevel(logging.INFO)
    try:
        run_pipeline(args.run_id)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        LOGGER.exception("Pipeline failed; any incomplete run directories were left untouched.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
