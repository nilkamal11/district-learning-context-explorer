from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

DOMAIN_COLUMNS = {
    "district_scale": ["log_enrollment"],
    "economic_context": ["family_poverty_rate", "socioeconomic_status_composite"],
    "student_composition": [
        "share_native_american",
        "share_asian",
        "share_hispanic",
        "share_black",
        "share_white",
        "share_other_race_ethnicity",
    ],
    "place": ["share_city", "share_suburb", "share_town", "share_rural"],
}

MATCH_CONTEXT_COLUMNS = [
    "district_id",
    "district_name",
    "state_abbreviation",
    "year",
    "grade_low",
    "grade_high",
    "grade_span_bucket",
    "dominant_locale",
    "has_core_peer_context",
    "enrollment_grades_3_8",
    "family_poverty_rate",
    "socioeconomic_status_composite",
    *DOMAIN_COLUMNS["student_composition"],
    *DOMAIN_COLUMNS["place"],
]


@dataclass(frozen=True)
class PeerSelection:
    target: dict[str, Any]
    peers: pd.DataFrame
    diagnostics: dict[str, Any]


def hellinger_distance(left: np.ndarray, right: np.ndarray) -> float:
    """Calculate Hellinger distance for two nonnegative composition vectors."""
    if np.isnan(left).any() or np.isnan(right).any():
        return np.nan
    left_sum = left.sum()
    right_sum = right.sum()
    if left_sum <= 0 or right_sum <= 0:
        return np.nan
    left = left / left_sum
    right = right / right_sum
    return float(np.sqrt(0.5 * np.square(np.sqrt(left) - np.sqrt(right)).sum()))


def _robust_ranges(frame: pd.DataFrame) -> dict[str, float]:
    ranges: dict[str, float] = {}
    numeric_columns = DOMAIN_COLUMNS["district_scale"] + DOMAIN_COLUMNS["economic_context"]
    for column in numeric_columns:
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        span = float(values.quantile(0.95) - values.quantile(0.05)) if len(values) else 0.0
        ranges[column] = span if span > 0 else 1.0
    return ranges


def _numeric_distance(value: object, target: object, span: float) -> float:
    if pd.isna(value) or pd.isna(target):
        return np.nan
    return float(min(abs(float(value) - float(target)) / span, 1.0))


def _composition_distances(
    frame: pd.DataFrame, columns: list[str], target_vector: np.ndarray
) -> pd.Series:
    return frame[columns].apply(
        lambda row: hellinger_distance(row.to_numpy(dtype=float), target_vector), axis=1
    )


def calculate_context_distances(
    eligible: pd.DataFrame,
    target_id: str,
    domain_weights: dict[str, float],
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Score contextual similarity from an explicit context-only column allowlist."""
    missing = sorted(set(MATCH_CONTEXT_COLUMNS) - set(eligible.columns))
    if missing:
        raise ValueError(f"Peer context is missing required columns: {missing}")

    working = eligible[MATCH_CONTEXT_COLUMNS].copy()
    working["log_enrollment"] = np.log1p(working["enrollment_grades_3_8"].astype(float))
    target_rows = working.loc[working["district_id"] == target_id]
    if len(target_rows) != 1:
        raise ValueError(
            f"Expected one context row for target {target_id}; found {len(target_rows)}"
        )
    target = target_rows.iloc[0]
    ranges = _robust_ranges(working)

    for domain in ("district_scale", "economic_context"):
        columns = DOMAIN_COLUMNS[domain]
        feature_distances = pd.DataFrame(
            {
                column: (
                    (pd.to_numeric(working[column], errors="coerce") - float(target[column])).abs()
                    / ranges[column]
                ).clip(upper=1.0)
                for column in columns
            }
        )
        working[f"distance_{domain}"] = feature_distances.mean(axis=1, skipna=True)

    for domain in ("student_composition", "place"):
        columns = DOMAIN_COLUMNS[domain]
        target_vector = target[columns].to_numpy(dtype=float)
        working[f"distance_{domain}"] = _composition_distances(working, columns, target_vector)

    distance_columns = [f"distance_{domain}" for domain in domain_weights]

    def weighted_distance(row: pd.Series) -> float:
        available = {
            domain: float(row[f"distance_{domain}"])
            for domain in domain_weights
            if not pd.isna(row[f"distance_{domain}"])
        }
        if set(available) != set(domain_weights):
            return np.nan
        denominator = sum(domain_weights[domain] for domain in available)
        numerator = sum(domain_weights[domain] * value for domain, value in available.items())
        return numerator / denominator

    working["context_distance"] = working.apply(weighted_distance, axis=1)
    working["missing_match_domains"] = working[distance_columns].isna().sum(axis=1)
    return working, ranges


def _apply_calipers(
    scored: pd.DataFrame,
    target: pd.Series,
    *,
    enrollment_factor: float,
    poverty_points: float,
    same_locale: bool,
) -> pd.DataFrame:
    enrollment = float(target["enrollment_grades_3_8"])
    mask = (
        (scored["grade_span_bucket"] == target["grade_span_bucket"])
        & (scored["enrollment_grades_3_8"] >= enrollment / enrollment_factor)
        & (scored["enrollment_grades_3_8"] <= enrollment * enrollment_factor)
        & (
            (scored["family_poverty_rate"] - float(target["family_poverty_rate"])).abs()
            <= poverty_points
        )
        & scored["context_distance"].notna()
    )
    if same_locale:
        mask &= scored["dominant_locale"] == target["dominant_locale"]
    return scored.loc[mask].copy()


def _staged_candidates(
    scored: pd.DataFrame,
    target: pd.Series,
    *,
    desired_count: int,
    minimum_count: int,
    strict_calipers: dict[str, Any],
    relaxed_calipers: dict[str, Any],
) -> tuple[pd.DataFrame, str]:
    stages = [
        (
            "strict",
            float(strict_calipers["enrollment_factor"]),
            float(strict_calipers["poverty_points"]),
            bool(strict_calipers["same_locale"]),
        ),
        (
            "locale_relaxed",
            float(strict_calipers["enrollment_factor"]),
            float(strict_calipers["poverty_points"]),
            False,
        ),
        (
            "wide_calipers",
            float(relaxed_calipers["enrollment_factor"]),
            float(relaxed_calipers["poverty_points"]),
            bool(relaxed_calipers["same_locale"]),
        ),
    ]
    latest = scored.iloc[0:0].copy()
    latest_name = stages[-1][0]
    for name, enrollment_factor, poverty_points, same_locale in stages:
        latest = _apply_calipers(
            scored,
            target,
            enrollment_factor=enrollment_factor,
            poverty_points=poverty_points,
            same_locale=same_locale,
        )
        latest_name = name
        if len(latest) >= desired_count or len(latest) >= minimum_count:
            break
    return latest, latest_name


def _cap_per_state(frame: pd.DataFrame, max_per_state: int) -> pd.DataFrame:
    ordered = frame.sort_values(["context_distance", "district_id"]).copy()
    ordered["state_match_order"] = ordered.groupby("state_abbreviation").cumcount() + 1
    return ordered.loc[ordered["state_match_order"] <= max_per_state]


def _selection_status(selected_count: int, minimum: int, desired: int, stage: str) -> str:
    if selected_count < minimum:
        return "insufficient"
    if selected_count < desired:
        return "minimum_count_only"
    if stage == "strict":
        return "full_count_strict"
    return "full_count_relaxed"


def _distance_diagnostics(
    selected: pd.DataFrame, domain_weights: dict[str, float]
) -> dict[str, Any]:
    if selected.empty:
        return {
            "median_context_distance": None,
            "maximum_context_distance": None,
            "median_domain_distances": {domain: None for domain in domain_weights},
        }
    return {
        "median_context_distance": float(selected["context_distance"].median()),
        "maximum_context_distance": float(selected["context_distance"].max()),
        "median_domain_distances": {
            domain: float(selected[f"distance_{domain}"].median()) for domain in domain_weights
        },
    }


def select_peer_sets(
    context: pd.DataFrame,
    target_id: str,
    *,
    grade: int,
    domain_weights: dict[str, float],
    state_count: int = 15,
    state_minimum: int = 10,
    national_count: int = 20,
    max_national_per_state: int = 3,
    strict_calipers: dict[str, Any] | None = None,
    relaxed_calipers: dict[str, Any] | None = None,
    model_version: str = "context-match-v1",
) -> PeerSelection:
    """Create fixed same-state and national peer sets from one context snapshot."""
    strict_calipers = strict_calipers or {
        "enrollment_factor": 4,
        "poverty_points": 0.15,
        "same_locale": True,
    }
    relaxed_calipers = relaxed_calipers or {
        "enrollment_factor": 8,
        "poverty_points": 0.25,
        "same_locale": False,
    }
    missing = sorted(set(MATCH_CONTEXT_COLUMNS) - set(context.columns))
    if missing:
        raise ValueError(f"Peer context is missing required columns: {missing}")
    context_only = context[MATCH_CONTEXT_COLUMNS]
    eligible = context_only.loc[
        context_only["has_core_peer_context"].astype(bool)
        & (context_only["grade_low"] <= grade)
        & (context_only["grade_high"] >= grade)
    ].copy()
    if target_id not in set(eligible["district_id"]):
        raise ValueError(
            f"District {target_id} lacks the core context or grade coverage required for matching"
        )

    scored, ranges = calculate_context_distances(eligible, target_id, domain_weights)
    target = scored.loc[scored["district_id"] == target_id].iloc[0]
    if pd.isna(target["context_distance"]):
        raise ValueError(f"District {target_id} is missing at least one required match domain")
    candidates = scored.loc[scored["district_id"] != target_id].copy()

    state_universe = candidates.loc[
        candidates["state_abbreviation"] == target["state_abbreviation"]
    ]
    state_candidates, state_stage = _staged_candidates(
        state_universe,
        target,
        desired_count=state_count,
        minimum_count=state_minimum,
        strict_calipers=strict_calipers,
        relaxed_calipers=relaxed_calipers,
    )
    state_selected = state_candidates.sort_values(["context_distance", "district_id"]).head(
        state_count
    )
    state_selected = state_selected.assign(
        pool_type="same_state",
        relaxation_stage=state_stage,
        match_order=np.arange(1, len(state_selected) + 1),
    )

    cross_state_candidates = candidates.loc[
        candidates["state_abbreviation"] != target["state_abbreviation"]
    ]
    national_candidates, national_stage = _staged_candidates(
        cross_state_candidates,
        target,
        desired_count=national_count,
        minimum_count=national_count,
        strict_calipers=strict_calipers,
        relaxed_calipers=relaxed_calipers,
    )
    national_selected = _cap_per_state(
        national_candidates, max_per_state=max_national_per_state
    ).head(national_count)
    national_selected = national_selected.assign(
        pool_type="national_analogs",
        relaxation_stage=national_stage,
        match_order=np.arange(1, len(national_selected) + 1),
    )

    selected = pd.concat([state_selected, national_selected], ignore_index=True)
    keep = [
        "district_id",
        "district_name",
        "state_abbreviation",
        "pool_type",
        "match_order",
        "context_distance",
        "relaxation_stage",
        "missing_match_domains",
        "grade_span_bucket",
        "dominant_locale",
        "enrollment_grades_3_8",
        "family_poverty_rate",
        "socioeconomic_status_composite",
        *[f"distance_{domain}" for domain in domain_weights],
    ]
    selected = selected[keep].rename(columns={"district_id": "peer_id"})
    selected.insert(0, "target_id", target_id)

    diagnostics = {
        "model_version": model_version,
        "strict_calipers": strict_calipers,
        "relaxed_calipers": relaxed_calipers,
        "context_year": int(target["year"]),
        "grade": int(grade),
        "eligible_all_candidates": int(len(candidates)),
        "eligible_national_candidates": int(len(cross_state_candidates)),
        "eligible_state_candidates": int(len(state_universe)),
        "state_selected": int(len(state_selected)),
        "state_selection_status": _selection_status(
            len(state_selected), state_minimum, state_count, state_stage
        ),
        "state_relaxation_stage": state_stage,
        "national_selected": int(len(national_selected)),
        "national_selection_status": _selection_status(
            len(national_selected), national_count, national_count, national_stage
        ),
        "national_relaxation_stage": national_stage,
        "state_distance_diagnostics": _distance_diagnostics(state_selected, domain_weights),
        "national_distance_diagnostics": _distance_diagnostics(national_selected, domain_weights),
        "robust_feature_ranges": ranges,
        "outcome_variables_used": [],
    }
    target_payload = target.drop(labels=["log_enrollment"], errors="ignore").to_dict()
    return PeerSelection(target=target_payload, peers=selected, diagnostics=diagnostics)
