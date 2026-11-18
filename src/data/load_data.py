"""Load and validate the selected, unmodified FinAccess survey responses."""

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from src.financial_exclusion.config import INTERIM_DATA_DIR

PARQUET_PATH = INTERIM_DATA_DIR / "finaccess_selected.parquet"

# Outcome and design fields are retained for later analysis, not as predictors.
SELECTED_COLUMNS = (
    "county",
    "A07",
    "A08",
    "A18",
    "Sex",
    "A20",
    "A24i",
    "A24ii",
    "A24iii",
    "A24iv",
    "A24v",
    "A24vi",
    "B3A__2",
    "B3A__4",
    "B3Ii",
    "S1",
    "S2__1",
    "S3",
    "S4",
    "indWeight",
    "ID_card",
    "Access_fnl",
    "Overall_Access_fnl",
)


def validate_structure(schema: pa.Schema, row_count: int) -> None:
    """Reject missing, extra, duplicate, reordered, or empty respondent data."""
    actual = schema.names
    expected = list(SELECTED_COLUMNS)
    if actual != expected:
        raise ValueError(f"Unexpected columns: expected {expected}, found {actual}")
    if row_count <= 0:
        raise ValueError("The selected dataset contains no respondent records.")


def load_selected_data(path: Path = PARQUET_PATH) -> pa.Table:
    """Read the selected Parquet dataset and validate its columns and row count."""
    if not path.is_file():
        raise FileNotFoundError(f"Selected Parquet dataset does not exist: {path}")
    table = pq.read_table(path)
    validate_structure(table.schema, table.num_rows)
    return table
