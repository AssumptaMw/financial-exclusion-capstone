"""Provision private model assets from a Render runtime secret file."""

from __future__ import annotations

import base64
import binascii
import io
import os
import tarfile
import tempfile
from pathlib import Path

from src.data.feature_engineering import MODELING_DATASET_PATH
from src.models.load_model import MODEL_PATH

RENDER_ASSETS_SECRET = Path("/etc/secrets/financial-exclusion-runtime-assets.b64")
MAX_ASSET_BYTES = 100 * 1024 * 1024


def provision_runtime_assets(
    model_path: Path = MODEL_PATH,
    dataset_path: Path = MODELING_DATASET_PATH,
    secret_file: Path = RENDER_ASSETS_SECRET,
) -> None:
    """Restore missing model and SHAP background files from a secret bundle.

    The Render secret contains a base64-encoded gzip tar archive with exactly
    the model and modeling Parquet files. Files already present are preserved.
    """
    destinations = {Path(model_path).name: Path(model_path), Path(dataset_path).name: Path(dataset_path)}
    if len(destinations) != 2:
        raise ValueError("Runtime model and dataset must have distinct filenames.")

    missing = {name for name, path in destinations.items() if not path.is_file()}
    if not missing:
        return
    secret_file = Path(secret_file)
    if not secret_file.is_file():
        raise FileNotFoundError(
            "Runtime model assets are missing. Add the Render secret file "
            f"'{secret_file.name}' containing the generated runtime asset bundle."
        )

    try:
        encoded_bundle = b"".join(secret_file.read_bytes().split())
        bundle = base64.b64decode(encoded_bundle, validate=True)
        with tarfile.open(fileobj=io.BytesIO(bundle), mode="r:gz") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            if set(names) != set(destinations) or len(names) != len(destinations):
                raise ValueError("Runtime asset bundle must contain only the expected model and dataset files.")
            if any(
                not member.isfile()
                or Path(member.name).name != member.name
                or member.size > MAX_ASSET_BYTES
                for member in members
            ):
                raise ValueError("Runtime asset bundle contains an invalid or oversized file.")

            for member in members:
                if member.name not in missing:
                    continue
                source = archive.extractfile(member)
                if source is None:
                    raise ValueError(f"Runtime asset '{member.name}' could not be read.")
                destination = destinations[member.name]
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary_path: Path | None = None
                try:
                    with tempfile.NamedTemporaryFile(
                        mode="wb", dir=destination.parent, prefix=f".{destination.name}.", delete=False
                    ) as temporary_file:
                        temporary_path = Path(temporary_file.name)
                        copied = 0
                        while block := source.read(1024 * 1024):
                            copied += len(block)
                            if copied > member.size:
                                raise ValueError(f"Runtime asset '{member.name}' exceeds its declared size.")
                            temporary_file.write(block)
                        if copied != member.size:
                            raise ValueError(f"Runtime asset '{member.name}' is incomplete.")
                    os.replace(temporary_path, destination)
                finally:
                    source.close()
                    if temporary_path is not None:
                        temporary_path.unlink(missing_ok=True)
    except (binascii.Error, tarfile.TarError) as exc:
        raise ValueError("Render runtime asset secret is not a valid encoded gzip tar bundle.") from exc

    remaining = [str(path) for path in destinations.values() if not path.is_file()]
    if remaining:
        raise FileNotFoundError(f"Runtime asset bundle did not provide required files: {remaining}")
