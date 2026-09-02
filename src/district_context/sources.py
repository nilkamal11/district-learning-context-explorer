from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from district_context.config import output_dir, raw_data_dir, source_config
from district_context.utils import sha256_file, write_json


def _read_header(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return next(csv.reader(handle))


def source_locations() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source_id, spec in source_config().items():
        rows.append(
            {
                "source_id": source_id,
                "version": str(spec["version"]),
                "filename": spec["required_filename"],
                "official_url": spec["official_url"],
                "landing_page": spec["landing_page"],
            }
        )
    return rows


def verify_sources(
    *, compute_hashes: bool = True, write_inventory: bool = True
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for source_id, spec in source_config().items():
        path = raw_data_dir() / spec["required_filename"]
        result: dict[str, Any] = {
            "source_id": source_id,
            "version": str(spec["version"]),
            "path": str(path),
            "exists": path.is_file(),
            "valid": False,
            "checked_at_utc": datetime.now(UTC).isoformat(),
        }
        if not path.is_file():
            result["errors"] = ["required file is missing"]
            results.append(result)
            continue

        errors: list[str] = []
        size = path.stat().st_size
        header = _read_header(path)
        missing_columns = sorted(set(spec["required_columns"]) - set(header))
        if size < int(spec["expected_min_bytes"]):
            expected_size = int(spec["expected_min_bytes"])
            errors.append(f"file is smaller than expected ({size:,} < {expected_size:,} bytes)")
        if missing_columns:
            errors.append(f"missing columns: {', '.join(missing_columns)}")

        expected_checksum = spec.get("sha256")
        observed_checksum = sha256_file(path) if compute_hashes else None
        hash_verified = bool(
            compute_hashes and expected_checksum and observed_checksum == expected_checksum
        )
        if compute_hashes and expected_checksum and observed_checksum != expected_checksum:
            errors.append("SHA-256 does not match the pinned source manifest")

        result.update(
            {
                "size_bytes": size,
                "column_count": len(header),
                "schema_columns": header,
                "expected_sha256": expected_checksum,
                "observed_sha256": observed_checksum,
                "hash_verified": hash_verified,
                "errors": errors,
                "valid": not errors,
            }
        )
        results.append(result)

    if write_inventory:
        write_json(output_dir() / "source_inventory.json", results)
    return results


def require_valid_sources(*, compute_hashes: bool = True) -> list[dict[str, Any]]:
    results = verify_sources(compute_hashes=compute_hashes)
    invalid = [result for result in results if not result["valid"]]
    if invalid:
        details = "; ".join(
            f"{item['source_id']}: {', '.join(item.get('errors', []))}" for item in invalid
        )
        raise RuntimeError(f"Source verification failed. {details}")
    return results
