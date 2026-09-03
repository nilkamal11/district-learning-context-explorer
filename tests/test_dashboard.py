import json
import re
from pathlib import Path

from district_context.dashboard import (
    _compact_number,
    _safe_javascript_assignment,
    _safe_workbench_assignment,
    build_dashboard,
)

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_script_escapes_markup_and_round_trips():
    script = _safe_javascript_assignment({"district": "Example </script> & District"})

    assert "</script>" not in script
    payload = script.removeprefix("window.DISTRICT_DASHBOARD_DATA=").removesuffix(";\n")
    assert json.loads(payload) == {"district": "Example </script> & District"}


def test_dashboard_numbers_are_compact_and_missing_values_stay_missing():
    assert _compact_number(0.123456789) == 0.123457
    assert _compact_number(float("nan")) is None


def test_workbench_script_uses_grade_namespace_and_round_trips():
    script = _safe_workbench_assignment(3, {"district": "Example </script> & District"})
    prefix = (
        "window.SEDA_WORKBENCH_GRADES=window.SEDA_WORKBENCH_GRADES||{};"
        "window.SEDA_WORKBENCH_GRADES[3]="
    )

    assert script.startswith(prefix)
    assert "</script>" not in script
    assert json.loads(script.removeprefix(prefix).removesuffix(";\n")) == {
        "district": "Example </script> & District"
    }


def test_public_site_exposes_the_workbench_and_lazy_loader():
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    workbench_javascript = (ROOT / "site" / "assets" / "workbench.js").read_text(
        encoding="utf-8"
    )
    trends_javascript = (ROOT / "site" / "assets" / "trends.js").read_text(
        encoding="utf-8"
    )

    assert 'id="workbench-tab"' in html
    assert 'id="workbench-panel"' in html
    assert 'id="wb-trend-chart"' in html
    assert 'id="wb-distribution-chart"' in html
    assert "workbench-grade-${grade}.js" in workbench_javascript
    assert "window.SEDA_WORKBENCH" in workbench_javascript
    assert "validateBundle" in workbench_javascript
    assert 'scriptUrl.searchParams.set("v", source.generated_at_utc)' in workbench_javascript
    assert (
        'document.querySelectorAll("#workbench-panel button, #workbench-panel select, '
        '#workbench-panel input")' in workbench_javascript
    )

    assert 'id="trends-tab"' in html
    assert 'id="trends-panel"' in html
    assert 'id="trend-chart"' in html
    assert 'id="trend-data-note"' in html
    assert 'id="trend-records-body"' in html
    assert 'src="assets/trends.js' in html
    assert "How this differs from Stanford’s Explorer" in html
    assert 'const DEFAULT_DISTRICT_ID = "1728890"' in trends_javascript
    assert "const BASELINE_YEARS = [2019, 2022]" in trends_javascript
    assert "workbench-grade-${grade}.js" in trends_javascript
    assert "validateBundle" in trends_javascript
    assert "connectgaps: false" in trends_javascript
    assert "window.SEDA_TRENDS" in trends_javascript
    assert "latestYear <= baselineYear" in trends_javascript
    assert "different group of students" in html
    assert 'aria-describedby="trend-chart-caption"' in html

    assert re.search(
        r'<section aria-labelledby="trend-heading">.*?<h2 id="trend-heading"', html, re.S
    )
    assert re.search(
        r'<section aria-labelledby="simple-trend-heading">.*?'
        r'<h2 id="simple-trend-heading"',
        html,
        re.S,
    )

    element_ids = re.findall(r'\bid="([^"]+)"', html)
    assert len(element_ids) == len(set(element_ids))


def test_public_site_exposes_research_extensions_with_clear_boundaries():
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    dashboard_javascript = (ROOT / "site" / "assets" / "dashboard.js").read_text(
        encoding="utf-8"
    )

    assert 'id="research-tab"' in html
    assert 'aria-controls="research-panel"' in html
    assert 'id="research-panel"' in html
    assert 'aria-labelledby="research-tab"' in html
    assert "Did districts that increased instructional spending per student" in html
    assert "No findings invented" in html
    assert "Association, not causation" in html
    assert "174 crosswalk records need an ID change" in html
    assert "does not claim access to internal product data" in html
    assert "https://edopportunity.org/trends/data/downloads/" in html
    assert "https://www.census.gov/programs-surveys/school-finances.html" in html
    assert "https://nces.ed.gov/ccd/pau_rev.asp" in html
    assert "https://www.bls.gov/cpi/data.htm" in html
    assert '["explore", "trends", "workbench", "research", "technical"]' in dashboard_javascript
    assert '["trends", "workbench", "research", "technical"]' in dashboard_javascript


def test_public_dashboard_rejects_a_non_grade_four_initial_bundle(tmp_path):
    try:
        build_dashboard(
            None,
            destination=tmp_path,
            default_district_id="1700044",
            grade=5,
        )
    except ValueError as error:
        assert "embeds grade 4" in str(error)
    else:
        raise AssertionError("Expected a non-grade-4 dashboard build to be rejected")
