from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def normalize_district_id(value: object) -> str:
    """Return a seven-character district ID without losing leading zeroes."""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    if not text.isdigit():
        raise ValueError(f"District ID must be numeric, received {value!r}")
    if len(text) > 7:
        raise ValueError(f"District ID must contain at most seven digits, received {value!r}")
    return text.zfill(7)


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
