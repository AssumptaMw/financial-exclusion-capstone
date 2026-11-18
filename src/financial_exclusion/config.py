"""Shared project paths and reproducibility settings."""

from pathlib import Path

PROJECT_NAME = "An Explainable Machine Learning Framework for Predicting Financial Exclusion in Kenya"
RANDOM_SEED = 42

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
DOCUMENTATION_DIR = PROJECT_ROOT / "documentation"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
REPORTS_DIR = PROJECT_ROOT / "reports"

RAW_WORKBOOK_PATH = RAW_DATA_DIR / "2024_Finaccess_Publicdata.xlsx"
