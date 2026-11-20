"""Compare and train leakage-safe financial exclusion classifiers."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pyarrow
import pyarrow.parquet as pq
import sklearn
import xgboost
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC

from src.data.feature_engineering import (
    MODEL_METADATA_KEY,
    MODELING_DATASET_PATH,
    PREDICTOR_COLUMNS,
    TARGET_COLUMN,
)
from src.data.preprocessing import build_model_pipeline, split_modeling_data
from src.financial_exclusion.config import ARTIFACTS_DIR, RANDOM_SEED, REPORTS_DIR
from src.models.estimators import BalancedXGBClassifier
from src.models.evaluate import evaluate_model

LOGGER = logging.getLogger(__name__)
SCORING = {
    "accuracy": "accuracy",
    "precision": "precision",
    "recall": "recall",
    "f1": "f1",
    "roc_auc": "roc_auc",
    "pr_auc_average_precision": "average_precision",
}


def load_modeling_data(path: Path) -> pd.DataFrame:
    """Load the approved model dataset and verify its provenance."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Modeling dataset does not exist: {path}")
    table = pq.read_table(path)
    metadata = table.schema.metadata or {}
    if MODEL_METADATA_KEY not in metadata:
        raise ValueError("Modeling dataset is missing predictor provenance metadata.")
    provenance = json.loads(metadata[MODEL_METADATA_KEY])
    if provenance.get("predictors") != list(PREDICTOR_COLUMNS):
        raise ValueError("Modeling dataset predictors do not match the approved feature list.")
    if provenance.get("target_column") != TARGET_COLUMN:
        raise ValueError("Modeling dataset target does not match the approved target.")
    return table.to_pandas()


def train_candidates(
    X_train: pd.DataFrame, y_train: pd.Series, *, cv_splits: int = 5,
    forest_trees: int = 100, boosting_rounds: int = 100,
) -> tuple[str, Pipeline, dict]:
    """Compare fixed candidates on training folds, select by F1 then recall, and refit."""
    counts = y_train.value_counts()
    if set(counts.index) != {0, 1} or y_train.isna().any():
        raise ValueError("Training requires both non-null binary target classes.")
    if cv_splits < 2 or counts.min() < cv_splits:
        raise ValueError("Each training class must have at least one observation per fold.")
    if tuple(X_train.columns) != PREDICTOR_COLUMNS:
        raise ValueError("Training predictors do not match the approved feature list.")
    if not X_train.index.equals(y_train.index):
        raise ValueError("Training predictor and target indices must match.")
    candidates = {
        "logistic_regression": LogisticRegression(
            class_weight="balanced", max_iter=1000, solver="liblinear", random_state=RANDOM_SEED
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=forest_trees, class_weight="balanced",
            random_state=RANDOM_SEED, n_jobs=-1,
        ),
        "xgboost": BalancedXGBClassifier(
            n_estimators=boosting_rounds, random_state=RANDOM_SEED,
            n_jobs=4, tree_method="hist",
        ),
        "svm": SVC(
            kernel="rbf", class_weight="balanced", probability=False,
            cache_size=512, random_state=RANDOM_SEED,
        ),
    }
    cv = StratifiedKFold(n_splits=cv_splits, shuffle=True, random_state=RANDOM_SEED)
    results = {}
    for name, estimator in candidates.items():
        LOGGER.info("Cross-validating %s", name)
        scores = cross_validate(
            build_model_pipeline(estimator), X_train, y_train,
            cv=cv, scoring=SCORING, error_score="raise", n_jobs=1,
        )
        results[name] = {
            metric: {
                "folds": [float(value) for value in scores[f"test_{metric}"]],
                "mean": float(np.mean(scores[f"test_{metric}"])),
                "std": float(np.std(scores[f"test_{metric}"], ddof=0)),
            }
            for metric in SCORING
        }
    # Exact ties follow the fixed candidate order.
    selected = max(
        candidates,
        key=lambda name: (results[name]["f1"]["mean"], results[name]["recall"]["mean"]),
    )
    model = build_model_pipeline(candidates[selected])
    model.fit(X_train, y_train)
    return selected, model, results


def run_experiment(
    dataset_path: Path = MODELING_DATASET_PATH,
    results_dir: Path = REPORTS_DIR / "results",
    figures_dir: Path = REPORTS_DIR / "figures",
    artifacts_dir: Path = ARTIFACTS_DIR,
) -> dict:
    """Train on the established split and evaluate after training-only selection."""
    dataset_path = Path(dataset_path)
    results_dir = Path(results_dir)
    figures_dir = Path(figures_dir)
    artifacts_dir = Path(artifacts_dir)
    data = load_modeling_data(dataset_path)
    X_train, X_test, y_train, y_test = split_modeling_data(data)
    selected, model, comparison = train_candidates(X_train, y_train)

    results_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifacts_dir / "financial_exclusion_pipeline.joblib"
    joblib.dump(model, model_path)
    reloaded = joblib.load(model_path)
    if not np.array_equal(model.predict(X_train.iloc[:5]), reloaded.predict(X_train.iloc[:5])):
        raise ValueError("Reloaded pipeline predictions do not match the fitted model.")
    metrics = evaluate_model(reloaded, X_test, y_test, figures_dir)
    write_experiment_results(
        dataset_path, results_dir, figures_dir, len(X_train), len(X_test),
        selected, comparison, metrics,
    )
    LOGGER.info("Selected %s; saved fitted pipeline to %s", selected, model_path)
    return {"selected_model": selected, "comparison": comparison, "metrics": metrics, "model_path": model_path}


def write_experiment_results(
    dataset_path: Path, results_dir: Path, figures_dir: Path,
    train_rows: int, test_rows: int, selected: str, comparison: dict, metrics: dict,
) -> None:
    """Write the established experiment metadata and evaluation report."""
    dataset_path, results_dir, figures_dir = Path(dataset_path), Path(results_dir), Path(figures_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with dataset_path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    config = {
        "dataset": dataset_path.name,
        "dataset_sha256": digest.hexdigest(),
        "predictors": list(PREDICTOR_COLUMNS),
        "target": TARGET_COLUMN,
        "train_rows": train_rows,
        "test_rows": test_rows,
        "split": {"method": "stratified train_test_split", "test_size": 0.2, "random_state": RANDOM_SEED},
        "cross_validation": {"method": "StratifiedKFold", "folds": 5, "shuffle": True, "random_state": RANDOM_SEED},
        "selection": "highest mean CV F1 for class 1; recall breaks ties; candidate order breaks exact ties",
        "candidates": {
            "logistic_regression": {"class_weight": "balanced", "max_iter": 1000, "solver": "liblinear", "random_state": RANDOM_SEED},
            "random_forest": {"class_weight": "balanced", "n_estimators": 100, "random_state": RANDOM_SEED, "n_jobs": -1},
            "xgboost": {"scale_pos_weight": "negative/positive count within each fit", "n_estimators": 100, "tree_method": "hist", "random_state": RANDOM_SEED, "n_jobs": 4},
            "svm": {"kernel": "rbf", "class_weight": "balanced", "probability": False, "cache_size_mb": 512, "random_state": RANDOM_SEED},
        },
        "decision_threshold": metrics["threshold"],
        "score_type": metrics["score_type"],
        "positive_class": 1,
        "pr_auc_definition": "average precision (step-weighted precision-recall area)",
        "survey_weights_used": False,
        "selected_model": selected,
        "test_partition_previously_evaluated": True,
        "versions": {
            "python": platform.python_version(), "scikit_learn": sklearn.__version__,
            "pandas": pd.__version__, "numpy": np.__version__, "pyarrow": pyarrow.__version__,
            "joblib": joblib.__version__, "xgboost": xgboost.__version__,
        },
    }
    for name, value in (
        ("model_comparison.json", comparison),
        ("model_evaluation.json", metrics),
        ("model_experiment_config.json", config),
    ):
        (results_dir / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    _write_report(results_dir / "model_evaluation_report.md", selected, comparison, metrics, config, figures_dir)


def _write_report(
    path: Path, selected: str, comparison: dict, metrics: dict, config: dict,
    figures_dir: Path,
) -> None:
    rows = []
    for name, scores in comparison.items():
        values = [f"{scores[metric]['mean']:.4f} ± {scores[metric]['std']:.4f}" for metric in SCORING]
        rows.append("| " + " | ".join([name, *values]) + " |")
    matrix = metrics["confusion_matrix"]
    figure_link = Path(os.path.relpath(figures_dir, path.parent)).as_posix()
    report = [
        "# Model training and evaluation",
        "",
        "## Method",
        "",
        f"- Input: `{config['dataset']}`; SHA-256 `{config['dataset_sha256']}`.",
        f"- Existing stratified 80/20 split (seed {RANDOM_SEED}): {config['train_rows']:,} training and {config['test_rows']:,} held-out respondents.",
        "- Five shuffled stratified training folds (seed 42); each fold fits its own existing preprocessing and estimator. No resampling or hyperparameter tuning.",
        "- The approved proposal specifies four candidates: logistic regression (baseline), random forest (bagged trees), XGBoost (boosted trees), and an RBF support vector machine.",
        "- Logistic regression, random forest and SVM use balanced class weights; XGBoost calculates its positive-class weight from the negative/positive ratio within each fit, including each training fold.",
        "- Select the highest mean training-fold F1 for excluded class 1, then recall; complete ties follow the fixed order listed above. No candidate uses test results for selection.",
        f"- The selected model uses {metrics['score_type']} with the default decision threshold {metrics['threshold']}. SVM uses decision scores rather than calibrated probabilities. PR-AUC is average precision (step-weighted area); fold standard deviations use population convention (ddof=0).",
        "- This test partition was already evaluated and its results shared in the earlier two-model Phase 8 experiment. It is reused with researcher approval and is not a pristine independent assessment of the expanded comparison.",
        "- Metrics are unweighted sample descriptions; survey weights and design were not incorporated. The split and folds are not verified as cluster-aware.",
        "- The provider's original outcome classification derivation remains unverified. These cross-sectional results are neither causal nor nationally representative.",
        "",
        "## Training cross-validation comparison",
        "",
        "| Model | Accuracy | Precision | Recall | F1 | ROC-AUC | PR-AUC (AP) |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        *rows,
        "",
        f"Selected model: **{selected}**, using training-fold scores only. Fold values and settings are in the adjacent JSON files.",
        "",
        "## Selected model: held-out test evaluation",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        *[f"| {key} | {metrics[key]:.4f} |" for key in SCORING],
        "",
        "Confusion matrix (rows actual, columns predicted; 0 included, 1 excluded):",
        "",
        "| Actual / predicted | 0 | 1 |",
        "| --- | --- | --- |",
        f"| 0 | {matrix[0][0]} | {matrix[0][1]} |",
        f"| 1 | {matrix[1][0]} | {matrix[1][1]} |",
        "",
        "The full classification report and metric values are in `model_evaluation.json`.",
        "",
        f"![Confusion matrix]({figure_link}/model_confusion_matrix.png)",
        f"![ROC curve]({figure_link}/model_roc.png)",
        f"![Precision-recall curve]({figure_link}/model_precision_recall.png)",
        "",
        "## Limitations",
        "",
        "Recall and F1 concern the excluded class, not a population-level estimate. The previously examined test partition cannot provide a pristine assessment after expanding the candidate set; independent evaluation requires separately approved data or design. Threshold, model choice, and class weights require further substantive review; no test-set tuning was performed. Unresolved predictor response codes and survey design mappings remain documented in the variable selection and cleaning reports.",
        *(
            ["The fitted SVM contains transformed training observations as support vectors; keep the artifact local and do not commit it."]
            if selected == "svm" else []
        ),
        "",
    ]
    path.write_text("\n".join(report), encoding="utf-8")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        run_experiment()
    except (OSError, ValueError, TypeError, KeyError, pyarrow.ArrowException):
        LOGGER.exception("Model training and evaluation failed.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
