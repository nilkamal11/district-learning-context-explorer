from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
from plotly.offline.offline import get_plotlyjs

from district_context.config import PROJECT_ROOT, project_config, source_config

CATALOG_FIELDS = [
    "district_id",
    "district_name",
    "state",
    "first_year",
    "last_year",
    "has_context",
    "serves_grade",
    "has_core_context",
    "has_math",
    "has_reading",
]

CONTEXT_FIELDS = [
    "district_id",
    "district_name",
    "state",
    "grade_low",
    "grade_high",
    "grade_span",
    "locale",
    "enrollment",
    "poverty",
    "ses",
    "native_american",
    "asian",
    "hispanic",
    "black",
    "white",
    "other_race_ethnicity",
    "city",
    "suburb",
    "town",
    "rural",
    "has_core_context",
]

ACHIEVEMENT_FIELDS = [
    "district_id",
    "subject",
    "year",
    "estimate",
    "standard_error_within_state",
    "standard_error_cross_state",
    "tested_count",
    "tested_count_estimated",
]


def _compact_number(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (float, np.floating)):
        if np.isnan(value):
            return None
        return round(float(value), 6)
    if isinstance(value, np.integer):
        return int(value)
    return value


def _compact_rows(rows: list[tuple[Any, ...]]) -> list[list[Any]]:
    return [[_compact_number(value) for value in row] for row in rows]


def _safe_javascript_assignment(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    serialized = (
        serialized.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    return f"window.DISTRICT_DASHBOARD_DATA={serialized};\n"


def _software_test_count() -> int:
    fallback = sum(
        line.lstrip().startswith("def test_")
        for path in (PROJECT_ROOT / "tests").glob("test_*.py")
        for line in path.read_text(encoding="utf-8").splitlines()
    )
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    summary_match = re.search(r"(\d+) tests? collected", result.stdout)
    file_counts = re.findall(r":\s*(\d+)\s*$", result.stdout, flags=re.MULTILINE)
    if result.returncode == 0 and summary_match:
        return int(summary_match.group(1))
    if result.returncode == 0 and file_counts:
        return sum(int(count) for count in file_counts)
    return fallback


def _file_size(relative_path: str) -> int | None:
    path = PROJECT_ROOT / relative_path
    return path.stat().st_size if path.is_file() else None


def _build_payload(
    connection: duckdb.DuckDBPyConnection,
    *,
    grade: int,
    default_district_id: str,
) -> dict[str, Any]:
    cfg = project_config()
    sources = source_config()
    context_year = int(cfg["analysis"]["context_year"])

    catalog_rows = connection.execute(
        """
        WITH subject_flags AS (
            SELECT
                district_id,
                bool_or(subject = 'mth') AS has_math,
                bool_or(subject = 'rla') AS has_reading
            FROM mart_achievement
            WHERE grade = ?
            GROUP BY district_id
        ), context AS (
            SELECT *
            FROM mart_context_snapshot
            WHERE year = ?
        )
        SELECT
            d.district_id,
            coalesce(c.district_name, d.district_name) AS district_name,
            coalesce(c.state_abbreviation, d.state_abbreviation) AS state,
            d.first_year,
            d.last_year,
            c.district_id IS NOT NULL AS has_context,
            coalesce(c.grade_low <= ? AND c.grade_high >= ?, false) AS serves_grade,
            coalesce(c.has_core_peer_context, false) AS has_core_context,
            coalesce(f.has_math, false) AS has_math,
            coalesce(f.has_reading, false) AS has_reading
        FROM dim_district AS d
        LEFT JOIN context AS c USING (district_id)
        LEFT JOIN subject_flags AS f USING (district_id)
        ORDER BY state, district_name, district_id
        """,
        [grade, context_year, grade, grade],
    ).fetchall()

    context_rows = connection.execute(
        """
        SELECT
            district_id,
            district_name,
            state_abbreviation,
            grade_low,
            grade_high,
            grade_span_bucket,
            dominant_locale,
            enrollment_grades_3_8,
            family_poverty_rate,
            socioeconomic_status_composite,
            share_native_american,
            share_asian,
            share_hispanic,
            share_black,
            share_white,
            share_other_race_ethnicity,
            share_city,
            share_suburb,
            share_town,
            share_rural,
            has_core_peer_context
        FROM mart_context_snapshot
        WHERE year = ?
        ORDER BY district_id
        """,
        [context_year],
    ).fetchall()

    achievement_rows = connection.execute(
        """
        SELECT
            district_id,
            subject,
            year,
            achievement_cs,
            standard_error_within_state,
            standard_error_cross_state,
            tested_count,
            tested_count_estimated_flag
        FROM mart_achievement
        WHERE grade = ?
        ORDER BY district_id, subject, year
        """,
        [grade],
    ).fetchall()

    robust_ranges = connection.execute(
        """
        SELECT
            quantile_cont(ln(1 + enrollment_grades_3_8), 0.95)
                - quantile_cont(ln(1 + enrollment_grades_3_8), 0.05),
            quantile_cont(family_poverty_rate, 0.95)
                - quantile_cont(family_poverty_rate, 0.05),
            quantile_cont(socioeconomic_status_composite, 0.95)
                - quantile_cont(socioeconomic_status_composite, 0.05)
        FROM mart_context_snapshot
        WHERE year = ?
          AND has_core_peer_context
          AND grade_low <= ? AND grade_high >= ?
        """,
        [context_year, grade, grade],
    ).fetchone()

    table_names = [
        "stg_achievement",
        "stg_context",
        "stg_crosswalk_admin",
        "dim_district",
        "mart_achievement",
        "mart_context_snapshot",
        "mart_data_coverage",
        "mart_crosswalk_audit",
        "mart_exclusion_audit",
    ]
    table_counts = {
        name: connection.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        for name in table_names
    }
    source_rows = connection.execute(
        """
        SELECT source_id, version, size_bytes, expected_sha256, observed_sha256,
               hash_verified, json_array_length(schema_columns_json) AS column_count
        FROM meta_source_file
        ORDER BY source_id
        """
    ).fetchall()
    qa_rows = connection.execute(
        """
        SELECT name, severity, status, observed, expected
        FROM qa_result
        ORDER BY name
        """
    ).fetchall()
    changed_ids = connection.execute(
        "SELECT coalesce(sum(changed_stable_ids), 0) FROM mart_crosswalk_audit"
    ).fetchone()[0]
    eligible_count = connection.execute(
        """
        SELECT count(*)
        FROM mart_context_snapshot
        WHERE year = ?
          AND has_core_peer_context
          AND grade_low <= ? AND grade_high >= ?
        """,
        [context_year, grade, grade],
    ).fetchone()[0]

    configured_sources = {
        source_id: {
            "title": item["title"],
            "persistent_id": item["persistent_id"],
        }
        for source_id, item in sources.items()
    }
    source_payload = []
    for (
        source_id,
        version,
        size_bytes,
        expected_hash,
        observed_hash,
        verified,
        columns,
    ) in source_rows:
        source_payload.append(
            {
                "source_id": source_id,
                "version": version,
                "size_bytes": int(size_bytes),
                "expected_sha256": expected_hash,
                "observed_sha256": observed_hash,
                "hash_verified": bool(verified),
                "column_count": int(columns),
                **configured_sources[source_id],
            }
        )

    sql_models = [path.name for path in sorted((PROJECT_ROOT / "sql" / "models").glob("*.sql"))]
    qa_payload = [
        {
            "name": name,
            "severity": severity,
            "status": status,
            "observed": int(observed),
            "expected": int(expected),
        }
        for name, severity, status, observed, expected in qa_rows
    ]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "project": cfg["project"],
        "grade": grade,
        "default_district_id": default_district_id,
        "catalog_fields": CATALOG_FIELDS,
        "context_fields": CONTEXT_FIELDS,
        "achievement_fields": ACHIEVEMENT_FIELDS,
        "catalog": _compact_rows(catalog_rows),
        "context": _compact_rows(context_rows),
        "achievement": _compact_rows(achievement_rows),
        "model": {
            "analysis": cfg["analysis"],
            "peer_model": cfg["peer_model"],
            "robust_ranges": {
                "log_enrollment": _compact_number(robust_ranges[0]),
                "family_poverty_rate": _compact_number(robust_ranges[1]),
                "socioeconomic_status_composite": _compact_number(robust_ranges[2]),
            },
        },
        "technical": {
            "sources": source_payload,
            "source_total_bytes": sum(row["size_bytes"] for row in source_payload),
            "table_counts": table_counts,
            "changed_source_stable_id_mappings": int(changed_ids),
            "sql_models": sql_models,
            "persisted_table_count": int(
                connection.execute(
                    "SELECT count(*) FROM information_schema.tables WHERE table_schema='main'"
                ).fetchone()[0]
            ),
            "software_test_count": _software_test_count(),
            "qa": qa_payload,
            "qa_pass_count": sum(row["status"] == "pass" for row in qa_payload),
            "qa_warning_count": sum(row["status"] == "warn" for row in qa_payload),
            "eligible_match_districts": int(eligible_count),
            "published_catalog_rows": len(catalog_rows),
            "published_context_rows": len(context_rows),
            "published_achievement_rows": len(achievement_rows),
            "database_bytes": _file_size("data/processed/district_context.duckdb"),
            "offline_profile_bytes": _file_size(
                f"data/output/district_profile_{default_district_id}_grade_{grade}.html"
            ),
            "public_bundle_bytes": 0,
            "first_quoted_name_failure_line": 1_236_002,
            "publication_note": (
                "The project owner confirmed Stanford permission for this Git portfolio use. "
                "Raw source files and the local DuckDB database are not redistributed."
            ),
        },
    }
    return payload


def build_dashboard(
    connection: duckdb.DuckDBPyConnection,
    *,
    grade: int,
    default_district_id: str,
    destination: Path | None = None,
) -> Path:
    destination = destination or PROJECT_ROOT / "site"
    data_path = destination / "data" / "dashboard-data.js"
    vendor_path = destination / "assets" / "plotly-3.1.0.min.js"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    vendor_path.parent.mkdir(parents=True, exist_ok=True)

    payload = _build_payload(
        connection,
        grade=grade,
        default_district_id=default_district_id,
    )
    for _ in range(3):
        script = _safe_javascript_assignment(payload)
        size = len(script.encode("utf-8"))
        if payload["technical"]["public_bundle_bytes"] == size:
            break
        payload["technical"]["public_bundle_bytes"] = size
    data_path.write_text(_safe_javascript_assignment(payload), encoding="utf-8", newline="\n")
    vendor_path.write_text(get_plotlyjs(), encoding="utf-8", newline="\n")
    return destination / "index.html"
