(function () {
  "use strict";

  const source = window.DISTRICT_DASHBOARD_DATA;
  const statusElement = document.getElementById("wb-status");
  if (!source || !statusElement) return;

  const scope = source.workbench;
  if (!scope || !Array.isArray(scope.years) || !scope.years.length) {
    statusElement.textContent = "The workbench data contract is missing. Reload the page or use the Technical Process tab for details.";
    statusElement.classList.add("is-error");
    return;
  }
  const YEARS = scope.years;
  const CHART_YEARS = Array.from(
    { length: YEARS.at(-1) - YEARS[0] + 1 },
    (_, index) => YEARS[0] + index
  );
  const SUBJECT_LABELS = { mth: "Mathematics", rla: "Reading / language arts" };
  const COLORS = ["#dc7139", "#2d718c", "#28735e", "#76558f"];
  const CRITICAL_VALUE = scope.confidence_critical_value;
  const CONFIDENCE_PERCENT = Math.round(scope.confidence_level * 100);
  const SENSITIVITY_END_YEAR = Number(source.model.analysis.latest_result_year) - 1;
  const WORKBENCH_GRADES = Object.keys(source.technical.workbench_grade_rows || {}).map(Number).sort();
  const catalogFields = Object.fromEntries(source.catalog_fields.map((field, index) => [field, index]));
  const catalog = source.catalog;
  const catalogById = new Map(catalog.map((row) => [row[catalogFields.district_id], row]));
  const gradeCache = new Map();
  const gradePromises = new Map();

  const elements = Object.fromEntries([
    "wb-grade", "wb-subject", "wb-state", "wb-year", "wb-district-state", "wb-district", "wb-add-district",
    "wb-selected-districts", "wb-end-2024", "wb-download", "wb-share", "wb-status",
    "wb-results", "wb-se-basis", "wb-record-count", "wb-universe-count",
    "wb-low-precision-count", "wb-estimated-count", "wb-trend-caption",
    "wb-distribution-caption", "wb-distribution-summary", "wb-coverage-head",
    "wb-coverage-body", "wb-table-count", "wb-records-body"
  ].map((id) => [id, document.getElementById(id)]));

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const formatNumber = (value, digits = 0) => value === null || value === undefined || Number.isNaN(value)
    ? "Not available"
    : Number(value).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });

  const quantile = (values, probability) => {
    if (!values.length) return null;
    const sorted = [...values].sort((left, right) => left - right);
    const position = (sorted.length - 1) * probability;
    const lower = Math.floor(position);
    const upper = Math.ceil(position);
    if (lower === upper) return sorted[lower];
    return sorted[lower] + ((sorted[upper] - sorted[lower]) * (position - lower));
  };

  const schoolYear = (year) => `${year - 1}-${String(year).slice(-2)}`;
  const districtName = (districtId) => catalogById.get(districtId)?.[catalogFields.district_name] || districtId;
  const districtState = (districtId) => catalogById.get(districtId)?.[catalogFields.state] || "";

  const params = new URLSearchParams(window.location.search);
  const requestedGrade = Number(params.get("wb_grade"));
  const requestedYear = Number(params.get("wb_year"));
  const requestedDistricts = (params.get("wb_districts") || "")
    .split(",")
    .filter((districtId) => catalogById.has(districtId))
    .slice(0, 4);
  const workbenchDistrictsRequested = params.has("wb_districts");
  const currentExploreDistrict = params.get("district");
  const defaultDistrict = catalogById.has(currentExploreDistrict)
    ? currentExploreDistrict
    : catalogById.has(source.default_district_id)
      ? source.default_district_id
      : catalog[0]?.[catalogFields.district_id];

  const state = {
    grade: Number.isInteger(requestedGrade) && WORKBENCH_GRADES.includes(requestedGrade) ? requestedGrade : source.grade,
    subject: ["mth", "rla"].includes(params.get("wb_subject")) ? params.get("wb_subject") : "mth",
    universeState: params.get("wb_state") || districtState(requestedDistricts[0] || defaultDistrict) || "US",
    districtFilterState: params.get("wb_find_state") || districtState(requestedDistricts[0] || defaultDistrict),
    year: YEARS.includes(requestedYear) ? requestedYear : YEARS.at(-1),
    selectedDistricts: requestedDistricts.length ? requestedDistricts : [defaultDistrict].filter(Boolean),
    endAt2024: params.get("wb_end") === String(SENSITIVITY_END_YEAR),
    yearExplicit: YEARS.includes(requestedYear),
    indexed: null,
    initialized: false,
    requestToken: 0
  };

  const indexBundle = (bundle) => {
    const fields = Object.fromEntries(bundle.achievement_fields.map((field, index) => [field, index]));
    const byDistrict = new Map();
    const bySubjectYear = new Map();
    for (const row of bundle.achievement) {
      if (!Array.isArray(row) || row.length !== bundle.achievement_fields.length) {
        throw new Error(`Grade ${bundle.grade} contains a malformed record.`);
      }
      const districtId = row[fields.district_id];
      const subject = row[fields.subject];
      const year = row[fields.year];
      if (!byDistrict.has(districtId)) byDistrict.set(districtId, { mth: new Map(), rla: new Map() });
      byDistrict.get(districtId)[subject].set(year, row);
      const key = `${subject}|${year}`;
      if (!bySubjectYear.has(key)) bySubjectYear.set(key, []);
      bySubjectYear.get(key).push(row);
    }
    return { ...bundle, fields, byDistrict, bySubjectYear };
  };

  const validateBundle = (grade, bundle) => {
    const expectedFields = JSON.stringify(source.achievement_fields);
    const expectedRows = source.technical.workbench_grade_rows?.[String(grade)];
    const valid = bundle
      && bundle.schema_version === source.schema_version
      && bundle.release === scope.release
      && bundle.geography === scope.geography
      && bundle.subgroup === scope.subgroup
      && bundle.scale === scope.scale
      && bundle.grade === grade
      && JSON.stringify(bundle.achievement_fields) === expectedFields
      && Number.isInteger(expectedRows)
      && bundle.row_count === expectedRows
      && Array.isArray(bundle.achievement)
      && bundle.row_count === bundle.achievement.length;
    if (!valid) throw new Error(`Grade ${grade} bundle failed its release and schema checks.`);
    return bundle;
  };

  const setBusy = (busy, message = "") => {
    for (const control of document.querySelectorAll("#workbench-panel button, #workbench-panel select, #workbench-panel input")) {
      control.disabled = busy;
    }
    elements["wb-results"].hidden = busy || !state.indexed;
    elements["wb-results"].setAttribute("aria-busy", String(busy));
    elements["wb-status"].classList.toggle("is-loading", busy);
    if (busy) elements["wb-status"].classList.remove("is-error");
    if (message) elements["wb-status"].textContent = message;
  };

  const loadGrade = async (grade) => {
    if (gradeCache.has(grade)) return gradeCache.get(grade);
    if (grade === source.grade) {
      const indexed = indexBundle(validateBundle(grade, {
        schema_version: source.schema_version,
        release: scope.release,
        geography: scope.geography,
        subgroup: scope.subgroup,
        scale: scope.scale,
        grade: source.grade,
        achievement_fields: source.achievement_fields,
        row_count: source.achievement.length,
        achievement: source.achievement
      }));
      gradeCache.set(grade, indexed);
      return indexed;
    }
    if (window.SEDA_WORKBENCH_GRADES?.[grade]) {
      try {
        const indexed = indexBundle(validateBundle(grade, window.SEDA_WORKBENCH_GRADES[grade]));
        gradeCache.set(grade, indexed);
        return indexed;
      } catch (_) {
        delete window.SEDA_WORKBENCH_GRADES[grade];
      }
    }
    if (gradePromises.has(grade)) return gradePromises.get(grade);

    const promise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      const scriptUrl = new URL(`data/workbench-grade-${grade}.js`, document.baseURI);
      scriptUrl.searchParams.set("v", source.generated_at_utc);
      script.src = scriptUrl.href;
      script.async = true;
      script.onload = () => {
        const payload = window.SEDA_WORKBENCH_GRADES?.[grade];
        let indexed;
        try {
          indexed = indexBundle(validateBundle(grade, payload));
        } catch (error) {
          reject(error);
          return;
        }
        gradeCache.set(grade, indexed);
        resolve(indexed);
      };
      script.onerror = () => reject(new Error(`Grade ${grade} records could not be loaded.`));
      document.head.appendChild(script);
    }).finally(() => gradePromises.delete(grade));
    gradePromises.set(grade, promise);
    return promise;
  };

  const activeYears = () => YEARS.filter((year) => !state.endAt2024 || year <= SENSITIVITY_END_YEAR);
  const selectedStates = () => new Set(selectedRows().map(({ districtId }) => districtState(districtId)).filter(Boolean));
  const usesCrossStateError = () => selectedStates().size > 1;

  const errorIndex = () => usesCrossStateError()
    ? state.indexed.fields.standard_error_cross_state
    : state.indexed.fields.standard_error_within_state;

  const isLowPrecision = (row) => {
    if (!row) return false;
    const fields = state.indexed.fields;
    const margin = CRITICAL_VALUE * row[errorIndex()];
    return row[fields.tested_count] < 50
      || row[fields.tested_count_estimated] === 1
      || margin > 0.5;
  };

  const rowFor = (districtId, year) => (
    state.indexed.byDistrict.get(districtId)?.[state.subject]?.get(year) || null
  );

  const selectedRows = () => state.selectedDistricts.flatMap((districtId) => (
    activeYears().map((year) => ({ districtId, row: rowFor(districtId, year) }))
      .filter((item) => item.row)
  ));

  const universeRowsForYear = (year) => {
    const rows = state.indexed.bySubjectYear.get(`${state.subject}|${year}`) || [];
    if (state.universeState === "US") return rows;
    return rows.filter((row) => districtState(row[state.indexed.fields.district_id]) === state.universeState);
  };

  const universeRows = () => universeRowsForYear(state.year);

  const ensureUsefulYear = () => {
    if (state.yearExplicit && activeYears().includes(state.year)) return;
    const latest = [...activeYears()].reverse().find((year) => universeRowsForYear(year).length > 0);
    if (latest !== undefined) state.year = latest;
  };

  const updateUrl = () => {
    const url = new URL(window.location.href);
    url.searchParams.set("wb_grade", state.grade);
    url.searchParams.set("wb_subject", state.subject);
    url.searchParams.set("wb_state", state.universeState);
    url.searchParams.set("wb_find_state", state.districtFilterState);
    url.searchParams.set("wb_year", state.year);
    url.searchParams.set("wb_districts", state.selectedDistricts.join(","));
    if (state.endAt2024) url.searchParams.set("wb_end", String(SENSITIVITY_END_YEAR));
    else url.searchParams.delete("wb_end");
    if (!document.getElementById("workbench-panel").hidden) url.hash = "workbench";
    window.history.replaceState({}, "", url);
  };

  const populateYears = () => {
    const years = activeYears();
    if (!years.includes(state.year)) state.year = years.at(-1);
    elements["wb-year"].innerHTML = [...years].reverse()
      .map((year) => `<option value="${year}">${schoolYear(year)}</option>`)
      .join("");
    elements["wb-year"].value = String(state.year);
  };

  const populateDistrictPicker = () => {
    const fields = state.indexed.fields;
    const rows = catalog.filter((row) => row[catalogFields.state] === state.districtFilterState);
    elements["wb-district"].innerHTML = rows.map((row) => {
      const districtId = row[catalogFields.district_id];
      const hasSubject = (state.indexed.byDistrict.get(districtId)?.[state.subject]?.size || 0) > 0;
      const availability = hasSubject ? "" : " · no released record";
      return `<option value="${districtId}">${escapeHtml(row[catalogFields.district_name])} · ${row[catalogFields.state]} · ${districtId}${availability}</option>`;
    }).join("");
  };

  const renderChips = () => {
    elements["wb-selected-districts"].innerHTML = state.selectedDistricts.map((districtId, index) => {
      const hasRecords = (state.indexed.byDistrict.get(districtId)?.[state.subject]?.size || 0) > 0;
      return `
      <span class="district-chip ${hasRecords ? "" : "is-unavailable"}" style="--chip-color:${COLORS[index]}">
        <span class="district-chip-copy">${escapeHtml(districtName(districtId))} <small>${districtState(districtId)}</small>${hasRecords ? "" : `<small class="chip-unavailable">No grade ${state.grade} ${state.subject === "mth" ? "math" : "reading"} records</small>`}</span>
        <button type="button" data-remove-district="${districtId}" aria-label="Remove ${escapeHtml(districtName(districtId))}">×</button>
      </span>
    `;
    }).join("");
    for (const button of elements["wb-selected-districts"].querySelectorAll("[data-remove-district]")) {
      button.addEventListener("click", () => {
        if (state.selectedDistricts.length === 1) {
          elements["wb-status"].textContent = "Keep at least one district in the comparison.";
          return;
        }
        state.selectedDistricts = state.selectedDistricts.filter((districtId) => districtId !== button.dataset.removeDistrict);
        renderAll();
      });
    }
  };

  const chartBase = () => ({
    margin: { l: 60, r: 24, t: 58, b: 72 },
    paper_bgcolor: "#fffefa",
    plot_bgcolor: "#fffefa",
    font: { family: "Inter, Arial, sans-serif", color: "#344852", size: 11 },
    hovermode: "closest",
    legend: { orientation: "h", y: -0.22, x: 0, font: { size: 10 } },
    xaxis: { gridcolor: "#e9edec" },
    yaxis: { gridcolor: "#e9edec", zerolinecolor: "#aeb9bd" }
  });

  const renderTrend = () => {
    const fields = state.indexed.fields;
    const lastYear = state.endAt2024 ? SENSITIVITY_END_YEAR : YEARS.at(-1);
    const basis = usesCrossStateError() ? "adjusted cross-state" : "within-state";
    const traces = state.selectedDistricts.map((districtId, index) => {
      const rows = CHART_YEARS.map((year) => year <= lastYear ? rowFor(districtId, year) : null);
      const estimates = rows.map((row) => row?.[fields.estimate] ?? null);
      const margins = rows.map((row) => row ? CRITICAL_VALUE * row[errorIndex()] : null);
      const custom = rows.map((row, rowIndex) => {
        if (!row) return [schoolYear(CHART_YEARS[rowIndex]), "Missing", "Not available", "Not available"];
        return [
          schoolYear(CHART_YEARS[rowIndex]),
          isLowPrecision(row) ? "Low precision" : "Reported",
          formatNumber(row[fields.tested_count]),
          row[fields.tested_count_estimated] === 1 ? "Estimated count" : "Reported count",
          margins[rowIndex]
        ];
      });
      return {
        x: CHART_YEARS,
        y: estimates,
        customdata: custom,
        mode: "lines+markers",
        name: `${districtName(districtId)} (${districtState(districtId)})`,
        line: { color: COLORS[index], width: 2.5 },
        marker: { color: COLORS[index], size: 6 },
        error_y: { type: "data", array: margins, visible: true, color: COLORS[index], thickness: 0.8, width: 2 },
        connectgaps: false,
        hovertemplate: `%{customdata[0]}<br>Estimate %{y:.3f}<br>${CONFIDENCE_PERCENT}% margin ±%{customdata[4]:.3f}<br>Tests represented %{customdata[2]} (%{customdata[3]})<br>%{customdata[1]}<extra>%{fullData.name}</extra>`
      };
    });
    const hasTrendData = traces.some((trace) => trace.y.some((value) => value !== null));
    const layout = {
      ...chartBase(),
      title: { text: `${SUBJECT_LABELS[state.subject]}, grade ${state.grade}`, x: 0.02, xanchor: "left", font: { size: 17, color: "#152632" } },
      height: 440,
      xaxis: { ...chartBase().xaxis, title: "Spring assessment year", dtick: 2, range: [2008.6, lastYear + 0.4] },
      yaxis: { ...chartBase().yaxis, title: "CS standard deviations" },
      shapes: [{ type: "rect", x0: 2019.5, x1: 2021.5, y0: 0, y1: 1, yref: "paper", fillcolor: "rgba(100,114,124,.10)", line: { width: 0 } }],
      annotations: [
        { x: 2020.5, y: 1, yref: "paper", text: "No 2020–21 results", showarrow: false, yshift: 10, font: { size: 9, color: "#64727c" } },
        ...(!hasTrendData ? [{ x: 0.5, y: 0.5, xref: "paper", yref: "paper", text: `No released grade ${state.grade} ${state.subject === "mth" ? "math" : "reading"} records for the selected district${state.selectedDistricts.length === 1 ? "" : "s"}.`, showarrow: false, font: { size: 13, color: "#64727c" } }] : [])
      ]
    };
    window.Plotly.react("wb-trend-chart", traces, layout, { displaylogo: false, responsive: true, displayModeBar: false });
    elements["wb-trend-caption"].innerHTML = `The gap preserves the absence of 2020 and 2021 results. Intervals use <strong>${basis} standard errors</strong>. ${state.endAt2024 ? `The ${YEARS.at(-1)} estimate is hidden for this sensitivity view.` : `SEDA’s ${YEARS.at(-1)} scale uses modeled state NAEP values because ${YEARS.at(-1) + 1} NAEP was not yet available.`} Hover a point for detail; the records table provides the same values for keyboard and screen-reader users.`;
  };

  const renderDistribution = () => {
    const fields = state.indexed.fields;
    const rows = universeRows();
    const estimates = rows.map((row) => row[fields.estimate]);
    const median = quantile(estimates, 0.5);
    const q25 = quantile(estimates, 0.25);
    const q75 = quantile(estimates, 0.75);
    const selectedPoints = state.selectedDistricts.map((districtId, index) => {
      const row = rowFor(districtId, state.year);
      return row ? { districtId, row, index } : null;
    }).filter(Boolean);
    const traces = [{
      x: estimates,
      type: "histogram",
      nbinsx: 38,
      marker: { color: "rgba(45,113,140,.65)", line: { color: "#2d718c", width: 0.5 } },
      name: state.universeState === "US" ? "U.S. districts" : `${state.universeState} districts`,
      hovertemplate: "Estimate bin %{x}<br>District records %{y}<extra></extra>"
    }, ...selectedPoints.map(({ districtId, row, index }) => ({
      x: [row[fields.estimate]],
      y: [0],
      type: "scatter",
      mode: "markers",
      name: districtName(districtId),
      marker: { color: COLORS[index], size: 13, symbol: "triangle-up", line: { color: "white", width: 1 } },
      hovertemplate: `${escapeHtml(districtName(districtId))}<br>Estimate %{x:.3f}<br>${districtState(districtId)}${districtState(districtId) === state.universeState || state.universeState === "US" ? "" : " · outside displayed universe"}<extra></extra>`
    }))];
    const layout = {
      ...chartBase(),
      title: { text: `${schoolYear(state.year)} ${SUBJECT_LABELS[state.subject].toLowerCase()}, grade ${state.grade}`, x: 0.02, xanchor: "left", font: { size: 17, color: "#152632" } },
      height: 400,
      barmode: "overlay",
      bargap: 0.05,
      xaxis: { ...chartBase().xaxis, title: "CS estimate" },
      yaxis: { ...chartBase().yaxis, title: "District records" },
      shapes: estimates.length ? [
        { type: "rect", x0: q25, x1: q75, y0: 0, y1: 1, yref: "paper", fillcolor: "rgba(220,113,57,.08)", line: { width: 0 }, layer: "below" },
        { type: "line", x0: median, x1: median, y0: 0, y1: 1, yref: "paper", line: { color: "#dc7139", width: 2, dash: "dot" } }
      ] : [],
      annotations: estimates.length ? [] : [{ x: 0.5, y: 0.5, xref: "paper", yref: "paper", text: "No released records for this state and year.", showarrow: false }]
    };
    window.Plotly.react("wb-distribution-chart", traces, layout, { displaylogo: false, responsive: true, displayModeBar: false });
    const universeLabel = state.universeState === "US" ? "United States" : state.universeState;
    elements["wb-distribution-summary"].textContent = estimates.length
      ? `${formatNumber(estimates.length)} districts · median ${formatNumber(median, 2)} · middle 50% ${formatNumber(q25, 2)} to ${formatNumber(q75, 2)}`
      : "No released records";
    elements["wb-distribution-caption"].textContent = `The ${universeLabel} distribution is a broad reporting universe, not a matched peer set. It uses released ${schoolYear(state.year)} records and does not assign ordinal ranks.`;
  };

  const renderMetrics = () => {
    const rows = selectedRows();
    const fields = state.indexed.fields;
    elements["wb-record-count"].textContent = formatNumber(rows.length);
    elements["wb-universe-count"].textContent = formatNumber(universeRows().length);
    elements["wb-low-precision-count"].textContent = formatNumber(rows.filter(({ row }) => isLowPrecision(row)).length);
    elements["wb-estimated-count"].textContent = formatNumber(rows.filter(({ row }) => row[fields.tested_count_estimated] === 1).length);
    elements["wb-se-basis"].textContent = usesCrossStateError()
      ? "Adjusted cross-state standard errors"
      : "Within-state standard errors";
  };

  const renderCoverage = () => {
    const years = activeYears();
    elements["wb-coverage-head"].innerHTML = `<tr><th>District</th>${years.map((year) => `<th title="${schoolYear(year)}">${year}</th>`).join("")}</tr>`;
    elements["wb-coverage-body"].innerHTML = state.selectedDistricts.map((districtId) => `
      <tr>
        <th scope="row"><span>${escapeHtml(districtName(districtId))}</span><small>${districtState(districtId)}</small></th>
        ${years.map((year) => {
          const row = rowFor(districtId, year);
          const status = !row ? "missing" : isLowPrecision(row) ? "caution" : "reported";
          const label = !row ? "Missing" : isLowPrecision(row) ? "Low precision" : "Reported";
          const symbol = status === "reported" ? "✓" : status === "caution" ? "!" : "—";
          return `<td class="coverage-cell ${status}" title="${schoolYear(year)}: ${label}"><span aria-hidden="true">${symbol}</span><span class="sr-only">${label}</span></td>`;
        }).join("")}
      </tr>
    `).join("");
  };

  const renderRecords = () => {
    const fields = state.indexed.fields;
    const crossState = usesCrossStateError();
    const rows = selectedRows().sort((left, right) => (
      right.row[fields.year] - left.row[fields.year]
      || districtName(left.districtId).localeCompare(districtName(right.districtId))
    ));
    elements["wb-table-count"].textContent = `${formatNumber(rows.length)} released records`;
    elements["wb-records-body"].innerHTML = rows.length ? rows.map(({ districtId, row }) => {
      const estimate = row[fields.estimate];
      const error = row[errorIndex()];
      const margin = CRITICAL_VALUE * error;
      const estimated = row[fields.tested_count_estimated] === 1;
      const lowPrecision = isLowPrecision(row);
      return `<tr>
        <td><strong>${escapeHtml(districtName(districtId))}</strong><br><span class="small">${districtState(districtId)} · ${districtId}</span></td>
        <td>${schoolYear(row[fields.year])}</td>
        <td>${formatNumber(estimate, 3)}</td>
        <td>${formatNumber(estimate - margin, 3)} to ${formatNumber(estimate + margin, 3)}<br><span class="small">SE ${formatNumber(error, 3)}</span></td>
        <td>${crossState ? "Cross-state adjusted" : "Within-state"}</td>
        <td>${formatNumber(row[fields.tested_count])}${estimated ? '<br><span class="status-tag warn">estimated count</span>' : ""}</td>
        <td><span class="status-tag ${lowPrecision ? "warn" : "pass"}">${lowPrecision ? "Use caution" : "Reported"}</span></td>
      </tr>`;
    }).join("") : '<tr><td colspan="7">No released records match the selected districts, grade, subject, and evidence window.</td></tr>';
  };

  const renderCharts = () => {
    if (document.getElementById("workbench-panel").hidden) return;
    renderTrend();
    renderDistribution();
  };

  const renderAll = () => {
    if (!state.indexed) return;
    elements["wb-results"].hidden = false;
    ensureUsefulYear();
    populateYears();
    populateDistrictPicker();
    renderChips();
    renderMetrics();
    renderCoverage();
    renderRecords();
    renderCharts();
    const rowCount = source.technical.workbench_grade_rows?.[String(state.grade)] || state.indexed.row_count;
    const unavailable = state.selectedDistricts.filter((districtId) => (
      (state.indexed.byDistrict.get(districtId)?.[state.subject]?.size || 0) === 0
    )).length;
    const unavailableNote = unavailable
      ? ` ${unavailable} selected district${unavailable === 1 ? " has" : "s have"} no released grade ${state.grade} ${state.subject === "mth" ? "math" : "reading"} records.`
      : "";
    elements["wb-status"].textContent = `Grade ${state.grade} is ready: ${formatNumber(rowCount)} released math and reading records in the public workbench slice.${unavailableNote}`;
    updateUrl();
  };

  const selectGrade = async (grade) => {
    const token = ++state.requestToken;
    const previousGrade = state.grade;
    const previousIndexed = state.indexed;
    setBusy(true, `Loading ${formatNumber(source.technical.workbench_grade_rows?.[String(grade)] || 0)} grade ${grade} records…`);
    try {
      const indexed = await loadGrade(grade);
      if (token !== state.requestToken) return;
      for (const cachedGrade of gradeCache.keys()) {
        if (cachedGrade !== source.grade && cachedGrade !== grade) gradeCache.delete(cachedGrade);
      }
      for (const loadedGrade of Object.keys(window.SEDA_WORKBENCH_GRADES || {})) {
        if (Number(loadedGrade) !== grade) delete window.SEDA_WORKBENCH_GRADES[loadedGrade];
      }
      state.grade = grade;
      state.indexed = indexed;
      setBusy(false);
      renderAll();
    } catch (error) {
      if (token !== state.requestToken) return;
      state.grade = previousGrade;
      state.indexed = previousIndexed;
      elements["wb-grade"].value = String(previousGrade);
      setBusy(false);
      if (previousIndexed) renderAll();
      elements["wb-status"].textContent = `${error.message} The previous grade remains active; choose another grade or reload the page to retry.`;
      elements["wb-status"].classList.add("is-error");
    }
  };

  const csvCell = (value) => {
    const text = String(value ?? "");
    return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
  };

  const downloadCurrentView = () => {
    const fields = state.indexed.fields;
    const crossState = usesCrossStateError();
    const header = [
      "release", "geography", "subgroup", "scale", "grade", "subject", "district_id",
      "district_name", "state", "year", "school_year", "estimate", "se_basis",
      "standard_error", `ci_${CONFIDENCE_PERCENT}_low`, `ci_${CONFIDENCE_PERCENT}_high`, "tested_count",
      "tested_count_estimated", "low_precision"
    ];
    const rows = selectedRows().map(({ districtId, row }) => {
      const estimate = row[fields.estimate];
      const error = row[errorIndex()];
      const margin = CRITICAL_VALUE * error;
      return [
        state.indexed.release, state.indexed.geography, state.indexed.subgroup, state.indexed.scale, state.grade,
        state.subject, districtId, districtName(districtId), districtState(districtId),
        row[fields.year], schoolYear(row[fields.year]), estimate,
        crossState ? "cross_state_adjusted" : "within_state", error,
        estimate - margin, estimate + margin, row[fields.tested_count],
        row[fields.tested_count_estimated] === 1, isLowPrecision(row)
      ];
    });
    const csv = [header, ...rows].map((row) => row.map(csvCell).join(",")).join("\n");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const releaseSlug = state.indexed.release.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-").replaceAll(/^-|-$/g, "");
    link.download = `${releaseSlug}-grade-${state.grade}-${state.subject}-current-view.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
    elements["wb-status"].textContent = `Downloaded ${formatNumber(rows.length)} records from the current selection.`;
  };

  const copyShareLink = async () => {
    updateUrl();
    try {
      await navigator.clipboard.writeText(window.location.href);
      elements["wb-status"].textContent = "Share link copied. It preserves the workbench controls and selected districts.";
    } catch (_) {
      const input = document.createElement("textarea");
      input.value = window.location.href;
      input.style.position = "fixed";
      input.style.opacity = "0";
      document.body.appendChild(input);
      input.select();
      document.execCommand("copy");
      input.remove();
      elements["wb-status"].textContent = "Share link copied. It preserves the workbench controls and selected districts.";
    }
  };

  const addDistrict = () => {
    const districtId = elements["wb-district"].value;
    if (!districtId) return;
    if (state.selectedDistricts.includes(districtId)) {
      elements["wb-status"].textContent = `${districtName(districtId)} is already selected.`;
      return;
    }
    if (state.selectedDistricts.length >= 4) {
      elements["wb-status"].textContent = "Remove a district before adding another. The comparison is limited to four.";
      return;
    }
    state.selectedDistricts.push(districtId);
    renderAll();
  };

  const initialize = () => {
    const states = [...new Set(catalog.map((row) => row[catalogFields.state]).filter(Boolean))].sort();
    if (state.universeState !== "US" && !states.includes(state.universeState)) state.universeState = "US";
    if (!states.includes(state.districtFilterState)) {
      state.districtFilterState = districtState(state.selectedDistricts[0]) || states[0];
    }
    elements["wb-state"].innerHTML = '<option value="US">United States</option>'
      + states.map((item) => `<option value="${item}">${item}</option>`).join("");
    elements["wb-district-state"].innerHTML = states
      .map((item) => `<option value="${item}">${item}</option>`).join("");
    elements["wb-state"].value = state.universeState;
    elements["wb-district-state"].value = state.districtFilterState;
    elements["wb-grade"].value = String(state.grade);
    elements["wb-subject"].value = state.subject;
    elements["wb-end-2024"].checked = state.endAt2024;
    populateYears();

    elements["wb-grade"].addEventListener("change", (event) => {
      state.yearExplicit = false;
      selectGrade(Number(event.target.value));
    });
    elements["wb-subject"].addEventListener("change", (event) => {
      state.subject = event.target.value;
      state.yearExplicit = false;
      renderAll();
    });
    elements["wb-state"].addEventListener("change", (event) => {
      state.universeState = event.target.value;
      state.yearExplicit = false;
      renderAll();
    });
    elements["wb-district-state"].addEventListener("change", (event) => {
      state.districtFilterState = event.target.value;
      populateDistrictPicker();
      updateUrl();
    });
    elements["wb-year"].addEventListener("change", (event) => {
      state.year = Number(event.target.value);
      state.yearExplicit = true;
      renderAll();
    });
    elements["wb-end-2024"].addEventListener("change", (event) => {
      state.endAt2024 = event.target.checked;
      renderAll();
    });
    elements["wb-add-district"].addEventListener("click", addDistrict);
    elements["wb-download"].addEventListener("click", downloadCurrentView);
    elements["wb-share"].addEventListener("click", copyShareLink);
    state.initialized = true;
    selectGrade(state.grade);
  };

  window.SEDA_WORKBENCH = {
    activate() {
      if (!state.initialized) {
        if (!workbenchDistrictsRequested) {
          const liveDistrict = new URLSearchParams(window.location.search).get("district");
          if (catalogById.has(liveDistrict)) {
            state.selectedDistricts = [liveDistrict];
            state.universeState = districtState(liveDistrict) || state.universeState;
            state.districtFilterState = districtState(liveDistrict) || state.districtFilterState;
          }
        }
        initialize();
        return;
      }
      if (state.indexed) {
        renderCharts();
        window.setTimeout(() => {
          for (const id of ["wb-trend-chart", "wb-distribution-chart"]) {
            const chart = document.getElementById(id);
            if (chart?.data) window.Plotly.Plots.resize(chart);
          }
        }, 0);
      }
    }
  };

  if (!document.getElementById("workbench-panel").hidden) initialize();
})();
