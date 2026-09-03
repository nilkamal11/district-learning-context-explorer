from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape
from plotly.offline import get_plotlyjs

from district_context.config import PROJECT_ROOT
from district_context.illinois_database import build_illinois_database, illinois_database_path
from district_context.utils import write_json

NORTH_PALOS = "North Palos SD 117"
FEATURED_DISTRICTS = (
    NORTH_PALOS,
    "Indian Springs SD 109",
    "Palos CCSD 118",
    "Worth SD 127",
)

PROFICIENCY_DEFINITION = (
    "For 2022–2024, this dashboard derives proficiency by adding ISBE's published "
    "Level 4 and Level 5 percentages. For 2025, it uses ISBE's published Grade 4 "
    "proficiency-rate field; under the new four-level structure, Levels 3 and 4 "
    "count as proficient."
)


def _safe_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _dashboard_records(rows: pd.DataFrame) -> list[dict[str, Any]]:
    columns = (
        "report_card_year",
        "rcdts",
        "rcdts_formatted",
        "school_name",
        "district_name",
        "grade",
        "subject",
        "proficiency_rate",
        "proficiency_status",
        "proficiency_metric_version",
        "participation_rate",
        "participation_status",
        "growth_percentile",
        "growth_status",
        "growth_metric_version",
        "school_enrollment",
        "grade4_enrollment",
        "pct_iep",
        "pct_el",
        "pct_low_income",
        "mobility_rate",
        "chronic_absenteeism_rate",
        "chronic_absenteeism_grade4_rate",
        "source_file",
    )
    result = []
    ordered = rows.sort_values(["school_name", "report_card_year", "subject"])
    for row in ordered.to_dict("records"):
        result.append({column: _safe_value(row[column]) for column in columns})
    return result


def _school_catalog(rows: pd.DataFrame) -> list[dict[str, Any]]:
    columns = (
        "rcdts",
        "rcdts_formatted",
        "school_name",
        "district_name",
        "city",
        "grades_served",
        "school_enrollment",
        "has_grade4_results",
    )
    ordered = rows.sort_values(["district_name", "school_name"])
    return [
        {column: _safe_value(row[column]) for column in columns}
        for row in ordered.to_dict("records")
    ]


def build_north_palos_profile(*, db_path: Path | None = None) -> dict[str, Any]:
    target_db = db_path or illinois_database_path()
    if not target_db.is_file():
        build_illinois_database()
    with duckdb.connect(str(target_db), read_only=True) as connection:
        placeholders = ", ".join("?" for _ in FEATURED_DISTRICTS)
        rows = connection.execute(
            f"""
            SELECT * FROM mart_illinois_grade4_school_year
            WHERE district_name IN ({placeholders})
            ORDER BY district_name, school_name, report_card_year, subject
            """,
            list(FEATURED_DISTRICTS),
        ).df()
        roster = connection.execute(
            f"""
            SELECT * FROM dim_illinois_school
            WHERE district_name IN ({placeholders})
            ORDER BY district_name, school_name
            """,
            list(FEATURED_DISTRICTS),
        ).df()
    north_palos_roster = roster.loc[roster["district_name"] == NORTH_PALOS]
    if len(north_palos_roster) != 5:
        raise RuntimeError("North Palos dashboard requires the current five-school roster.")
    missing_districts = set(FEATURED_DISTRICTS) - set(roster["district_name"])
    if missing_districts:
        raise RuntimeError(f"Missing featured district rosters: {sorted(missing_districts)}")

    records = _dashboard_records(rows)
    catalog = _school_catalog(roster)
    environment = Environment(
        loader=PackageLoader("district_context", "templates"),
        autoescape=select_autoescape(["html", "xml"]),
        undefined=StrictUndefined,
    )
    template = environment.get_template("illinois_grade4_profile.html.j2")
    built_at = datetime.now(UTC)
    template_context = {
        "dashboard_records": records,
        "school_catalog": catalog,
        "default_district": NORTH_PALOS,
        "proficiency_definition": PROFICIENCY_DEFINITION,
    }
    html = template.render(
        **template_context,
        plotly_js=get_plotlyjs(),
    )
    public_html = template.render(
        **template_context,
        plotly_js="",
    )
    output_path = PROJECT_ROOT / "data" / "output" / "illinois_grade4_north_palos_profile.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    public_path = PROJECT_ROOT / "site" / "illinois.html"
    public_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.write_text(public_html, encoding="utf-8")

    payload_path = output_path.with_suffix(".json")
    write_json(
        payload_path,
        {
            "built_at_utc": built_at.isoformat(),
            "district_name": NORTH_PALOS,
            "featured_districts": list(FEATURED_DISTRICTS),
            "school_count": len(catalog),
            "row_count": len(rows),
            "school_catalog": catalog,
            "records": records,
        },
    )
    return {
        "output": str(output_path),
        "public_output": str(public_path),
        "payload": str(payload_path),
        "district_count": len(FEATURED_DISTRICTS),
        "school_count": len(catalog),
        "row_count": len(rows),
        "status": "success",
    }
