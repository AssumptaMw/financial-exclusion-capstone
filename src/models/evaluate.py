"""Evaluate a fitted pipeline on the untouched held-out partition."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.pipeline import Pipeline


def evaluate_model(
    model: Pipeline, X_test: pd.DataFrame, y_test: pd.Series, figures_dir: Path
) -> dict:
    """Return unweighted test metrics and save confusion, ROC and PR figures."""
    if set(y_test.unique()) != {0, 1} or y_test.isna().any():
        raise ValueError("Held-out evaluation requires both non-null binary classes.")
    if list(model.classes_) != [0, 1]:
        raise ValueError("The fitted model must expose classes 0 and 1 in order.")
    predictions = model.predict(X_test)
    probabilities = model.predict_proba(X_test)[:, 1]
    matrix = confusion_matrix(y_test, predictions, labels=[0, 1])
    metrics = {
        "n": int(len(y_test)),
        "positive_class": 1,
        "threshold": 0.5,
        "accuracy": float(accuracy_score(y_test, predictions)),
        "precision": float(precision_score(y_test, predictions, zero_division=0)),
        "recall": float(recall_score(y_test, predictions, zero_division=0)),
        "f1": float(f1_score(y_test, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, probabilities)),
        "pr_auc_average_precision": float(average_precision_score(y_test, probabilities)),
        "confusion_matrix": matrix.tolist(),
        "classification_report": classification_report(
            y_test, predictions, labels=[0, 1],
            target_names=["included", "excluded"], output_dict=True, zero_division=0,
        ),
    }

    figures_dir = Path(figures_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 5), layout="constrained")
    image = ax.imshow(matrix, cmap="Blues")
    fig.colorbar(image, ax=ax, label="Respondents")
    ax.set_xticks([0, 1], labels=["Included (0)", "Excluded (1)"])
    ax.set_yticks([0, 1], labels=["Included (0)", "Excluded (1)"])
    ax.set_xlabel("Predicted class")
    ax.set_ylabel("Actual class")
    ax.set_title("Held-out confusion matrix (unweighted)")
    for row in range(2):
        for column in range(2):
            ax.text(column, row, f"{matrix[row, column]:,}", ha="center", va="center",
                    color="white" if matrix[row, column] > matrix.max() / 2 else "black")
    fig.savefig(figures_dir / "model_confusion_matrix.png", dpi=140)
    plt.close(fig)

    false_positive, true_positive, _ = roc_curve(y_test, probabilities)
    fig, ax = plt.subplots(figsize=(6, 5), layout="constrained")
    ax.plot(false_positive, true_positive, label=f"ROC-AUC = {metrics['roc_auc']:.3f}")
    ax.plot([0, 1], [0, 1], "--", color="gray", label="Random ranking")
    ax.set(xlabel="False positive rate", ylabel="True positive rate",
           title="Held-out ROC curve (unweighted)", xlim=(0, 1), ylim=(0, 1))
    ax.legend(loc="lower right")
    fig.savefig(figures_dir / "model_roc.png", dpi=140)
    plt.close(fig)

    precision, recall, _ = precision_recall_curve(y_test, probabilities)
    fig, ax = plt.subplots(figsize=(6, 5), layout="constrained")
    ax.step(recall, precision, where="post",
            label=f"Average precision = {metrics['pr_auc_average_precision']:.3f}")
    ax.axhline(float(np.mean(y_test)), linestyle="--", color="gray",
               label=f"Prevalence = {np.mean(y_test):.3f}")
    ax.set(xlabel="Recall (excluded class)", ylabel="Precision (excluded class)",
           title="Held-out precision-recall curve (unweighted)", xlim=(0, 1), ylim=(0, 1))
    ax.legend(loc="lower left")
    fig.savefig(figures_dir / "model_precision_recall.png", dpi=140)
    plt.close(fig)
    return metrics
