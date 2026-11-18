import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from openpyxl import Workbook

from src.data.convert_to_parquet import (
    METADATA_KEY,
    SOURCE_SHEET,
    _output_value,
    convert_to_parquet,
)
from src.data.load_data import SELECTED_COLUMNS, load_selected_data


def make_workbook(path, *, missing=None, duplicate=False, formula=False) -> None:
    workbook = Workbook()
    workbook.active.title = "Other sheet"
    sheet = workbook.create_sheet(SOURCE_SHEET)
    headers = [name for name in SELECTED_COLUMNS if name != missing]
    headers.insert(1, "unselected")
    if duplicate:
        headers.append(SELECTED_COLUMNS[0])
    sheet.append(headers)
    values = {name: "label" for name in SELECTED_COLUMNS}
    values.update(
        A07=12,
        A18=17,
        B3Ii=100,
        S2__1=1,
        indWeight=2.5,
        Access_fnl="Excluded",
        Overall_Access_fnl="excluded",
    )
    if formula:
        values["A18"] = "=1+1"
    sheet.append([values.get(name, "not selected") for name in headers])
    values.update(A18=34, B3Ii="#NULL!", S2__1="#NULL!", Access_fnl="Informal")
    sheet.append([values.get(name, "not selected") for name in headers])
    workbook.save(path)
    workbook.close()


def test_conversion_streams_selected_columns_preserving_rows_and_values(tmp_path) -> None:
    source = tmp_path / "source.xlsx"
    output = tmp_path / "selected.parquet"
    make_workbook(source)

    metadata = convert_to_parquet(source, output)
    table = load_selected_data(output)

    assert table.column_names == list(SELECTED_COLUMNS)
    assert table.num_rows == 2
    assert table["A18"].to_pylist() == [17, 34]
    assert table["B3Ii"].to_pylist() == ["100", "#NULL!"]
    assert table["S2__1"].to_pylist() == ["1", "#NULL!"]
    assert table["indWeight"].to_pylist() == [2.5, 2.5]
    assert table["Access_fnl"].to_pylist() == ["Excluded", "Informal"]
    assert metadata["source_reported_rows"] == metadata["extracted_rows"] == 2
    assert metadata["source_columns"] == len(SELECTED_COLUMNS) + 1
    assert metadata["selected_columns"] == list(SELECTED_COLUMNS)
    assert metadata["row_filter"] == "none"
    assert metadata["excel_error_cell_counts"] == {"B3Ii": 1, "S2__1": 1}
    assert set(metadata["mixed_columns_serialized_as_text"]) == {"B3Ii", "S2__1"}
    assert json.loads(table.schema.metadata[METADATA_KEY]) == metadata
    assert not list(tmp_path.glob("finaccess-*"))


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"missing": "A18"}, "missing from the source"),
        ({"duplicate": True}, "duplicate column headers"),
        ({"formula": True}, "Formula in selected column"),
    ],
)
def test_invalid_workbook_does_not_replace_existing_output(tmp_path, options, message) -> None:
    source = tmp_path / "source.xlsx"
    output = tmp_path / "selected.parquet"
    make_workbook(source, **options)
    output.write_bytes(b"existing")

    with pytest.raises(ValueError, match=message):
        convert_to_parquet(source, output)

    assert output.read_bytes() == b"existing"
    assert not list(tmp_path.glob("finaccess-*"))


def test_missing_source_and_source_destination_collision(tmp_path) -> None:
    source = tmp_path / "source.xlsx"
    with pytest.raises(FileNotFoundError, match="Source workbook"):
        convert_to_parquet(source, tmp_path / "selected.parquet")
    make_workbook(source)
    original = source.read_bytes()
    with pytest.raises(ValueError, match="must not be the source"):
        convert_to_parquet(source, source)
    assert source.read_bytes() == original


def test_loader_rejects_missing_and_invalid_parquet(tmp_path) -> None:
    path = tmp_path / "selected.parquet"
    with pytest.raises(FileNotFoundError, match="does not exist"):
        load_selected_data(path)
    pq.write_table(pa.table({"unexpected": [1]}), path)
    with pytest.raises(ValueError, match="Unexpected columns"):
        load_selected_data(path)


def test_late_mixed_value_and_batch_boundary_are_preserved(tmp_path) -> None:
    source = tmp_path / "source.xlsx"
    output = tmp_path / "selected.parquet"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = SOURCE_SHEET
    sheet.append(list(SELECTED_COLUMNS))
    for row_number in range(1_001):
        sheet.append([
            "#NULL!" if name == "B3Ii" and row_number == 1_000 else row_number
            for name in SELECTED_COLUMNS
        ])
    workbook.save(source)
    workbook.close()

    metadata = convert_to_parquet(source, output)
    table = load_selected_data(output)

    assert table.num_rows == 1_001
    assert table["B3Ii"].slice(999).to_pylist() == ["999", "#NULL!"]
    assert table["A18"].slice(999).to_pylist() == [999, 1_000]
    assert metadata["excel_error_cell_counts"] == {"B3Ii": 1}


def test_unrepresentable_integer_is_not_silently_rounded() -> None:
    with pytest.raises(ValueError, match="cannot be represented exactly"):
        _output_value(2**53 + 1, pa.float64())
