"""Load the trusted, selected model without retraining it."""

from pathlib import Path

import joblib
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC
from sklearn.utils.validation import check_is_fitted

from src.data.feature_engineering import PREDICTOR_COLUMNS
from src.financial_exclusion.config import ARTIFACTS_DIR

MODEL_PATH = ARTIFACTS_DIR / "financial_exclusion_pipeline.joblib"


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
    check_is_fitted(estimator)
    if list(estimator.classes_) != [0, 1]:
        raise ValueError("SVM classes must be ordered as included 0, excluded 1.")
    preprocessing = model.named_steps["preprocessing"]
    if not isinstance(preprocessing, Pipeline) or "preprocessor" not in preprocessing.named_steps:
        raise ValueError("Expected the fitted preprocessing pipeline.")
    transformer = preprocessing.named_steps["preprocessor"]
    check_is_fitted(transformer)
    if tuple(transformer.feature_names_in_) != PREDICTOR_COLUMNS:
        raise ValueError("Saved model predictors do not match the approved input schema.")
    return model
