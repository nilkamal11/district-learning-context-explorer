import duckdb
import pandas as pd

from district_context import report


def context_fixture() -> pd.DataFrame:
    rows = []
    states = ["IL"] * 24 + ["WI"] * 12 + ["IN"] * 12 + ["IA"] * 12
    for index, state in enumerate(states, start=1):
        shift = ((index % 9) - 4) / 100
        rows.append(
            {
                "district_id": str(index).zfill(7),
                "district_name": f"Test-only district {index}",
                "state_abbreviation": state,
                "year": 2024,
                "grade_low": 0,
                "grade_high": 12,
                "grade_span_bucket": "unified_or_k12",
                "dominant_locale": "Suburb",
                "has_core_peer_context": True,
                "total_enrollment_grades_3_8": 2000 + index * 8,
                "family_poverty_rate": 0.14 + shift,
                "socioeconomic_status_composite": 0.20 - shift,
                "share_native_american": 0.01,
                "share_asian": 0.08,
                "share_hispanic": 0.24 + shift,
                "share_black": 0.16,
                "share_white": 0.47 - shift,
                "share_other_race_ethnicity": 0.04,
                "share_city": 0.10,
                "share_suburb": 0.75,
                "share_town": 0.05,
                "share_rural": 0.10,
            }
        )
    return pd.DataFrame(rows)


def achievement_fixture(context: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for district_id in context["district_id"]:
        for subject in ("mth", "rla"):
            rows.append(
                {
                    "district_id": district_id,
                    "subject": subject,
                    "grade": 4,
                    "year": 2024,
                    "achievement_cs": 0.1,
                    "standard_error_within_state": 0.05,
                    "standard_error_cross_state": 0.07,
                    "tested_count": 100,
                    "tested_count_estimated_flag": 0,
                }
            )
    return pd.DataFrame(rows)


def test_full_report_renders_with_strict_template_contract(tmp_path, monkeypatch):
    context = context_fixture()
    achievement = achievement_fixture(context)
    connection = duckdb.connect()
    connection.register("context_fixture", context)
    connection.register("achievement_fixture", achievement)
    connection.execute("CREATE TABLE mart_context_snapshot AS SELECT * FROM context_fixture")
    connection.execute("CREATE TABLE mart_achievement AS SELECT * FROM achievement_fixture")
    connection.execute(
        """
        CREATE TABLE qa_result AS
        SELECT 'test_only_check' AS name, 'error' AS severity, 'pass' AS status,
               0::BIGINT AS observed, 0::BIGINT AS expected, current_timestamp AS checked_at_utc
        """
    )
    monkeypatch.setattr(
        report,
        "project_config",
        lambda: {
            "project": {"title": "Test-only Explorer"},
            "analysis": {
                "context_year": 2024,
                "latest_result_year": 2025,
                "confidence_level": 0.95,
                "state_peer_count": 15,
                "state_peer_minimum": 10,
                "national_peer_count": 20,
                "max_national_peers_per_state": 3,
                "minimum_reporting_peers": 10,
                "minimum_reporting_fraction": 0.70,
            },
            "peer_model": {
                "version": "test-only-v1",
                "domain_weights": {
                    "district_scale": 0.25,
                    "economic_context": 0.25,
                    "student_composition": 0.25,
                    "place": 0.25,
                },
                "strict_calipers": {
                    "enrollment_factor": 4,
                    "poverty_points": 0.15,
                    "same_locale": True,
                },
                "relaxed_calipers": {
                    "enrollment_factor": 8,
                    "poverty_points": 0.25,
                    "same_locale": False,
                },
            },
        },
    )
    monkeypatch.setattr(report, "source_config", lambda: {})
    monkeypatch.setattr(report, "output_dir", lambda: tmp_path)
    monkeypatch.setattr(report, "_trend_figure", lambda *_, **__: "<div>Test chart</div>")
    destination = tmp_path / "report.html"

    report.build_profile(connection, "0000001", grade=4, destination=destination)

    html = destination.read_text(encoding="utf-8")
    assert "15 of 15 selected peers" in html
    assert "Full peer count under strict calipers" in html
    assert "Test-only district 1" in html
