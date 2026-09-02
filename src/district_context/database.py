from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from district_context.config import (
    PROJECT_ROOT,
    database_path,
    project_config,
    raw_data_dir,
    source_config,
)
from district_context.qa import has_failures, run_qa
from district_context.sources import require_valid_sources
from district_context.utils import write_json


def connect(path: Path | None = None, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    target = path or database_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(target), read_only=read_only)


def _sql_literal(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def _git_commit() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _render_sql(path: Path, replacements: dict[str, str]) -> str:
    sql = path.read_text(encoding="utf-8")
    for name, value in replacements.items():
        sql = sql.replace("{{ " + name + " }}", value)
    if "{{" in sql or "}}" in sql:
        raise ValueError(f"Unresolved SQL template marker in {path}")
    return sql


def build_database(*, compute_hashes: bool = True) -> dict[str, Any]:
    source_results = require_valid_sources(compute_hashes=compute_hashes)
    raw = raw_data_dir()
    cfg = project_config()
    sources = source_config()
    replacements = {
        "achievement_path": _sql_literal(raw / sources["seda_achievement"]["required_filename"]),
        "context_path": _sql_literal(raw / sources["seda_context"]["required_filename"]),
        "crosswalk_path": _sql_literal(raw / sources["seda_crosswalk"]["required_filename"]),
        "context_year": str(int(cfg["analysis"]["context_year"])),
    }

    db_path = database_path()
    build_path = db_path.with_name(f"{db_path.stem}.building{db_path.suffix}")
    if build_path.exists():
        build_path.unlink()
    started_at = datetime.now(UTC)
    executed: list[str] = []
    try:
        with connect(build_path) as connection:
            connection.execute("SET preserve_insertion_order = false")
            connection.execute("SET threads = 4")
            for sql_path in sorted((PROJECT_ROOT / "sql" / "models").glob("*.sql")):
                connection.execute(_render_sql(sql_path, replacements))
                executed.append(sql_path.name)

            connection.execute(
                """
                CREATE OR REPLACE TABLE meta_source_file (
                    source_id VARCHAR,
                    version VARCHAR,
                    local_path VARCHAR,
                    size_bytes BIGINT,
                    expected_sha256 VARCHAR,
                    observed_sha256 VARCHAR,
                    hash_verified BOOLEAN,
                    schema_columns_json VARCHAR,
                    loaded_at_utc TIMESTAMP
                )
                """
            )
            connection.executemany(
                "INSERT INTO meta_source_file VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        item["source_id"],
                        item["version"],
                        item["path"],
                        item["size_bytes"],
                        item["expected_sha256"],
                        item["observed_sha256"],
                        item["hash_verified"],
                        json.dumps(item["schema_columns"]),
                        started_at,
                    )
                    for item in source_results
                ],
            )

            table_counts = {
                table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in (
                    "stg_achievement",
                    "stg_context",
                    "stg_crosswalk_admin",
                    "dim_district",
                    "mart_achievement",
                    "mart_context_snapshot",
                    "mart_data_coverage",
                    "mart_crosswalk_audit",
                    "mart_exclusion_audit",
                )
            }
            qa_results = run_qa(connection)
            if has_failures(qa_results):
                failed = [row["name"] for row in qa_results if row["status"] == "fail"]
                raise RuntimeError(f"QA failed; prior database preserved: {', '.join(failed)}")

        os.replace(build_path, db_path)
    finally:
        if build_path.exists():
            build_path.unlink()

    manifest = {
        "project": cfg["project"]["title"],
        "data_version": cfg["project"]["data_version"],
        "database": str(db_path),
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "git_commit": _git_commit(),
        "sql_models": executed,
        "table_counts": table_counts,
        "qa_checks_passed": sum(row["status"] == "pass" for row in qa_results),
        "qa_diagnostic_warnings": sum(row["status"] == "warn" for row in qa_results),
        "qa_checks_total": len(qa_results),
        "sources": [
            {
                key: item[key]
                for key in (
                    "source_id",
                    "version",
                    "size_bytes",
                    "expected_sha256",
                    "observed_sha256",
                    "hash_verified",
                    "column_count",
                )
            }
            for item in source_results
        ],
        "status": "success",
    }
    write_json(PROJECT_ROOT / "data" / "output" / "build_manifest.json", manifest)
    return manifest
