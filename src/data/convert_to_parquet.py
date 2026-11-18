"""Stream the confirmed FinAccess respondent sheet into a selected Parquet file."""

from __future__ import annotations

import json
import logging
import math
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zipfile import BadZipFile
from xml.etree.ElementTree import ParseError

import pyarrow as pa
import pyarrow.parquet as pq
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from src.data.load_data import PARQUET_PATH, SELECTED_COLUMNS, validate_structure
from src.financial_exclusion.config import RAW_WORKBOOK_PATH

LOGGER = logging.getLogger(__name__)
SOURCE_SHEET = "2024_Finaccess_Publicdata"
BATCH_SIZE = 1_000
METADATA_KEY = b"finaccess_extraction"


def _arrow_type(types: set[type]) -> pa.DataType:
    if not types or types == {str}:
        return pa.string()
    if types == {bool}:
        return pa.bool_()
    if types == {int}:
        return pa.int64()
    if types <= {int, float}:
        return pa.float64()
    return pa.string()


def _output_value(value: Any, arrow_type: pa.DataType) -> Any:
    if value is None:
        return None
    if pa.types.is_string(arrow_type) and not isinstance(value, str):
        return str(value)
    if pa.types.is_floating(arrow_type) and isinstance(value, int):
        if int(float(value)) != value:
            raise ValueError(f"Integer {value} cannot be represented exactly as float64.")
    return value


def _write_batch(
    writer: pq.ParquetWriter,
    batch: list[list[Any]],
    schema: pa.Schema,
) -> None:
    arrays = [
        pa.array(
            [_output_value(row[index], schema.field(index).type) for row in batch],
            type=schema.field(index).type,
        )
        for index in range(len(SELECTED_COLUMNS))
    ]
    writer.write_table(pa.Table.from_arrays(arrays, schema=schema))


def _validate_written_file(
    path: Path, expected_rows: int, expected_metadata: dict[str, Any]
) -> None:
    parquet = pq.ParquetFile(path)
    validate_structure(parquet.schema_arrow, parquet.metadata.num_rows)
    if parquet.metadata.num_rows != expected_rows:
        raise ValueError(
            f"Parquet row count {parquet.metadata.num_rows} differs from "
            f"source row count {expected_rows}."
        )
    metadata = parquet.schema_arrow.metadata or {}
    if METADATA_KEY not in metadata or json.loads(metadata[METADATA_KEY]) != expected_metadata:
        raise ValueError("Parquet extraction metadata is missing or inconsistent.")
    read_rows = sum(batch.num_rows for batch in parquet.iter_batches(batch_size=BATCH_SIZE))
    if read_rows != expected_rows:
        raise ValueError(f"Parquet read-back returned {read_rows} rows, expected {expected_rows}.")


def convert_to_parquet(
    source: Path = RAW_WORKBOOK_PATH, destination: Path = PARQUET_PATH
) -> dict[str, Any]:
    """Extract selected columns, preserve every source row, and validate the output."""
    if not source.is_file():
        raise FileNotFoundError(f"Source workbook does not exist: {source}")
    if source.resolve() == destination.resolve():
        raise ValueError("The Parquet destination must not be the source workbook.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="finaccess-", dir=destination.parent) as temp_dir:
        temp_path = Path(temp_dir)
        spool = temp_path / "selected.jsonl"
        parquet_path = temp_path / "selected.parquet"
        workbook = load_workbook(source, read_only=True, data_only=False)
        try:
            if SOURCE_SHEET not in workbook.sheetnames:
                raise ValueError(f"Required respondent sheet not found: {SOURCE_SHEET}")
            sheet = workbook[SOURCE_SHEET]
            if sheet.max_row is None or sheet.max_column is None or sheet.max_row < 2:
                raise ValueError("Respondent sheet dimensions are missing or contain no records.")
            source_rows = sheet.max_row - 1
            source_columns = sheet.max_column
            rows = sheet.iter_rows(max_col=source_columns)
            header = [cell.value for cell in next(rows)]
            if any(not isinstance(name, str) or not name for name in header):
                raise ValueError("Respondent sheet contains a blank or invalid column header.")
            if len(set(header)) != len(header):
                raise ValueError("Respondent sheet contains duplicate column headers.")
            missing = [name for name in SELECTED_COLUMNS if name not in header]
            if missing:
                raise ValueError(f"Selected columns are missing from the source sheet: {missing}")
            indices = [header.index(name) for name in SELECTED_COLUMNS]
            observed_types: dict[str, set[type]] = {name: set() for name in SELECTED_COLUMNS}
            error_counts: Counter[str] = Counter()
            row_count = 0
            with spool.open("w", encoding="utf-8", newline="\n") as output:
                for source_row, row in enumerate(rows, start=2):
                    selected = []
                    for name, index in zip(SELECTED_COLUMNS, indices):
                        cell = row[index]
                        value = cell.value
                        if cell.data_type == "f":
                            raise ValueError(f"Formula in selected column {name}, row {source_row}.")
                        if cell.data_type == "e":
                            error_counts[name] += 1
                        if value is not None:
                            if type(value) not in (str, int, float, bool):
                                raise ValueError(
                                    f"Unsupported cell type {type(value).__name__} "
                                    f"in column {name}, row {source_row}."
                                )
                            if isinstance(value, float) and not math.isfinite(value):
                                raise ValueError(f"Non-finite number in column {name}, row {source_row}.")
                            observed_types[name].add(type(value))
                        selected.append(value)
                    output.write(json.dumps(selected, ensure_ascii=False, allow_nan=False) + "\n")
                    row_count += 1
                    if row_count % 5_000 == 0:
                        LOGGER.info("Read %s source records", row_count)
            if row_count != source_rows:
                raise ValueError(
                    f"Streamed {row_count} records but sheet dimensions report {source_rows}."
                )
        finally:
            workbook.close()

        types = {name: _arrow_type(observed_types[name]) for name in SELECTED_COLUMNS}
        mixed = [
            name for name in SELECTED_COLUMNS
            if len(observed_types[name]) > 1 and pa.types.is_string(types[name])
        ]
        metadata: dict[str, Any] = {
            "source_workbook": source.name,
            "source_sheet": SOURCE_SHEET,
            "source_reported_rows": source_rows,
            "source_columns": source_columns,
            "selected_columns": list(SELECTED_COLUMNS),
            "extracted_rows": row_count,
            "extracted_at_utc": datetime.now(timezone.utc).isoformat(),
            "mixed_columns_serialized_as_text": mixed,
            "excel_error_cell_counts": dict(error_counts),
            "row_filter": "none",
        }
        schema = pa.schema(
            [(name, types[name]) for name in SELECTED_COLUMNS],
            metadata={METADATA_KEY: json.dumps(metadata, ensure_ascii=False).encode("utf-8")},
        )
        validate_structure(schema, row_count)
        if mixed:
            LOGGER.warning("Mixed-type columns serialized as text: %s", ", ".join(mixed))
        if error_counts:
            LOGGER.warning("Excel error values preserved as text; counts by column: %s", dict(error_counts))

        with pq.ParquetWriter(parquet_path, schema, compression="snappy") as writer:
            batch: list[list[Any]] = []
            with spool.open(encoding="utf-8") as input_file:
                for line in input_file:
                    batch.append(json.loads(line))
                    if len(batch) == BATCH_SIZE:
                        _write_batch(writer, batch, schema)
                        batch.clear()
            if batch:
                _write_batch(writer, batch, schema)
        _validate_written_file(parquet_path, row_count, metadata)
        parquet_path.replace(destination)

    LOGGER.info(
        "Validated %s records and %s selected columns against %s source columns; output %s bytes",
        row_count, len(SELECTED_COLUMNS), source_columns, destination.stat().st_size,
    )
    return metadata


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        convert_to_parquet()
    except (OSError, ValueError, TypeError, KeyError, BadZipFile, EOFError,
            InvalidFileException, ParseError, pa.ArrowException):
        LOGGER.exception("FinAccess extraction failed; existing output was not replaced.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
