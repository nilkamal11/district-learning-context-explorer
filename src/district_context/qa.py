from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import duckdb

from district_context.config import PROJECT_ROOT, output_dir

CHECKS = [
    {
        "name": "achievement_key_is_unique",
        "severity": "error",
        "sql": """
            SELECT count(*) FROM (
                SELECT district_id, subject, grade, year, count(*) AS n
                FROM stg_achievement
                GROUP BY ALL
                HAVING count(*) > 1
            )
        """,
        "expected": 0,
    },
    {
        "name": "context_key_is_unique",
        "severity": "error",
        "sql": """
            SELECT count(*) FROM (
                SELECT district_id, year, count(*) AS n
                FROM stg_context
                GROUP BY ALL
                HAVING count(*) > 1
            )
        """,
        "expected": 0,
    },
    {
        "name": "crosswalk_source_year_key_is_unique",
        "severity": "error",
        "sql": """
            SELECT count(*) FROM (
                SELECT source_district_id, year, count(*) AS n
                FROM stg_crosswalk_admin
                GROUP BY ALL
                HAVING count(*) > 1
            )
        """,
        "expected": 0,
    },
    {
        "name": "district_ids_are_seven_digits",
        "severity": "error",
        "sql": """
            SELECT count(*) FROM dim_district
            WHERE NOT regexp_full_match(district_id, '[0-9]{7}')
        """,
        "expected": 0,
    },
    {
        "name": "mart_has_no_2020_or_2021_results",
        "severity": "error",
        "sql": "SELECT count(*) FROM mart_achievement WHERE year IN (2020, 2021)",
        "expected": 0,
    },
    {
        "name": "achievement_year_domain_matches_release",
        "severity": "error",
        "sql": """
            WITH expected(year) AS (
                VALUES (2009), (2010), (2011), (2012), (2013), (2014), (2015),
                       (2016), (2017), (2018), (2019), (2022), (2023), (2024), (2025)
            ), actual AS (
                SELECT DISTINCT year FROM stg_achievement
            )
            SELECT count(*)
            FROM expected
            FULL OUTER JOIN actual USING (year)
            WHERE expected.year IS NULL OR actual.year IS NULL
        """,
        "expected": 0,
    },
    {
        "name": "achievement_subjects_are_expected",
        "severity": "error",
        "sql": "SELECT count(*) FROM mart_achievement WHERE subject NOT IN ('mth', 'rla')",
        "expected": 0,
    },
    {
        "name": "achievement_subject_domain_is_complete",
        "severity": "error",
        "sql": """
            SELECT CASE WHEN count(DISTINCT subject) = 2 THEN 0 ELSE 1 END
            FROM mart_achievement
        """,
        "expected": 0,
    },
    {
        "name": "achievement_grades_are_expected",
        "severity": "error",
        "sql": "SELECT count(*) FROM mart_achievement WHERE grade NOT BETWEEN 3 AND 8",
        "expected": 0,
    },
    {
        "name": "standard_errors_are_nonnegative",
        "severity": "error",
        "sql": """
            SELECT count(*) FROM mart_achievement
            WHERE standard_error_within_state < 0 OR standard_error_cross_state < 0
        """,
        "expected": 0,
    },
    {
        "name": "released_rows_meet_disclosure_bounds",
        "severity": "error",
        "sql": """
            SELECT count(*) FROM mart_achievement
            WHERE tested_count < 20
               OR standard_error_within_state >= 1
               OR standard_error_cross_state >= 1
        """,
        "expected": 0,
    },
    {
        "name": "context_shares_stay_in_range",
        "severity": "error",
        "sql": """
            SELECT count(*) FROM mart_context_snapshot
            WHERE share_city NOT BETWEEN 0 AND 1
               OR share_suburb NOT BETWEEN 0 AND 1
               OR share_town NOT BETWEEN 0 AND 1
               OR share_rural NOT BETWEEN 0 AND 1
               OR share_native_american NOT BETWEEN 0 AND 1
               OR share_asian NOT BETWEEN 0 AND 1
               OR share_hispanic NOT BETWEEN 0 AND 1
               OR share_black NOT BETWEEN 0 AND 1
               OR share_white NOT BETWEEN 0 AND 1
               OR share_other_race_ethnicity NOT BETWEEN 0 AND 1
               OR family_poverty_rate NOT BETWEEN 0 AND 1
        """,
        "expected": 0,
    },
    {
        "name": "released_locale_differs_from_share_argmax",
        "severity": "warning",
        "sql": """
            SELECT count(*)
            FROM mart_context_snapshot
            WHERE is_default_context_year
              AND dominant_locale IS NOT NULL
              AND share_argmax_locale IS NOT NULL
              AND dominant_locale <> share_argmax_locale
        """,
        "expected": 0,
    },
    {
        "name": "default_context_year_has_usable_districts",
        "severity": "error",
        "sql": """
            SELECT CASE WHEN count(*) >= 5000 THEN 0 ELSE 1 END
            FROM mart_context_snapshot
            WHERE is_default_context_year AND has_core_peer_context AND serves_grade_4
        """,
        "expected": 0,
    },
    {
        "name": "peer_match_features_have_variation",
        "severity": "error",
        "sql": """
            SELECT CASE
                WHEN stddev_pop(ln(1 + enrollment_grades_3_8)) > 0
                 AND stddev_pop(family_poverty_rate) > 0
                 AND stddev_pop(socioeconomic_status_composite) > 0
                 AND stddev_pop(share_native_american) > 0
                 AND stddev_pop(share_asian) > 0
                 AND stddev_pop(share_hispanic) > 0
                 AND stddev_pop(share_black) > 0
                 AND stddev_pop(share_white) > 0
                 AND stddev_pop(share_city) > 0
                 AND stddev_pop(share_suburb) > 0
                 AND stddev_pop(share_town) > 0
                 AND stddev_pop(share_rural) > 0
                 AND count(DISTINCT dominant_locale) = 4
                THEN 0 ELSE 1
            END
            FROM mart_context_snapshot
            WHERE is_default_context_year AND has_core_peer_context AND serves_grade_4
        """,
        "expected": 0,
    },
    {
        "name": "composition_vectors_have_plausible_totals",
        "severity": "error",
        "sql": """
            SELECT count(*)
            FROM mart_context_snapshot
            WHERE is_default_context_year AND has_core_peer_context AND serves_grade_4
              AND (
                  share_native_american + share_asian + share_hispanic
                  + share_black + share_white <= 0
                  OR share_native_american + share_asian + share_hispanic
                     + share_black + share_white > 1.02
              )
        """,
        "expected": 0,
    },
    {
        "name": "crosswalk_contains_stable_id_changes",
        "severity": "error",
        "sql": """
            SELECT CASE WHEN count(*) > 0 THEN 0 ELSE 1 END
            FROM stg_crosswalk_admin
            WHERE source_district_id <> stable_district_id
        """,
        "expected": 0,
    },
    {
        "name": "coverage_mart_key_is_unique",
        "severity": "error",
        "sql": """
            SELECT count(*) FROM (
                SELECT state_abbreviation, year, grade, subject, count(*) AS n
                FROM mart_data_coverage
                GROUP BY ALL
                HAVING count(*) > 1
            )
        """,
        "expected": 0,
    },
    {
        "name": "multi_component_rows_are_explicitly_excluded",
        "severity": "warning",
        "sql": """
            SELECT count(*)
            FROM stg_achievement
            WHERE coalesce(multi_component_flag, 0) = 1
        """,
        "expected": 0,
    },
    {
        "name": "released_achievement_volume_is_plausible",
        "severity": "error",
        "sql": "SELECT CASE WHEN count(*) >= 1000000 THEN 0 ELSE 1 END FROM mart_achievement",
        "expected": 0,
    },
]


def run_qa(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    checked_at = datetime.now(UTC)
    results: list[dict[str, Any]] = []
    for check in CHECKS:
        observed = connection.execute(check["sql"]).fetchone()[0]
        status = (
            "pass"
            if observed == check["expected"]
            else ("warn" if check["severity"] == "warning" else "fail")
        )
        results.append(
            {
                "name": check["name"],
                "severity": check["severity"],
                "status": status,
                "observed": int(observed),
                "expected": int(check["expected"]),
                "checked_at_utc": checked_at.isoformat(),
            }
        )

    connection.execute(
        """
        CREATE OR REPLACE TABLE qa_result (
            name VARCHAR,
            severity VARCHAR,
            status VARCHAR,
            observed BIGINT,
            expected BIGINT,
            checked_at_utc TIMESTAMP
        )
        """
    )
    connection.executemany(
        "INSERT INTO qa_result VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                row["name"],
                row["severity"],
                row["status"],
                row["observed"],
                row["expected"],
                checked_at,
            )
            for row in results
        ],
    )
    _write_qa_outputs(results)
    return results


def _write_qa_outputs(results: list[dict[str, Any]]) -> None:
    target = output_dir() / "qa_results.json"
    target.write_text(json.dumps(results, indent=2), encoding="utf-8")
    passes = sum(row["status"] == "pass" for row in results)
    lines = [
        "# Data quality summary",
        "",
        f"**Status:** {passes} of {len(results)} checks passed.",
        "",
        "| Check | Severity | Status | Observed | Expected |",
        "|---|---:|---:|---:|---:|",
    ]
    lines.extend(
        f"| `{row['name']}` | {row['severity']} | {row['status']} | "
        f"{row['observed']:,} | {row['expected']:,} |"
        for row in results
    )
    (output_dir() / "qa_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    public_summary = PROJECT_ROOT / "reports" / "qa_check_catalog.md"
    if not public_summary.exists():
        public_summary.write_text(
            "# Quality-control catalog\n\n"
            "The executable checks are defined in `src/district_context/qa.py`. "
            "Run results remain local because they are tied to source data that this repository "
            "does not redistribute.\n",
            encoding="utf-8",
        )


def has_failures(results: list[dict[str, Any]]) -> bool:
    return any(row["status"] == "fail" and row["severity"] == "error" for row in results)
