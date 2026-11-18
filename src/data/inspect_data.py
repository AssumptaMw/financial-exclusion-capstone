"""Audit the FinAccess workbook using bounded, read-only inspection."""

from __future__ import annotations

import csv
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zipfile import BadZipFile
from xml.etree.ElementTree import ParseError

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data" / "raw" / "2024_Finaccess_Publicdata.xlsx"
REPORT = ROOT / "reports" / "results" / "data_audit.md"
INVENTORY = ROOT / "reports" / "results" / "variable_inventory.csv"
SAMPLE_ROWS = 5
MAX_COLUMNS = 5_000
MAX_LABEL_EXAMPLES = 20

LOGGER = logging.getLogger(__name__)
READ_ERRORS = (BadZipFile, EOFError, InvalidFileException, KeyError, OSError, ParseError, ValueError)
DESIGN_PATTERNS = {
    "possible sampling weight": re.compile(r"\bweights?\b", re.IGNORECASE),
    "possible stratum/stratification field": re.compile(
        r"\bstrat(?:um|a|ification)?\b", re.IGNORECASE
    ),
    "possible cluster/PSU field": re.compile(
        r"\bcluster(?:\s+(?:number|id))\b|\bpsu\b|primary sampling unit|"
        r"sampling unit|enumeration area",
        re.IGNORECASE,
    ),
    "possible cluster descriptor": re.compile(
        r"\bcluster\s+type\b",
        re.IGNORECASE,
    ),
}
IDENTIFIER_PATTERN = re.compile(r"(?:^|_)(?:id|identifier|key)$", re.IGNORECASE)
LOCATION_PATTERN = re.compile(r"\b(?:latitude|longitude|coordinates?|gps)\b", re.IGNORECASE)
MISSING_TOKEN_PATTERN = re.compile(
    r"^\s*(?:\.(?:[a-z])?|n/?a|null|none|missing|refused|not stated|"
    r"not applicable|don't know|do not know|dk|-9{1,2})\s*$",
    re.IGNORECASE,
)
MISSING_LABEL_PATTERN = re.compile(
    r"\b(?:don't know|do not know|refused|not stated|not applicable|"
    r"missing|no response|not known|not available)\b",
    re.IGNORECASE,
)
INVENTORY_FIELDS = [
    "position",
    "original_variable_name",
    "sample_python_types",
    "sample_nonempty_count",
    "sample_blank_count",
    "possible_missing_tokens_in_sample",
    "metadata_storage_type",
    "metadata_isnumeric",
    "metadata_format",
    "metadata_value_label",
    "metadata_variable_label",
    "possible_role_candidate",
]


def _markdown(value: Any) -> str:
    return _text(value).replace("|", "\\|") or "—"


@dataclass
class SheetInfo:
    worksheet: Any
    name: str
    state: str
    dimension: str | None
    rows: int | None
    columns: int | None
    headers: list[Any]
    sample: list[tuple[Any, ...]]
    role: str = "Unclassified; manual review required"
    notes: list[str] = field(default_factory=list)


def _text(value: Any) -> str:
    return "" if value is None else str(value).replace("\r", " ").replace("\n", " ").strip()


def _header_key(value: Any) -> str:
    return _text(value).casefold().replace("_", "").replace(" ", "")


def _inspect_sheet(worksheet: Any) -> SheetInfo:
    row_count, column_count = worksheet.max_row, worksheet.max_column
    column_limit = min(column_count or MAX_COLUMNS, MAX_COLUMNS)
    row_limit = min(row_count or SAMPLE_ROWS + 1, SAMPLE_ROWS + 1)
    rows = list(
        worksheet.iter_rows(
            min_row=1,
            max_row=row_limit,
            max_col=column_limit,
            values_only=True,
        )
    )
    try:
        dimension = worksheet.calculate_dimension()
    except ValueError:
        dimension = None

    notes = []
    if column_count is None:
        notes.append(f"Column count unavailable; preview limited to {MAX_COLUMNS} columns.")
    elif column_count > MAX_COLUMNS:
        notes.append(f"Preview limited to {MAX_COLUMNS} of {column_count} columns.")
    elif column_count > MAX_COLUMNS:
        notes.append(f"Preview limited to {MAX_COLUMNS} of {column_count} columns.")
    if row_count is None:
        notes.append("Row count unavailable; only the bounded preview was read.")

    return SheetInfo(
        worksheet=worksheet,
        name=worksheet.title,
        state=worksheet.sheet_state,
        dimension=dimension,
        rows=row_count,
        columns=column_count,
        headers=list(rows[0]) if rows else [],
        sample=[tuple(row) for row in rows[1:]],
        notes=notes,
    )


def _classify_sheet(sheet: SheetInfo) -> str:
    name = sheet.name.casefold()
    headers = {_header_key(value) for value in sheet.headers}
    if {"name", "type", "varlab"} <= headers:
        return "Likely variable metadata/codebook (column-header match)"
    if re.search(r"variable|codebook|dictionary|metadata|value|label|reference", name):
        return "Likely documentation or value-label reference (sheet-name match)"
    if (
        (sheet.columns or 0) >= 10
        and (sheet.rows or 0) > 10
        and sum(bool(_text(value)) for value in sheet.headers) >= 10
    ):
        return "Likely respondent-level data candidate (wide layout; verify documentation)"
    return "Unclassified; manual review required"


def _codebook_sheet(sheets: list[SheetInfo]) -> SheetInfo | None:
    return next(
        (
            sheet
            for sheet in sheets
            if {"name", "type"} <= {_header_key(value) for value in sheet.headers}
        ),
        None,
    )


def _read_codebook(
    sheet: SheetInfo | None, limitations: list[str]
) -> dict[str, dict[str, Any]]:
    if sheet is None:
        limitations.append("No codebook sheet with recognizable name/type columns was found.")
        return {}

    aliases = {
        "name": {"name"},
        "type": {"type"},
        "isnumeric": {"isnumeric"},
        "format": {"format"},
        "vallab": {"vallab", "valuelabel"},
        "varlab": {"varlab", "variablelabel"},
    }
    keys = [_header_key(value) for value in sheet.headers]
    indices = {
        field: next((index for index, key in enumerate(keys) if key in variants), -1)
        for field, variants in aliases.items()
    }
    metadata: dict[str, dict[str, Any]] = {}
    try:
        for row in sheet.worksheet.iter_rows(
            min_row=2, max_col=sheet.columns or len(sheet.headers), values_only=True
        ):
            index = indices["name"]
            if index < 0 or index >= len(row) or not _text(row[index]):
                continue
            name = _text(row[index])
            metadata[name] = {
                field: row[column] if 0 <= column < len(row) else None
                for field, column in indices.items()
            }
    except READ_ERRORS as error:
        limitations.append(f"Could not read the full codebook sheet '{sheet.name}': {error}")
    return metadata


def _candidate_role(name: str, metadata: dict[str, Any]) -> str:
    details = " ".join(
        (name, _text(metadata.get("varlab")), _text(metadata.get("vallab")))
    )
    details = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", details)
    for role, pattern in DESIGN_PATTERNS.items():
        if pattern.search(details):
            return f"{role}; verify against official sampling documentation"
    if IDENTIFIER_PATTERN.search(name):
        return "Possible identifier; review before modeling"
    if LOCATION_PATTERN.search(details):
        return "Possible location field; review before modeling"
    return ""


def _inventory_rows(
    sheets: list[SheetInfo], metadata: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[tuple[str, str, str]]]:
    records: list[dict[str, Any]] = []
    candidates: list[tuple[str, str, str]] = []
    for sheet in sheets:
        if not sheet.role.startswith("Likely respondent-level data"):
            continue
        for position, header in enumerate(sheet.headers, start=1):
            name = _text(header)
            sample = [
                row[position - 1] if position - 1 < len(row) else None
                for row in sheet.sample
            ]
            values = [value for value in sample if value is not None]
            labels = sorted(
                {
                    _text(value)
                    for value in values
                    if isinstance(value, str) and MISSING_TOKEN_PATTERN.fullmatch(value)
                }
            )
            python_types = sorted({type(value).__name__ for value in values})
            field_info = metadata.get(name, {})
            role = _candidate_role(name, field_info)
            if role:
                candidates.append((name, role, _text(field_info.get("varlab"))))
            records.append(
                {
                    "position": position,
                    "original_variable_name": name,
                    "sample_python_types": "; ".join(python_types),
                    "sample_nonempty_count": len(values),
                    "sample_blank_count": len(sample) - len(values),
                    "possible_missing_tokens_in_sample": "; ".join(labels),
                    "metadata_storage_type": _text(field_info.get("type")),
                    "metadata_isnumeric": _text(field_info.get("isnumeric")),
                    "metadata_format": _text(field_info.get("format")),
                    "metadata_value_label": _text(field_info.get("vallab")),
                    "metadata_variable_label": _text(field_info.get("varlab")),
                    "possible_role_candidate": role,
                }
            )
    return records, candidates


def _scan_value_labels(
    sheets: list[SheetInfo], limitations: list[str]
) -> tuple[int, list[str], int]:
    count, scanned = 0, 0
    examples: list[str] = []
    seen: set[str] = set()
    for sheet in sheets:
        if not re.search(r"value|label", sheet.name, re.IGNORECASE):
            continue
        try:
            for row in sheet.worksheet.iter_rows(min_row=1, max_col=1, values_only=True):
                scanned += 1
                value = row[0] if row else None
                if not isinstance(value, str) or not MISSING_LABEL_PATTERN.search(value):
                    continue
                count += 1
                text = _text(value)
                if text not in seen and len(examples) < MAX_LABEL_EXAMPLES:
                    seen.add(text)
                    examples.append(text)
        except READ_ERRORS as error:
            limitations.append(f"Could not finish scanning labels in '{sheet.name}': {error}")
    return count, examples, scanned


def _column_names(headers: list[Any]) -> str:
    names = [_text(value).replace("`", "\\`") for value in headers]
    return "\n".join(
        ", ".join(names[index : index + 8]) for index in range(0, len(names), 8)
    )


def _relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _write_outputs(
    report_path: Path,
    inventory_path: Path,
    source_path: Path,
    size: int,
    sheets: list[SheetInfo],
    codebook: dict[str, dict[str, Any]],
    limitations: list[str],
    label_results: tuple[int, list[str], int],
) -> None:
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    records, candidates = _inventory_rows(sheets, codebook)
    with inventory_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=INVENTORY_FIELDS)
        writer.writeheader()
        writer.writerows(records)

    data_sheets = [s for s in sheets if s.role.startswith("Likely respondent-level data")]
    codebook_sheet = _codebook_sheet(sheets)
    relevant = data_sheets + ([codebook_sheet] if codebook_sheet else [])
    label_count, label_examples, label_rows = label_results
    lines = [
        "# FinAccess workbook data audit",
        "",
        "## Source and inspection scope",
        "",
        f"- Workbook: `{_relative(source_path)}`",
        f"- Size: {size:,} bytes ({size / 1_000_000:,.2f} MB; {size / 1024**2:,.2f} MiB)",
        "- Opened with `openpyxl` in read-only mode; the source workbook was not modified.",
        f"- Read the header and up to {SAMPLE_ROWS} respondent records per sheet; no "
        "full respondent table was loaded or copied into the report.",
        "- No financial-exclusion target was constructed.",
        "",
        "## Workbook sheets",
        "",
        "| Sheet | Visibility | Reported dimensions | Likely role (heuristic) |",
        "|---|---|---|---|",
    ]
    for sheet in sheets:
        dimension = sheet.dimension or (
            f"{sheet.rows} rows x {sheet.columns} columns (reported bounds)"
            if sheet.rows is not None and sheet.columns is not None
            else "Not reported"
        )
        lines.append(
            f"| {_markdown(sheet.name)} | {_markdown(sheet.state)} | "
            f"{_markdown(dimension)} | {_markdown(sheet.role)} |"
        )
    lines.extend(["", "## Column names for relevant sheets", ""])
    for sheet in relevant:
        lines.extend(
            [
                f"### {sheet.name} ({len(sheet.headers):,} columns)",
                "",
                "<details>",
                f"<summary>Show column names in workbook order ({len(sheet.headers):,})</summary>",
                "",
                "```text",
                _column_names(sheet.headers),
                "```",
                "</details>",
                "",
            ]
        )
    for sheet in sheets:
        if sheet in relevant:
            continue
        heading = ", ".join(
            f"`{_markdown(value)}`" for value in sheet.headers if _text(value)
        )
        lines.extend(
            [
                f"### {sheet.name}",
                "",
                f"First-row column values: {heading or 'No explicit heading'}",
                "",
            ]
        )

    lines.extend(
        [
            "## Preliminary variable inventory",
            "",
            f"The complete {sum(len(s.headers) for s in data_sheets):,}-variable inventory is "
            f"`{_relative(inventory_path)}`. It contains original names, source metadata where "
            "available, types and blank counts from the bounded sample, possible string missing "
            "tokens, and heuristic role candidates.",
            "",
            "| Respondent sheet | Sample rows | Columns | Blank headers | Duplicate headers |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for sheet in data_sheets:
        headers = [_text(value) for value in sheet.headers if _text(value)]
        lines.append(
            f"| {sheet.name} | {len(sheet.sample)} | {len(sheet.headers)} | "
            f"{len(sheet.headers) - len(headers)} | {len(headers) - len(set(headers))} |"
        )
    lines.extend(
        [
            "",
            "Sample types and blanks are not full-dataset statistics. Source storage types and "
            "labels are reproduced as metadata, not independently validated definitions.",
            "",
            "## Possible nonresponse or special-value labels",
            "",
            f"Streamed {label_rows:,} rows from value/label reference sheets; {label_count:,} "
            "entries matched common nonresponse wording. These labels are variable-specific "
            "candidates, not global missing-value codes.",
            "",
        ]
    )
    lines.extend(f"- `{_markdown(value)}`" for value in label_examples)
    if not label_examples:
        lines.append("No entries matched the scanned nonresponse terms.")
    lines.extend(
        [
            "",
            "The respondent sample was checked for blank cells and possible string tokens. "
            "Numeric sentinel values were not inferred or recoded; review the associated "
            "variable-specific value labels and official documentation.",
            "",
            "## Possible survey-design, identifier, or location fields",
            "",
            "Name/label matches are preliminary only and do not establish a field's survey role.",
            "",
            "| Original variable | Candidate | Source variable label |",
            "|---|---|---|",
        ]
    )
    if candidates:
        lines.extend(
            f"| `{_markdown(name)}` | {_markdown(role)} | "
            f"{_markdown(label) if label else 'No variable label found'} |"
            for name, role, label in candidates
        )
    else:
        lines.append("| None identified by this scan | — | — |")
    if not any("stratum" in role for _, role, _ in candidates):
        lines.extend(
            [
                "",
                "No stratum/stratification candidate was found by name or label matching. "
                "This does not establish that the survey lacks strata; confirm from official "
                "sampling documentation.",
            ]
        )
    lines.extend(
        [
            "",
            "## Limitations and follow-up",
            "",
            "- Dimensions are workbook-reported bounds and may include blank cells.",
            "- Respondent types and blank counts are based only on the small sample.",
            "- Sheet roles, design fields, and special-value candidates require verification "
            "against official FinAccess documentation.",
            "- The value-label reference sheet was scanned as a streamed single column; "
            "candidate labels were not mapped to respondent variables.",
            "",
        ]
    )
    for sheet in sheets:
        limitations.extend(f"Sheet '{sheet.name}': {note}" for note in sheet.notes)
    if limitations:
        lines.extend(["### Inspection limitations encountered", ""])
        lines.extend(f"- {note}" for note in limitations)
        lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def inspect_workbook(
    source_path: Path = SOURCE,
    report_path: Path = REPORT,
    inventory_path: Path = INVENTORY,
) -> int:
    """Write a data audit and variable inventory, returning a process exit code."""
    source_path, report_path, inventory_path = map(
        Path, (source_path, report_path, inventory_path)
    )
    if not source_path.is_file():
        message = f"Source workbook does not exist: {source_path}"
        LOGGER.error(message)
        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(f"# FinAccess workbook data audit\n\n{message}\n", encoding="utf-8")
        except OSError as error:
            LOGGER.error("Could not write failure report: %s", error)
        return 1

    try:
        size = source_path.stat().st_size
    except OSError as error:
        LOGGER.error("Could not read workbook metadata: %s", error)
        return 1

    try:
        workbook = load_workbook(source_path, read_only=True, data_only=True, keep_links=False)
    except READ_ERRORS as error:
        LOGGER.error("Could not open workbook in read-only mode: %s", error)
        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                f"# FinAccess workbook data audit\n\n"
                f"- Workbook: `{source_path}`\n"
                f"- Size: {size:,} bytes\n"
                f"- Inspection limitation: {error}\n",
                encoding="utf-8",
            )
        except OSError as report_error:
            LOGGER.error("Could not write failure report: %s", report_error)
        return 1

    limitations: list[str] = []
    sheets: list[SheetInfo] = []
    try:
        LOGGER.info("Inspecting %s (%s bytes; read-only)", source_path, f"{size:,}")
        for worksheet in workbook.worksheets:
            try:
                sheet = _inspect_sheet(worksheet)
                sheet.role = _classify_sheet(sheet)
                sheets.append(sheet)
                LOGGER.info("Sheet '%s': %s (%s)", sheet.name, sheet.role, sheet.dimension)
            except READ_ERRORS as error:
                limitations.append(f"Could not inspect sheet '{worksheet.title}': {error}")

        if not any(sheet.role.startswith("Likely respondent-level data") for sheet in sheets):
            limitations.append("No likely respondent-level data sheet was identified.")
        codebook = _read_codebook(_codebook_sheet(sheets), limitations)
        label_results = _scan_value_labels(sheets, limitations)
        _write_outputs(
            report_path,
            inventory_path,
            source_path,
            size,
            sheets,
            codebook,
            limitations,
            label_results,
        )
    except OSError as error:
        LOGGER.error("Could not write audit outputs: %s", error)
        return 1
    finally:
        workbook.close()

    if limitations:
        LOGGER.warning("Audit completed with limitations; see %s", report_path)
        return 1
    LOGGER.info("Audit report: %s", report_path)
    LOGGER.info("Variable inventory: %s", inventory_path)
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    return inspect_workbook()


if __name__ == "__main__":
    sys.exit(main())
