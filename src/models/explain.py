"""Training-only, model-agnostic SHAP explanations for the fitted SVM."""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC

from src.data.feature_engineering import MODELING_DATASET_PATH, PREDICTOR_COLUMNS
from src.data.preprocessing import CATEGORICAL_FEATURES, NUMERIC_FEATURES, split_modeling_data
from src.financial_exclusion.config import ARTIFACTS_DIR, RANDOM_SEED, REPORTS_DIR
from src.models.train import load_modeling_data

LOGGER = logging.getLogger(__name__)
MODEL_PATH = ARTIFACTS_DIR / "financial_exclusion_pipeline.joblib"
RESULTS_DIR = REPORTS_DIR / "results"
FIGURES_DIR = REPORTS_DIR / "figures"
BACKGROUND_SIZE = 24
EXPLANATION_SIZE = 64
COALITION_SAMPLES = 128
FEATURE_LABELS = {
    "A18": "Respondent age",
    "Sex": "Respondent sex",
    "A20": "Education completed",
    "county": "County",
    "A08": "Rural/urban cluster type",
    "B3A__2": "Income source: employed",
    "B3A__4": "Income source: own business",
    "B3Ii": "Income received last month",
    "ID_card": "Identification document",
    "S1": "Phone ownership/use",
    "S3": "Internet-use frequency",
    "A24i": "Difficulty seeing",
    "A24ii": "Difficulty hearing",
    "A24iii": "Difficulty walking/climbing",
    "A24iv": "Difficulty remembering/concentrating",
    "A24v": "Difficulty with self-care",
    "A24vi": "Difficulty communicating",
}


def load_svm(path: Path) -> Pipeline:
    """Load the trusted local pipeline and verify the class-1 score semantics."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Fitted SVM pipeline does not exist: {path}")
    model = joblib.load(path)
    if not isinstance(model, Pipeline) or list(model.named_steps) != ["preprocessing", "estimator"]:
        raise ValueError("Expected the fitted preprocessing and estimator pipeline.")
    estimator = model.named_steps["estimator"]
    if not isinstance(estimator, SVC) or estimator.kernel != "rbf":
        raise ValueError("Expected the selected RBF SVC estimator.")
    if list(estimator.classes_) != [0, 1]:
        raise ValueError("SVM classes must be ordered as included 0, excluded 1.")
    return model


def transformed_feature_mapping(model: Pipeline) -> list[dict[str, str]]:
    """Map every fitted numeric, missing-indicator and one-hot feature to its source."""
    transformer = model.named_steps["preprocessing"].named_steps["preprocessor"]
    all_names = list(transformer.get_feature_names_out())
    numeric = transformer.named_transformers_["numeric"]
    categorical = transformer.named_transformers_["categorical"]
    numeric_names = numeric.get_feature_names_out(list(NUMERIC_FEATURES))
    mapping = []
    for name in numeric_names:
        source = name.removeprefix("missingindicator_")
        if source not in NUMERIC_FEATURES:
            raise ValueError(f"Unrecognized numeric transformed feature: {name}")
        mapping.append({"transformed_feature": f"numeric__{name}", "source_variable": source})
    encoder = categorical.named_steps["onehot"]
    if encoder.drop_idx_ is not None or encoder.min_frequency is not None or encoder.max_categories is not None:
        raise ValueError("Unexpected one-hot grouping; cannot safely map transformed features.")
    categorical_names = list(categorical.get_feature_names_out(list(CATEGORICAL_FEATURES)))
    offset = 0
    for column, categories in zip(CATEGORICAL_FEATURES, encoder.categories_):
        names = categorical_names[offset:offset + len(categories)]
        if len(names) != len(categories) or any(not name.startswith(f"{column}_") for name in names):
            raise ValueError(f"Cannot map one-hot features for {column}.")
        mapping.extend(
            {"transformed_feature": f"categorical__{name}", "source_variable": column}
            for name in names
        )
        offset += len(categories)
    if [entry["transformed_feature"] for entry in mapping] != all_names:
        raise ValueError("Transformed feature mapping does not match the fitted preprocessing.")
    return mapping


def select_training_samples(
    X_train: pd.DataFrame, background_size: int, explanation_size: int, seed: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Draw disjoint background and explanation rows from the training partition."""
    if tuple(X_train.columns) != PREDICTOR_COLUMNS:
        raise ValueError("Explanation input must contain exactly the approved predictors in order.")
    if not X_train.index.is_unique:
        raise ValueError("Training rows must have unique indices for disjoint sampling.")
    if background_size < 1 or explanation_size < 1 or background_size + explanation_size > len(X_train):
        raise ValueError("Requested explanation samples must be positive and fit within training data.")
    chosen = X_train.sample(n=background_size + explanation_size, random_state=seed)
    return chosen.iloc[:background_size].copy(), chosen.iloc[background_size:].copy()


def synthetic_excluded_profile(model: Pipeline, X_train: pd.DataFrame) -> pd.DataFrame:
    """Construct a modal composite from training rows the model predicts as excluded."""
    predicted_excluded = X_train.loc[model.predict(X_train) == 1]
    if predicted_excluded.empty:
        raise ValueError("No training rows are predicted excluded; cannot construct the local profile.")
    values = {}
    for column in PREDICTOR_COLUMNS:
        modes = predicted_excluded[column].mode(dropna=True)
        if modes.empty:
            raise ValueError(f"Cannot form a modal value for {column}.")
        values[column] = modes.iloc[0]
    profile = pd.DataFrame([values], columns=PREDICTOR_COLUMNS)
    if X_train.eq(profile.iloc[0]).all(axis=1).any():
        raise ValueError("The synthetic profile matches a training record; cannot publish a local example.")
    if int(model.predict(profile)[0]) != 1:
        raise ValueError("The synthetic modal profile is not predicted excluded.")
    return profile


def explain_samples(
    model: Pipeline, background: pd.DataFrame, samples: pd.DataFrame,
    *, seed: int = RANDOM_SEED, coalition_samples: int = COALITION_SAMPLES,
) -> tuple[float, np.ndarray, np.ndarray]:
    """Explain the RBF SVM's class-1 margin at original-variable level."""
    if tuple(background.columns) != PREDICTOR_COLUMNS or tuple(samples.columns) != PREDICTOR_COLUMNS:
        raise ValueError("SHAP inputs must contain the approved predictors in order.")
    if background.empty or samples.empty or coalition_samples < 2:
        raise ValueError("SHAP requires nonempty samples and at least two coalition samples.")

    def class_one_margin(rows: np.ndarray) -> np.ndarray:
        frame = pd.DataFrame(rows, columns=PREDICTOR_COLUMNS)
        return model.decision_function(frame)

    explainer = shap.KernelExplainer(class_one_margin, background)
    previous_state = np.random.get_state()
    try:
        np.random.seed(seed)
        values = np.asarray(
            explainer.shap_values(samples, nsamples=coalition_samples, l1_reg=0.0, silent=True)
        )
    finally:
        np.random.set_state(previous_state)
    baseline = float(explainer.expected_value)
    margins = np.asarray(class_one_margin(samples.to_numpy()), dtype=float)
    if values.shape != (len(samples), len(PREDICTOR_COLUMNS)) or not np.isfinite(values).all():
        raise ValueError("SHAP returned unexpected or non-finite attribution values.")
    if not np.allclose(baseline + values.sum(axis=1), margins, rtol=1e-6, atol=1e-6):
        raise ValueError("SHAP attributions do not add up to the SVM decision margins.")
    return baseline, values, margins


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_explanations(
    model_path: Path = MODEL_PATH, dataset_path: Path = MODELING_DATASET_PATH,
    results_dir: Path = RESULTS_DIR, figures_dir: Path = FIGURES_DIR,
    *, background_size: int = BACKGROUND_SIZE, explanation_size: int = EXPLANATION_SIZE,
    coalition_samples: int = COALITION_SAMPLES, seed: int = RANDOM_SEED,
) -> dict:
    """Generate global training-sample and synthetic local SVM explanations."""
    model_path, dataset_path = Path(model_path), Path(dataset_path)
    results_dir, figures_dir = Path(results_dir), Path(figures_dir)
    model_hash, dataset_hash = _sha256(model_path), _sha256(dataset_path)
    model = load_svm(model_path)
    mapping = transformed_feature_mapping(model)
    data = load_modeling_data(dataset_path)
    X_train, _, _, _ = split_modeling_data(data)
    background, sample = select_training_samples(X_train, background_size, explanation_size, seed)
    local = synthetic_excluded_profile(model, X_train)
    combined = pd.concat([sample, local], ignore_index=True)
    baseline, values, margins = explain_samples(
        model, background, combined, seed=seed, coalition_samples=coalition_samples
    )
    global_values, local_values = values[:-1], values[-1]
    importance = pd.Series(
        np.abs(global_values).mean(axis=0), index=PREDICTOR_COLUMNS
    ).sort_values(ascending=False)
    results_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    shap.summary_plot(
        global_values, feature_names=[f"{name}: {FEATURE_LABELS[name]}" for name in PREDICTOR_COLUMNS],
        max_display=len(PREDICTOR_COLUMNS), show=False, rng=np.random.default_rng(seed),
    )
    plt.xlabel("SHAP value (class-1 decision margin)")
    plt.title(f"Training-sample SHAP summary (n={explanation_size}, unweighted)")
    plt.tight_layout()
    plt.savefig(figures_dir / "shap_summary.png", dpi=140, bbox_inches="tight")
    plt.close()

    fig, ax = plt.subplots(figsize=(9, 7), layout="constrained")
    labelled_importance = importance.rename(index=lambda name: f"{name}: {FEATURE_LABELS[name]}")
    labelled_importance.iloc[::-1].plot.barh(ax=ax, color="#32658a")
    ax.set_xlabel("Mean absolute SHAP value (class-1 decision margin)")
    ax.set_title(f"Global feature importance (training sample, n={explanation_size})")
    fig.savefig(figures_dir / "shap_feature_importance.png", dpi=140)
    plt.close(fig)

    local_series = pd.Series(
        local_values, index=[f"{name}: {FEATURE_LABELS[name]}" for name in PREDICTOR_COLUMNS]
    ).sort_values()
    fig, ax = plt.subplots(figsize=(9, 7), layout="constrained")
    local_series.plot.barh(ax=ax, color=["#b45c38" if value > 0 else "#32658a" for value in local_series])
    ax.axvline(0, color="black", linewidth=0.7)
    ax.set_xlabel("SHAP contribution to class-1 decision margin")
    ax.set_title("Synthetic excluded-class prediction: local SHAP contributions")
    fig.savefig(figures_dir / "shap_local.png", dpi=140)
    plt.close(fig)

    result = {
        "model_sha256": model_hash,
        "dataset_sha256": dataset_hash,
        "explainer": "shap.KernelExplainer",
        "shap_version": shap.__version__,
        "score": "SVC decision_function; positive margins favor excluded class 1",
        "background": {"source": "training", "size": len(background), "seed": seed},
        "global_sample": {"source": "training", "size": len(sample), "disjoint_from_background": True},
        "coalition_samples": coalition_samples,
        "l1_reg": 0.0,
        "expected_margin": baseline,
        "global_mean_absolute_shap": {name: float(value) for name, value in importance.items()},
        "local": {
            "profile": "synthetic per-variable modes among training rows predicted excluded; no raw values saved",
            "predicted_class": int(model.predict(local)[0]),
            "margin": float(margins[-1]),
            "shap_values": {name: float(value) for name, value in zip(PREDICTOR_COLUMNS, local_values)},
        },
        "max_additivity_residual": float(np.max(np.abs(baseline + values.sum(axis=1) - margins))),
        "transformed_feature_mapping": mapping,
    }
    (results_dir / "shap_explanations.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    _write_report(results_dir / "shap_report.md", result)
    if _sha256(model_path) != model_hash or _sha256(dataset_path) != dataset_hash:
        raise ValueError("The model or input dataset changed during explanation.")
    LOGGER.info("SHAP output created from %s training explanations", len(sample))
    return result


def _write_report(path: Path, result: dict) -> None:
    importance = result["global_mean_absolute_shap"]
    local = result["local"]
    lines = [
        "# SHAP explanations for the selected SVM",
        "",
        "## Method and scope",
        "",
        f"- The fitted pipeline is an RBF SVC with classes `[0, 1]`, 17 approved raw inputs and {len(result['transformed_feature_mapping'])} fitted transformed features.",
        "- Model-agnostic `shap.KernelExplainer` explains the complete unchanged pipeline's `decision_function`, not an assumed linear model or a probability. Positive margins and positive SHAP contributions favor class 1 (excluded).",
        f"- A disjoint random sample of {result['background']['size']} training rows is the background; {result['global_sample']['size']} other training rows form the global sample (seed {result['background']['seed']}). No test rows are used.",
        f"- Approximate Kernel SHAP uses {result['coalition_samples']} sampled coalitions per explanation, `l1_reg=0.0` and SHAP {result['shap_version']}. Mean absolute SHAP values are unweighted sample summaries.",
        "- Masking is performed at the original-variable level through the fitted pipeline. Thus each source variable's numeric, missing-indicator or one-hot outputs are varied together; the complete transformed-to-source mapping is in `shap_explanations.json`.",
        f"- Model SHA-256: `{result['model_sha256']}`. Dataset SHA-256: `{result['dataset_sha256']}`.",
        f"- Background mean margin: {result['expected_margin']:.4f}; maximum numerical additivity residual: {result['max_additivity_residual']:.2e}.",
        "",
        "## Global importance",
        "",
        "| Original variable | Description | Mean absolute SHAP value |",
        "| --- | --- | ---: |",
        *[f"| `{name}` | {FEATURE_LABELS[name]} | {value:.4f} |" for name, value in importance.items()],
        "",
        "![SHAP summary](../figures/shap_summary.png)",
        "![SHAP feature importance](../figures/shap_feature_importance.png)",
        "",
        "## Local explanation",
        "",
        "The local case is a synthetic composite of the per-variable modes among training rows the model predicts excluded. It is not a reported individual; the input values are not exported. Combining modes can form an implausible profile.",
        f"Its predicted class is {local['predicted_class']} (excluded), decision margin {local['margin']:.4f}, and background margin {result['expected_margin']:.4f}. The signed contributions in the figure and JSON sum to the difference.",
        "",
        "![Synthetic local explanation](../figures/shap_local.png)",
        "",
        "## Limitations",
        "",
        "These are model associations, not causal effects, probabilities, or nationally representative estimates. Small background and explanation samples and approximate coalition sampling can change rankings; they are not uncertainty estimates. Independently substituting background variables can create implausible combinations and does not establish conditional or causal effects. Correlated predictors can share or redistribute attribution. The model's prior held-out evaluation was already exposed, survey weights/design are not used, and the provider's target derivation remains unverified. Do not use these results to change features or tune the model based on the test set.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    LOGGER.setLevel(logging.INFO)
    try:
        run_explanations()
    except (OSError, ValueError, TypeError, KeyError):
        LOGGER.exception("SVM SHAP explanation failed.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
