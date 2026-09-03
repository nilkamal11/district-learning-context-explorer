import pytest

from district_context.illinois_grade4 import (
    _derived_proficiency,
    _iar_metric_columns,
    _metric,
    format_rcdts,
    normalize_rcdts,
)


def test_suppression_is_not_converted_to_zero():
    assert _metric("*") == (None, "suppressed")


def test_unpublished_is_distinct_from_missing():
    assert _metric(None, unavailable=True) == (None, "not_published")
    assert _metric(None) == (None, "missing")


def test_legacy_proficiency_adds_levels_four_and_five():
    assert _derived_proficiency(23.44, 18.14) == (41.6, "reported")


def test_legacy_proficiency_stays_suppressed_if_either_component_is_suppressed():
    assert _derived_proficiency("*", 18.1) == (None, "suppressed")


def test_2025_proficiency_uses_the_published_rate_field_directly():
    headers = [
        "IAR ELA Proficiency Rate Grade 4 - Total",
        "IAR ELA Participation Rate Grade 4 - Total",
        "ELA Growth Percentile Grade 4 - Total",
    ]

    mapping = _iar_metric_columns(headers, 2025, "ela")

    assert mapping["proficiency"] == "IAR ELA Proficiency Rate Grade 4 - Total"
    assert mapping["levels"] == []


def test_rcdts_normalization_removes_presentation_hyphens_only():
    assert normalize_rcdts("07-016-1170-02-2003") == "070161170022003"
    assert normalize_rcdts("070161170022003") == "070161170022003"
    assert format_rcdts("070161170022003") == "07-016-1170-02-2003"
    assert normalize_rcdts("04-101-2050-25-201C") == "04101205025201C"


def test_invalid_rcdts_is_rejected():
    with pytest.raises(ValueError, match="15-character"):
        normalize_rcdts("117")
