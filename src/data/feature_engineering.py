"""Construct the approved modeling dataset and binary outcome."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.data.prepare_data import PREPARED_PATH, PREPARATION_METADATA_KEY
from src.financial_exclusion.config import PROCESSED_DATA_DIR

LOGGER = logging.getLogger(__name__)

MODELING_DATASET_PATH = PROCESSED_DATA_DIR / "finaccess_modeling_dataset_6c.parquet"
MODEL_METADATA_KEY = b"finaccess_modeling"
TARGET_COLUMN = "financial_exclusion_status"
TARGET_SOURCE_COLUMN = "Overall_Access_fnl"
TRACEABILITY_COLUMNS = ("Access_fnl", "Overall_Access_fnl")
DESIGN_COLUMNS = ("indWeight", "A07")
REVIEW_COLUMNS = ("S2__1", "S4")

TARGET_MAPPING = {
    "formal only": 0,
    "informal only": 0,
    "excluded": 1,
}

PREDICTOR_COLUMNS = (
    "A18",
    "Sex",
    "A20",
    "county",
    "A08",
    "B3A__2",
    "B3A__4",
    "B3Ii",
    "ID_card",
    "S1",
    "S3",
    "A24i",
    "A24ii",
    "A24iii",
    "A24iv",
    "A24v",
    "A24vi",
)

MODELING_COLUMNS = (
    *PREDICTOR_COLUMNS,
    *REVIEW_COLUMNS,
    TARGET_COLUMN,
    *TRACEABILITY_COLUMNS,
    *DESIGN_COLUMNS,
)

if set(PREDICTOR_COLUMNS) & (
    set(TRACEABILITY_COLUMNS) | set(DESIGN_COLUMNS) | set(REVIEW_COLUMNS)
    | {TARGET_COLUMN}
):
    raise RuntimeError("Predictor columns overlap target or survey metadata fields.")


def build_modeling_dataset(adult_data: pd.DataFrame) -> pd.DataFrame:
    """Map verified overall-access labels and select approved non-leakage fields."""
    required = set(MODELING_COLUMNS) - {TARGET_COLUMN}
    missing = sorted(required - set(adult_data.columns))
    if missing:
        raise ValueError(f"Adult dataset is missing required columns: {missing}")

    labels = adult_data[TARGET_SOURCE_COLUMN]
    mapped = labels.map(TARGET_MAPPING)
    unresolved_mask = mapped.isna()
    if unresolved_mask.any():
        unresolved = Counter(
            repr(value) for value in labels.loc[unresolved_mask].tolist()
        )
        raise ValueError(
            "Unrecognized or missing Overall_Access_fnl categories; "
            f"target was not constructed: {dict(unresolved)}"
        )

    modeling_data = adult_data.loc[:, (*PREDICTOR_COLUMNS, *REVIEW_COLUMNS)].copy()
    modeling_data[TARGET_COLUMN] = mapped.astype("int8")
    for column in (*TRACEABILITY_COLUMNS, *DESIGN_COLUMNS):
        modeling_data[column] = adult_data[column].copy()
    return modeling_data.loc[:, MODELING_COLUMNS]


def create_modeling_dataset(
    source: Path = PREPARED_PATH,
    destination: Path = MODELING_DATASET_PATH,
) -> dict[str, Any]:
    """Build and atomically write a modeling dataset from the adult-only file."""
    source = Path(source)
    destination = Path(destination)
    if not source.is_file():
        raise FileNotFoundError(f"Adult-only Parquet dataset does not exist: {source}")
    if source.resolve() == destination.resolve():
        raise ValueError("The modeling destination must not replace the adult-only source.")

    source_table = pq.read_table(source)
    source_metadata = source_table.schema.metadata or {}
    if PREPARATION_METADATA_KEY not in source_metadata:
        raise ValueError("Adult-only Parquet is missing preparation provenance metadata.")
    preparation = json.loads(source_metadata[PREPARATION_METADATA_KEY])
    if preparation.get("target_constructed") is not False:
        raise ValueError("Adult-only source is expected to contain no constructed target.")

    modeling_data = build_modeling_dataset(source_table.to_pandas())
    target_counts = modeling_data[TARGET_COLUMN].value_counts().sort_index()
    metadata: dict[str, Any] = {
        "source_file": source.name,
        "source_rows": source_table.num_rows,
        "modeling_rows": len(modeling_data),
        "predictors": list(PREDICTOR_COLUMNS),
        "target_column": TARGET_COLUMN,
        "target_source": TARGET_SOURCE_COLUMN,
        "target_mapping": TARGET_MAPPING,
        "target_counts": {
            "0_financially_included": int(target_counts.get(0, 0)),
            "1_financially_excluded": int(target_counts.get(1, 0)),
        },
        "traceability_columns": list(TRACEABILITY_COLUMNS),
        "excluded_review_columns": list(REVIEW_COLUMNS),
        "survey_design_columns_not_predictors": list(DESIGN_COLUMNS),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider_classification_method_independently_verified": False,
        "preprocessing_fitted": False,
    }

    destination.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(modeling_data, preserve_index=False)
    table_metadata = dict(source_metadata)
    table_metadata[MODEL_METADATA_KEY] = json.dumps(
        metadata, ensure_ascii=False
    ).encode("utf-8")
    table = table.replace_schema_metadata(table_metadata)

    with tempfile.TemporaryDirectory(
        prefix="finaccess-modeling-", dir=destination.parent
    ) as temporary_directory:
        temporary_path = Path(temporary_directory) / destination.name
        pq.write_table(table, temporary_path, compression="snappy")
        written_file = pq.ParquetFile(temporary_path)
        try:
            written = written_file.read()
        finally:
            written_file.close()
        if written.column_names != list(MODELING_COLUMNS):
            raise ValueError("Modeling Parquet columns do not match the approved schema.")
        if written.num_rows != source_table.num_rows:
            raise ValueError("Modeling Parquet row count differs from the adult source.")
        if not written.equals(table, check_metadata=True):
            raise ValueError("Modeling Parquet values or metadata failed validation.")
        os.replace(temporary_path, destination)

    LOGGER.info(
        "Created modeling dataset with %s rows, %s predictors, and class counts %s",
        len(modeling_data),
        len(PREDICTOR_COLUMNS),
        metadata["target_counts"],
    )
    LOGGER.info("Modeling dataset: %s (%s bytes)", destination, destination.stat().st_size)
    return metadata


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        create_modeling_dataset()
    except (OSError, ValueError, TypeError, KeyError, pa.ArrowException):
        LOGGER.exception("FinAccess modeling dataset creation failed.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
