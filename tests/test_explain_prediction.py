"""Tests for the SHAP explanation endpoint and local explainer."""

import pandas as pd
import pytest
from pathlib import Path

from src.models.explain_prediction import LocalSHAPExplainer, explain_prediction, FEATURE_LABELS
from src.data.feature_engineering import PREDICTOR_COLUMNS


@pytest.fixture(scope="module")
def explainer():
    """Create a LocalSHAPExplainer instance."""
    try:
        return LocalSHAPExplainer()
    except Exception as e:
        pytest.skip(f"Could not initialize explainer: {e}")


def test_shap_explainer_initialization(explainer):
    """Test that LocalSHAPExplainer initializes correctly."""
    assert explainer is not None
    assert explainer.model is not None
    assert explainer.background is not None
    assert len(explainer.background) == 24


def test_shap_explainer_with_valid_record(explainer):
    """Test SHAP explanation with a valid record."""
    # Create a valid record with all predictors
    record = pd.DataFrame({col: [None] for col in PREDICTOR_COLUMNS})
    record['A18'] = 35
    record['Sex'] = 'Female'
    record['A20'] = '"None "'
    record['county'] = 'Nairobi City'
    record['A08'] = 'Urban'
    record['B3A__2'] = 1
    record['B3A__4'] = 0
    record['B3Ii'] = 15000
    record['ID_card'] = 'Has ID (National Identity Card (ID),Passport,Alien ID)'
    record['S1'] = 'I own a mobile that only I use/Nina simu ambayo ni mimi tu ninaitumia'
    record['S3'] = 'Daily/"Kila siku"'
    record['A24i'] = 'No- no difficulty'
    record['A24ii'] = 'No- no difficulty'
    record['A24iii'] = 'No- no difficulty'
    record['A24iv'] = 'No- no difficulty'
    record['A24v'] = 'No- no difficulty'
    record['A24vi'] = 'No- no difficulty'

    shap_values = explainer.explain(record)

    assert isinstance(shap_values, dict)
    assert len(shap_values) == len(PREDICTOR_COLUMNS)
    for var in PREDICTOR_COLUMNS:
        assert var in shap_values
        assert isinstance(shap_values[var], float)


def test_shap_explainer_rejects_invalid_input(explainer):
    """Test that LocalSHAPExplainer rejects invalid input."""
    # Too many rows
    record = pd.DataFrame({col: [None, None] for col in PREDICTOR_COLUMNS})
    with pytest.raises(ValueError, match="Expected a single record"):
        explainer.explain(record)

    # Wrong columns
    record = pd.DataFrame({'wrongcol': [1]})
    with pytest.raises(ValueError, match="Record columns must be"):
        explainer.explain(record)


def test_shap_explainer_values_are_bounded(explainer):
    """Test that SHAP values are reasonable magnitude (not NaN or inf)."""
    record = pd.DataFrame({col: [None] for col in PREDICTOR_COLUMNS})
    record['A18'] = 25
    record['Sex'] = 'Male'
    record['A20'] = '"University completed "'
    record['county'] = 'Mombasa'
    record['A08'] = 'Rural'
    record['B3A__2'] = 0
    record['B3A__4'] = 1
    record['B3Ii'] = 25000
    record['ID_card'] = 'No ID'
    record['S1'] = "I don't own a mobile phone but am able to use someone else's phone regularly"
    record['S3'] = 'Weekly/Kila wiki"'
    record['A24i'] = 'Yes - some difficulty'
    record['A24ii'] = 'Yes - some difficulty'
    record['A24iii'] = 'Yes - some difficulty'
    record['A24iv'] = 'Yes - some difficulty'
    record['A24v'] = 'Yes - some difficulty'
    record['A24vi'] = 'Yes - some difficulty'

    shap_values = explainer.explain(record)

    for var, value in shap_values.items():
        assert -100 < value < 100, f"SHAP value for {var} out of reasonable range: {value}"
        assert not pd.isna(value), f"SHAP value for {var} is NaN"


def test_explain_prediction_success(explainer):
    """Test explain_prediction returns valid explanation."""
    record = pd.DataFrame({col: [None] for col in PREDICTOR_COLUMNS})
    record['A18'] = 45
    record['Sex'] = 'Female'
    record['A20'] = '"Secondary completed "'
    record['county'] = 'Kisumu'
    record['A08'] = 'Urban'
    record['B3A__2'] = 1
    record['B3A__4'] = 1
    record['B3Ii'] = 20000
    record['ID_card'] = 'Has ID (National Identity Card (ID),Passport,Alien ID)'
    record['S1'] = 'I own a mobile phone that both me and others use/Nina simu ya mkononi ambayo mim'
    record['S3'] = 'Daily/"Kila siku"'
    record['A24i'] = 'No- no difficulty'
    record['A24ii'] = 'No- no difficulty'
    record['A24iii'] = 'No- no difficulty'
    record['A24iv'] = 'No- no difficulty'
    record['A24v'] = 'No- no difficulty'
    record['A24vi'] = 'No- no difficulty'

    result = explain_prediction(record, explainer)

    assert result['success'] is True
    assert isinstance(result['margin'], (int, float))
    assert result['shap_values'] is not None
    assert isinstance(result['shap_values'], dict)
    assert result['top_contributors'] is not None
    assert isinstance(result['top_contributors'], list)
    assert len(result['top_contributors']) <= 5
    for contrib in result['top_contributors']:
        assert 'variable' in contrib
        assert 'label' in contrib
        assert 'shap_value' in contrib
        assert 'direction' in contrib
        assert contrib['direction'] in ('towards excluded', 'towards included')


def test_feature_labels_coverage():
    """Test that all predictors have feature labels."""
    for var in PREDICTOR_COLUMNS:
        assert var in FEATURE_LABELS, f"No feature label for {var}"
        assert isinstance(FEATURE_LABELS[var], str)
        assert len(FEATURE_LABELS[var]) > 0
