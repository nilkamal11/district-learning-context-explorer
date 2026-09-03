from __future__ import annotations

import csv
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from district_context.config import PROJECT_ROOT
from district_context.illinois_xlsx import XlsxReader
from district_context.utils import sha256_file, write_json

SUBJECT_LABELS = {"ela": "ELA", "math": "Mathematics"}


def normalize_rcdts(value: Any) -> str:
    code = re.sub(r"[^0-9A-Za-z]", "", str(value or "")).upper()
    if len(code) != 15:
        raise ValueError(f"Expected a 15-character RCDTS code, received {value!r}")
    return code


def format_rcdts(value: str) -> str:
    code = normalize_rcdts(value)
    return f"{code[:2]}-{code[2:5]}-{code[5:9]}-{code[9:11]}-{code[11:]}"


def _source_config() -> dict[str, Any]:
    with (PROJECT_ROOT / "config" / "illinois_sources.yml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _first_existing(
    headers: list[str], candidates: list[str], *, required: bool = True
) -> str | None:
    for candidate in candidates:
        if candidate in headers:
            return candidate
    if required:
        raise ValueError(f"None of the expected columns were found: {', '.join(candidates)}")
    return None


def _metric(value: Any, *, unavailable: bool = False) -> tuple[float | None, str]:
    if unavailable:
        return None, "not_published"
    if value == "*":
        return None, "suppressed"
    if value is None or str(value).strip() in {"", "-", "--"}:
        return None, "missing"
    try:
        return float(value), "reported"
    except (TypeError, ValueError):
        return None, "invalid"


def _derived_proficiency(first: Any, second: Any) -> tuple[float | None, str]:
    first_value, first_status = _metric(first)
    second_value, second_status = _metric(second)
    statuses = {first_status, second_status}
    if statuses == {"reported"}:
        return round(float(first_value) + float(second_value), 1), "reported"
    if "suppressed" in statuses:
        return None, "suppressed"
    if "invalid" in statuses:
        return None, "invalid"
    return None, "missing"


def _general_columns(headers: list[str]) -> dict[str, str | None]:
    return {
        "rcdts": _first_existing(headers, ["RCDTS"]),
        "entity_level": _first_existing(headers, ["Level", "Type"]),
        "school_name": _first_existing(headers, ["School Name"]),
        "district_name": _first_existing(headers, ["District"]),
        "city": _first_existing(headers, ["City"]),
        "county": _first_existing(headers, ["County"]),
        "school_type": _first_existing(headers, ["School Type"]),
        "grades_served": _first_existing(headers, ["Grades Served"]),
        "school_enrollment": _first_existing(headers, ["# Student Enrollment"]),
        "grade4_enrollment": _first_existing(
            headers,
            ["# Student Enrollment -Grade 4", "# Student Enrollment - Grade 4"],
            required=False,
        ),
        "pct_iep": _first_existing(headers, ["% Student Enrollment - IEP"]),
        "pct_el": _first_existing(headers, ["% Student Enrollment - EL"]),
        "pct_low_income": _first_existing(headers, ["% Student Enrollment - Low Income"]),
        "mobility_rate": _first_existing(headers, ["Student Mobility Rate"]),
        "chronic_absenteeism_rate": _first_existing(headers, ["Chronic Absenteeism"]),
        "chronic_absenteeism_grade4_rate": _first_existing(
            headers, ["Chronic Absenteeism - Grade 4"], required=False
        ),
    }


def _iar_base_columns(headers: list[str]) -> dict[str, str]:
    return {
        "rcdts": _first_existing(headers, ["RCDTS"]),
        "entity_level": _first_existing(headers, ["Level", "Type"]),
        "school_name": _first_existing(headers, ["School Name"]),
        "district_name": _first_existing(headers, ["District"]),
        "city": _first_existing(headers, ["City"]),
        "county": _first_existing(headers, ["County"]),
        "school_type": _first_existing(headers, ["School Type"]),
        "grades_served": _first_existing(headers, ["Grades Served"]),
    }


def _iar_metric_columns(headers: list[str], year: int, subject: str) -> dict[str, Any]:
    if year == 2025:
        prefix = "IAR ELA" if subject == "ela" else "IAR Math"
        growth_prefix = "ELA" if subject == "ela" else "Math"
        return {
            "proficiency": _first_existing(headers, [f"{prefix} Proficiency Rate Grade 4 - Total"]),
            "participation": _first_existing(
                headers, [f"{prefix} Participation Rate Grade 4 - Total"]
            ),
            "growth": _first_existing(
                headers, [f"{growth_prefix} Growth Percentile Grade 4 - Total"]
            ),
            "levels": [],
        }
    label = SUBJECT_LABELS[subject]
    return {
        "proficiency": None,
        "participation": None,
        "growth": None,
        "levels": [
            _first_existing(headers, [f"% All students IAR {label} Level 4 - Grade 4"]),
            _first_existing(headers, [f"% All students IAR {label} Level 5 - Grade 4"]),
        ],
    }


def _selected_columns(mapping: dict[str, str | None]) -> list[str]:
    return list(dict.fromkeys(column for column in mapping.values() if column))


def _general_context(reader: XlsxReader) -> dict[str, dict[str, Any]]:
    mapping = _general_columns(reader.header("General"))
    selected = _selected_columns(mapping)
    result: dict[str, dict[str, Any]] = {}
    for source_row in reader.records("General", selected):
        row = {name: source_row.get(column) if column else None for name, column in mapping.items()}
        if str(row["entity_level"] or "").strip().lower() != "school":
            continue
        rcdts_source = str(row["rcdts"] or "").strip()
        if rcdts_source:
            row["rcdts_source"] = rcdts_source
            result[normalize_rcdts(rcdts_source)] = row
    return result


def extract_year(
    path: Path, year: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with XlsxReader(path) as reader:
        context = _general_context(reader)
        roster_rows = []
        for rcdts, school in context.items():
            enrollment, enrollment_status = _metric(school.get("school_enrollment"))
            roster_rows.append(
                {
                    "report_card_year": year,
                    "rcdts": rcdts,
                    "rcdts_formatted": format_rcdts(rcdts),
                    "rcdts_source": school["rcdts_source"],
                    "school_name": school.get("school_name"),
                    "district_name": school.get("district_name"),
                    "city": school.get("city"),
                    "county": school.get("county"),
                    "school_type": school.get("school_type"),
                    "grades_served": school.get("grades_served"),
                    "school_enrollment": enrollment,
                    "school_enrollment_status": enrollment_status,
                    "source_file": path.name,
                    "source_sheet": "General",
                }
            )
        headers = reader.header("IAR")
        base_mapping = _iar_base_columns(headers)
        subject_mappings = {
            subject: _iar_metric_columns(headers, year, subject) for subject in SUBJECT_LABELS
        }
        selected = _selected_columns(base_mapping)
        for metric_mapping in subject_mappings.values():
            selected.extend(
                column
                for column in [
                    metric_mapping["proficiency"],
                    metric_mapping["participation"],
                    metric_mapping["growth"],
                    *metric_mapping["levels"],
                ]
                if column and column not in selected
            )

        unmatched_context = 0
        for source_row in reader.records("IAR", selected):
            base = {name: source_row.get(column) for name, column in base_mapping.items()}
            if str(base["entity_level"] or "").strip().lower() != "school":
                continue
            rcdts_source = str(base["rcdts"] or "").strip()
            rcdts = normalize_rcdts(rcdts_source)
            school_context = context.get(rcdts)
            if school_context is None:
                unmatched_context += 1
                school_context = {}

            for subject, metric_mapping in subject_mappings.items():
                raw_metric_values = [
                    source_row.get(column)
                    for column in [
                        metric_mapping["proficiency"],
                        metric_mapping["participation"],
                        metric_mapping["growth"],
                        *metric_mapping["levels"],
                    ]
                    if column
                ]
                if not any(value is not None for value in raw_metric_values):
                    continue

                if metric_mapping["proficiency"]:
                    proficiency, proficiency_status = _metric(
                        source_row.get(metric_mapping["proficiency"])
                    )
                else:
                    proficiency, proficiency_status = _derived_proficiency(
                        *(source_row.get(column) for column in metric_mapping["levels"])
                    )
                participation, participation_status = _metric(
                    source_row.get(metric_mapping["participation"])
                    if metric_mapping["participation"]
                    else None,
                    unavailable=metric_mapping["participation"] is None,
                )
                growth, growth_status = _metric(
                    source_row.get(metric_mapping["growth"]) if metric_mapping["growth"] else None,
                    unavailable=metric_mapping["growth"] is None,
                )

                context_values: dict[str, Any] = {}
                for field in (
                    "school_enrollment",
                    "grade4_enrollment",
                    "pct_iep",
                    "pct_el",
                    "pct_low_income",
                    "mobility_rate",
                    "chronic_absenteeism_rate",
                    "chronic_absenteeism_grade4_rate",
                ):
                    value, status = _metric(
                        school_context.get(field),
                        unavailable=(
                            field in {"grade4_enrollment", "chronic_absenteeism_grade4_rate"}
                            and year < 2024
                        ),
                    )
                    context_values[field] = value
                    context_values[f"{field}_status"] = status

                rows.append(
                    {
                        "report_card_year": year,
                        "rcdts": rcdts,
                        "rcdts_formatted": format_rcdts(rcdts),
                        "rcdts_source": rcdts_source,
                        "entity_level": base["entity_level"],
                        "school_name": base["school_name"],
                        "district_name": base["district_name"],
                        "city": base["city"],
                        "county": base["county"],
                        "school_type": base["school_type"],
                        "grades_served": base["grades_served"],
                        "grade": 4,
                        "subject": subject,
                        "proficiency_rate": proficiency,
                        "proficiency_status": proficiency_status,
                        "proficiency_metric_version": (
                            "iar_4_level_published_rate_2025"
                            if year == 2025
                            else "iar_5_level_levels_4_plus_5"
                        ),
                        "participation_rate": participation,
                        "participation_status": participation_status,
                        "growth_percentile": growth,
                        "growth_status": growth_status,
                        "growth_metric_version": "published_grade4_mean_sgp",
                        **context_values,
                        "source_file": path.name,
                        "source_sheet": "IAR",
                    }
                )

    return rows, roster_rows, {
        "year": year,
        "unmatched_iar_school_rows": unmatched_context,
        "school_roster_rows": len(roster_rows),
    }


def _validate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    keys = [(row["report_card_year"], row["rcdts"], row["grade"], row["subject"]) for row in rows]
    duplicate_count = sum(count - 1 for count in Counter(keys).values() if count > 1)
    checks.append({"name": "unique_school_year_grade_subject", "failures": duplicate_count})

    for field, lower, upper in (
        ("proficiency_rate", 0, 100),
        ("participation_rate", 0, 100),
        ("growth_percentile", 1, 99),
        ("mobility_rate", 0, 100),
        ("chronic_absenteeism_rate", 0, 100),
        ("chronic_absenteeism_grade4_rate", 0, 100),
        ("pct_iep", 0, 100),
        ("pct_el", 0, 100),
        ("pct_low_income", 0, 100),
    ):
        failures = sum(
            value is not None and not lower <= float(value) <= upper
            for value in (row[field] for row in rows)
        )
        checks.append({"name": f"{field}_range", "failures": failures})
    return [dict(check, status="pass" if check["failures"] == 0 else "fail") for check in checks]


def build_grade4_extract() -> dict[str, Any]:
    config = _source_config()
    raw_dir = PROJECT_ROOT / "data" / "raw" / "illinois_report_card"
    processed_dir = PROJECT_ROOT / "data" / "processed"
    output_dir = PROJECT_ROOT / "data" / "output"
    processed_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, Any]] = []
    all_roster_rows: list[dict[str, Any]] = []
    source_results: list[dict[str, Any]] = []
    extraction_notes: list[dict[str, Any]] = []
    for year, source in sorted(config["report_card"].items()):
        path = raw_dir / source["filename"]
        if not path.is_file():
            raise FileNotFoundError(f"Missing Illinois source: {path}")
        observed_hash = sha256_file(path)
        if observed_hash != source["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {path.name}")
        if path.stat().st_size < int(source["expected_min_bytes"]):
            raise ValueError(f"Source file is unexpectedly small: {path.name}")
        year_rows, roster_rows, notes = extract_year(path, int(year))
        all_rows.extend(year_rows)
        all_roster_rows.extend(roster_rows)
        extraction_notes.append(notes)
        source_results.append(
            {
                "year": int(year),
                "file": path.name,
                "bytes": path.stat().st_size,
                "sha256": observed_hash,
                "row_count": len(year_rows),
            }
        )

    checks = _validate(all_rows)
    failed = [check["name"] for check in checks if check["status"] == "fail"]
    if failed:
        raise RuntimeError(f"Illinois Grade 4 QA failed: {', '.join(failed)}")

    output_path = processed_dir / "illinois_grade4_school_year.csv"
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_rows[0]))
        writer.writeheader()
        writer.writerows(all_rows)

    roster_path = processed_dir / "illinois_school_roster.csv"
    with roster_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_roster_rows[0]))
        writer.writeheader()
        writer.writerows(all_roster_rows)

    coverage = []
    for year in sorted({int(row["report_card_year"]) for row in all_rows}):
        year_rows = [row for row in all_rows if int(row["report_card_year"]) == year]
        coverage.append(
            {
                "year": year,
                "schools": len({row["rcdts"] for row in year_rows}),
                "rows": len(year_rows),
                "proficiency_reported": sum(
                    row["proficiency_status"] == "reported" for row in year_rows
                ),
                "growth_reported": sum(row["growth_status"] == "reported" for row in year_rows),
                "growth_not_published": sum(
                    row["growth_status"] == "not_published" for row in year_rows
                ),
            }
        )

    manifest = {
        "project": config["project"]["title"],
        "built_at_utc": datetime.now(UTC).isoformat(),
        "output": str(output_path),
        "school_roster_output": str(roster_path),
        "row_count": len(all_rows),
        "school_roster_row_count": len(all_roster_rows),
        "school_count": len({row["rcdts"] for row in all_rows}),
        "coverage": coverage,
        "sources": source_results,
        "extraction_notes": extraction_notes,
        "qa": checks,
        "status": "success",
    }
    write_json(output_dir / "illinois_grade4_build_manifest.json", manifest)
    return manifest
