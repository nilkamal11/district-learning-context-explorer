from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_DATA_FILES = {
    "data/raw/.gitkeep",
    "data/processed/.gitkeep",
    "data/output/.gitkeep",
}
APPROVED_SITE_FILES = {
    "site/.nojekyll",
    "site/index.html",
    "site/assets/dashboard.js",
    "site/assets/plotly-3.1.0.min.js",
    "site/assets/styles.css",
    "site/assets/trends.js",
    "site/assets/workbench.js",
    "site/data/dashboard-data.js",
    "site/data/workbench-grade-3.js",
    "site/data/workbench-grade-5.js",
    "site/data/workbench-grade-6.js",
    "site/data/workbench-grade-7.js",
    "site/data/workbench-grade-8.js",
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


def _repository_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    return sorted(
        path.decode("utf-8", errors="surrogateescape").replace("\\", "/")
        for path in result.stdout.split(b"\0")
        if path
    )


def _violations(paths: list[str]) -> list[str]:
    violations = []
    for relative in paths:
        path = Path(relative)
        unapproved_site_file = relative.startswith("site/") and relative not in APPROVED_SITE_FILES
        restricted_data_path = relative.startswith("data/") and relative not in ALLOWED_DATA_FILES
        row_level_artifact = path.suffix.lower() in BLOCKED_SUFFIXES and not relative.startswith(
            "site/"
        )
        generated_output_name = path.name.lower().startswith(BLOCKED_OUTPUT_NAME_PREFIXES)
        if (
            unapproved_site_file
            or restricted_data_path
            or row_level_artifact
            or generated_output_name
        ):
            violations.append(relative)
    return violations


def main() -> None:
    violations = _violations(_repository_files())
    if violations:
        joined = "\n  - ".join(violations)
        raise SystemExit(
            "Restricted, row-level, generated, or unapproved public-site files are tracked "
            f"or untracked:\n  - {joined}"
        )
    print(
        "PASS: tracked and untracked nonignored files contain no restricted data, "
        "unapproved output, or unapproved public-site assets"
    )


if __name__ == "__main__":
    main()
