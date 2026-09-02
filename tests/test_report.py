import numpy as np
import pandas as pd

from district_context.report import _trend_summary


def achievement_fixture(peer_count: int, *, cross_state_error: float = 0.08) -> pd.DataFrame:
    rows = [
        {
            "district_id": "0000001",
            "subject": "mth",
            "year": 2024,
            "achievement_cs": 0.40,
            "standard_error_within_state": 0.05,
            "standard_error_cross_state": cross_state_error,
            "tested_count": 100,
            "tested_count_estimated_flag": 0,
        }
    ]
    rows.extend(
        {
            "district_id": str(index + 2).zfill(7),
            "subject": "mth",
            "year": 2024,
            "achievement_cs": 0.05,
            "standard_error_within_state": 0.05,
            "standard_error_cross_state": 0.08,
            "tested_count": 100,
            "tested_count_estimated_flag": 0,
        }
        for index in range(peer_count)
    )
    return pd.DataFrame(rows)


def test_sparse_reporting_peers_suppress_directional_comparison():
    data = achievement_fixture(9)
    summary = _trend_summary(
        data,
        "0000001",
        set(data.loc[data["district_id"] != "0000001", "district_id"]),
        "mth",
        use_cross_state_error=False,
        selected_peer_count=15,
        minimum_reporting_peers=10,
        minimum_reporting_fraction=0.70,
        allow_directional_inference=True,
    )
    row = summary.loc[summary["year"] == 2024].iloc[0]
    assert not bool(row["comparison_has_coverage"])
    assert np.isnan(row["difference_ci_low"])


def test_national_comparison_remains_descriptive_with_sufficient_coverage():
    data = achievement_fixture(12)
    summary = _trend_summary(
        data,
        "0000001",
        set(data.loc[data["district_id"] != "0000001", "district_id"]),
        "mth",
        use_cross_state_error=True,
        selected_peer_count=12,
        minimum_reporting_peers=10,
        minimum_reporting_fraction=0.70,
        allow_directional_inference=False,
    )
    row = summary.loc[summary["year"] == 2024].iloc[0]
    assert bool(row["comparison_has_coverage"])
    assert not bool(row["directional_inference_allowed"])
    assert np.isnan(row["difference_ci_low"])


def test_precision_rule_uses_the_error_for_the_selected_pool():
    data = achievement_fixture(12, cross_state_error=0.30)
    summary = _trend_summary(
        data,
        "0000001",
        set(data.loc[data["district_id"] != "0000001", "district_id"]),
        "mth",
        use_cross_state_error=True,
        selected_peer_count=12,
        minimum_reporting_peers=10,
        minimum_reporting_fraction=0.70,
        allow_directional_inference=True,
    )
    row = summary.loc[summary["year"] == 2024].iloc[0]
    assert bool(row["target_low_precision"])
    assert not bool(row["directional_inference_allowed"])
