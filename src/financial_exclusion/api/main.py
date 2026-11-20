"""FastAPI service for the locally saved financial-exclusion pipeline."""

from contextlib import asynccontextmanager
import logging

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.data.feature_engineering import PREDICTOR_COLUMNS
from src.financial_exclusion.api.schemas import (
    BatchPredictionInput,
    BatchPredictionOutput,
    PredictionInput,
    PredictionOutput,
    PredictionWithExplanation,
)
from src.models.load_model import MODEL_PATH, load_svm
from src.models.explain_prediction import LocalSHAPExplainer

LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model = None
    app.state.explainer = None
    try:
        app.state.model = load_svm(MODEL_PATH)
        app.state.explainer = LocalSHAPExplainer(MODEL_PATH)
    except Exception:
        LOGGER.exception("Failed to load the local prediction pipeline at startup.")
    yield
    app.state.model = None
    app.state.explainer = None


app = FastAPI(
    title="Financial Exclusion Prediction API",
    description="Predict the project-defined class for adults using the approved 17 workbook fields.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": "Invalid request; check the API schema at /docs."})


@app.get("/")
def welcome() -> dict[str, str]:
    return {"message": "Financial Exclusion Prediction API", "health": "/health", "docs": "/docs"}


@app.get("/health")
def health(request: Request) -> dict[str, str]:
    if request.app.state.model is None:
        raise HTTPException(status_code=503, detail="Prediction service is unavailable.")
    return {"status": "ready"}


def predict_records(request: Request, records: list[PredictionInput]) -> list[PredictionOutput]:
    model = request.app.state.model
    if model is None:
        raise HTTPException(status_code=503, detail="Prediction service is unavailable.")
    frame = pd.DataFrame(
        [record.model_dump() for record in records], columns=PREDICTOR_COLUMNS
    ).replace({None: np.nan})
    try:
        predictions = model.predict(frame)
        if len(predictions) != len(records) or not all(value in (0, 1) for value in predictions):
            raise ValueError("Unexpected model prediction shape or class.")
        return [
            PredictionOutput(
                financial_exclusion_status=int(value),
                label="Financially excluded" if value == 1 else "Financially included",
            )
            for value in predictions
        ]
    except Exception as exc:
        LOGGER.error("Prediction failed (%s).", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Prediction failed.") from exc


@app.post("/predict", response_model=PredictionOutput)
def predict(request: Request, record: PredictionInput) -> PredictionOutput:
    return predict_records(request, [record])[0]


@app.post("/predict/batch", response_model=BatchPredictionOutput)
def predict_batch(request: Request, batch: BatchPredictionInput) -> BatchPredictionOutput:
    return BatchPredictionOutput(predictions=predict_records(request, batch.records))


@app.post("/predict/with-explanation", response_model=PredictionWithExplanation)
def predict_with_explanation(request: Request, record: PredictionInput) -> PredictionWithExplanation:
    """Predict with SHAP-based local explanation. Warning: computationally expensive."""
    model = request.app.state.model
    explainer = request.app.state.explainer
    if model is None or explainer is None:
        raise HTTPException(status_code=503, detail="Prediction service is unavailable.")

    frame = pd.DataFrame([record.model_dump()], columns=PREDICTOR_COLUMNS).replace({None: np.nan})

    try:
        predictions = model.predict(frame)
        if len(predictions) != 1 or predictions[0] not in (0, 1):
            raise ValueError("Unexpected model prediction.")

        prediction = PredictionOutput(
            financial_exclusion_status=int(predictions[0]),
            label="Financially excluded" if predictions[0] == 1 else "Financially included",
        )

        try:
            explanation_result = {
                "success": True,
                "margin": float(model.decision_function(frame)[0]),
                "contributors": [],
            }

            shap_values = explainer.explain(frame)
            top_contributors = sorted(
                [(var, shap_values[var]) for var in PREDICTOR_COLUMNS],
                key=lambda x: abs(x[1]),
                reverse=True,
            )[:5]

            explanation_result["contributors"] = [
                {
                    "variable": var,
                    "shap_value": value,
                    "direction": "towards excluded" if value > 0 else "towards included",
                }
                for var, value in top_contributors
            ]
        except Exception as exc:
            LOGGER.warning("SHAP explanation failed: %s", exc)
            explanation_result = {"success": False, "error": str(exc)}

        return PredictionWithExplanation(
            financial_exclusion_status=prediction.financial_exclusion_status,
            label=prediction.label,
            explanation=explanation_result,
        )

    except Exception as exc:
        LOGGER.error("Prediction with explanation failed (%s).", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Prediction failed.") from exc

