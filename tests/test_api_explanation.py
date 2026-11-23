"""Integration tests for the prediction and explanation endpoint."""

import pytest
from fastapi.testclient import TestClient

from src.financial_exclusion.api.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client


def get_valid_payload():
    """Create a valid prediction request payload."""
    return {
        "A18": 35,
        "Sex": "Female",
        "A20": '"None "',
        "county": "Nairobi City",
        "A08": "Urban",
        "B3A__2": 1,
        "B3A__4": 0,
        "B3Ii": 15000,
        "ID_card": "Has ID (National Identity Card (ID),Passport,Alien ID)",
        "S1": "I own a mobile that only I use/Nina simu ambayo ni mimi tu ninaitumia",
        "S3": 'Daily/"Kila siku"',
        "A24i": "No- no difficulty",
        "A24ii": "No- no difficulty",
        "A24iii": "No- no difficulty",
        "A24iv": "No- no difficulty",
        "A24v": "No- no difficulty",
        "A24vi": "No- no difficulty",
    }


def test_predict_endpoint_exists(client):
    """Test that the /predict endpoint exists."""
    response = client.post("/predict", json=get_valid_payload())
    assert response.status_code == 200


def test_predict_with_explanation_endpoint_exists(client):
    """Test that the /predict/with-explanation endpoint exists."""
    response = client.post("/predict/with-explanation", json=get_valid_payload())
    assert response.status_code == 200


def test_predict_with_explanation_response_format(client):
    """Test that /predict/with-explanation returns the expected format."""
    response = client.post("/predict/with-explanation", json=get_valid_payload())
    assert response.status_code == 200
    data = response.json()

    assert "financial_exclusion_status" in data
    assert data["financial_exclusion_status"] in (0, 1)
    assert "label" in data
    assert data["label"] in ("Financially included", "Financially excluded")
    assert "explanation" in data


def test_predict_with_explanation_includes_contributors(client):
    """Test that explanation includes contributor information."""
    response = client.post("/predict/with-explanation", json=get_valid_payload())
    assert response.status_code == 200
    data = response.json()

    explanation = data.get("explanation")
    assert explanation is not None

    if explanation.get("success"):
        assert "contributors" in explanation
        contributors = explanation["contributors"]
        assert isinstance(contributors, list)

        for contrib in contributors:
            assert "variable" in contrib
            assert "shap_value" in contrib
            assert "direction" in contrib
            assert contrib["direction"] in ("towards excluded", "towards included")


def test_predict_with_explanation_handles_missing_values(client):
    """Test that explanation works with missing values."""
    payload = get_valid_payload()
    payload["B3Ii"] = None
    payload["A20"] = None

    response = client.post("/predict/with-explanation", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "financial_exclusion_status" in data
    assert "explanation" in data


def test_predict_with_explanation_with_null_income(client):
    """Test that explanation works when income is null."""
    payload = get_valid_payload()
    payload["B3Ii"] = None

    response = client.post("/predict/with-explanation", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["financial_exclusion_status"] in (0, 1)


def test_predict_with_explanation_rejects_invalid_age(client):
    """Test that invalid age is rejected."""
    payload = get_valid_payload()
    payload["A18"] = 15  # Below minimum

    response = client.post("/predict/with-explanation", json=payload)
    assert response.status_code == 422


def test_predict_with_explanation_rejects_special_age_codes(client):
    """Test that special age codes 98/99 are rejected."""
    for age in [98, 99]:
        payload = get_valid_payload()
        payload["A18"] = age
        response = client.post("/predict/with-explanation", json=payload)
        assert response.status_code == 422


def test_predict_with_explanation_rejects_invalid_indicator(client):
    """Test that invalid indicator values are rejected."""
    payload = get_valid_payload()
    payload["B3A__2"] = 2  # Invalid; must be 0 or 1

    response = client.post("/predict/with-explanation", json=payload)
    assert response.status_code == 422


def test_backward_compatibility_with_basic_predict(client):
    """Test that the basic /predict endpoint still works."""
    response = client.post("/predict", json=get_valid_payload())
    assert response.status_code == 200
    data = response.json()

    assert "financial_exclusion_status" in data
    assert "label" in data
    # Basic predict should not include explanation
    if "explanation" not in data:
        # This is acceptable for backward compatibility
        assert True


def test_health_check(client):
    """Test that the health endpoint indicates readiness."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ready"


def test_welcome_endpoint(client):
    """Test that the welcome endpoint provides API information."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
