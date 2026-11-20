import hashlib

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.data.feature_engineering import PREDICTOR_COLUMNS
from src.financial_exclusion.api import main
from src.models.load_model import MODEL_PATH, load_svm


@pytest.fixture
def record():
    return {
        "A18": 35,
        "Sex": "Female",
        "A20": '"Secondary completed "',
        "county": "Nairobi City",
        "A08": "Urban",
        "B3A__2": 1,
        "B3A__4": 0,
        "B3Ii": 10000,
        "ID_card": "No ID",
        "S1": "I own a mobile that only I use/Nina simu ambayo ni mimi tu ninaitumia",
        "S3": 'Daily/"Kila siku"',
        "A24i": "No- no difficulty",
        "A24ii": "No- no difficulty",
        "A24iii": "No- no difficulty",
        "A24iv": "No- no difficulty",
        "A24v": "No- no difficulty",
        "A24vi": "No- no difficulty",
    }


class RecordingModel:
    def __init__(self):
        self.frames = []

    def predict(self, frame):
        self.frames.append(frame.copy())
        return np.array([index % 2 for index in range(len(frame))])


@pytest.fixture
def client(monkeypatch):
    model = RecordingModel()
    loads = []
    monkeypatch.setattr(main, "load_svm", lambda path: loads.append(path) or model)
    with TestClient(main.app) as test_client:
        yield test_client, model, loads


def test_endpoints_load_once_and_predict_with_exact_features(client, record):
    test_client, model, loads = client
    assert test_client.get("/").status_code == 200
    assert test_client.get("/docs").status_code == 200
    assert test_client.get("/health").json() == {"status": "ready"}
    single = test_client.post("/predict", json=record)
    assert single.status_code == 200
    assert single.json() == {"financial_exclusion_status": 0, "label": "Financially included"}
    missing = {**record, "A20": "95", "county": None, "B3Ii": "#NULL!"}
    batch = test_client.post("/predict/batch", json={"records": [record, missing]})
    assert batch.status_code == 200
    assert batch.json() == {"predictions": [
        {"financial_exclusion_status": 0, "label": "Financially included"},
        {"financial_exclusion_status": 1, "label": "Financially excluded"},
    ]}
    assert len(loads) == 1
    assert list(model.frames[1].columns) == list(PREDICTOR_COLUMNS)
    assert model.frames[1].iloc[1]["A20"] == "95"
    assert model.frames[1].iloc[1]["B3Ii"] == "#NULL!"
    assert pd.isna(model.frames[1].iloc[1]["county"])


@pytest.mark.parametrize(
    "change",
    [
        {"A18": 17}, {"A18": 98}, {"A18": 99}, {"A18": True},
        {"B3A__2": True}, {"B3A__4": 1.0}, {"B3A__2": 2},
        {"B3Ii": -1}, {"B3Ii": "not income"}, {"county": " "},
        {"Sex": 1}, {"Overall_Access_fnl": "excluded"},
    ],
)
def test_rejects_invalid_input_without_echoing_it(client, record, change):
    test_client, model, _ = client
    result = test_client.post("/predict", json={**record, **change})
    assert result.status_code == 422
    assert result.json() == {"detail": "Invalid request; check the API schema at /docs."}
    assert not model.frames


def test_missing_fields_and_invalid_batches_are_rejected(client, record):
    test_client, model, _ = client
    del record["Sex"]
    assert test_client.post("/predict", json=record).status_code == 422
    assert test_client.post("/predict/batch", json={"records": []}).status_code == 422
    assert test_client.post("/predict/batch", json={"records": [record] * 101}).status_code == 422
    assert test_client.post("/predict/batch", json={"records": [], "extra": 1}).status_code == 422
    assert not model.frames


def test_load_failure_keeps_health_and_predictions_unavailable(monkeypatch, record):
    def broken_loader(path):
        raise FileNotFoundError("sensitive local path")

    monkeypatch.setattr(main, "load_svm", broken_loader)
    with TestClient(main.app) as client:
        assert client.get("/").status_code == 200
        for result in (client.get("/health"), client.post("/predict", json=record)):
            assert result.status_code == 503
            assert result.json() == {"detail": "Prediction service is unavailable."}


def test_prediction_failure_does_not_expose_input_or_model_details(client, record):
    test_client, model, _ = client

    def fail(frame):
        raise ValueError("sensitive model detail")

    model.predict = fail
    result = test_client.post("/predict", json=record)
    assert result.status_code == 500
    assert result.json() == {"detail": "Prediction failed."}


def test_invalid_model_output_is_not_returned(client, record):
    test_client, model, _ = client
    model.predict = lambda frame: np.array([7])
    assert test_client.post("/predict", json=record).status_code == 500


@pytest.mark.skipif(not MODEL_PATH.is_file(), reason="Local trusted SVM artifact is not present.")
def test_saved_svm_predicts_synthetic_requests_without_modifying_artifact(record):
    before = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
    model = load_svm(MODEL_PATH)
    second = {**record, "county": "Unseen synthetic county", "B3Ii": None, "A20": "95"}
    third = {name: None if name != "A18" else 35 for name in record}
    frame = pd.DataFrame([record, second, third], columns=PREDICTOR_COLUMNS).replace({None: np.nan})
    expected = [int(value) for value in model.predict(frame)]
    with TestClient(main.app) as client:
        assert client.get("/health").json() == {"status": "ready"}
        response = client.post("/predict/batch", json={"records": [record, second, third]})
    assert response.status_code == 200
    assert [item["financial_exclusion_status"] for item in response.json()["predictions"]] == expected
    assert hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest() == before
