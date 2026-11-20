import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.data.convert_to_parquet import METADATA_KEY
from src.data.load_data import SELECTED_COLUMNS
from src.data.prepare_data import (
    PREPARATION_METADATA_KEY,
    REPORT_GENERATED_END,
    REPORT_GENERATED_START,
    prepare_data,
)


def write_interim(path, ages=(17, 18, 98, 99, 100, None), *, metadata=True) -> None:
    count = len(ages)
    values = {
        "county": ["Nairobi City"] * count,
        "A07": [1] * count,
        "A08": ["Urban"] * count,
        "A18": list(ages),
        "Sex": ["Female"] * count,
        "A20": ["Completed secondary"] * count,
        "A24i": ["No- no difficulty"] * count,
        "A24ii": ["No- no difficulty"] * count,
        "A24iii": ["No- no difficulty"] * count,
        "A24iv": ["No- no difficulty"] * count,
        "A24v": ["No- no difficulty"] * count,
        "A24vi": ["No- no difficulty"] * count,
        "B3A__2": [0] * count,
        "B3A__4": [1] * count,
        "B3Ii": ["1000"] * count,
        "S1": ["I own a mobile"] * count,
        "S2__1": ["1"] * count,
        "S3": ["Never/Situmii\""] * count,
        "S4": ["#NULL!"] * count,
        "indWeight": [1.5] * count,
        "ID_card": ["Has ID"] * count,
        "Access_fnl": ["Excluded"] * count,
        "Overall_Access_fnl": ["excluded"] * count,
    }
    schema = pa.schema(
        [
            ("county", pa.string()),
            ("A07", pa.int64()),
            ("A08", pa.string()),
            ("A18", pa.int64()),
            ("Sex", pa.string()),
            ("A20", pa.string()),
            ("A24i", pa.string()),
            ("A24ii", pa.string()),
            ("A24iii", pa.string()),
            ("A24iv", pa.string()),
            ("A24v", pa.string()),
            ("A24vi", pa.string()),
            ("B3A__2", pa.int64()),
            ("B3A__4", pa.int64()),
            ("B3Ii", pa.string()),
            ("S1", pa.string()),
            ("S2__1", pa.string()),
            ("S3", pa.string()),
            ("S4", pa.string()),
            ("indWeight", pa.float64()),
            ("ID_card", pa.string()),
            ("Access_fnl", pa.string()),
            ("Overall_Access_fnl", pa.string()),
        ]
    )
    assert schema.names == list(SELECTED_COLUMNS)
    if metadata:
        extraction = {
            "source_reported_rows": count,
            "extracted_rows": count,
            "row_filter": "none",
        }
        schema = schema.with_metadata(
            {METADATA_KEY: json.dumps(extraction).encode("utf-8")}
        )
    table = pa.Table.from_pydict(values, schema=schema)
    pq.write_table(table, path)


def test_prepare_filters_only_ineligible_ages_and_preserves_source_values(tmp_path):
    source = tmp_path / "interim.parquet"
    destination = tmp_path / "adults.parquet"
    report = tmp_path / "data_cleaning_report.md"
    write_interim(source)
    original_bytes = source.read_bytes()

    metadata = prepare_data(source, destination, report)
    prepared = pq.read_table(destination)
    preparation_metadata = json.loads(
        prepared.schema.metadata[PREPARATION_METADATA_KEY]
    )

    assert prepared["A18"].to_pylist() == [18, 100]
    assert prepared["Access_fnl"].to_pylist() == ["Excluded", "Excluded"]
    assert prepared["Overall_Access_fnl"].to_pylist() == ["excluded", "excluded"]
    assert prepared["S4"].to_pylist() == ["#NULL!", "#NULL!"]
    assert prepared["indWeight"].to_pylist() == [1.5, 1.5]
    assert metadata["source_rows"] == 6
    assert metadata["retained_adults"] == 2
    assert metadata["excluded_under_18"] == 1
    assert metadata["age_code_98"] == 1
    assert metadata["age_code_99"] == 1
    assert metadata["missing_age"] == 1
    assert metadata["invalid_age"] == 0
    assert preparation_metadata == metadata
    assert source.read_bytes() == original_bytes
    assert "No predictor matrix" in report.read_text(encoding="utf-8")
    assert "No global recoding" in report.read_text(encoding="utf-8")


def test_prepare_rejects_unverified_interim_and_does_not_publish(tmp_path):
    source = tmp_path / "interim.parquet"
    destination = tmp_path / "adults.parquet"
    report = tmp_path / "data_cleaning_report.md"
    write_interim(source, metadata=False)
    destination.write_bytes(b"existing output")

    with pytest.raises(ValueError, match="missing extraction provenance"):
        prepare_data(source, destination, report)

    assert destination.read_bytes() == b"existing output"
    assert not report.exists()


def test_prepare_refreshes_generated_report_without_overwriting_investigation(tmp_path):
    source = tmp_path / "interim.parquet"
    destination = tmp_path / "adults.parquet"
    report = tmp_path / "data_cleaning_report.md"
    write_interim(source)
    prepare_data(source, destination, report)
    manual = "\r\n## Investigation findings\r\n\r\nEvidence remains: café.\r\n"
    prefix = "Manual introduction.\r\n\r\n"
    report.write_bytes(
        (prefix + report.read_bytes().decode("utf-8") + manual).encode("utf-8")
    )
    write_interim(source, ages=(18, 19, 20))

    prepare_data(source, destination, report)

    updated = report.read_bytes().decode("utf-8")
    assert updated.startswith(prefix)
    assert updated.endswith(manual)
    assert "Input records: 3" in updated
    assert "Input records: 6" not in updated
    assert updated.count("## Investigation findings") == 1
    assert updated.count(REPORT_GENERATED_START) == 1
    assert updated.count(REPORT_GENERATED_END) == 1


@pytest.mark.parametrize(
    "content",
    [
        "# Existing report\n\n## Investigation\nPreserve me.\n",
        f"{REPORT_GENERATED_START}\n## Findings\n",
        f"{REPORT_GENERATED_END}\n{REPORT_GENERATED_START}\n",
        f"{REPORT_GENERATED_START}\n{REPORT_GENERATED_START}\n{REPORT_GENERATED_END}\n",
    ],
)
def test_prepare_rejects_invalid_report_without_modifying_outputs(tmp_path, content):
    source = tmp_path / "interim.parquet"
    destination = tmp_path / "adults.parquet"
    report = tmp_path / "data_cleaning_report.md"
    write_interim(source)
    destination.write_bytes(b"existing dataset")
    report.write_text(content, encoding="utf-8")
    original_report = report.read_bytes()

    with pytest.raises(ValueError, match="generated section markers"):
        prepare_data(source, destination, report)

    assert report.read_bytes() == original_report
    assert destination.read_bytes() == b"existing dataset"
