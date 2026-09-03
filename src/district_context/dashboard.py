from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from statistics import NormalDist
from typing import Any

import duckdb
import numpy as np

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

WORKBENCH_GRADES = tuple(range(3, 9))
VERSIONED_SITE_ASSETS = (
    "assets/styles.css",
    "data/dashboard-data.js",
    "assets/data-loader.js",
    "assets/dashboard.js",
    "assets/workbench.js",
    "assets/trends.js",
)


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


def _safe_workbench_assignment(grade: int, payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    serialized = (
        serialized.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    return (
        "window.SEDA_WORKBENCH_GRADES=window.SEDA_WORKBENCH_GRADES||{};"
        f"window.SEDA_WORKBENCH_GRADES[{grade}]={serialized};\n"
    )


def _safe_state_assignment(
    grade: int,
    state: str,
    payload: dict[str, Any],
) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    serialized = (
        serialized.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    state_key = json.dumps(state)
    return (
        "window.SEDA_ACHIEVEMENT_STATES=window.SEDA_ACHIEVEMENT_STATES||{};"
        f"window.SEDA_ACHIEVEMENT_STATES[{grade}]="
        f"window.SEDA_ACHIEVEMENT_STATES[{grade}]||{{}};"
        f"window.SEDA_ACHIEVEMENT_STATES[{grade}][{state_key}]={serialized};\n"
    )


def _achievement_rows_for_grade(
    connection: duckdb.DuckDBPyConnection,
    grade: int,
) -> list[tuple[Any, ...]]:
    return connection.execute(
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


def _achievement_rows_by_state(
    connection: duckdb.DuckDBPyConnection,
    grade: int,
) -> dict[str, list[tuple[Any, ...]]]:
    rows = connection.execute(
        """
        SELECT
            state_abbreviation,
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
        ORDER BY state_abbreviation, district_id, subject, year
        """,
        [grade],
    ).fetchall()
    grouped: dict[str, list[tuple[Any, ...]]] = {}
    for row in rows:
        grouped.setdefault(str(row[0]), []).append(row[1:])
    states = [
        str(row[0])
        for row in connection.execute(
            "SELECT DISTINCT state_abbreviation FROM dim_district ORDER BY state_abbreviation"
        ).fetchall()
    ]
    return {state: grouped.get(state, []) for state in states}


def _build_workbench_grade_payload(
    connection: duckdb.DuckDBPyConnection,
    grade: int,
    scope: dict[str, Any],
) -> dict[str, Any]:
    rows = _compact_rows(_achievement_rows_for_grade(connection, grade))
    return {
        "schema_version": 1,
        "release": scope["release"],
        "geography": scope["geography"],
        "subgroup": scope["subgroup"],
        "scale": scope["scale"],
        "grade": grade,
        "achievement_fields": ACHIEVEMENT_FIELDS,
        "row_count": len(rows),
        "achievement": rows,
    }


def _build_state_payload(
    *,
    grade: int,
    state: str,
    rows: list[tuple[Any, ...]],
    scope: dict[str, Any],
) -> dict[str, Any]:
    compact_rows = _compact_rows(rows)
    return {
        "schema_version": 1,
        "release": scope["release"],
        "geography": scope["geography"],
        "subgroup": scope["subgroup"],
        "scale": scope["scale"],
        "grade": grade,
        "state": state,
        "achievement_fields": ACHIEVEMENT_FIELDS,
        "row_count": len(compact_rows),
        "achievement": compact_rows,
    }


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


def _canonical_asset_digest(path: Path) -> str:
    canonical_bytes = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(canonical_bytes).hexdigest()[:16]


def _version_site_assets(destination: Path) -> None:
    index_path = destination / "index.html"
    html = index_path.read_text(encoding="utf-8")
    for relative_path in VERSIONED_SITE_ASSETS:
        asset_path = destination / relative_path
        digest = _canonical_asset_digest(asset_path)
        pattern = re.compile(
            rf'(?P<prefix>(?:src|href)="{re.escape(relative_path)})(?:\?v=[^"]*)?(?P<suffix>")'
        )
        html, replacements = pattern.subn(
            lambda match, asset_digest=digest: (
                f'{match.group("prefix")}?v={asset_digest}{match.group("suffix")}'
            ),
            html,
        )
        if replacements != 1:
            raise ValueError(
                f"Expected one versionable reference to {relative_path}; found {replacements}."
            )
    index_path.write_text(html, encoding="utf-8", newline="\n")


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
            total_enrollment_grades_3_8,
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

    workbench_grade_rows = dict(
        connection.execute(
            """
            SELECT grade, count(*)
            FROM mart_achievement
            WHERE grade BETWEEN 3 AND 8
            GROUP BY grade
            ORDER BY grade
            """
        ).fetchall()
    )
    workbench_years = [
        int(row[0])
        for row in connection.execute(
            """
            SELECT DISTINCT year
            FROM mart_achievement
            WHERE grade BETWEEN 3 AND 8
            ORDER BY year
            """
        ).fetchall()
    ]
    confidence_level = float(cfg["analysis"]["confidence_level"])
    workbench_scope = {
        "release": cfg["project"]["data_version"],
        "geography": "administrative district",
        "subgroup": "all students",
        "scale": f"Cohort Standardized ({cfg['project']['scale']})",
        "years": workbench_years,
        "confidence_level": confidence_level,
        "confidence_critical_value": NormalDist().inv_cdf(0.5 + confidence_level / 2),
    }

    robust_ranges = connection.execute(
        """
        SELECT
            quantile_cont(ln(1 + total_enrollment_grades_3_8), 0.95)
                - quantile_cont(ln(1 + total_enrollment_grades_3_8), 0.05),
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
        "workbench": workbench_scope,
        "grade": grade,
        "default_district_id": default_district_id,
        "catalog_fields": CATALOG_FIELDS,
        "context_fields": CONTEXT_FIELDS,
        "achievement_fields": ACHIEVEMENT_FIELDS,
        "catalog": _compact_rows(catalog_rows),
        "context": _compact_rows(context_rows),
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
            "published_achievement_rows": int(workbench_grade_rows.get(grade, 0)),
            "workbench_grade_rows": {
                str(row_grade): int(workbench_grade_rows.get(row_grade, 0))
                for row_grade in WORKBENCH_GRADES
            },
            "workbench_total_rows": int(sum(workbench_grade_rows.values())),
            "database_bytes": _file_size("data/processed/district_context.duckdb"),
            "offline_profile_bytes": _file_size(
                f"data/output/district_profile_{default_district_id}_grade_{grade}.html"
            ),
            "public_bundle_bytes": 0,
            "achievement_state_rows": {},
            "achievement_state_bundle_bytes": {},
            "achievement_state_public_data_bytes": 0,
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
    if grade != 4:
        raise ValueError(
            "The public dashboard uses grade 4 for its Explore view; "
            "grades 3 through 8 are generated as separate workbench bundles."
        )

    destination = destination or PROJECT_ROOT / "site"
    data_path = destination / "data" / "dashboard-data.js"
    data_path.parent.mkdir(parents=True, exist_ok=True)

    payload = _build_payload(
        connection,
        grade=grade,
        default_district_id=default_district_id,
    )

    workbench_bundle_bytes: dict[str, int] = {}
    for workbench_grade in WORKBENCH_GRADES:
        workbench_payload = _build_workbench_grade_payload(
            connection,
            workbench_grade,
            payload["workbench"],
        )
        workbench_path = destination / "data" / f"workbench-grade-{workbench_grade}.js"
        workbench_path.write_text(
            _safe_workbench_assignment(workbench_grade, workbench_payload),
            encoding="utf-8",
            newline="\n",
        )
        workbench_bundle_bytes[str(workbench_grade)] = workbench_path.stat().st_size

    state_rows = _achievement_rows_by_state(connection, grade)
    state_bundle_bytes: dict[str, int] = {}
    for state, rows in state_rows.items():
        state_payload = _build_state_payload(
            grade=grade,
            state=state,
            rows=rows,
            scope=payload["workbench"],
        )
        state_path = destination / "data" / f"achievement-grade-{grade}-{state}.js"
        state_path.write_text(
            _safe_state_assignment(grade, state, state_payload),
            encoding="utf-8",
            newline="\n",
        )
        state_bundle_bytes[state] = state_path.stat().st_size

    payload["technical"]["workbench_bundle_bytes"] = workbench_bundle_bytes
    payload["technical"]["workbench_public_data_bytes"] = sum(
        workbench_bundle_bytes.values()
    )
    payload["technical"]["achievement_state_rows"] = {
        state: len(rows) for state, rows in state_rows.items()
    }
    payload["technical"]["achievement_state_bundle_bytes"] = state_bundle_bytes
    payload["technical"]["achievement_state_public_data_bytes"] = sum(
        state_bundle_bytes.values()
    )
    for _ in range(5):
        script = _safe_javascript_assignment(payload)
        size = len(script.encode("utf-8"))
        payload["technical"]["public_bundle_bytes"] = size
        payload["technical"]["workbench_bundle_bytes"] = {
            str(bundle_grade): payload["technical"]["workbench_bundle_bytes"][
                str(bundle_grade)
            ]
            for bundle_grade in WORKBENCH_GRADES
        }
        payload["technical"]["workbench_public_data_bytes"] = sum(
            payload["technical"]["workbench_bundle_bytes"].values()
        )
    data_path.write_text(_safe_javascript_assignment(payload), encoding="utf-8", newline="\n")
    _version_site_assets(destination)
    return destination / "index.html"
