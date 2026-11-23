"""Create the ignored base64 secret bundle needed by the Render API service."""

from __future__ import annotations

import base64
import io
import tarfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS = (
    PROJECT_ROOT / "artifacts" / "financial_exclusion_pipeline.joblib",
    PROJECT_ROOT / "data" / "processed" / "finaccess_modeling_dataset_6c.parquet",
)
OUTPUT = PROJECT_ROOT / ".secrets" / "financial-exclusion-runtime-assets.b64"


def main() -> int:
    missing = [str(path.relative_to(PROJECT_ROOT)) for path in ASSETS if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Required deployment asset(s) are missing: {', '.join(missing)}")

    archive_buffer = io.BytesIO()
    with tarfile.open(fileobj=archive_buffer, mode="w:gz") as archive:
        for asset in ASSETS:
            archive.add(asset, arcname=asset.name, recursive=False)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    encoded = base64.b64encode(archive_buffer.getvalue())
    OUTPUT.write_bytes(encoded)
    print(f"Created {OUTPUT.relative_to(PROJECT_ROOT)} ({len(encoded):,} bytes).")
    print("This file contains the private model and survey-derived data; do not commit or share it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
