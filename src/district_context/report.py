from __future__ import annotations

import json
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from statistics import NormalDist
from typing import Any

import duckdb
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from district_context.config import output_dir, project_config, source_config
from district_context.peers import PeerSelection, select_peer_sets


def _safe_number(value: object) -> float | None:
    return None if pd.isna(value) else float(value)


def _format_context_value(value: object, kind: str) -> str:
    if pd.isna(value):
        return "Not available"
    if kind == "percent":
        return f"{100 * float(value):.1f}%"
    if kind == "decimal":
        return f"{float(value):.2f}"
    return f"{float(value):,.0f}"


def _make_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _make_json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_make_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value) if not isinstance(value, (str, bool)) else False:
        return None
    return value


def _query_context(connection: duckdb.DuckDBPyConnection, context_year: int) -> pd.DataFrame:
    return connection.execute(
        "SELECT * FROM mart_context_snapshot WHERE year = ?", [context_year]
    ).df()


def _query_achievement(
    connection: duckdb.DuckDBPyConnection,
    district_ids: list[str],
    grade: int,
) -> pd.DataFrame:
    ids = pd.DataFrame({"district_id": sorted(set(district_ids))})
    connection.register("selected_district_ids", ids)
    try:
        return connection.execute(
            """
            SELECT a.*
            FROM mart_achievement AS a
            INNER JOIN selected_district_ids AS ids USING (district_id)
            WHERE a.grade = ?
            ORDER BY a.subject, a.year, a.district_id
            """,
            [grade],
        ).df()
    finally:
        connection.unregister("selected_district_ids")


def _trend_summary(
    achievement: pd.DataFrame,
    target_id: str,
    peer_ids: set[str],
    subject: str,
    *,
    use_cross_state_error: bool,
    selected_peer_count: int,
    minimum_reporting_peers: int,
    minimum_reporting_fraction: float,
    allow_directional_inference: bool,
    confidence_level: float = 0.95,
) -> pd.DataFrame:
    critical_value = NormalDist().inv_cdf(0.5 + confidence_level / 2)
    subject_rows = achievement.loc[achievement["subject"] == subject].copy()
    target = subject_rows.loc[subject_rows["district_id"] == target_id].set_index("year")
    peers = subject_rows.loc[subject_rows["district_id"].isin(peer_ids)].copy()
    error_column = (
        "standard_error_cross_state" if use_cross_state_error else "standard_error_within_state"
    )
    peer_year = peers.groupby("year").agg(
        peer_median=("achievement_cs", "median"),
        peer_q25=("achievement_cs", lambda values: values.quantile(0.25)),
        peer_q75=("achievement_cs", lambda values: values.quantile(0.75)),
        peer_mean=("achievement_cs", "mean"),
        peer_count=("district_id", "nunique"),
        peer_error_variance=(error_column, lambda values: float(np.square(values).sum())),
    )
    years = pd.Index(range(2009, 2026), name="year")
    summary = pd.DataFrame(index=years).join(
        target[
            [
                "achievement_cs",
                error_column,
                "tested_count",
                "tested_count_estimated_flag",
            ]
        ].rename(
            columns={
                "achievement_cs": "target_estimate",
                error_column: "target_standard_error",
            }
        )
    )
    summary = summary.join(peer_year)
    summary["target_margin"] = critical_value * summary["target_standard_error"]
    summary["target_ci_low"] = summary["target_estimate"] - summary["target_margin"]
    summary["target_ci_high"] = summary["target_estimate"] + summary["target_margin"]
    summary["target_low_precision"] = (
        (summary["tested_count"] < 50)
        | (summary["tested_count_estimated_flag"].fillna(0) == 1)
        | (summary["target_margin"] > 0.50)
    ).fillna(True)
    if selected_peer_count > 0:
        summary["peer_reporting_fraction"] = summary["peer_count"] / selected_peer_count
    else:
        summary["peer_reporting_fraction"] = np.nan
    summary["comparison_has_coverage"] = (
        (summary["peer_count"] >= minimum_reporting_peers)
        & (summary["peer_reporting_fraction"] >= minimum_reporting_fraction)
    ).fillna(False)
    summary["directional_inference_allowed"] = (
        summary["comparison_has_coverage"]
        & ~summary["target_low_precision"]
        & allow_directional_inference
    )
    summary["difference"] = summary["target_estimate"] - summary["peer_mean"]
    summary["difference_standard_error"] = np.sqrt(
        np.square(summary["target_standard_error"])
        + summary["peer_error_variance"] / np.square(summary["peer_count"])
    )
    summary["difference_ci_low"] = (
        summary["difference"] - critical_value * summary["difference_standard_error"]
    ).where(summary["directional_inference_allowed"])
    summary["difference_ci_high"] = (
        summary["difference"] + critical_value * summary["difference_standard_error"]
    ).where(summary["directional_inference_allowed"])
    return summary.reset_index()


def _comparison_phrase(row: pd.Series) -> str:
    if not bool(row["comparison_has_coverage"]):
        return "Not enough reporting peers for a stable comparison"
    if not bool(row["directional_inference_allowed"]):
        if bool(row["target_low_precision"]):
            return "Estimate is too imprecise for a directional comparison"
        return "Descriptive cross-state comparison only"
    if pd.isna(row["difference_ci_low"]) or pd.isna(row["difference_ci_high"]):
        return "Not enough peer data for an uncertainty-aware comparison"
    if row["difference_ci_low"] > 0:
        return "Higher than the peer mean in this estimate"
    if row["difference_ci_high"] < 0:
        return "Lower than the peer mean in this estimate"
    return "Not clearly different from the peer mean"


def _latest_summary(summary: pd.DataFrame, latest_year: int) -> dict[str, Any] | None:
    available = summary.loc[
        (summary["year"] <= latest_year)
        & summary["target_estimate"].notna()
        & summary["peer_median"].notna()
    ]
    if available.empty:
        return None
    row = available.iloc[-1]
    return {
        "year": int(row["year"]),
        "target_estimate": _safe_number(row["target_estimate"]),
        "target_ci_low": _safe_number(row["target_ci_low"]),
        "target_ci_high": _safe_number(row["target_ci_high"]),
        "peer_median": _safe_number(row["peer_median"]),
        "peer_mean": _safe_number(row["peer_mean"]),
        "peer_q25": _safe_number(row["peer_q25"]),
        "peer_q75": _safe_number(row["peer_q75"]),
        "peer_count": int(row["peer_count"]),
        "peer_reporting_fraction": _safe_number(row["peer_reporting_fraction"]),
        "comparison_reportable": bool(row["comparison_has_coverage"]),
        "directional_inference_allowed": bool(row["directional_inference_allowed"]),
        "difference": _safe_number(row["difference"]),
        "difference_ci_low": _safe_number(row["difference_ci_low"]),
        "difference_ci_high": _safe_number(row["difference_ci_high"]),
        "comparison": _comparison_phrase(row),
        "low_precision": bool(row["target_low_precision"]),
    }


def _selection_status_label(status: str) -> str:
    return {
        "full_count_strict": "Full peer count under strict calipers",
        "full_count_relaxed": "Full peer count after documented relaxation",
        "minimum_count_only": "Minimum peer count reached",
        "insufficient": "Insufficient peer count",
    }[status]


def _match_balance_rows(diagnostics: dict[str, Any], pool_type: str) -> list[dict[str, str]]:
    prefix = "state" if pool_type == "same_state" else "national"
    values = diagnostics[f"{prefix}_distance_diagnostics"]["median_domain_distances"]
    labels = {
        "district_scale": "District scale",
        "economic_context": "Economic context",
        "student_composition": "Student composition",
        "place": "Place / locale",
    }
    return [
        {
            "domain": labels[domain],
            "median_distance": "Not available" if value is None else f"{value:.3f}",
        }
        for domain, value in values.items()
    ]


def _trend_figure(
    summary: pd.DataFrame,
    district_name: str,
    subject_label: str,
    peer_label: str,
    confidence_percentage: int,
    include_plotlyjs: bool,
) -> str:
    years = summary["year"]
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=years,
            y=summary["peer_q75"],
            mode="lines",
            line={"width": 0},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    figure.add_trace(
        go.Scatter(
            x=years,
            y=summary["peer_q25"],
            mode="lines",
            line={"width": 0},
            fill="tonexty",
            fillcolor="rgba(42, 111, 151, 0.14)",
            name=f"{peer_label} middle 50%",
            hovertemplate="Year %{x}<br>Peer lower quartile %{y:.2f}<extra></extra>",
            connectgaps=False,
        )
    )
    figure.add_trace(
        go.Scatter(
            x=years,
            y=summary["peer_median"],
            mode="lines",
            line={"color": "#2a6f97", "width": 2, "dash": "dot"},
            name=f"{peer_label} median",
            hovertemplate="Year %{x}<br>Peer median %{y:.2f}<extra></extra>",
            connectgaps=False,
        )
    )
    figure.add_trace(
        go.Scatter(
            x=years,
            y=summary["target_estimate"],
            mode="lines+markers",
            line={"color": "#db6b32", "width": 3},
            marker={"size": 7, "color": "#db6b32"},
            error_y={
                "type": "data",
                "array": summary["target_margin"],
                "visible": True,
                "color": "rgba(219, 107, 50, 0.45)",
                "thickness": 1,
                "width": 2,
            },
            name=district_name,
            hovertemplate=(
                "Year %{x}<br>District estimate %{y:.2f}<br>"
                f"{confidence_percentage}% margin %{{error_y.array:.2f}}<extra></extra>"
            ),
            connectgaps=False,
        )
    )
    figure.add_vrect(
        x0=2019.5,
        x1=2021.5,
        fillcolor="rgba(106, 115, 125, 0.10)",
        line_width=0,
        annotation_text="No 2020–21 results",
        annotation_position="top",
    )
    figure.update_layout(
        title={"text": subject_label, "x": 0.02, "xanchor": "left"},
        template="plotly_white",
        height=390,
        margin={"l": 55, "r": 20, "t": 55, "b": 55},
        legend={"orientation": "h", "y": -0.22, "x": 0},
        hovermode="x unified",
        xaxis={"title": "Spring assessment year", "dtick": 2, "range": [2008.6, 2025.4]},
        yaxis={"title": "Achievement estimate (CS standard deviations)", "zeroline": True},
        font={"family": "Inter, Arial, sans-serif", "color": "#172433"},
    )
    return figure.to_html(
        full_html=False,
        include_plotlyjs=include_plotlyjs,
        config={"displaylogo": False, "responsive": True},
    )


def _context_comparison(target: dict[str, Any], peers: pd.DataFrame) -> list[dict[str, Any]]:
    metrics = [
        ("Enrollment in grades 3–8", "enrollment_grades_3_8", "number"),
        ("Family poverty rate", "family_poverty_rate", "percent"),
        ("Socioeconomic status composite", "socioeconomic_status_composite", "decimal"),
    ]
    rows: list[dict[str, Any]] = []
    for label, column, kind in metrics:
        peer_values = pd.to_numeric(peers[column], errors="coerce").dropna()
        target_value = target.get(column)
        rows.append(
            {
                "label": label,
                "target": _format_context_value(target_value, kind),
                "peer_median": _format_context_value(peer_values.median(), kind)
                if len(peer_values)
                else "Not available",
                "peer_range": (
                    f"{_format_context_value(peer_values.quantile(0.25), kind)} to "
                    f"{_format_context_value(peer_values.quantile(0.75), kind)}"
                    if len(peer_values)
                    else "Not available"
                ),
            }
        )
    rows.append(
        {
            "label": "Dominant locale",
            "target": target.get("dominant_locale") or "Not available",
            "peer_median": peers["dominant_locale"].mode().iloc[0]
            if not peers["dominant_locale"].mode().empty
            else "Not available",
            "peer_range": "Most common category",
        }
    )
    return rows


def build_profile(
    connection: duckdb.DuckDBPyConnection,
    target_id: str,
    *,
    grade: int,
    destination: Path | None = None,
) -> Path:
    cfg = project_config()
    analysis = cfg["analysis"]
    confidence_level = float(analysis["confidence_level"])
    confidence_percentage = round(100 * confidence_level)
    context = _query_context(connection, int(analysis["context_year"]))
    selection: PeerSelection = select_peer_sets(
        context,
        target_id,
        grade=grade,
        domain_weights=cfg["peer_model"]["domain_weights"],
        state_count=int(analysis["state_peer_count"]),
        state_minimum=int(analysis["state_peer_minimum"]),
        national_count=int(analysis["national_peer_count"]),
        max_national_per_state=int(analysis["max_national_peers_per_state"]),
        strict_calipers=cfg["peer_model"]["strict_calipers"],
        relaxed_calipers=cfg["peer_model"]["relaxed_calipers"],
        model_version=str(cfg["peer_model"]["version"]),
    )
    peers = selection.peers
    state_peers = peers.loc[peers["pool_type"] == "same_state"].copy()
    national_peers = peers.loc[peers["pool_type"] == "national_analogs"].copy()
    state_reportable = len(state_peers) >= int(analysis["state_peer_minimum"])
    primary_peers = state_peers if state_reportable else national_peers
    primary_pool = "same_state" if state_reportable else "national_analogs"
    peer_label = (
        "Similar in-state districts" if state_reportable else "Similar districts nationally"
    )

    achievement = _query_achievement(
        connection,
        [target_id, *peers["peer_id"].tolist()],
        grade,
    )
    use_cross_state_error = primary_pool == "national_analogs"
    subject_specs = [("mth", "Mathematics"), ("rla", "Reading / language arts")]
    subject_panels: list[dict[str, Any]] = []
    for subject_index, (subject, label) in enumerate(subject_specs):
        trend = _trend_summary(
            achievement,
            target_id,
            set(primary_peers["peer_id"]),
            subject,
            use_cross_state_error=use_cross_state_error,
            selected_peer_count=len(primary_peers),
            minimum_reporting_peers=int(analysis["minimum_reporting_peers"]),
            minimum_reporting_fraction=float(analysis["minimum_reporting_fraction"]),
            allow_directional_inference=not use_cross_state_error,
            confidence_level=confidence_level,
        )
        subject_panels.append(
            {
                "subject": subject,
                "label": label,
                "chart": _trend_figure(
                    trend,
                    str(selection.target["district_name"]),
                    label,
                    peer_label,
                    confidence_percentage,
                    include_plotlyjs=subject_index == 0,
                ),
                "latest": _latest_summary(trend, int(analysis["latest_result_year"])),
            }
        )

    latest_by_pool: list[dict[str, Any]] = []
    for pool_type, pool_frame, pool_label, cross_state in (
        ("same_state", state_peers, "Same-state peers", False),
        ("national_analogs", national_peers, "National analogs", True),
    ):
        for subject, label in subject_specs:
            trend = _trend_summary(
                achievement,
                target_id,
                set(pool_frame["peer_id"]),
                subject,
                use_cross_state_error=cross_state,
                selected_peer_count=len(pool_frame),
                minimum_reporting_peers=int(analysis["minimum_reporting_peers"]),
                minimum_reporting_fraction=float(analysis["minimum_reporting_fraction"]),
                allow_directional_inference=not cross_state,
                confidence_level=confidence_level,
            )
            latest = _latest_summary(trend, int(analysis["latest_result_year"]))
            latest_by_pool.append(
                {
                    "pool_type": pool_type,
                    "pool_label": pool_label,
                    "subject": label,
                    "selected_peer_count": len(pool_frame),
                    "reportable": bool(latest and latest["comparison_reportable"]),
                    "latest": latest,
                }
            )

    qa_rows = []
    with suppress(duckdb.CatalogException):
        qa_rows = (
            connection.execute("SELECT * FROM qa_result ORDER BY name").df().to_dict("records")
        )
    exclusion_rows = []
    with suppress(duckdb.CatalogException):
        exclusion_rows = (
            connection.execute("SELECT * FROM mart_exclusion_audit").df().to_dict("records")
        )

    rendered_at = datetime.now(UTC)
    payload = {
        "title": cfg["project"]["title"],
        "district": selection.target,
        "grade": grade,
        "context_year": int(analysis["context_year"]),
        "confidence_percentage": confidence_percentage,
        "peer_label": peer_label,
        "primary_peer_count": len(primary_peers),
        "primary_pool": primary_pool,
        "state_reportable": state_reportable,
        "subjects": subject_panels,
        "latest_by_pool": latest_by_pool,
        "context_comparison": _context_comparison(selection.target, primary_peers),
        "match_balance": _match_balance_rows(selection.diagnostics, primary_pool),
        "peers": primary_peers.to_dict("records"),
        "diagnostics": selection.diagnostics,
        "selection_status": selection.diagnostics[
            "state_selection_status"
            if primary_pool == "same_state"
            else "national_selection_status"
        ],
        "selection_status_label": _selection_status_label(
            selection.diagnostics[
                "state_selection_status"
                if primary_pool == "same_state"
                else "national_selection_status"
            ]
        ),
        "qa_passed": bool(qa_rows)
        and not any(row["status"] == "fail" and row["severity"] == "error" for row in qa_rows),
        "qa_count": len(qa_rows),
        "qa_warning_count": sum(row["status"] == "warn" for row in qa_rows),
        "exclusions": exclusion_rows,
        "rendered_at": rendered_at.strftime("%Y-%m-%d %H:%M UTC"),
        "sources": source_config(),
    }
    environment = Environment(
        loader=PackageLoader("district_context", "templates"),
        autoescape=select_autoescape(["html", "xml"]),
        undefined=StrictUndefined,
    )
    html = environment.get_template("district_profile.html.j2").render(**payload)
    destination = destination or output_dir() / f"district_profile_{target_id}_grade_{grade}.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding="utf-8")

    peers.to_csv(output_dir() / f"peer_membership_{target_id}_grade_{grade}.csv", index=False)
    summary_payload = _make_json_safe(
        {
            "target_id": target_id,
            "district_name": selection.target["district_name"],
            "grade": grade,
            "rendered_at_utc": rendered_at.isoformat(),
            "diagnostics": selection.diagnostics,
            "latest_by_pool": latest_by_pool,
        }
    )
    (output_dir() / f"profile_summary_{target_id}_grade_{grade}.json").write_text(
        json.dumps(summary_payload, indent=2), encoding="utf-8"
    )
    return destination
