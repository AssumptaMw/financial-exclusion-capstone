"""Prepare an adult-only response file without recoding survey responses."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from src.data.convert_to_parquet import METADATA_KEY as EXTRACTION_METADATA_KEY
from src.data.load_data import PARQUET_PATH, SELECTED_COLUMNS, validate_structure
from src.financial_exclusion.config import PROCESSED_DATA_DIR, REPORTS_DIR

LOGGER = logging.getLogger(__name__)
PREPARED_PATH = PROCESSED_DATA_DIR / "finaccess_adults_unprepared.parquet"
REPORT_PATH = REPORTS_DIR / "results" / "data_cleaning_report.md"
PREPARATION_METADATA_KEY = b"finaccess_preparation"
AGE_COLUMN = "A18"
AGE_SPECIAL_CODES = {98: "Don't know", 99: "Refused"}
BATCH_SIZE = 1_000
EXCEL_ERROR_PREFIX = "#"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _age_disposition(age: Any) -> str:
    if age is None:
        return "missing"
    if isinstance(age, bool) or not isinstance(age, int) or age < 0:
        return "invalid"
    if age in AGE_SPECIAL_CODES:
        return "special"
    if age < 18:
        return "under_18"
    return "adult"


def _profile(path: Path) -> dict[str, Any]:
    parquet = pq.ParquetFile(path)
    row_count = parquet.metadata.num_rows
    counts: dict[str, Counter[Any]] = {
        name: Counter() for name in parquet.schema_arrow.names
    }
    try:
        for batch in parquet.iter_batches(batch_size=BATCH_SIZE):
            for name in batch.schema.names:
                counts[name].update(batch.column(name).to_pylist())

        fields: dict[str, Any] = {}
        for field in parquet.schema_arrow:
            value_counts = counts[field.name]
            errors = {
                value: count
                for value, count in value_counts.items()
                if isinstance(value, str) and value.startswith(EXCEL_ERROR_PREFIX)
            }
            fields[field.name] = {
                "type": str(field.type),
                "nulls": value_counts.get(None, 0),
                "unique": len(value_counts) - (1 if None in value_counts else 0),
                "counts": value_counts,
                "errors": errors,
            }
        return {"rows": row_count, "fields": fields}
    finally:
        parquet.close()


def _format_value(value: Any) -> str:
    if value is None:
        return "Parquet null"
    text = str(value).replace("\n", " ").replace("|", "\\|")
    if len(text) > 110:
        text = text[:107] + "..."
    return f"`{text}`"


def _value_summary(profile: dict[str, Any], name: str) -> str:
    field = profile["fields"][name]
    counts: Counter[Any] = field["counts"]
    distinct = field["unique"]

    if distinct == 0:
        return "No non-null values"
    if distinct <= 14:
        return "; ".join(
            f"{_format_value(value)}: {count:,}"
            for value, count in counts.most_common()
        )

    top = "; ".join(
        f"{_format_value(value)}: {count:,}"
        for value, count in counts.most_common(5)
    )
    numeric_values: list[float] = []
    if field["type"].startswith(("int", "uint", "float", "double")) or name == "B3Ii":
        for value in counts:
            if value is None or (isinstance(value, str) and value.startswith("#")):
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(numeric):
                numeric_values.append(numeric)
    numeric_summary = ""
    if numeric_values:
        numeric_summary = (
            f"; numeric range {min(numeric_values):g}–{max(numeric_values):g}"
        )
    if name == "B3Ii":
        numeric_summary += (
            f"; workbook special-value labels 98: {counts.get('98', 0):,}, "
            f"99: {counts.get('99', 0):,}"
        )
    return f"{distinct:,} distinct values{numeric_summary}; most frequent: {top}"


def _error_total(profile: dict[str, Any], name: str) -> int:
    return sum(profile["fields"][name]["errors"].values())


def _cross_tab(
    profile_path: Path, left_name: str, right_name: str
) -> Counter[tuple[Any, Any]]:
    counts: Counter[tuple[Any, Any]] = Counter()
    parquet = pq.ParquetFile(profile_path)
    try:
        for batch in parquet.iter_batches(
            columns=[left_name, right_name], batch_size=BATCH_SIZE
        ):
            left_values = batch.column(0).to_pylist()
            right_values = batch.column(1).to_pylist()
            counts.update(zip(left_values, right_values))
    finally:
        parquet.close()
    return counts


def _render_report(
    *,
    source: Path,
    destination: Path,
    source_profile: dict[str, Any],
    prepared_profile: dict[str, Any],
    metadata: dict[str, Any],
    source_sha256: str,
) -> str:
    adult_count = metadata["retained_adults"]
    lines = [
        "# FinAccess data cleaning and preparation report",
        "",
        f"Generated (UTC): {metadata['prepared_at_utc']}",
        "",
        "## Scope and input",
        "",
        f"- Input: `{source.as_posix()}`",
        f"- Output: `{destination.as_posix()}`",
        f"- Input records: {source_profile['rows']:,}",
        f"- Prepared records: {adult_count:,}",
        f"- Selected columns retained, in source order: {len(SELECTED_COLUMNS)}",
        f"- Input SHA-256: `{source_sha256}`",
        "- The source interim Parquet was read-only; no source values or labels were rewritten.",
        "",
        "## Row eligibility and counts",
        "",
        "| A18 disposition | Records | Handling |",
        "|---|---:|---|",
        f"| Adult age (18+, excluding documented special codes) | {adult_count:,} | Retained |",
        f"| Under 18 | {metadata['excluded_under_18']:,} | Excluded from this adult-only file |",
        f"| A18 = 98 (Don't know) | {metadata['age_code_98']:,} | Excluded; age eligibility is unresolved |",
        f"| A18 = 99 (Refused) | {metadata['age_code_99']:,} | Excluded; age eligibility is unresolved |",
        f"| Missing A18 | {metadata['missing_age']:,} | Excluded if present; no value was imputed |",
        f"| Invalid A18 | {metadata['invalid_age']:,} | Excluded if present; no value was imputed |",
        "",
        "Age codes 98 and 99 are treated as special responses based on the verified "
        "questionnaire coding recorded in `documentation/data_dictionary.md`. "
        "Only these field-specific codes are treated specially; values 96 and 97 "
        "were not recoded, and no maximum age was imposed. Respondents aged 100 "
        "or older were retained when their recorded age met the rule.",
        "",
        "## Field-level value and missingness audit",
        "",
        "Parquet nulls are counted separately from preserved Excel error strings "
        "such as `#NULL!`. Text responses such as Refused and Don't know are "
        "reported as observed categories, not silently mapped to null. The value "
        "summary describes the adult-only output; Excel error counts show "
        "input → output, to make any age-filter effect visible.",
        "",
        "| Original field | Parquet type | Adult distinct values | Parquet nulls (input → adult) | Excel error tokens (input → adult) | Adult observed values / summary |",
        "|---|---|---:|---:|---:|---|",
    ]
    for name in SELECTED_COLUMNS:
        input_field = source_profile["fields"][name]
        output_field = prepared_profile["fields"][name]
        input_errors = _error_total(source_profile, name)
        output_errors = _error_total(prepared_profile, name)
        lines.append(
            f"| `{name}` | `{input_field['type']}` | {output_field['unique']:,} "
            f"| {input_field['nulls']:,} → {output_field['nulls']:,} "
            f"| {input_errors:,} → {output_errors:,} "
            f"| {_value_summary(prepared_profile, name)} |"
        )

    s1_s2 = _cross_tab(source, "S1", "S2__1")
    s3_s4 = _cross_tab(source, "S3", "S4")
    s3_counts = source_profile["fields"]["S3"]["counts"]
    s4_counts = source_profile["fields"]["S4"]["counts"]
    never_values = [
        value for value in s3_counts
        if isinstance(value, str) and value.startswith("Never/")
    ]
    never_rows = sum(s3_counts[value] for value in never_values)
    never_s4_errors = sum(
        count
        for (s3_value, s4_value), count in s3_s4.items()
        if s3_value in never_values
        and isinstance(s4_value, str)
        and s4_value.startswith(EXCEL_ERROR_PREFIX)
    )
    never_s4_nonerrors = never_rows - never_s4_errors
    s4_errors_non_never = sum(
        count
        for (s3_value, s4_value), count in s3_s4.items()
        if s3_value not in never_values
        and isinstance(s4_value, str)
        and s4_value.startswith(EXCEL_ERROR_PREFIX)
    )
    s2_errors_by_s1 = {
        s1_value: count
        for (s1_value, s2_value), count in s1_s2.items()
        if isinstance(s2_value, str) and s2_value.startswith(EXCEL_ERROR_PREFIX)
    }
    a20_source_95 = source_profile["fields"]["A20"]["counts"].get("95", 0)
    a20_adult_95 = prepared_profile["fields"]["A20"]["counts"].get("95", 0)
    lines.extend(
        [
            "",
            "## Special responses, Excel errors, and skip-pattern review",
            "",
            "- No global recoding of 96, 97, 98, or 99 was applied. Special-code "
            "interpretation is field-specific and only used for `A18` eligibility.",
            "- Aside from excluding records without an eligible `A18` as "
            "documented above, no Parquet nulls or Excel error tokens were "
            "imputed, normalized, or dropped. Errors remain text and are "
            "counted per field above.",
            f"- `A20` contains labeled Don't know and Refused responses as text, "
            f"plus {a20_adult_95:,} adult `95` value(s) without a verified "
            f"meaning ({a20_source_95:,} in the full extract); retained values "
            "were not changed.",
            "- The `A24i`–`A24vi` workbook value labels document codes 98/99 as "
            "Don't know/Refused. The extracted responses contain substantive "
            "text labels and the reported Excel errors; no such codes were "
            "recoded. Refer to the field-level counts above.",
            "- `B3Ii` is stored as text because the extraction found mixed cell "
            "types. Numeric-looking strings remain strings, `#NULL!` remains an "
            "Excel error token, and no income value or sentinel was imputed. "
            "The workbook documents 98/99 as special responses; no global "
            "numeric-string replacement was made.",
            "- `S1`, `S3`, and `S4` preserve the workbook's text response labels, "
            "including their explicit Refused labels. `S2__1` preserves observed "
            "`0`/`1` strings and `#NULL!`; its value-label mapping was not "
            "confirmed in the workbook inventory.",
            "- The source workbook and extracted text for some `S1`/`S4` labels "
            "contain visible character-encoding artifacts (for example, "
            "`donâ€™t`). These strings were preserved as supplied; no "
            "normalization was attempted.",
            "- Workbook labels describe `S4` as the main place/device used the "
            "last time the respondent used the internet, so a skip for non-use "
            "is plausible. However, the observed cross-tab is not perfectly "
            "aligned: `S3` Never appears with `S4` Excel errors in "
            f"{never_s4_errors:,} rows and with a non-error `S4` response in "
            f"{never_s4_nonerrors:,} rows; `S4` Excel errors also occur with "
            f"non-Never/unknown/refused `S3` in {s4_errors_non_never:,} rows. "
            "These are unresolved routing/data-quality cases, not recoded "
            "structural missingness.",
            "- `S2__1` Excel errors by observed `S1` category: "
            + "; ".join(
                f"{_format_value(value)}: {count:,}"
                for value, count in s2_errors_by_s1.items()
            )
            + ". The pattern is compatible with routing for some respondents "
            "but includes exceptions; no `S2__1` errors were interpreted or "
            "replaced.",
            "",
            "## Transformations and retained fields",
            "",
            "- Applied only the adult eligibility filter on `A18`: retain "
            "non-special numeric ages greater than or equal to 18; exclude "
            "under-18, age special-code, missing, or invalid-age records as "
            "counted above.",
            "- Preserved all 23 source column names, order, Parquet types, "
            "response values, labels, and Excel error tokens in the output.",
            "- Preserved `Access_fnl` and `Overall_Access_fnl` as their original "
            "text labels. No binary financial-exclusion target was created, "
            "and the `Access_fnl` derivation remains unverified.",
            "- Kept `indWeight` and `A07` in the response file as analysis "
            "metadata, not predictors. `A07`'s mapping to the official PSU/EA "
            "and the stratum identifier remain unverified; full survey-design "
            "analysis is not claimed.",
            "- Retained `S4` provisionally. It remains a general internet-use "
            "context candidate, not an approved final predictor.",
            "- No wealth quantile was added. No predictor matrix, final "
            "modelling dataset, model, or target was created. The selected "
            "extraction contains no direct financial-service transaction "
            "fields; the two outcome classification fields are retained only "
            "for later review.",
            "",
            "## Unresolved issues and next review",
            "",
            "- Obtain/confirm official `Access_fnl` derivation and the "
            "sampling-design crosswalk before target construction or claiming "
            "design-based analysis.",
            "- Review the unexplained `A20` value `95`, Excel error tokens, "
            "and routing exceptions in `S2__1`/`S4` with the questionnaire "
            "and data provider before any predictor missingness treatment.",
            "- Confirm the `S2__1` 0/1 meaning and whether `S4` is suitable "
            "after resolving observed skip-pattern inconsistencies.",
            "",
            "## Integrity checks",
            "",
            f"- Input and output row counts reconcile: {source_profile['rows']:,} "
            f"= {adult_count:,} retained + "
            f"{metadata['excluded_under_18']:,} under 18 + "
            f"{metadata['age_special_codes_excluded']:,} age special + "
            f"{metadata['missing_age']:,} missing age + "
            f"{metadata['invalid_age']:,} invalid age.",
            f"- Interim input SHA-256 after preparation: "
            f"`{metadata['source_sha256_after']}`.",
            f"- Interim input unchanged: **{metadata['source_sha256_before'] == metadata['source_sha256_after']}**.",
            f"- Prepared Parquet size: {destination.stat().st_size:,} bytes.",
            "",
        ]
    )
    return "\n".join(lines)


def prepare_data(
    source: Path = PARQUET_PATH,
    destination: Path = PREPARED_PATH,
    report_path: Path = REPORT_PATH,
) -> dict[str, Any]:
    """Write an adult-only response file, preserving source values and metadata."""
    source = Path(source)
    destination = Path(destination)
    report_path = Path(report_path)
    if not source.is_file():
        raise FileNotFoundError(f"Interim Parquet dataset does not exist: {source}")
    if source.resolve() == destination.resolve():
        raise ValueError("The prepared destination must not replace the interim source.")
    if destination.resolve() == report_path.resolve():
        raise ValueError("The Parquet destination and report path must differ.")

    source_sha256 = _sha256(source)
    input_file = pq.ParquetFile(source)
    validate_structure(input_file.schema_arrow, input_file.metadata.num_rows)
    schema_metadata = input_file.schema_arrow.metadata or {}
    if EXTRACTION_METADATA_KEY not in schema_metadata:
        raise ValueError("Interim Parquet is missing extraction provenance metadata.")
    extraction_metadata = json.loads(schema_metadata[EXTRACTION_METADATA_KEY])
    if (
        extraction_metadata.get("extracted_rows") != input_file.metadata.num_rows
        or extraction_metadata.get("source_reported_rows") != input_file.metadata.num_rows
        or extraction_metadata.get("row_filter") != "none"
    ):
        raise ValueError("Interim Parquet row counts or no-filter provenance do not reconcile.")
    age_field = input_file.schema_arrow.field(AGE_COLUMN)
    if not pa.types.is_integer(age_field.type):
        raise ValueError(f"{AGE_COLUMN} must have an integer Parquet type, found {age_field.type}.")

    source_profile = _profile(source)
    age_dispositions: Counter[str] = Counter()
    destination.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="finaccess-preparation-", dir=destination.parent
    ) as temporary_directory:
        temporary_path = Path(temporary_directory) / destination.name
        output_metadata = dict(schema_metadata)
        preparation: dict[str, Any] = {
            "source_file": source.name,
            "source_rows": input_file.metadata.num_rows,
            "age_variable": AGE_COLUMN,
            "minimum_age_inclusive": 18,
            "age_special_codes": {
                str(code): label for code, label in AGE_SPECIAL_CODES.items()
            },
            "row_filter": "A18 >= 18, excluding A18 special codes 98 and 99",
            "retained_adults": 0,
            "excluded_under_18": 0,
            "age_code_98": 0,
            "age_code_99": 0,
            "missing_age": 0,
            "invalid_age": 0,
            "age_special_codes_excluded": 0,
            "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
            "target_constructed": False,
            "predictor_matrix_created": False,
            "wealth_quantile_included": False,
        }
        with pq.ParquetWriter(
            temporary_path,
            input_file.schema_arrow,
            compression="snappy",
        ) as writer:
            for batch in input_file.iter_batches(batch_size=BATCH_SIZE):
                ages = batch.column(batch.schema.get_field_index(AGE_COLUMN)).to_pylist()
                dispositions = [_age_disposition(age) for age in ages]
                age_dispositions.update(dispositions)
                keep_mask = pa.array(
                    [disposition == "adult" for disposition in dispositions],
                    type=pa.bool_(),
                )
                filtered = pc.filter(batch, keep_mask)
                if filtered.num_rows:
                    writer.write_batch(filtered)
                    preparation["retained_adults"] += filtered.num_rows

        preparation["excluded_under_18"] = age_dispositions["under_18"]
        source_ages = source_profile["fields"][AGE_COLUMN]["counts"]
        preparation["age_code_98"] = source_ages.get(98, 0)
        preparation["age_code_99"] = source_ages.get(99, 0)
        preparation["age_special_codes_excluded"] = (
            preparation["age_code_98"] + preparation["age_code_99"]
        )
        preparation["missing_age"] = age_dispositions["missing"]
        preparation["invalid_age"] = age_dispositions["invalid"]
        preparation["source_sha256_before"] = source_sha256
        source_sha256_after = _sha256(source)
        if source_sha256 != source_sha256_after:
            raise RuntimeError("The interim Parquet changed during preparation.")
        preparation["source_sha256_after"] = source_sha256_after
        output_metadata[PREPARATION_METADATA_KEY] = json.dumps(
            preparation, ensure_ascii=False
        ).encode("utf-8")
        # Attach metadata by rewriting only the Parquet footer while preserving batches.
        _rewrite_metadata(temporary_path, output_metadata)

        output_file = pq.ParquetFile(temporary_path)
        try:
            validate_structure(output_file.schema_arrow, output_file.metadata.num_rows)
            if output_file.metadata.num_rows != preparation["retained_adults"]:
                raise ValueError("Prepared Parquet row count does not match the age-filter counts.")
            if not input_file.schema_arrow.equals(output_file.schema_arrow, check_metadata=False):
                raise ValueError("Prepared Parquet schema differs from the interim source.")
            output_schema_metadata = output_file.schema_arrow.metadata or {}
            if PREPARATION_METADATA_KEY not in output_schema_metadata:
                raise ValueError("Prepared Parquet is missing preparation metadata.")
            if json.loads(output_schema_metadata[PREPARATION_METADATA_KEY]) != preparation:
                raise ValueError("Prepared Parquet preparation metadata is inconsistent.")
        finally:
            output_file.close()

        temporary_path.replace(destination)

    prepared_profile = _profile(destination)
    input_file.close()
    report = _render_report(
        source=source,
        destination=destination,
        source_profile=source_profile,
        prepared_profile=prepared_profile,
        metadata=preparation,
        source_sha256=source_sha256,
    )
    report_temp = report_path.with_name(report_path.name + ".tmp")
    report_temp.write_text(report, encoding="utf-8")
    os.replace(report_temp, report_path)
    LOGGER.info(
        "Prepared %s of %s records; excluded %s under-18 and %s age-special records",
        preparation["retained_adults"],
        preparation["source_rows"],
        preparation["excluded_under_18"],
        preparation["age_special_codes_excluded"],
    )
    LOGGER.info("Prepared data: %s (%s bytes)", destination, destination.stat().st_size)
    LOGGER.info("Cleaning report: %s", report_path)
    return preparation


def _rewrite_metadata(path: Path, metadata: dict[bytes, bytes]) -> None:
    """Replace Parquet footer metadata without changing row groups or values."""
    temporary_path = path.with_name(path.name + ".metadata.tmp")
    parquet = pq.ParquetFile(path)
    try:
        with pq.ParquetWriter(
            temporary_path,
            parquet.schema_arrow.with_metadata(metadata),
            compression="snappy",
        ) as writer:
            for batch in parquet.iter_batches(batch_size=BATCH_SIZE):
                writer.write_batch(batch)
    finally:
        parquet.close()
    temporary_path.replace(path)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        prepare_data()
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, pa.ArrowException):
        LOGGER.exception("FinAccess preparation failed.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
