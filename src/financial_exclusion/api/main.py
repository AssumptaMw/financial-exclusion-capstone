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
)
from src.models.load_model import MODEL_PATH, load_svm

LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model = None
    try:
        app.state.model = load_svm(MODEL_PATH)
    except Exception:
        LOGGER.exception("Failed to load the local prediction pipeline at startup.")
    yield
    app.state.model = None


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
