(function () {
  "use strict";

  const data = window.DISTRICT_DASHBOARD_DATA;
  if (!data) {
    document.getElementById("district-heading").textContent = "Dashboard data could not be loaded";
    return;
  }

  const indexFields = (fields) => Object.fromEntries(fields.map((field, index) => [field, index]));
  const CATALOG = indexFields(data.catalog_fields);
  const CONTEXT = indexFields(data.context_fields);
  const ACHIEVEMENT = indexFields(data.achievement_fields);
  const catalog = data.catalog;
  const contexts = data.context;
  const grade = data.grade;
  const analysis = data.model.analysis;
  const peerModel = data.model.peer_model;
  const ranges = data.model.robust_ranges;
  const loader = window.SEDA_DATA_LOADER;
  const years = data.workbench.years;
  const chartYears = Array.from(
    { length: years.at(-1) - years[0] + 1 },
    (_, index) => years[0] + index
  );
  const criticalValue = data.workbench.confidence_critical_value;
  const confidencePercent = Math.round(data.workbench.confidence_level * 100);

  const catalogById = new Map(catalog.map((row) => [row[CATALOG.district_id], row]));
  const contextById = new Map(contexts.map((row) => [row[CONTEXT.district_id], row]));
  const eligibleContexts = contexts.filter((row) => (
    row[CONTEXT.has_core_context]
    && row[CONTEXT.grade_low] !== null
    && row[CONTEXT.grade_high] !== null
    && row[CONTEXT.grade_low] <= grade
    && row[CONTEXT.grade_high] >= grade
  ));

  const achievementByDistrict = new Map();
  const indexedAchievementStates = new Set();
  let renderRequestToken = 0;
  let selectorsInitialized = false;
  let technicalRendered = false;

  const indexStateBundle = (bundle) => {
    if (indexedAchievementStates.has(bundle.state)) return;
    for (const row of bundle.achievement) {
      const districtId = row[ACHIEVEMENT.district_id];
      const subject = row[ACHIEVEMENT.subject];
      if (!achievementByDistrict.has(districtId)) {
        achievementByDistrict.set(districtId, { mth: [], rla: [] });
      }
      achievementByDistrict.get(districtId)[subject].push(row);
    }
    indexedAchievementStates.add(bundle.state);
  };

  const loadAchievementStates = async (states) => {
    if (!loader) throw new Error("The dashboard data loader is unavailable.");
    const needed = [...new Set(states)].filter((state) => !indexedAchievementStates.has(state));
    const bundles = await Promise.all(needed.map((state) => loader.loadAchievementState(grade, state)));
    for (const bundle of bundles) indexStateBundle(bundle);
  };

  const elements = Object.fromEntries([
    "state-select", "district-select", "district-heading", "district-subtitle",
    "district-id-meta", "district-state-meta", "availability-indicator", "catalog-count",
    "unavailable-panel", "unavailable-title", "unavailable-copy", "analysis-content",
    "primary-pool-label", "math-card", "reading-card", "context-table-body",
    "selection-status-copy", "distance-bars", "peer-table-body", "sensitivity-table-body",
    "source-size-kpi", "staged-rows-kpi", "districts-kpi", "qa-kpi", "source-table-body",
    "hash-list", "model-table-body", "sql-model-list", "qa-status-grid", "qa-warning-list",
    "failure-line", "publication-note"
  ].map((id) => [id, document.getElementById(id)]));

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const formatNumber = (value, digits = 0) => value === null || Number.isNaN(value)
    ? "Not available"
    : Number(value).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });

  const formatPercent = (value) => value === null ? "Not available" : `${(100 * value).toFixed(1)}%`;

  const formatBytes = (bytes) => {
    if (bytes === null || bytes === undefined) return "Not available";
    const units = ["bytes", "KB", "MB", "GB"];
    let value = Number(bytes);
    let unit = 0;
    while (value >= 1000 && unit < units.length - 1) {
      value /= 1000;
      unit += 1;
    }
    const digits = unit === 0 ? 0 : value >= 100 ? 1 : 2;
    return `${value.toFixed(digits)} ${units[unit]}`;
  };

  const formatExactBytes = (bytes) => bytes === null || bytes === undefined
    ? "Not available"
    : `${formatBytes(bytes)} (${formatNumber(bytes)} bytes)`;

  const average = (values) => values.length
    ? values.reduce((total, value) => total + value, 0) / values.length
    : null;

  const quantile = (values, probability) => {
    if (!values.length) return null;
    const sorted = [...values].sort((left, right) => left - right);
    const position = (sorted.length - 1) * probability;
    const lower = Math.floor(position);
    const upper = Math.ceil(position);
    if (lower === upper) return sorted[lower];
    return sorted[lower] + (sorted[upper] - sorted[lower]) * (position - lower);
  };

  const mode = (values) => {
    const counts = new Map();
    for (const value of values.filter(Boolean)) counts.set(value, (counts.get(value) || 0) + 1);
    return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0]?.[0] || null;
  };

  const hellinger = (left, right) => {
    if (left.some((value) => value === null) || right.some((value) => value === null)) return null;
    const leftSum = left.reduce((sum, value) => sum + value, 0);
    const rightSum = right.reduce((sum, value) => sum + value, 0);
    if (leftSum <= 0 || rightSum <= 0) return null;
    const squared = left.reduce((sum, value, index) => {
      const difference = Math.sqrt(value / leftSum) - Math.sqrt(right[index] / rightSum);
      return sum + difference * difference;
    }, 0);
    return Math.sqrt(0.5 * squared);
  };

  const clippedDistance = (left, right, range) => {
    if (left === null || right === null || !range) return null;
    return Math.min(Math.abs(left - right) / range, 1);
  };

  const scoreContext = (candidate, target) => {
    const scale = clippedDistance(
      Math.log1p(candidate[CONTEXT.enrollment]),
      Math.log1p(target[CONTEXT.enrollment]),
      ranges.log_enrollment
    );
    const economic = average([
      clippedDistance(candidate[CONTEXT.poverty], target[CONTEXT.poverty], ranges.family_poverty_rate),
      clippedDistance(candidate[CONTEXT.ses], target[CONTEXT.ses], ranges.socioeconomic_status_composite)
    ].filter((value) => value !== null));
    const composition = hellinger(
      [
        candidate[CONTEXT.native_american], candidate[CONTEXT.asian], candidate[CONTEXT.hispanic],
        candidate[CONTEXT.black], candidate[CONTEXT.white], candidate[CONTEXT.other_race_ethnicity]
      ],
      [
        target[CONTEXT.native_american], target[CONTEXT.asian], target[CONTEXT.hispanic],
        target[CONTEXT.black], target[CONTEXT.white], target[CONTEXT.other_race_ethnicity]
      ]
    );
    const place = hellinger(
      [candidate[CONTEXT.city], candidate[CONTEXT.suburb], candidate[CONTEXT.town], candidate[CONTEXT.rural]],
      [target[CONTEXT.city], target[CONTEXT.suburb], target[CONTEXT.town], target[CONTEXT.rural]]
    );
    const domains = { district_scale: scale, economic_context: economic, student_composition: composition, place };
    if (Object.values(domains).some((value) => value === null || Number.isNaN(value))) return null;
    const distance = Object.entries(domains).reduce(
      (sum, [domain, value]) => sum + peerModel.domain_weights[domain] * value,
      0
    ) / Object.values(peerModel.domain_weights).reduce((sum, value) => sum + value, 0);
    return { row: candidate, distance, domains };
  };

  const applyCalipers = (scored, target, settings) => {
    const targetEnrollment = target[CONTEXT.enrollment];
    return scored.filter(({ row }) => (
      row[CONTEXT.grade_span] === target[CONTEXT.grade_span]
      && row[CONTEXT.enrollment] >= targetEnrollment / settings.enrollment_factor
      && row[CONTEXT.enrollment] <= targetEnrollment * settings.enrollment_factor
      && Math.abs(row[CONTEXT.poverty] - target[CONTEXT.poverty]) <= settings.poverty_points
      && (!settings.same_locale || row[CONTEXT.locale] === target[CONTEXT.locale])
    ));
  };

  const capStates = (rows, maximum) => {
    const counts = new Map();
    return rows.filter(({ row }) => {
      const state = row[CONTEXT.state];
      const count = counts.get(state) || 0;
      if (count >= maximum) return false;
      counts.set(state, count + 1);
      return true;
    });
  };

  const stagedSelection = (scored, target, desired, minimum, maxPerState = null) => {
    const stages = [
      ["strict", peerModel.strict_calipers],
      ["locale_relaxed", { ...peerModel.strict_calipers, same_locale: false }],
      ["wide_calipers", peerModel.relaxed_calipers]
    ];
    let candidates = [];
    let stage = "wide_calipers";
    for (const [stageName, settings] of stages) {
      candidates = applyCalipers(scored, target, settings).sort((left, right) => (
        left.distance - right.distance
        || left.row[CONTEXT.district_id].localeCompare(right.row[CONTEXT.district_id])
      ));
      if (maxPerState !== null) candidates = capStates(candidates, maxPerState);
      stage = stageName;
      if (candidates.length >= minimum) break;
    }
    return { selected: candidates.slice(0, desired), stage };
  };

  const selectionStatus = (count, minimum, desired, stage) => {
    if (count < minimum) return "insufficient";
    if (count < desired) return "minimum_count_only";
    return stage === "strict" ? "full_count_strict" : "full_count_relaxed";
  };

  const selectPeers = (target) => {
    const targetId = target[CONTEXT.district_id];
    const scored = eligibleContexts
      .filter((row) => row[CONTEXT.district_id] !== targetId)
      .map((row) => scoreContext(row, target))
      .filter(Boolean);
    const stateUniverse = scored.filter(({ row }) => row[CONTEXT.state] === target[CONTEXT.state]);
    const nationalUniverse = scored.filter(({ row }) => row[CONTEXT.state] !== target[CONTEXT.state]);
    const sameState = stagedSelection(
      stateUniverse,
      target,
      analysis.state_peer_count,
      analysis.state_peer_minimum
    );
    const national = stagedSelection(
      nationalUniverse,
      target,
      analysis.national_peer_count,
      analysis.national_peer_count,
      analysis.max_national_peers_per_state
    );
    return {
      sameState: {
        ...sameState,
        status: selectionStatus(
          sameState.selected.length,
          analysis.state_peer_minimum,
          analysis.state_peer_count,
          sameState.stage
        ),
        universe: stateUniverse.length
      },
      national: {
        ...national,
        status: selectionStatus(
          national.selected.length,
          analysis.national_peer_count,
          analysis.national_peer_count,
          national.stage
        ),
        universe: nationalUniverse.length
      }
    };
  };

  const achievementRow = (districtId, subject, year) => (
    achievementByDistrict.get(districtId)?.[subject]?.find((row) => row[ACHIEVEMENT.year] === year) || null
  );

  const trendSummary = (targetId, peers, subject, crossState) => {
    const selectedCount = peers.length;
    return chartYears.map((year) => {
      const target = achievementRow(targetId, subject, year);
      const peerRows = peers
        .map(({ row }) => achievementRow(row[CONTEXT.district_id], subject, year))
        .filter((row) => row && row[ACHIEVEMENT.estimate] !== null);
      const peerEstimates = peerRows.map((row) => row[ACHIEVEMENT.estimate]);
      const errorIndex = crossState
        ? ACHIEVEMENT.standard_error_cross_state
        : ACHIEVEMENT.standard_error_within_state;
      const targetEstimate = target?.[ACHIEVEMENT.estimate] ?? null;
      const targetError = target?.[errorIndex] ?? null;
      const targetMargin = targetError === null ? null : criticalValue * targetError;
      const lowPrecision = target ? (
        (target[ACHIEVEMENT.tested_count] !== null && target[ACHIEVEMENT.tested_count] < 50)
        || target[ACHIEVEMENT.tested_count_estimated] === 1
        || (targetMargin !== null && targetMargin > 0.5)
      ) : true;
      const peerCount = peerRows.length;
      const reportingFraction = selectedCount ? peerCount / selectedCount : null;
      const hasCoverage = peerCount >= analysis.minimum_reporting_peers
        && reportingFraction >= analysis.minimum_reporting_fraction;
      const directionalAllowed = hasCoverage && !lowPrecision && !crossState;
      const peerMean = average(peerEstimates);
      const difference = targetEstimate === null || peerMean === null ? null : targetEstimate - peerMean;
      const peerErrorVariance = peerRows.reduce((sum, row) => {
        const error = row[errorIndex];
        return sum + (error === null ? 0 : error * error);
      }, 0);
      const differenceError = targetError === null || peerCount === 0
        ? null
        : Math.sqrt(targetError * targetError + peerErrorVariance / (peerCount * peerCount));
      const differenceLow = directionalAllowed && difference !== null && differenceError !== null
        ? difference - criticalValue * differenceError
        : null;
      const differenceHigh = directionalAllowed && difference !== null && differenceError !== null
        ? difference + criticalValue * differenceError
        : null;
      return {
        year,
        targetEstimate,
        targetMargin,
        targetLow: targetEstimate === null || targetMargin === null ? null : targetEstimate - targetMargin,
        targetHigh: targetEstimate === null || targetMargin === null ? null : targetEstimate + targetMargin,
        lowPrecision,
        peerMean,
        peerMedian: quantile(peerEstimates, 0.5),
        peerQ25: quantile(peerEstimates, 0.25),
        peerQ75: quantile(peerEstimates, 0.75),
        peerCount,
        reportingFraction,
        hasCoverage,
        directionalAllowed,
        differenceLow,
        differenceHigh
      };
    });
  };

  const interpretation = (row, crossState) => {
    if (!row) return "Not enough overlapping data";
    if (!row.hasCoverage) return "Not enough comparison districts reported data";
    if (crossState) return "Nationwide comparison shown for context only";
    if (row.lowPrecision) return "The estimate is too uncertain for a clear comparison";
    if (row.differenceLow > 0) return "Higher than the comparison-group average";
    if (row.differenceHigh < 0) return "Lower than the comparison-group average";
    return "Not clearly different from the comparison-group average";
  };

  const latestSummary = (summary) => [...summary]
    .reverse()
    .find((row) => row.year <= analysis.latest_result_year && row.targetEstimate !== null && row.peerMedian !== null) || null;

  const renderMetricCard = (element, label, latest, selectedCount, crossState) => {
    if (!latest) {
      element.innerHTML = `<h3>${escapeHtml(label)}</h3><p class="comparison-copy">Not enough results in the same year</p><p class="metric-detail">No year has both a district result and a comparison-group result.</p>`;
      return;
    }
    element.innerHTML = `
      <h3>${escapeHtml(label)}</h3>
      <div class="metric-value">${formatNumber(latest.targetEstimate, 2)}</div>
      <div class="metric-detail">${latest.year} estimated average · ${confidencePercent}% uncertainty interval ${formatNumber(latest.targetLow, 2)} to ${formatNumber(latest.targetHigh, 2)}</div>
      <p class="comparison-copy">${escapeHtml(interpretation(latest, crossState))}</p>
      <p class="metric-detail">Comparison-group average ${formatNumber(latest.peerMean, 2)}; typical result ${formatNumber(latest.peerMedian, 2)}; middle half ${formatNumber(latest.peerQ25, 2)} to ${formatNumber(latest.peerQ75, 2)}. ${latest.peerCount} of ${selectedCount} selected districts reported a result.</p>
      ${latest.lowPrecision ? '<span class="precision-tag">Use extra caution: this estimate is less certain</span>' : ""}
    `;
  };

  const chartLayout = (title) => ({
    title: { text: title, x: 0.02, xanchor: "left", font: { size: 17, color: "#152632" } },
    height: 420,
    margin: { l: 84, r: 20, t: 54, b: 82 },
    paper_bgcolor: "#fffefa",
    plot_bgcolor: "#fffefa",
    font: { family: "Inter, Arial, sans-serif", color: "#344852", size: 11 },
    legend: { orientation: "h", y: -0.28, x: 0, font: { size: 10 } },
    hovermode: "x unified",
    xaxis: { title: { text: "Year", standoff: 10 }, automargin: true, dtick: 2, range: [chartYears[0] - 0.4, chartYears.at(-1) + 0.4], gridcolor: "#e9edec" },
    yaxis: { title: { text: "Average score vs. national reference", standoff: 12 }, automargin: true, zeroline: true, zerolinecolor: "#82939a", zerolinewidth: 1.5, gridcolor: "#e9edec" },
    shapes: [{ type: "rect", x0: 2019.5, x1: 2021.5, y0: 0, y1: 1, yref: "paper", fillcolor: "rgba(100,114,124,.10)", line: { width: 0 } }],
    annotations: [
      { x: 2020.5, y: 1, yref: "paper", text: "No results released", showarrow: false, yshift: 10, font: { size: 9, color: "#64727c" } },
      { x: 1, xref: "paper", xanchor: "right", y: 0, yref: "y", yanchor: "bottom", text: "National reference (0)", showarrow: false, yshift: 4, bgcolor: "rgba(255,254,250,.88)", font: { size: 9, color: "#52656e" } }
    ]
  });

  const renderChart = (elementId, title, districtName, peerLabel, summary) => {
    const years = summary.map((row) => row.year);
    const traces = [
      {
        x: years, y: summary.map((row) => row.peerQ75), mode: "lines",
        line: { width: 0 }, hoverinfo: "skip", showlegend: false
      },
      {
        x: years, y: summary.map((row) => row.peerQ25), mode: "lines",
        line: { width: 0 }, fill: "tonexty", fillcolor: "rgba(45,113,140,.14)",
        customdata: summary.map((row) => row.peerQ75),
        name: `Middle half of ${peerLabel}`, hovertemplate: "Year %{x}<br>Middle half of comparison districts: %{y:.2f} to %{customdata:.2f}<extra></extra>", connectgaps: false
      },
      {
        x: years, y: summary.map((row) => row.peerMedian), mode: "lines",
        line: { color: "#2d718c", width: 2, dash: "dot" }, name: `Typical ${peerLabel}`,
        hovertemplate: "Year %{x}<br>Typical comparison district: %{y:.2f}<extra></extra>", connectgaps: false
      },
      {
        x: years, y: summary.map((row) => row.targetEstimate), mode: "lines+markers",
        line: { color: "#dc7139", width: 3 }, marker: { color: "#dc7139", size: 6 },
        error_y: { type: "data", array: summary.map((row) => row.targetMargin), visible: true, color: "rgba(220,113,57,.45)", thickness: 1, width: 2 },
        customdata: summary.map((row) => [row.targetLow, row.targetHigh]),
        name: districtName, hovertemplate: `Year %{x}<br>Estimated average: %{y:.2f}<br>${confidencePercent}% uncertainty interval: %{customdata[0]:.2f} to %{customdata[1]:.2f}<extra></extra>`, connectgaps: false
      }
    ];
    window.Plotly.react(elementId, traces, chartLayout(title), { displaylogo: false, responsive: true, displayModeBar: false });
  };

  const domainDiagnostics = (peers) => {
    const keys = ["district_scale", "economic_context", "student_composition", "place"];
    return Object.fromEntries(keys.map((key) => [key, quantile(peers.map((peer) => peer.domains[key]), 0.5)]));
  };

  const renderContextTable = (target, peers) => {
    const rows = [
      ["Enrollment in grades 3–8", CONTEXT.enrollment, (value) => formatNumber(value), false],
      ["Family poverty rate", CONTEXT.poverty, formatPercent, false],
      ["Socioeconomic status composite", CONTEXT.ses, (value) => formatNumber(value, 2), false],
      ["Dominant locale", CONTEXT.locale, (value) => value || "Not available", true]
    ];
    elements["context-table-body"].innerHTML = rows.map(([label, index, formatter, categorical]) => {
      const values = peers.map(({ row }) => row[index]).filter((value) => value !== null);
      const middle = categorical ? mode(values) : quantile(values, 0.5);
      const spread = categorical
        ? "Most common category"
        : `${formatter(quantile(values, 0.25))} to ${formatter(quantile(values, 0.75))}`;
      return `<tr><td>${label}</td><td>${formatter(target[index])}</td><td>${formatter(middle)}</td><td>${spread}</td></tr>`;
    }).join("");
  };

  const renderMatchDiagnostics = (pool, poolLabel) => {
    const statusLabels = {
      full_count_strict: "Close match on all four factors",
      full_count_relaxed: "Match found after widening the search",
      minimum_count_only: "Smaller comparison group",
      insufficient: "Not enough similar districts"
    };
    const statusClass = pool.status === "full_count_strict" ? "pass" : "warn";
    elements["selection-status-copy"].innerHTML = `
      <span class="status-tag ${statusClass}">${statusLabels[pool.status]}</span><br>
      <span class="small">${pool.selected.length} ${poolLabel.toLowerCase()} selected from ${formatNumber(pool.universe)} available candidates. Shorter bars below mean a closer match.</span>
    `;
    const labels = {
      district_scale: "District size",
      economic_context: "Economic context",
      student_composition: "Student composition",
      place: "Place / locale"
    };
    const diagnostics = domainDiagnostics(pool.selected);
    elements["distance-bars"].innerHTML = Object.entries(labels).map(([key, label]) => {
      const value = diagnostics[key];
      const width = value === null ? 0 : Math.min(100, value * 200);
      return `<div class="distance-row"><span>${label}</span><div class="distance-track"><span style="width:${width.toFixed(1)}%"></span></div><output>${value === null ? "—" : value.toFixed(3)}</output></div>`;
    }).join("");
    elements["peer-table-body"].innerHTML = pool.selected.map((peer) => {
      const row = peer.row;
      return `<tr><td>${escapeHtml(row[CONTEXT.district_name])}</td><td>${row[CONTEXT.state]}</td><td>${peer.distance.toFixed(3)}</td><td>${escapeHtml(row[CONTEXT.locale])}</td><td>${formatNumber(row[CONTEXT.enrollment])}</td></tr>`;
    }).join("");
  };

  const renderSensitivity = (targetId, selection, nationalStatus = "ready") => {
    const pools = [
      ["Same-state comparison", selection.sameState, false],
      ["Nationwide comparison", selection.national, true]
    ];
    const subjects = [["mth", "Mathematics"], ["rla", "Reading / language arts"]];
    elements["sensitivity-table-body"].innerHTML = pools.flatMap(([label, pool, crossState]) => (
      subjects.map(([subject, subjectLabel]) => {
        if (crossState && nationalStatus !== "ready") {
          const message = nationalStatus === "failed"
            ? "Nationwide records could not be loaded. Reload the page to retry."
            : "Loading the selected nationwide comparison records…";
          return `<tr><td>${label}</td><td>${subjectLabel}</td><td colspan="5">${message}</td></tr>`;
        }
        const latest = latestSummary(trendSummary(targetId, pool.selected, subject, crossState));
        if (!latest) return `<tr><td>${label}</td><td>${subjectLabel}</td><td colspan="5">Not enough overlapping data</td></tr>`;
        const limited = latest.hasCoverage ? "" : ' <span class="status-tag warn">limited</span>';
        return `<tr>
          <td>${label}${limited}</td><td>${subjectLabel}</td><td>${latest.year}</td>
          <td>${latest.peerCount} of ${pool.selected.length} (${formatPercent(latest.reportingFraction)})</td>
          <td>${formatNumber(latest.targetEstimate, 2)}</td><td>${formatNumber(latest.peerMean, 2)}</td>
          <td>${escapeHtml(interpretation(latest, crossState))}</td>
        </tr>`;
      })
    )).join("");
  };

  const availabilityReasons = (catalogRow, context) => {
    const reasons = [];
    if (!catalogRow[CATALOG.has_context]) reasons.push("it has no 2024 context record");
    if (catalogRow[CATALOG.has_context] && !catalogRow[CATALOG.serves_grade]) reasons.push(`its reported grade span does not include grade ${grade}`);
    if (catalogRow[CATALOG.has_context] && !catalogRow[CATALOG.has_core_context]) reasons.push("the required matching context is incomplete");
    if (!catalogRow[CATALOG.has_math] && !catalogRow[CATALOG.has_reading]) reasons.push(`no grade ${grade} math or reading estimates are available`);
    else if (!catalogRow[CATALOG.has_math]) reasons.push(`no grade ${grade} math estimates are available`);
    else if (!catalogRow[CATALOG.has_reading]) reasons.push(`no grade ${grade} reading estimates are available`);
    if (!context && reasons.length === 0) reasons.push("a usable matching record is not available");
    return reasons;
  };

  const renderUnavailable = (catalogRow, context) => {
    const reasons = availabilityReasons(catalogRow, context);
    elements["availability-indicator"].textContent = "Grade 4 unavailable";
    elements["availability-indicator"].className = "status-dot unavailable";
    elements["analysis-content"].hidden = true;
    elements["unavailable-panel"].hidden = false;
    elements["unavailable-title"].textContent = `No grade ${grade} comparison for this district`;
    elements["unavailable-copy"].textContent = `${catalogRow[CATALOG.district_name]} remains in the full catalog, but ${reasons.join("; ")}.`;
    window.Plotly?.purge?.("math-chart");
    window.Plotly?.purge?.("reading-chart");
  };

  const renderLoadFailure = (districtName, error) => {
    elements["availability-indicator"].textContent = "Data could not be loaded";
    elements["availability-indicator"].className = "status-dot unavailable";
    elements["analysis-content"].hidden = true;
    elements["unavailable-panel"].hidden = false;
    elements["unavailable-title"].textContent = `Could not load ${districtName}’s results`;
    elements["unavailable-copy"].textContent = `${error.message} Reload the page to try again.`;
  };

  const renderDistrict = async (districtId) => {
    const token = ++renderRequestToken;
    const catalogRow = catalogById.get(districtId);
    if (!catalogRow) return;
    const context = contextById.get(districtId);
    const districtName = catalogRow[CATALOG.district_name];
    const state = catalogRow[CATALOG.state];
    elements["district-heading"].textContent = districtName;
    elements["district-subtitle"].textContent = `How do this district’s grade ${grade} math and reading results compare with districts serving similar communities?`;
    elements["district-id-meta"].textContent = `SEDA district ${districtId}`;
    elements["district-state-meta"].textContent = state;

    const url = new URL(window.location.href);
    url.searchParams.set("state", state);
    url.searchParams.set("district", districtId);
    window.history.replaceState({}, "", url);

    const eligible = context
      && context[CONTEXT.has_core_context]
      && context[CONTEXT.grade_low] !== null
      && context[CONTEXT.grade_high] !== null
      && context[CONTEXT.grade_low] <= grade
      && context[CONTEXT.grade_high] >= grade
      && (catalogRow[CATALOG.has_math] || catalogRow[CATALOG.has_reading]);
    if (!eligible) {
      renderUnavailable(catalogRow, context);
      return;
    }

    const selection = selectPeers(context);
    const stateReportable = selection.sameState.selected.length >= analysis.state_peer_minimum;
    const primary = stateReportable ? selection.sameState : selection.national;
    const crossState = !stateReportable;
    const peerLabel = stateReportable ? "similar same-state districts" : "similar districts nationwide";
    const primaryStates = [
      state,
      ...primary.selected.map(({ row }) => row[CONTEXT.state])
    ];

    elements["availability-indicator"].textContent = "Loading results";
    elements["availability-indicator"].className = "status-dot";
    elements["unavailable-panel"].hidden = true;
    elements["analysis-content"].hidden = true;

    try {
      await Promise.all([loader.loadPlotly(), loadAchievementStates(primaryStates)]);
      if (token !== renderRequestToken) return;
    } catch (error) {
      if (token === renderRequestToken) renderLoadFailure(districtName, error);
      return;
    }

    elements["availability-indicator"].textContent = "Profile available";
    elements["availability-indicator"].className = "status-dot available";
    elements["analysis-content"].hidden = false;
    elements["primary-pool-label"].textContent = `${primary.selected.length} ${peerLabel}`;

    const math = trendSummary(districtId, primary.selected, "mth", crossState);
    const reading = trendSummary(districtId, primary.selected, "rla", crossState);
    renderMetricCard(elements["math-card"], "Fourth-grade math", latestSummary(math), primary.selected.length, crossState);
    renderMetricCard(elements["reading-card"], "Fourth-grade reading", latestSummary(reading), primary.selected.length, crossState);
    renderChart("math-chart", "Average math score", districtName, peerLabel, math);
    renderChart("reading-chart", "Average reading score", districtName, peerLabel, reading);
    renderContextTable(context, primary.selected);
    renderMatchDiagnostics(primary, stateReportable ? "same-state districts" : "districts nationwide");
    renderSensitivity(districtId, selection, stateReportable ? "loading" : "ready");

    if (stateReportable) {
      const nationalStates = [
        state,
        ...selection.national.selected.map(({ row }) => row[CONTEXT.state])
      ];
      try {
        await loadAchievementStates(nationalStates);
        if (token === renderRequestToken) renderSensitivity(districtId, selection, "ready");
      } catch (_) {
        if (token === renderRequestToken) renderSensitivity(districtId, selection, "failed");
      }
    }
  };

  const populateDistricts = (state, selectedId = null) => {
    const rows = catalog.filter((row) => row[CATALOG.state] === state);
    elements["district-select"].innerHTML = rows.map((row) => (
      `<option value="${row[CATALOG.district_id]}">${escapeHtml(row[CATALOG.district_name])} · ${row[CATALOG.district_id]}</option>`
    )).join("");
    const desired = selectedId && rows.some((row) => row[CATALOG.district_id] === selectedId)
      ? selectedId
      : rows[0]?.[CATALOG.district_id];
    if (desired) elements["district-select"].value = desired;
    return desired;
  };

  const initializeSelectors = () => {
    if (selectorsInitialized) return;
    selectorsInitialized = true;
    const states = [...new Set(catalog.map((row) => row[CATALOG.state]).filter(Boolean))].sort();
    elements["state-select"].innerHTML = states.map((state) => `<option value="${state}">${state}</option>`).join("");
    elements["catalog-count"].textContent = formatNumber(catalog.length);
    const params = new URLSearchParams(window.location.search);
    const requestedId = params.get("district");
    const defaultRow = catalogById.get(requestedId) || catalogById.get(data.default_district_id) || catalog[0];
    const state = defaultRow[CATALOG.state];
    elements["state-select"].value = state;
    const selected = populateDistricts(state, defaultRow[CATALOG.district_id]);
    if (selected) renderDistrict(selected);

    elements["state-select"].addEventListener("change", (event) => {
      const districtId = populateDistricts(event.target.value);
      if (districtId) renderDistrict(districtId);
    });
    elements["district-select"].addEventListener("change", (event) => renderDistrict(event.target.value));
  };

  const renderTechnical = () => {
    const technical = data.technical;
    elements["source-size-kpi"].textContent = formatBytes(technical.source_total_bytes);
    elements["staged-rows-kpi"].textContent = formatNumber(technical.table_counts.stg_achievement);
    elements["districts-kpi"].textContent = formatNumber(technical.table_counts.dim_district);
    elements["qa-kpi"].textContent = `${technical.qa_pass_count} + ${technical.qa_warning_count}`;
    elements["failure-line"].textContent = formatNumber(technical.first_quoted_name_failure_line);
    elements["publication-note"].textContent = technical.publication_note;

    const sourceLabels = {
      seda_achievement: "Achievement estimates",
      seda_context: "Annual context",
      seda_crosswalk: "Identifier crosswalk"
    };
    elements["source-table-body"].innerHTML = technical.sources.map((source) => `
      <tr><td>${sourceLabels[source.source_id]}</td><td>${formatExactBytes(source.size_bytes)}</td><td>${formatNumber(source.column_count)}</td><td><span class="status-tag pass">Verified</span></td></tr>
    `).join("") + `
      <tr><td><strong>Total</strong></td><td><strong>${formatExactBytes(technical.source_total_bytes)}</strong></td><td>215</td><td><span class="status-tag pass">3 of 3</span></td></tr>
    `;
    elements["hash-list"].innerHTML = technical.sources.map((source) => `
      <div><strong>${sourceLabels[source.source_id]}</strong><code>${source.observed_sha256}</code></div>
    `).join("");

    const modelRows = [
      ["Achievement rows loaded and kept", `${formatNumber(technical.table_counts.stg_achievement)} loaded; ${formatNumber(technical.table_counts.mart_achievement)} kept`],
      ["District context rows", formatNumber(technical.table_counts.stg_context)],
      ["District ID mappings", formatNumber(technical.table_counts.stg_crosswalk_admin)],
      ["Source IDs that changed", formatNumber(technical.changed_source_stable_id_mappings)],
      ["Coverage summary rows", formatNumber(technical.table_counts.mart_data_coverage)],
      ["DuckDB database", `${formatExactBytes(technical.database_bytes)} · ${technical.persisted_table_count} tables`],
      ["Single-district offline report", formatExactBytes(technical.offline_profile_bytes)],
      ["Opening catalog and context file", formatExactBytes(technical.public_bundle_bytes)],
      [`Grade ${grade} state files`, `${formatExactBytes(technical.achievement_state_public_data_bytes)} · ${formatNumber(technical.published_achievement_rows)} estimates`],
      ["Six grade-level workbench files", formatExactBytes(technical.workbench_public_data_bytes)],
      ["Annual estimates available in the workbench", formatNumber(technical.workbench_total_rows)],
      ["District selector and context data", `${formatNumber(technical.published_catalog_rows)} districts · ${formatNumber(technical.published_context_rows)} context rows`]
    ];
    elements["model-table-body"].innerHTML = modelRows.map(([label, value]) => `<tr><td>${label}</td><td>${value}</td></tr>`).join("");
    elements["sql-model-list"].innerHTML = technical.sql_models.map((model) => `<li>${model}</li>`).join("");

    const qaCards = [
      [`${technical.qa_pass_count} passed`, "required data checks"],
      [`${technical.qa_warning_count} flagged`, "items to review"],
      [formatNumber(technical.software_test_count), "software tests"],
      ["Every update", "tests and publication checks run before publishing"]
    ];
    elements["qa-status-grid"].innerHTML = qaCards.map(([value, label]) => `<article><strong>${value}</strong><span>${label}</span></article>`).join("");
    const warningText = {
      released_locale_differs_from_share_argmax: (row) => `${formatNumber(row.observed)} 2024 district rows have a released urbanicity category different from the largest calculated locale share. The released category is used and the recomputation remains available for audit.`,
      multi_component_rows_are_explicitly_excluded: (row) => `${formatNumber(row.observed)} multi-component rows across 41 districts in AZ, NM, and UT during 2016–2019 are excluded from the within-state design and recorded in an audit mart.`
    };
    elements["qa-warning-list"].innerHTML = technical.qa
      .filter((row) => row.status === "warn")
      .map((row) => `<article><strong>Diagnostic warning</strong><br>${warningText[row.name]?.(row) || escapeHtml(row.name)}</article>`)
      .join("");
  };

  const activateTab = (name, updateHash = true) => {
    for (const button of document.querySelectorAll("[data-tab]")) {
      const active = button.dataset.tab === name;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-selected", String(active));
      button.tabIndex = active ? 0 : -1;
    }
    for (const panelName of ["explore", "trends", "workbench", "research", "technical"]) {
      document.getElementById(`${panelName}-panel`).hidden = name !== panelName;
    }
    if (updateHash) {
      const url = new URL(window.location.href);
      url.hash = name === "explore" ? "" : name;
      window.history.replaceState({}, "", url);
    }
    if (name === "explore") {
      initializeSelectors();
      window.setTimeout(() => {
        for (const id of ["math-chart", "reading-chart"]) {
          const chart = document.getElementById(id);
          if (chart?.data) window.Plotly?.Plots?.resize(chart);
        }
      }, 0);
    }
    if (name === "workbench") {
      window.setTimeout(() => window.SEDA_WORKBENCH?.activate(), 0);
    }
    if (name === "trends") {
      window.setTimeout(() => window.SEDA_TRENDS?.activate(), 0);
    }
    if (name === "technical" && !technicalRendered) {
      renderTechnical();
      technicalRendered = true;
    }
  };

  const initializeTabs = () => {
    const buttons = [...document.querySelectorAll("[data-tab]")];
    buttons.forEach((button, index) => {
      button.addEventListener("click", () => activateTab(button.dataset.tab));
      button.addEventListener("keydown", (event) => {
        if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
        event.preventDefault();
        const direction = event.key === "ArrowRight" ? 1 : -1;
        const next = buttons[(index + direction + buttons.length) % buttons.length];
        next.focus();
        activateTab(next.dataset.tab);
      });
    });
    const requested = window.location.hash.replace("#", "");
    activateTab(["trends", "workbench", "research", "technical"].includes(requested) ? requested : "explore", false);
  };

  initializeTabs();
})();
