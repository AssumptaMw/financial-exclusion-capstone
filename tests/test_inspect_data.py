import csv

from openpyxl import Workbook

from src.data.inspect_data import _candidate_role, inspect_workbook


def test_inspection_writes_audit_and_inventory_without_record_values(tmp_path) -> None:
    source_path = tmp_path / "small_workbook.xlsx"
    report_path = tmp_path / "reports" / "data_audit.md"
    inventory_path = tmp_path / "reports" / "variable_inventory.csv"

    workbook = Workbook()
    respondents = workbook.active
    respondents.title = "Respondents"
    headers = [
        "record_id",
        "county",
        "A07",
        "A08",
        "indWeight",
        "hhWeight",
        "age",
        "sex",
        "access",
        "usage",
    ]
    respondents.append(headers)
    for row_number in range(11):
        respondents.append(
            [
                f"id-{row_number}",
                "Example County",
                row_number,
                "Urban",
                1.0,
                2.0,
                30,
                "Example sex",
                "Example access",
                "Example usage",
            ]
        )

    variables = workbook.create_sheet("Variables")
    variables.append(["position", "name", "type", "isnumeric", "format", "vallab", "varlab"])
    variables.append([3, "A07", "int", 1, "%12.0g", "", "Cluster Number"])
    variables.append([5, "indWeight", "double", 1, "%12.0g", "", "Individual Weights"])
    values = workbook.create_sheet("Values")
    values.append([None])
    values.append(["99 Not Stated"])
    workbook.save(source_path)

    exit_code = inspect_workbook(source_path, report_path, inventory_path)

    assert exit_code == 0
    report = report_path.read_text(encoding="utf-8")
    assert "Likely respondent-level data candidate" in report
    assert "Cluster Number" in report
    assert "99 Not Stated" in report
    assert "Example access" not in report

    with inventory_path.open(encoding="utf-8", newline="") as inventory_file:
        inventory_rows = list(csv.DictReader(inventory_file))
    assert len(inventory_rows) == len(headers)
    assert inventory_rows[2]["original_variable_name"] == "A07"
    assert "possible cluster/PSU field" in inventory_rows[2]["possible_role_candidate"]
    assert inventory_rows[4]["metadata_variable_label"] == "Individual Weights"


def test_missing_workbook_writes_failure_report(tmp_path) -> None:
    report_path = tmp_path / "reports" / "data_audit.md"

    exit_code = inspect_workbook(
        tmp_path / "missing.xlsx",
        report_path,
        tmp_path / "reports" / "inventory.csv",
    )

    assert exit_code == 1
    assert "Source workbook does not exist" in report_path.read_text(encoding="utf-8")


def test_candidate_roles_cover_weights_and_avoid_id_substring_false_positives() -> None:
    assert "sampling weight" in _candidate_role("hhWeight", {})
    assert "identifier" in _candidate_role("interview__key", {})
    assert _candidate_role("ID_card", {}) == ""
    assert "location field" in _candidate_role("Latitude", {})
    assert "cluster descriptor" in _candidate_role(
        "A08", {"varlab": "A8. Cluster type"}
    )
