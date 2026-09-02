from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
from statistics import NormalDist
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "site" / "data" / "dashboard-data.js"
PREFIX = "window.DISTRICT_DASHBOARD_DATA="
SUFFIX = ";\n"
INITIAL_GRADE = 4
WORKBENCH_GRADES = tuple(range(3, 9))
LAZY_WORKBENCH_GRADES = tuple(grade for grade in WORKBENCH_GRADES if grade != INITIAL_GRADE)

CATALOG_FIELDS = (
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
)
CONTEXT_FIELDS = (
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
)
ACHIEVEMENT_FIELDS = (
    "district_id",
    "subject",
    "year",
    "estimate",
    "standard_error_within_state",
    "standard_error_cross_state",
    "tested_count",
    "tested_count_estimated",
)
MAIN_KEYS = {
    "schema_version",
    "generated_at_utc",
    "project",
    "workbench",
    "grade",
    "default_district_id",
    "catalog_fields",
    "context_fields",
    "achievement_fields",
    "catalog",
    "context",
    "achievement",
    "model",
    "technical",
}
WORKBENCH_CONFIG_KEYS = {
    "release",
    "geography",
    "subgroup",
    "scale",
    "years",
    "confidence_level",
    "confidence_critical_value",
}
WORKBENCH_KEYS = {
    "schema_version",
    "release",
    "geography",
    "subgroup",
    "scale",
    "grade",
    "achievement_fields",
    "row_count",
    "achievement",
}
MODEL_KEYS = {"analysis", "peer_model", "robust_ranges"}
TECHNICAL_KEYS = {
    "sources",
    "source_total_bytes",
    "table_counts",
    "changed_source_stable_id_mappings",
    "sql_models",
    "persisted_table_count",
    "software_test_count",
    "qa",
    "qa_pass_count",
    "qa_warning_count",
    "eligible_match_districts",
    "published_catalog_rows",
    "published_context_rows",
    "published_achievement_rows",
    "workbench_grade_rows",
    "workbench_total_rows",
    "database_bytes",
    "offline_profile_bytes",
    "public_bundle_bytes",
    "first_quoted_name_failure_line",
    "publication_note",
    "workbench_bundle_bytes",
    "workbench_public_data_bytes",
}
SOURCE_KEYS = {
    "source_id",
    "version",
    "size_bytes",
    "expected_sha256",
    "observed_sha256",
    "hash_verified",
    "column_count",
    "title",
    "persistent_id",
}
QA_KEYS = {"name", "severity", "status", "observed", "expected"}
TABLE_COUNT_KEYS = {
    "stg_achievement",
    "stg_context",
    "stg_crosswalk_admin",
    "dim_district",
    "mart_achievement",
    "mart_context_snapshot",
    "mart_data_coverage",
    "mart_crosswalk_audit",
    "mart_exclusion_audit",
}

# Approved public row contracts for the three pinned SEDA 2025.2 source files.
# A source or transformation change must update these deliberately before publication.
EXPECTED_CATALOG_ROWS = 19_461
EXPECTED_CONTEXT_ROWS = 17_852
EXPECTED_GRADE_ROWS = {
    3: 313_372,
    4: 311_427,
    5: 323_925,
    6: 321_292,
    7: 289_152,
    8: 268_216,
}
EXPECTED_YEARS = frozenset((*range(2009, 2020), *range(2022, 2026)))
EXPECTED_SUBJECTS = frozenset({"mth", "rla"})
EXPECTED_STATES = frozenset(
    {
        "AK",
        "AL",
        "AR",
        "AZ",
        "CA",
        "CO",
        "CT",
        "DC",
        "DE",
        "FL",
        "GA",
        "HI",
        "IA",
        "ID",
        "IL",
        "IN",
        "KS",
        "KY",
        "LA",
        "MA",
        "MD",
        "ME",
        "MI",
        "MN",
        "MO",
        "MS",
        "MT",
        "NC",
        "ND",
        "NE",
        "NH",
        "NJ",
        "NM",
        "NV",
        "NY",
        "OH",
        "OK",
        "OR",
        "PA",
        "RI",
        "SC",
        "SD",
        "TN",
        "TX",
        "UT",
        "VA",
        "VT",
        "WA",
        "WI",
        "WV",
        "WY",
    }
)
EXPECTED_SOURCE_BYTES = {
    "seda_achievement": 1_026_013_873,
    "seda_context": 151_936_891,
    "seda_crosswalk": 32_851_173,
}
EXPECTED_SOURCE_COLUMNS = {
    "seda_achievement": 103,
    "seda_context": 99,
    "seda_crosswalk": 13,
}
FORBIDDEN_MARKERS = (
    "C:\\Users\\",
    "source_row_hash",
    "seda_admindist_long_cs_2025.2.csv",
    "seda_cov_admindist_annual_2025.2.csv",
    "seda_crosswalk_2025.2.csv",
)
DISTRICT_ID_PATTERN = re.compile(r"\d{7}")
STATE_PATTERN = re.compile(r"[A-Z]{2}")
VERSIONED_SITE_ASSETS = (
    "assets/styles.css",
    "data/dashboard-data.js",
    "assets/plotly-3.1.0.min.js",
    "assets/dashboard.js",
    "assets/workbench.js",
)


def _fail(message: str) -> None:
    raise SystemExit(message)


def _canonical_asset_digest(path: Path) -> str:
    canonical_bytes = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(canonical_bytes).hexdigest()[:16]


def _exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(f"{label} must be an object")
    actual = set(value)
    if actual != expected:
        _fail(
            f"{label} fields differ from the approved contract; "
            f"missing={sorted(expected - actual)}, unexpected={sorted(actual - expected)}"
        )
    return value


def _is_number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _read_assignment(path: Path, prefix: str, label: str) -> tuple[dict[str, Any], int]:
    script = path.read_text(encoding="utf-8")
    if not script.startswith(prefix) or not script.endswith(SUFFIX):
        _fail(f"{label} does not use the expected inert assignment wrapper")
    size = path.stat().st_size
    if size >= 95_000_000:
        _fail(f"{label} is too close to GitHub's per-file size limit")
    exposed = [marker for marker in FORBIDDEN_MARKERS if marker in script]
    if exposed:
        _fail(f"{label} contains forbidden local/source detail: {exposed}")
    try:
        payload = json.loads(script[len(prefix) : -len(SUFFIX)])
    except json.JSONDecodeError as exc:
        _fail(f"{label} is not valid JSON: {exc}")
    if not isinstance(payload, dict):
        _fail(f"{label} payload must be an object")
    return payload, size


def _validate_catalog(rows: Any) -> tuple[set[str], dict[str, tuple[str, str]]]:
    if not isinstance(rows, list) or len(rows) != EXPECTED_CATALOG_ROWS:
        _fail(f"Catalog must contain exactly {EXPECTED_CATALOG_ROWS:,} rows")
    ids: set[str] = set()
    lookup: dict[str, tuple[str, str]] = {}
    states: set[str] = set()
    for row_number, row in enumerate(rows, start=1):
        if not isinstance(row, list) or len(row) != len(CATALOG_FIELDS):
            _fail(f"Catalog row {row_number} does not have {len(CATALOG_FIELDS)} fields")
        district_id, name, state, first_year, last_year, *flags = row
        if not isinstance(district_id, str) or not DISTRICT_ID_PATTERN.fullmatch(district_id):
            _fail(f"Catalog row {row_number} has an invalid district_id")
        if district_id in ids:
            _fail(f"Catalog contains duplicate district_id {district_id}")
        if not isinstance(name, str) or not name.strip():
            _fail(f"Catalog district {district_id} has an invalid name")
        if not isinstance(state, str) or not STATE_PATTERN.fullmatch(state):
            _fail(f"Catalog district {district_id} has an invalid state")
        if type(first_year) is not int or not 2009 <= first_year <= 2025:
            _fail(f"Catalog district {district_id} has an invalid first_year")
        if type(last_year) is not int or not 2009 <= last_year <= 2025 or first_year > last_year:
            _fail(f"Catalog district {district_id} has an invalid last_year")
        if any(type(flag) is not bool for flag in flags):
            _fail(f"Catalog district {district_id} has a non-boolean availability flag")
        ids.add(district_id)
        lookup[district_id] = (name, state)
        states.add(state)
    if states != EXPECTED_STATES:
        _fail(f"Catalog state domain differs from the approved contract: {sorted(states)}")
    return ids, lookup


def _validate_context(rows: Any, catalog: dict[str, tuple[str, str]]) -> None:
    if not isinstance(rows, list) or len(rows) != EXPECTED_CONTEXT_ROWS:
        _fail(f"Context must contain exactly {EXPECTED_CONTEXT_ROWS:,} rows")
    fields = {field: index for index, field in enumerate(CONTEXT_FIELDS)}
    ids: set[str] = set()
    states: set[str] = set()
    bounded_shares = (
        "poverty",
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
    )
    race_fields = (
        "native_american",
        "asian",
        "hispanic",
        "black",
        "white",
        "other_race_ethnicity",
    )
    locale_fields = ("city", "suburb", "town", "rural")
    for row_number, row in enumerate(rows, start=1):
        if not isinstance(row, list) or len(row) != len(CONTEXT_FIELDS):
            _fail(f"Context row {row_number} does not have {len(CONTEXT_FIELDS)} fields")
        district_id = row[fields["district_id"]]
        name = row[fields["district_name"]]
        state = row[fields["state"]]
        if not isinstance(district_id, str) or not DISTRICT_ID_PATTERN.fullmatch(district_id):
            _fail(f"Context row {row_number} has an invalid district_id")
        if district_id in ids:
            _fail(f"Context contains duplicate district_id {district_id}")
        if district_id not in catalog:
            _fail(f"Context district {district_id} is absent from the catalog")
        if (name, state) != catalog[district_id]:
            _fail(f"Context identity disagrees with catalog for district {district_id}")
        grade_low = row[fields["grade_low"]]
        grade_high = row[fields["grade_high"]]
        if grade_low is not None and (type(grade_low) is not int or not -1 <= grade_low <= 12):
            _fail(f"Context district {district_id} has an invalid grade_low")
        if grade_high is not None and (
            type(grade_high) is not int or not -1 <= grade_high <= 12
        ):
            _fail(f"Context district {district_id} has an invalid grade_high")
        if grade_low is not None and grade_high is not None and grade_low > grade_high:
            _fail(f"Context district {district_id} has a reversed grade span")
        if row[fields["grade_span"]] not in {"elementary_or_k8", "unified_or_k12", "other"}:
            _fail(f"Context district {district_id} has an invalid grade_span")
        if row[fields["locale"]] not in {"City", "Suburb", "Town", "Rural"}:
            _fail(f"Context district {district_id} has an invalid locale")
        enrollment = row[fields["enrollment"]]
        if not _is_number(enrollment) or enrollment < 0:
            _fail(f"Context district {district_id} has an invalid enrollment")
        ses = row[fields["ses"]]
        if ses is not None and not _is_number(ses):
            _fail(f"Context district {district_id} has an invalid SES value")
        for field in bounded_shares:
            value = row[fields[field]]
            if value is not None and (not _is_number(value) or not 0 <= value <= 1):
                _fail(f"Context district {district_id} has an invalid {field} value")
        if type(row[fields["has_core_context"]]) is not bool:
            _fail(f"Context district {district_id} has a non-boolean core-context flag")
        race_values = [row[fields[field]] for field in race_fields]
        if all(value is not None for value in race_values) and not 0.98 <= sum(race_values) <= 1.02:
            _fail(f"Context district {district_id} has an implausible race/ethnicity total")
        locale_values = [row[fields[field]] for field in locale_fields]
        if any(value is None for value in locale_values) or not 0.98 <= sum(locale_values) <= 1.02:
            _fail(f"Context district {district_id} has an implausible locale total")
        ids.add(district_id)
        states.add(state)
    if states != EXPECTED_STATES:
        _fail(f"Context state domain differs from the approved contract: {sorted(states)}")


def _validate_achievement(
    rows: Any,
    *,
    grade: int,
    catalog_ids: set[str],
    label: str,
) -> int:
    expected_count = EXPECTED_GRADE_ROWS[grade]
    if not isinstance(rows, list) or len(rows) != expected_count:
        _fail(f"{label} must contain exactly {expected_count:,} achievement rows")
    keys: set[tuple[str, str, int]] = set()
    subjects: set[str] = set()
    years: set[int] = set()
    for row_number, row in enumerate(rows, start=1):
        if not isinstance(row, list) or len(row) != len(ACHIEVEMENT_FIELDS):
            _fail(f"{label} row {row_number} does not have {len(ACHIEVEMENT_FIELDS)} fields")
        district_id, subject, year, estimate, within_se, cross_se, tested_count, estimated = row
        if not isinstance(district_id, str) or not DISTRICT_ID_PATTERN.fullmatch(district_id):
            _fail(f"{label} row {row_number} has an invalid district_id")
        if district_id not in catalog_ids:
            _fail(f"{label} district {district_id} is absent from the catalog")
        if subject not in EXPECTED_SUBJECTS:
            _fail(f"{label} row {row_number} has an invalid subject")
        if type(year) is not int or year not in EXPECTED_YEARS:
            _fail(f"{label} row {row_number} has an invalid year")
        key = (district_id, subject, year)
        if key in keys:
            _fail(f"{label} contains duplicate key {key}")
        if not _is_number(estimate):
            _fail(f"{label} row {row_number} has an invalid estimate")
        if not _is_number(within_se) or not 0 <= within_se <= 1:
            _fail(f"{label} row {row_number} has an invalid within-state standard error")
        if not _is_number(cross_se) or not 0 <= cross_se <= 1:
            _fail(f"{label} row {row_number} has an invalid cross-state standard error")
        if type(tested_count) is not int or tested_count < 20:
            _fail(f"{label} row {row_number} violates the released test-count bound")
        if type(estimated) is not int or estimated not in (0, 1):
            _fail(f"{label} row {row_number} has an invalid estimated-count flag")
        keys.add(key)
        subjects.add(subject)
        years.add(year)
    if subjects != EXPECTED_SUBJECTS:
        _fail(f"{label} subject coverage is incomplete: {sorted(subjects)}")
    if years != EXPECTED_YEARS:
        _fail(f"{label} year coverage is incomplete: {sorted(years)}")
    return expected_count


def _validate_sources(technical: dict[str, Any], source_config: dict[str, Any]) -> None:
    sources = technical["sources"]
    expected_ids = set(EXPECTED_SOURCE_BYTES)
    if not isinstance(sources, list) or len(sources) != len(expected_ids):
        _fail("Dashboard source provenance must contain exactly the three approved sources")
    if set(source_config) != expected_ids:
        _fail("config/sources.yml does not contain exactly the approved source IDs")
    seen: set[str] = set()
    for source in sources:
        source = _exact_keys(source, SOURCE_KEYS, "Source provenance entry")
        source_id = source["source_id"]
        if source_id not in expected_ids or source_id in seen:
            _fail(f"Unexpected or duplicate source provenance ID: {source_id}")
        contract = source_config[source_id]
        pinned_hash = contract["sha256"]
        if source["version"] != contract["version"]:
            _fail(f"{source_id} version differs from config/sources.yml")
        if source["title"] != contract["title"]:
            _fail(f"{source_id} title differs from config/sources.yml")
        if source["persistent_id"] != contract["persistent_id"]:
            _fail(f"{source_id} persistent ID differs from config/sources.yml")
        if source["expected_sha256"] != pinned_hash or source["observed_sha256"] != pinned_hash:
            _fail(f"{source_id} expected/observed SHA-256 does not match the pinned hash")
        if source["hash_verified"] is not True:
            _fail(f"{source_id} was not hash verified")
        if source["size_bytes"] != EXPECTED_SOURCE_BYTES[source_id]:
            _fail(f"{source_id} byte size differs from the approved source contract")
        if source["column_count"] != EXPECTED_SOURCE_COLUMNS[source_id]:
            _fail(f"{source_id} column count differs from the approved source contract")
        seen.add(source_id)
    if seen != expected_ids:
        _fail(f"Source provenance is incomplete: {sorted(expected_ids - seen)}")
    if technical["source_total_bytes"] != sum(EXPECTED_SOURCE_BYTES.values()):
        _fail("Total source bytes differ from the approved source contract")


def _validate_technical(
    technical: Any,
    *,
    source_config: dict[str, Any],
    data_size: int,
) -> dict[str, Any]:
    technical = _exact_keys(technical, TECHNICAL_KEYS, "Technical metadata")
    _validate_sources(technical, source_config)
    expected_grade_rows = {str(grade): count for grade, count in EXPECTED_GRADE_ROWS.items()}
    if technical["workbench_grade_rows"] != expected_grade_rows:
        _fail("Workbench grade-row metadata differs from the approved row contract")
    total_rows = sum(EXPECTED_GRADE_ROWS.values())
    if technical["workbench_total_rows"] != total_rows:
        _fail("Workbench total-row metadata differs from the approved row contract")
    if technical["published_catalog_rows"] != EXPECTED_CATALOG_ROWS:
        _fail("Published catalog-row metadata differs from the approved row contract")
    if technical["published_context_rows"] != EXPECTED_CONTEXT_ROWS:
        _fail("Published context-row metadata differs from the approved row contract")
    if technical["published_achievement_rows"] != EXPECTED_GRADE_ROWS[INITIAL_GRADE]:
        _fail("Published initial achievement-row metadata differs from the approved row contract")
    if technical["public_bundle_bytes"] != data_size:
        _fail("Initial dashboard bundle size does not match its metadata")
    table_counts = _exact_keys(technical["table_counts"], TABLE_COUNT_KEYS, "Table counts")
    if any(type(value) is not int or value < 0 for value in table_counts.values()):
        _fail("Table counts must be nonnegative integers")
    if table_counts["dim_district"] != EXPECTED_CATALOG_ROWS:
        _fail("dim_district count differs from the approved catalog contract")
    if table_counts["mart_achievement"] != total_rows:
        _fail("mart_achievement count differs from the approved workbench contract")
    qa = technical["qa"]
    if not isinstance(qa, list):
        _fail("Technical QA metadata must be an array")
    statuses: list[str] = []
    names: set[str] = set()
    for item in qa:
        item = _exact_keys(item, QA_KEYS, "QA result")
        if not isinstance(item["name"], str) or not item["name"] or item["name"] in names:
            _fail("QA result names must be unique nonempty strings")
        if item["severity"] not in {"error", "warning"}:
            _fail(f"QA result {item['name']} has an invalid severity")
        if item["status"] not in {"pass", "warn"}:
            _fail(f"QA result {item['name']} is not publishable: {item['status']}")
        if type(item["observed"]) is not int or type(item["expected"]) is not int:
            _fail(f"QA result {item['name']} has non-integer counts")
        names.add(item["name"])
        statuses.append(item["status"])
    if technical["qa_pass_count"] != statuses.count("pass"):
        _fail("QA pass count does not match the published QA rows")
    if technical["qa_warning_count"] != statuses.count("warn"):
        _fail("QA warning count does not match the published QA rows")
    expected_sql_models = sorted(path.name for path in (ROOT / "sql" / "models").glob("*.sql"))
    if technical["sql_models"] != expected_sql_models:
        _fail("Published SQL-model inventory differs from the repository")
    return technical


def main() -> None:
    required = [
        ROOT / "site" / "index.html",
        ROOT / "site" / "assets" / "styles.css",
        ROOT / "site" / "assets" / "dashboard.js",
        ROOT / "site" / "assets" / "workbench.js",
        ROOT / "site" / "assets" / "plotly-3.1.0.min.js",
        DATA_PATH,
        *(
            ROOT / "site" / "data" / f"workbench-grade-{grade}.js"
            for grade in LAZY_WORKBENCH_GRADES
        ),
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        _fail(f"Public dashboard files are missing: {', '.join(missing)}")

    index_html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    for relative_path in VERSIONED_SITE_ASSETS:
        digest = _canonical_asset_digest(ROOT / "site" / relative_path)
        expected_reference = f'{relative_path}?v={digest}'
        if index_html.count(expected_reference) != 1:
            _fail(
                f"site/index.html must reference {relative_path} exactly once with its "
                "current content hash"
            )

    project_config = yaml.safe_load((ROOT / "config" / "project.yml").read_text(encoding="utf-8"))
    source_config = yaml.safe_load((ROOT / "config" / "sources.yml").read_text(encoding="utf-8"))
    if not isinstance(project_config, dict) or not isinstance(source_config, dict):
        _fail("Project and source configuration must be YAML objects")

    payload, data_size = _read_assignment(DATA_PATH, PREFIX, "Dashboard data")
    payload = _exact_keys(payload, MAIN_KEYS, "Dashboard payload")
    if payload["schema_version"] != 1:
        _fail("Dashboard data schema version is not supported")
    try:
        generated_at = datetime.fromisoformat(payload["generated_at_utc"])
    except (TypeError, ValueError):
        _fail("Dashboard generated_at_utc is invalid")
    if generated_at.tzinfo is None:
        _fail("Dashboard generated_at_utc must include a timezone")
    if payload["project"] != project_config.get("project"):
        _fail("Dashboard project metadata differs from config/project.yml")
    if (
        payload["grade"] != INITIAL_GRADE
        or project_config["analysis"]["default_grade"] != INITIAL_GRADE
    ):
        _fail("The approved public dashboard contract requires grade 4 as the initial bundle")
    workbench = _exact_keys(payload["workbench"], WORKBENCH_CONFIG_KEYS, "Workbench metadata")
    confidence_level = project_config["analysis"]["confidence_level"]
    expected_workbench = {
        "release": project_config["project"]["data_version"],
        "geography": "administrative district",
        "subgroup": "all students",
        "scale": "Cohort Standardized (CS)",
        "years": sorted(EXPECTED_YEARS),
        "confidence_level": confidence_level,
        "confidence_critical_value": NormalDist().inv_cdf(0.5 + confidence_level / 2),
    }
    if workbench != expected_workbench:
        _fail("Dashboard workbench metadata differs from the approved/configured contract")
    if tuple(payload["catalog_fields"]) != CATALOG_FIELDS:
        _fail("Catalog fields differ from the approved public allowlist")
    if tuple(payload["context_fields"]) != CONTEXT_FIELDS:
        _fail("Context fields differ from the approved public allowlist")
    if tuple(payload["achievement_fields"]) != ACHIEVEMENT_FIELDS:
        _fail("Achievement fields differ from the approved public allowlist")
    model = _exact_keys(payload["model"], MODEL_KEYS, "Model metadata")
    if model["analysis"] != project_config.get("analysis"):
        _fail("Dashboard analysis metadata differs from config/project.yml")
    if model["peer_model"] != project_config.get("peer_model"):
        _fail("Dashboard peer-model metadata differs from config/project.yml")
    robust_ranges = _exact_keys(
        model["robust_ranges"],
        {"log_enrollment", "family_poverty_rate", "socioeconomic_status_composite"},
        "Robust-range metadata",
    )
    if any(not _is_number(value) or value <= 0 for value in robust_ranges.values()):
        _fail("Robust-range metadata must contain positive finite numbers")

    catalog_ids, catalog_lookup = _validate_catalog(payload["catalog"])
    if payload["default_district_id"] not in catalog_ids:
        _fail("Default district is absent from the dashboard catalog")
    _validate_context(payload["context"], catalog_lookup)
    workbench_rows = _validate_achievement(
        payload["achievement"],
        grade=INITIAL_GRADE,
        catalog_ids=catalog_ids,
        label="Initial grade 4 bundle",
    )
    technical = _validate_technical(
        payload["technical"], source_config=source_config, data_size=data_size
    )

    workbench_bytes = {str(INITIAL_GRADE): data_size}
    for grade in LAZY_WORKBENCH_GRADES:
        grade_path = ROOT / "site" / "data" / f"workbench-grade-{grade}.js"
        grade_prefix = (
            "window.SEDA_WORKBENCH_GRADES=window.SEDA_WORKBENCH_GRADES||{};"
            f"window.SEDA_WORKBENCH_GRADES[{grade}]="
        )
        grade_payload, grade_size = _read_assignment(
            grade_path, grade_prefix, f"Grade {grade} bundle"
        )
        grade_payload = _exact_keys(grade_payload, WORKBENCH_KEYS, f"Grade {grade} payload")
        expected_scope = {
            "schema_version": 1,
            "release": project_config["project"]["data_version"],
            "geography": "administrative district",
            "subgroup": "all students",
            "scale": "Cohort Standardized (CS)",
            "grade": grade,
        }
        for field, expected in expected_scope.items():
            if grade_payload[field] != expected:
                _fail(f"Grade {grade} bundle has invalid {field} metadata")
        if tuple(grade_payload["achievement_fields"]) != ACHIEVEMENT_FIELDS:
            _fail(f"Grade {grade} fields differ from the approved public allowlist")
        if grade_payload["row_count"] != EXPECTED_GRADE_ROWS[grade]:
            _fail(f"Grade {grade} row_count differs from the approved row contract")
        workbench_rows += _validate_achievement(
            grade_payload["achievement"],
            grade=grade,
            catalog_ids=catalog_ids,
            label=f"Grade {grade} bundle",
        )
        workbench_bytes[str(grade)] = grade_size

    if workbench_rows != sum(EXPECTED_GRADE_ROWS.values()):
        _fail("Workbench rows do not match the approved six-grade total")
    expected_bytes = {str(grade): workbench_bytes[str(grade)] for grade in WORKBENCH_GRADES}
    if technical["workbench_bundle_bytes"] != expected_bytes:
        _fail("Workbench bundle sizes do not match their metadata")
    if technical["workbench_public_data_bytes"] != sum(expected_bytes.values()):
        _fail("Total public workbench data size does not match its metadata")
    print(
        "PASS: public dashboard matches the exact SEDA 2025.2 field, row, source, "
        "domain, uniqueness, membership, and bundle contracts"
    )


if __name__ == "__main__":
    main()
