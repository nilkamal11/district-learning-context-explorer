from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_DATA_FILES = {
    "data/raw/.gitkeep",
    "data/processed/.gitkeep",
    "data/output/.gitkeep",
}
BLOCKED_SUFFIXES = {
    ".7z",
    ".arrow",
    ".csv",
    ".db",
    ".dta",
    ".duckdb",
    ".feather",
    ".gz",
    ".html",
    ".json",
    ".jsonl",
    ".ndjson",
    ".parquet",
    ".pdf",
    ".sas7bdat",
    ".sav",
    ".sqlite",
    ".tsv",
    ".xls",
    ".xlsx",
    ".zip",
}
BLOCKED_OUTPUT_NAME_PREFIXES = (
    "build_manifest",
    "district_profile_",
    "peer_membership_",
    "profile_summary_",
    "qa_results",
    "qa_summary",
    "source_inventory",
)
PUBLIC_SITE_SUFFIXES = {".css", ".html", ".js"}
PUBLIC_DERIVED_DATA = "site/data/dashboard-data.js"


def main() -> None:
    result = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    tracked = [line.strip().replace("\\", "/") for line in result.stdout.splitlines()]
    violations = []
    for relative in tracked:
        path = Path(relative)
        public_site_asset = relative.startswith("site/") and path.suffix.lower() in (
            PUBLIC_SITE_SUFFIXES
        )
        unapproved_site_data = relative.startswith("site/data/") and relative != (
            PUBLIC_DERIVED_DATA
        )
        restricted_data_path = relative.startswith("data/") and relative not in ALLOWED_DATA_FILES
        row_level_artifact = path.suffix.lower() in BLOCKED_SUFFIXES and not public_site_asset
        generated_output_name = path.name.lower().startswith(BLOCKED_OUTPUT_NAME_PREFIXES)
        if (
            restricted_data_path
            or row_level_artifact
            or generated_output_name
            or unapproved_site_data
        ):
            violations.append(relative)
    if violations:
        joined = "\n  - ".join(violations)
        raise SystemExit(f"Restricted or row-level data are tracked:\n  - {joined}")
    print("PASS: no restricted raw, processed, or unapproved output data are tracked")


if __name__ == "__main__":
    main()
