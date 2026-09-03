import duckdb
import pandas as pd

from district_context.config import PROJECT_ROOT
from district_context.database import _render_sql, _sql_literal
from district_context.illinois_database import _qa


def _north_palos_rows() -> pd.DataFrame:
    rows = []
    for year in range(2022, 2026):
        for rcdts in ("070161170022003", "070161170022004"):
            for subject in ("ela", "math"):
                rows.append(
                    {
                        "report_card_year": year,
                        "rcdts": rcdts,
                        "grade": 4,
                        "subject": subject,
                        "district_name": "North Palos SD 117",
                        "proficiency_rate": 70.0,
                        "proficiency_status": "reported",
                        "participation_rate": None,
                        "growth_percentile": 55.0 if year == 2025 else None,
                        "growth_status": "reported" if year == 2025 else "not_published",
                        "mobility_rate": 8.0,
                        "chronic_absenteeism_rate": 10.0,
                        "chronic_absenteeism_grade4_rate": 9.0,
                    }
                )
    return pd.DataFrame(rows)


def _create_qa_tables(connection: duckdb.DuckDBPyConnection, rows: pd.DataFrame) -> None:
    connection.register("source_rows", rows)
    connection.execute("CREATE TABLE stg_illinois_grade4 AS SELECT * FROM source_rows")
    connection.execute(
        "CREATE TABLE mart_illinois_grade4_school_year AS SELECT * FROM source_rows"
    )
    connection.execute(
        """
        CREATE TABLE dim_illinois_school AS
        SELECT * FROM (VALUES
            ('Dorn Elementary School', 'North Palos SD 117'),
            ('Dr Kenneth M Sorrick School', 'North Palos SD 117'),
            ('Glen Oaks Elem School', 'North Palos SD 117'),
            ('H H Conrady Jr High School', 'North Palos SD 117'),
            ('Oak Ridge Elem School', 'North Palos SD 117')
        ) AS schools(school_name, district_name)
        """
    )


def test_illinois_database_qa_accepts_expected_north_palos_panel():
    connection = duckdb.connect()
    _create_qa_tables(connection, _north_palos_rows())

    results = _qa(connection)

    assert results
    assert {result["status"] for result in results} == {"pass"}


def test_illinois_database_qa_detects_duplicate_key():
    rows = _north_palos_rows()
    rows = pd.concat([rows, rows.iloc[[0]]], ignore_index=True)
    connection = duckdb.connect()
    _create_qa_tables(connection, rows)

    results = {result["name"]: result for result in _qa(connection)}

    assert results["unique_school_year_grade_subject"]["status"] == "fail"


def test_illinois_sql_models_compile_against_test_fixture(tmp_path):
    row = {
        "report_card_year": 2025,
        "rcdts": "070161170022003",
        "rcdts_formatted": "07-016-1170-02-2003",
        "rcdts_source": "070161170022003",
        "entity_level": "School",
        "school_name": "Glen Oaks Elem School",
        "district_name": "North Palos SD 117",
        "city": "Hickory Hills",
        "county": "Cook",
        "school_type": "ELEMENTARY",
        "grades_served": "2 - 5",
        "grade": 4,
        "subject": "ela",
        "proficiency_rate": 85.7,
        "proficiency_status": "reported",
        "proficiency_metric_version": "iar_4_level_published_rate_2025",
        "participation_rate": 100.0,
        "participation_status": "reported",
        "growth_percentile": 64.9,
        "growth_status": "reported",
        "growth_metric_version": "published_grade4_mean_sgp",
        "school_enrollment": 800,
        "school_enrollment_status": "reported",
        "grade4_enrollment": 170,
        "grade4_enrollment_status": "reported",
        "pct_iep": 15.0,
        "pct_iep_status": "reported",
        "pct_el": 18.0,
        "pct_el_status": "reported",
        "pct_low_income": 30.0,
        "pct_low_income_status": "reported",
        "mobility_rate": 10.1,
        "mobility_rate_status": "reported",
        "chronic_absenteeism_rate": 7.3,
        "chronic_absenteeism_rate_status": "reported",
        "chronic_absenteeism_grade4_rate": 6.3,
        "chronic_absenteeism_grade4_rate_status": "reported",
        "source_file": "2025-report-card.xlsx",
        "source_sheet": "IAR",
    }
    csv_path = tmp_path / "illinois.csv"
    roster_path = tmp_path / "roster.csv"
    pd.DataFrame([row]).to_csv(csv_path, index=False)
    pd.DataFrame(
        [
            {
                key: row[key]
                for key in (
                    "report_card_year",
                    "rcdts",
                    "rcdts_formatted",
                    "rcdts_source",
                    "school_name",
                    "district_name",
                    "city",
                    "county",
                    "school_type",
                    "grades_served",
                    "school_enrollment",
                    "school_enrollment_status",
                    "source_file",
                    "source_sheet",
                )
            }
        ]
    ).to_csv(roster_path, index=False)

    connection = duckdb.connect()
    replacements = {
        "grade4_csv_path": _sql_literal(csv_path),
        "school_roster_csv_path": _sql_literal(roster_path),
    }
    for model in sorted((PROJECT_ROOT / "sql" / "illinois").glob("*.sql")):
        connection.execute(_render_sql(model, replacements))

    assert connection.execute("SELECT count(*) FROM dim_illinois_school").fetchone()[0] == 1
    assert connection.execute(
        "SELECT growth_percentile FROM mart_illinois_grade4_school_year"
    ).fetchone()[0] == 64.9
