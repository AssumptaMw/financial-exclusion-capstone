"""Tests for restoring model assets from the Render secret bundle."""

import base64
import io
import tarfile

import pytest

from src.financial_exclusion.runtime_assets import provision_runtime_assets


def make_bundle(files: dict[str, bytes]) -> bytes:
    archive_buffer = io.BytesIO()
    with tarfile.open(fileobj=archive_buffer, mode="w:gz") as archive:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return base64.b64encode(archive_buffer.getvalue())


def test_provision_runtime_assets_extracts_only_expected_files(tmp_path):
    model_path = tmp_path / "artifacts" / "financial_exclusion_pipeline.joblib"
    dataset_path = tmp_path / "data" / "finaccess_modeling_dataset_6c.parquet"
    secret_file = tmp_path / "runtime-assets.b64"
    secret_file.write_bytes(
        make_bundle({model_path.name: b"model bytes", dataset_path.name: b"dataset bytes"})
    )

    provision_runtime_assets(model_path, dataset_path, secret_file)

    assert model_path.read_bytes() == b"model bytes"
    assert dataset_path.read_bytes() == b"dataset bytes"


def test_provision_runtime_assets_preserves_existing_files(tmp_path):
    model_path = tmp_path / "financial_exclusion_pipeline.joblib"
    dataset_path = tmp_path / "finaccess_modeling_dataset_6c.parquet"
    model_path.write_bytes(b"existing model")
    dataset_path.write_bytes(b"existing dataset")

    provision_runtime_assets(model_path, dataset_path, tmp_path / "missing-secret")

    assert model_path.read_bytes() == b"existing model"
    assert dataset_path.read_bytes() == b"existing dataset"


def test_provision_runtime_assets_requires_render_secret_when_files_are_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="Add the Render secret file"):
        provision_runtime_assets(
            tmp_path / "financial_exclusion_pipeline.joblib",
            tmp_path / "finaccess_modeling_dataset_6c.parquet",
            tmp_path / "missing-secret",
        )


def test_provision_runtime_assets_rejects_unexpected_archive_paths(tmp_path):
    model_path = tmp_path / "financial_exclusion_pipeline.joblib"
    dataset_path = tmp_path / "finaccess_modeling_dataset_6c.parquet"
    secret_file = tmp_path / "runtime-assets.b64"
    secret_file.write_bytes(
        make_bundle({"../financial_exclusion_pipeline.joblib": b"unsafe", dataset_path.name: b"dataset"})
    )

    with pytest.raises(ValueError, match="only the expected"):
        provision_runtime_assets(model_path, dataset_path, secret_file)
