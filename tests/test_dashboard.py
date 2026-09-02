import json
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
    javascript = (ROOT / "site" / "assets" / "workbench.js").read_text(encoding="utf-8")

    assert 'id="workbench-tab"' in html
    assert 'id="workbench-panel"' in html
    assert 'id="wb-trend-chart"' in html
    assert 'id="wb-distribution-chart"' in html
    assert "workbench-grade-${grade}.js" in javascript
    assert "window.SEDA_WORKBENCH" in javascript
    assert "validateBundle" in javascript
    assert 'scriptUrl.searchParams.set("v", source.generated_at_utc)' in javascript
    assert (
        'document.querySelectorAll("#workbench-panel button, #workbench-panel select, '
        '#workbench-panel input")' in javascript
    )


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
