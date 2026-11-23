"""Local SHAP explanations for individual predictions."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import shap

from src.data.feature_engineering import MODELING_DATASET_PATH, PREDICTOR_COLUMNS
from src.data.preprocessing import split_modeling_data
from src.models.load_model import load_svm
from src.models.train import load_modeling_data

LOGGER = logging.getLogger(__name__)

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

BACKGROUND_SIZE = 24
COALITION_SAMPLES = 128


class LocalSHAPExplainer:
    """Thread-safe local SHAP explainer for a fitted SVM pipeline."""

    def __init__(self, model_path: Path | str, background_size: int = BACKGROUND_SIZE):
        """Load the model and training background data."""
        self.model_path = Path(model_path)
        self.background_size = background_size
        self.model = None
        self.background = None
        self.explainer = None
        self._load()

    def _load(self) -> None:
        """Load the model and prepare the background data."""
        try:
            self.model = load_svm(self.model_path)
            X_train, _, _, _ = split_modeling_data(load_modeling_data(MODELING_DATASET_PATH), test_size=0.2, random_state=42)
            if len(X_train) < self.background_size:
                raise ValueError(f"Training data has {len(X_train)} rows; {self.background_size} required.")
            self.background = X_train.sample(n=self.background_size, random_state=42).reset_index(drop=True)
            self.explainer = None
        except Exception as exc:
            LOGGER.error("Failed to load model and background data: %s", exc)
            raise

    def _get_or_create_explainer(self) -> shap.KernelExplainer:
        """Create a Kernel SHAP explainer lazily."""
        if self.explainer is None:
            # Wrap decision_function to avoid SHAP trying to set feature_names_in_
            def predict_fn(X: np.ndarray) -> np.ndarray:
                """Wrapper that handles numpy array input from SHAP."""
                if isinstance(X, np.ndarray):
                    X = pd.DataFrame(X, columns=PREDICTOR_COLUMNS)
                return self.model.decision_function(X)
            
            self.explainer = shap.KernelExplainer(
                predict_fn,
                self.background.values,  # Use numpy array for background
                feature_names=list(PREDICTOR_COLUMNS),
            )
        return self.explainer

    def explain(self, record: pd.DataFrame) -> dict[str, float]:
        """
        Compute local SHAP values for a single record.

        Args:
            record: DataFrame with one row containing the predictor values.

        Returns:
            Dictionary mapping variable names to SHAP values (contributions to class-1 margin).

        Raises:
            ValueError: If the record is invalid or explanation fails.
        """
        if len(record) != 1:
            raise ValueError("Expected a single record for explanation.")
        if list(record.columns) != list(PREDICTOR_COLUMNS):
            raise ValueError(f"Record columns must be {PREDICTOR_COLUMNS}.")

        try:
            explainer = self._get_or_create_explainer()
            shap_values = explainer.shap_values(
                record,
                nsamples=COALITION_SAMPLES,
                l1_reg=0.0,
                silent=True,
            )
            if shap_values is None or not isinstance(shap_values, np.ndarray):
                raise ValueError("SHAP returned invalid values.")

            if shap_values.shape != (1, len(PREDICTOR_COLUMNS)):
                raise ValueError(f"Unexpected SHAP shape: {shap_values.shape}.")

            return {
                str(col): float(val)
                for col, val in zip(PREDICTOR_COLUMNS, shap_values[0])
            }
        except Exception as exc:
            LOGGER.error("SHAP explanation failed: %s", exc)
            raise


def explain_prediction(record: pd.DataFrame, explainer: LocalSHAPExplainer) -> dict[str, object]:
    """
    Generate a local explanation for a prediction.

    Args:
        record: DataFrame with one row containing the predictor values.
        explainer: LocalSHAPExplainer instance.

    Returns:
        Dictionary with 'shap_values', 'margin' and other explanation metadata.
    """
    try:
        shap_values = explainer.explain(record)
        margin = float(explainer.model.decision_function(record)[0])

        top_contributors = sorted(
            [(var, shap_values[var]) for var in PREDICTOR_COLUMNS],
            key=lambda x: abs(x[1]),
            reverse=True,
        )[:5]

        return {
            "success": True,
            "margin": margin,
            "shap_values": shap_values,
            "top_contributors": [
                {
                    "variable": var,
                    "label": FEATURE_LABELS.get(var, var),
                    "shap_value": value,
                    "direction": "towards excluded" if value > 0 else "towards included",
                }
                for var, value in top_contributors
            ],
        }
    except Exception as exc:
        LOGGER.error("Explanation generation failed: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "margin": None,
            "shap_values": None,
            "top_contributors": None,
        }
