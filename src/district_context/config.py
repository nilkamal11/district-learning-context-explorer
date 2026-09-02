from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_yaml(relative_path: str | Path) -> dict[str, Any]:
    path = PROJECT_ROOT / relative_path
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def project_config() -> dict[str, Any]:
    return load_yaml("config/project.yml")


def source_config() -> dict[str, Any]:
    return load_yaml("config/sources.yml")


def raw_data_dir() -> Path:
    return PROJECT_ROOT / "data" / "raw" / "seda_2025_2"


def database_path() -> Path:
    return PROJECT_ROOT / "data" / "processed" / "district_context.duckdb"


def output_dir() -> Path:
    path = PROJECT_ROOT / "data" / "output"
    path.mkdir(parents=True, exist_ok=True)
    return path
