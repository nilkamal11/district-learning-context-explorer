import json

from district_context.dashboard import _compact_number, _safe_javascript_assignment


def test_dashboard_script_escapes_markup_and_round_trips():
    script = _safe_javascript_assignment({"district": "Example </script> & District"})

    assert "</script>" not in script
    payload = script.removeprefix("window.DISTRICT_DASHBOARD_DATA=").removesuffix(";\n")
    assert json.loads(payload) == {"district": "Example </script> & District"}


def test_dashboard_numbers_are_compact_and_missing_values_stay_missing():
    assert _compact_number(0.123456789) == 0.123457
    assert _compact_number(float("nan")) is None
