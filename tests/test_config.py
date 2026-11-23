from financial_exclusion import config


def test_project_paths_are_root_relative() -> None:
    expected_paths = {
        "DATA_DIR": config.PROJECT_ROOT / "data",
        "RAW_DATA_DIR": config.PROJECT_ROOT / "data" / "raw",
        "INTERIM_DATA_DIR": config.PROJECT_ROOT / "data" / "interim",
        "PROCESSED_DATA_DIR": config.PROJECT_ROOT / "data" / "processed",
        "RAW_WORKBOOK_PATH": (
            config.PROJECT_ROOT / "data" / "raw" / "2024_Finaccess_Publicdata.xlsx"
        ),
    }

    assert config.PROJECT_ROOT.is_absolute()
    for name, expected_path in expected_paths.items():
        assert getattr(config, name) == expected_path
