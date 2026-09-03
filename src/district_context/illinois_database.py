from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from district_context.config import PROJECT_ROOT
from district_context.database import _git_commit, _render_sql, _sql_literal
from district_context.illinois_grade4 import build_grade4_extract
from district_context.utils import write_json


def illinois_database_path() -> Path:
    return PROJECT_ROOT / "data" / "processed" / "illinois_grade4.duckdb"


def _qa(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    checks = [
        (
            "unique_school_year_grade_subject",
            """
            SELECT count(*) - count(DISTINCT
                concat(report_card_year, '|', rcdts, '|', grade, '|', subject))
            FROM mart_illinois_grade4_school_year
            """,
        ),
        ("grade_is_four", "SELECT count(*) FROM stg_illinois_grade4 WHERE grade <> 4"),
        (
            "subjects_are_ela_or_math",
            "SELECT count(*) FROM stg_illinois_grade4 WHERE subject NOT IN ('ela', 'math')",
        ),
        (
            "reported_rates_have_values",
            """
            SELECT count(*) FROM stg_illinois_grade4
            WHERE (proficiency_status = 'reported' AND proficiency_rate IS NULL)
               OR (growth_status = 'reported' AND growth_percentile IS NULL)
            """,
        ),
        (
            "metric_ranges",
            """
            SELECT count(*) FROM stg_illinois_grade4
            WHERE proficiency_rate NOT BETWEEN 0 AND 100
               OR participation_rate NOT BETWEEN 0 AND 100
               OR growth_percentile NOT BETWEEN 1 AND 99
               OR mobility_rate NOT BETWEEN 0 AND 100
               OR chronic_absenteeism_rate NOT BETWEEN 0 AND 100
               OR chronic_absenteeism_grade4_rate NOT BETWEEN 0 AND 100
            """,
        ),
        (
            "grade4_growth_only_published_in_2025",
            """
            SELECT count(*) FROM stg_illinois_grade4
            WHERE report_card_year < 2025 AND growth_status <> 'not_published'
            """,
        ),
        (
            "north_palos_expected_grade4_rows",
            """
            SELECT abs(count(*) - 16) FROM stg_illinois_grade4
            WHERE district_name = 'North Palos SD 117'
            """,
        ),
        (
            "north_palos_expected_school_roster",
            """
            SELECT abs(count(*) - 5) FROM dim_illinois_school
            WHERE district_name = 'North Palos SD 117'
            """,
        ),
    ]
    results = []
    for name, query in checks:
        failures = int(connection.execute(query).fetchone()[0])
        results.append(
            {"name": name, "failures": failures, "status": "pass" if failures == 0 else "fail"}
        )
    return results


def build_illinois_database(*, rebuild_extract: bool = False) -> dict[str, Any]:
    csv_path = PROJECT_ROOT / "data" / "processed" / "illinois_grade4_school_year.csv"
    roster_path = PROJECT_ROOT / "data" / "processed" / "illinois_school_roster.csv"
    if rebuild_extract or not csv_path.is_file() or not roster_path.is_file():
        build_grade4_extract()

    db_path = illinois_database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    build_path = db_path.with_name(f"{db_path.stem}.building{db_path.suffix}")
    if build_path.exists():
        build_path.unlink()

    started_at = datetime.now(UTC)
    executed: list[str] = []
    try:
        with duckdb.connect(str(build_path)) as connection:
            connection.execute("SET preserve_insertion_order = false")
            connection.execute("SET threads = 4")
            replacements = {
                "grade4_csv_path": _sql_literal(csv_path),
                "school_roster_csv_path": _sql_literal(roster_path),
            }
            for sql_path in sorted((PROJECT_ROOT / "sql" / "illinois").glob("*.sql")):
                connection.execute(_render_sql(sql_path, replacements))
                executed.append(sql_path.name)

            extract_manifest_path = (
                PROJECT_ROOT / "data" / "output" / "illinois_grade4_build_manifest.json"
            )
            extract_manifest = (
                json.loads(extract_manifest_path.read_text(encoding="utf-8"))
                if extract_manifest_path.is_file()
                else {}
            )
            connection.execute(
                """
                CREATE OR REPLACE TABLE meta_illinois_build AS
                SELECT ?::TIMESTAMP AS built_at_utc,
                       ?::VARCHAR AS source_csv,
                       ?::VARCHAR AS source_manifest_json
                """,
                [
                    started_at.replace(tzinfo=None),
                    str(csv_path),
                    json.dumps(extract_manifest),
                ],
            )
            qa = _qa(connection)
            failed = [item["name"] for item in qa if item["status"] == "fail"]
            if failed:
                raise RuntimeError(f"Illinois DuckDB QA failed: {', '.join(failed)}")
            tables = [row[0] for row in connection.execute("SHOW TABLES").fetchall()]
            table_counts = {
                table: int(connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0])
                for table in tables
            }

        os.replace(build_path, db_path)
    finally:
        if build_path.exists():
            build_path.unlink()

    manifest = {
        "built_at_utc": started_at.isoformat(),
        "database": str(db_path),
        "git_commit": _git_commit(),
        "source_csv": str(csv_path),
        "sql_models": executed,
        "table_counts": table_counts,
        "qa": qa,
        "status": "success",
    }
    write_json(
        PROJECT_ROOT / "data" / "output" / "illinois_grade4_database_manifest.json",
        manifest,
    )
    return manifest
