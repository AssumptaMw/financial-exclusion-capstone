"""Load the approved modeling dataset and validate its schema provenance."""

import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from src.data.feature_engineering import MODEL_METADATA_KEY, PREDICTOR_COLUMNS, TARGET_COLUMN


def load_modeling_data(path: Path) -> pd.DataFrame:
    """Load the approved model dataset and verify its provenance."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Modeling dataset does not exist: {path}")
    table = pq.read_table(path)
    metadata = table.schema.metadata or {}
    if MODEL_METADATA_KEY not in metadata:
        raise ValueError("Modeling dataset is missing predictor provenance metadata.")
    provenance = json.loads(metadata[MODEL_METADATA_KEY])
    if provenance.get("predictors") != list(PREDICTOR_COLUMNS):
        raise ValueError("Modeling dataset predictors do not match the approved feature list.")
    if provenance.get("target_column") != TARGET_COLUMN:
        raise ValueError("Modeling dataset target does not match the approved target.")
    return table.to_pandas()
