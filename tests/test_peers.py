import numpy as np
import pandas as pd
import pytest

from district_context.peers import calculate_context_distances, hellinger_distance, select_peer_sets

WEIGHTS = {
    "district_scale": 0.25,
    "economic_context": 0.25,
    "student_composition": 0.25,
    "place": 0.25,
}


def make_context() -> pd.DataFrame:
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
                "share_english_learners": 0.10 + shift / 2,
                "share_special_education": 0.13,
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


def test_hellinger_distance_is_zero_for_identical_vectors():
    vector = np.array([0.2, 0.3, 0.5])
    assert hellinger_distance(vector, vector) == pytest.approx(0.0)


def test_peer_selection_is_context_only_and_excludes_target():
    context = make_context()
    selection = select_peer_sets(
        context,
        "0000001",
        grade=4,
        domain_weights=WEIGHTS,
        state_count=15,
        state_minimum=10,
        national_count=20,
        max_national_per_state=3,
    )
    assert "0000001" not in set(selection.peers["peer_id"])
    assert selection.diagnostics["outcome_variables_used"] == []
    assert selection.diagnostics["state_selected"] == 15
    assert set(selection.peers["pool_type"]) == {"same_state", "national_analogs"}
    national = selection.peers.loc[selection.peers["pool_type"] == "national_analogs"]
    assert set(national["state_abbreviation"]).isdisjoint({"IL"})


def test_context_allowlist_drops_outcome_columns():
    context = make_context()
    baseline, _ = calculate_context_distances(context, "0000001", WEIGHTS)
    context["growth_score"] = np.linspace(-10, 10, len(context))
    context["achievement_cs"] = np.linspace(10, -10, len(context))
    guarded, _ = calculate_context_distances(context, "0000001", WEIGHTS)
    assert "growth_score" not in guarded.columns
    assert "achievement_cs" not in guarded.columns
    pd.testing.assert_series_equal(
        baseline["context_distance"], guarded["context_distance"], check_names=False
    )


def test_national_relaxation_is_decided_after_state_caps():
    context = make_context()
    external_indexes = context.index[context["state_abbreviation"] != "IL"]
    states = ["WI", "IN", "IA", "MO", "OH", "KY", "MI", "MN"]
    for position, index in enumerate(external_indexes):
        state_position = min(position // 5, len(states) - 1)
        context.loc[index, "state_abbreviation"] = states[state_position]
        context.loc[index, "dominant_locale"] = (
            "Suburb" if state_position < 4 else "Rural"
        )

    selection = select_peer_sets(
        context,
        "0000001",
        grade=4,
        domain_weights=WEIGHTS,
        state_count=15,
        state_minimum=10,
        national_count=20,
        max_national_per_state=3,
    )

    national = selection.peers.loc[selection.peers["pool_type"] == "national_analogs"]
    assert len(national) == 20
    assert selection.diagnostics["national_relaxation_stage"] == "locale_relaxed"
    assert national.groupby("state_abbreviation").size().max() <= 3
