(function () {
  "use strict";

  const source = window.DISTRICT_DASHBOARD_DATA;
  const statusElement = document.getElementById("trend-status");
  if (!source || !statusElement) return;

  const scope = source.workbench;
  if (!scope || !Array.isArray(scope.years) || !scope.years.length) {
    statusElement.textContent = "The district trend data could not be prepared. Reload the page or open the Technical process tab.";
    statusElement.classList.add("is-error");
    return;
  }

  const DEFAULT_DISTRICT_ID = "1728890";
  const DEFAULT_GRADE = 4;
  const DEFAULT_SUBJECT = "mth";
  const BASELINE_YEARS = [2019, 2022];
  const SUBJECT_LABELS = { mth: "math", rla: "reading" };
  const YEARS = scope.years;
  const CHART_YEARS = Array.from(
    { length: YEARS.at(-1) - YEARS[0] + 1 },
    (_, index) => YEARS[0] + index
  );
  const CRITICAL_VALUE = scope.confidence_critical_value;
  const WORKBENCH_GRADES = Object.keys(source.technical.workbench_grade_rows || {}).map(Number).sort();
  const catalogFields = Object.fromEntries(source.catalog_fields.map((field, index) => [field, index]));
  const catalog = source.catalog;
  const catalogById = new Map(catalog.map((row) => [row[catalogFields.district_id], row]));
  const gradeCache = new Map();
  const loader = window.SEDA_DATA_LOADER;

  const elements = Object.fromEntries([
    "trend-state", "trend-district", "trend-grade", "trend-subject", "trend-show-range",
    "trend-copy", "trend-status", "trend-results", "trend-unavailable", "trend-unavailable-copy", "trend-data-note",
    "trend-hero-district", "trend-hero-school-year", "trend-hero-score", "trend-hero-copy",
    "trend-record-count", "trend-latest-value", "trend-latest-detail", "trend-change-2019",
    "trend-change-2019-detail", "trend-change-2022", "trend-change-2022-detail",
    "simple-trend-heading", "trend-chart-caption", "trend-records-body"
  ].map((id) => [id, document.getElementById(id)]));

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const schoolYear = (year) => `${year - 1}–${String(year).slice(-2)}`;
  const formatCount = (value) => value === null || value === undefined
    ? "Not available"
    : Number(value).toLocaleString("en-US");
  const formatScore = (value, digits = 2) => value === null || value === undefined || Number.isNaN(value)
    ? "Not available"
    : Number(value).toFixed(digits);
  const formatSigned = (value, digits = 2) => {
    if (value === null || value === undefined || Number.isNaN(value)) return "Not available";
    if (Math.abs(value) < (0.5 * (10 ** -digits))) return Number(0).toFixed(digits);
    const absolute = Math.abs(value).toFixed(digits);
    return value > 0 ? `+${absolute}` : `−${absolute}`;
  };
  const districtName = (districtId) => catalogById.get(districtId)?.[catalogFields.district_name] || districtId;
  const districtState = (districtId) => catalogById.get(districtId)?.[catalogFields.state] || "";
  const gradeSubject = () => `grade ${state.grade} ${SUBJECT_LABELS[state.subject]}`;

  const params = new URLSearchParams(window.location.search);
  const requestedDistrict = params.get("trend_district");
  const requestedGrade = Number(params.get("trend_grade"));
  const requestedSubject = params.get("trend_subject");
  const initialDistrict = catalogById.has(requestedDistrict)
    ? requestedDistrict
    : catalogById.has(DEFAULT_DISTRICT_ID)
      ? DEFAULT_DISTRICT_ID
      : source.default_district_id;

  const state = {
    grade: WORKBENCH_GRADES.includes(requestedGrade) ? requestedGrade : DEFAULT_GRADE,
    subject: ["mth", "rla"].includes(requestedSubject) ? requestedSubject : DEFAULT_SUBJECT,
    districtId: initialDistrict,
    stateCode: districtState(initialDistrict) || "IL",
    showRange: params.get("trend_range") === "1",
    indexed: null,
    initialized: false,
    requestToken: 0
  };

  const indexBundle = (bundle) => {
    const fields = Object.fromEntries(bundle.achievement_fields.map((field, index) => [field, index]));
    const byDistrict = new Map();
    for (const row of bundle.achievement) {
      if (!Array.isArray(row) || row.length !== bundle.achievement_fields.length) {
        throw new Error(`Grade ${bundle.grade} contains a malformed record.`);
      }
      const districtId = row[fields.district_id];
      const subject = row[fields.subject];
      const year = row[fields.year];
      if (!byDistrict.has(districtId)) byDistrict.set(districtId, { mth: new Map(), rla: new Map() });
      byDistrict.get(districtId)[subject].set(year, row);
    }
    return { ...bundle, fields, byDistrict };
  };

  const validateBundle = (grade, bundle, stateCode = null) => {
    const expectedFields = JSON.stringify(source.achievement_fields);
    const expectedRows = stateCode
      ? source.technical.achievement_state_rows?.[stateCode]
      : source.technical.workbench_grade_rows?.[String(grade)];
    const valid = bundle
      && bundle.schema_version === source.schema_version
      && bundle.release === scope.release
      && bundle.geography === scope.geography
      && bundle.subgroup === scope.subgroup
      && bundle.scale === scope.scale
      && bundle.grade === grade
      && (stateCode === null || bundle.state === stateCode)
      && JSON.stringify(bundle.achievement_fields) === expectedFields
      && Number.isInteger(expectedRows)
      && bundle.row_count === expectedRows
      && Array.isArray(bundle.achievement)
      && bundle.row_count === bundle.achievement.length;
    if (!valid) throw new Error(`Grade ${grade} data failed its release and schema checks.`);
    return bundle;
  };

  const loadGrade = async (grade, stateCode) => {
    const usesStateBundle = grade === source.grade;
    const cacheKey = usesStateBundle ? `${grade}:${stateCode}` : `${grade}:all`;
    if (gradeCache.has(cacheKey)) return gradeCache.get(cacheKey);
    if (!loader) throw new Error("The district trend data loader is unavailable.");
    const bundle = usesStateBundle
      ? await loader.loadAchievementState(grade, stateCode)
      : await loader.loadWorkbenchGrade(grade);
    const indexed = indexBundle(validateBundle(grade, bundle, usesStateBundle ? stateCode : null));
    gradeCache.set(cacheKey, indexed);
    return indexed;
  };

  const rowFor = (year) => state.indexed?.byDistrict.get(state.districtId)?.[state.subject]?.get(year) || null;
  const reportedRows = () => [...(state.indexed?.byDistrict.get(state.districtId)?.[state.subject]?.values() || [])]
    .sort((left, right) => left[state.indexed.fields.year] - right[state.indexed.fields.year]);
  const hasCurrentData = (districtId) => (
    (state.indexed?.byDistrict.get(districtId)?.[state.subject]?.size || 0) > 0
  );

  const updateUrl = () => {
    const url = new URL(window.location.href);
    url.searchParams.set("trend_state", state.stateCode);
    url.searchParams.set("trend_district", state.districtId);
    url.searchParams.set("trend_grade", state.grade);
    url.searchParams.set("trend_subject", state.subject);
    if (state.showRange) url.searchParams.set("trend_range", "1");
    else url.searchParams.delete("trend_range");
    if (!document.getElementById("trends-panel").hidden) url.hash = "trends";
    window.history.replaceState({}, "", url);
  };

  const setBusy = (busy, message = "") => {
    for (const control of document.querySelectorAll("#trends-panel button, #trends-panel select, #trends-panel input")) {
      control.disabled = busy;
    }
    elements["trend-results"].setAttribute("aria-busy", String(busy));
    if (busy) {
      elements["trend-results"].hidden = true;
      elements["trend-unavailable"].hidden = true;
    }
    elements["trend-status"].classList.toggle("is-loading", busy);
    if (busy) elements["trend-status"].classList.remove("is-error");
    if (message) elements["trend-status"].textContent = message;
  };

  const populateDistricts = () => {
    const rows = catalog
      .filter((row) => row[catalogFields.state] === state.stateCode)
      .sort((left, right) => String(left[catalogFields.district_name]).localeCompare(String(right[catalogFields.district_name])));
    if (!rows.some((row) => row[catalogFields.district_id] === state.districtId)) {
      state.districtId = rows.find((row) => hasCurrentData(row[catalogFields.district_id]))?.[catalogFields.district_id]
        || rows[0]?.[catalogFields.district_id]
        || state.districtId;
    }
    elements["trend-district"].innerHTML = rows.map((row) => {
      const districtId = row[catalogFields.district_id];
      const availability = hasCurrentData(districtId) ? "" : " · no released result";
      return `<option value="${districtId}">${escapeHtml(row[catalogFields.district_name])} · ${districtId}${availability}</option>`;
    }).join("");
    elements["trend-district"].value = state.districtId;
  };

  const populateStates = () => {
    const states = [...new Set(catalog.map((row) => row[catalogFields.state]).filter(Boolean))].sort();
    if (!states.includes(state.stateCode)) state.stateCode = districtState(state.districtId) || states[0];
    elements["trend-state"].innerHTML = states.map((item) => `<option value="${item}">${item}</option>`).join("");
    elements["trend-state"].value = state.stateCode;
  };

  const directionCopy = (value) => {
    if (Math.abs(value) < 0.005) return "at Stanford’s fixed national reference";
    return `${Math.abs(value).toFixed(2)} standard deviations ${value > 0 ? "above" : "below"} Stanford’s fixed national reference`;
  };

  const referenceSide = (value) => {
    if (Math.abs(value) < 0.005) return "at the national reference";
    return `${value > 0 ? "above" : "below"} the national reference`;
  };

  const changeCopy = (change, baselineYear) => {
    if (Math.abs(change) < 0.005) return `Essentially unchanged from ${schoolYear(baselineYear)} at two decimal places.`;
    return `${Math.abs(change).toFixed(2)} standard deviations ${change > 0 ? "higher" : "lower"} than ${schoolYear(baselineYear)}.`;
  };

  const baselineComparison = (latestEstimate, latestYear, baselineYear) => {
    if (latestYear <= baselineYear) {
      return {
        value: "No later result",
        detail: `The latest released result is ${schoolYear(latestYear)}, so there is no later year to compare with ${schoolYear(baselineYear)}.`
      };
    }
    const baseline = rowFor(baselineYear);
    if (!baseline) {
      return {
        value: "Not available",
        detail: `No released ${schoolYear(baselineYear)} result is available for this exact comparison.`
      };
    }
    const change = latestEstimate - baseline[state.indexed.fields.estimate];
    return { value: formatSigned(change), detail: changeCopy(change, baselineYear) };
  };

  const renderHero = (latestRow = null) => {
    const name = districtName(state.districtId);
    elements["trend-hero-district"].textContent = `${name} · ${districtState(state.districtId)} · ${state.districtId}`;
    if (!latestRow) {
      elements["trend-hero-school-year"].textContent = `Grade ${state.grade} ${SUBJECT_LABELS[state.subject]}`;
      elements["trend-hero-score"].textContent = "—";
      elements["trend-hero-copy"].textContent = "No released result is available for this choice.";
      return;
    }
    const fields = state.indexed.fields;
    const year = latestRow[fields.year];
    const estimate = latestRow[fields.estimate];
    elements["trend-hero-school-year"].textContent = `${schoolYear(year)} · Grade ${state.grade} ${SUBJECT_LABELS[state.subject]}`;
    elements["trend-hero-score"].textContent = formatSigned(estimate);
    elements["trend-hero-copy"].textContent = `This is ${directionCopy(estimate)} for this grade and subject.`;
  };

  const renderSummary = (rows) => {
    const fields = state.indexed.fields;
    const latest = rows.at(-1);
    const latestYear = latest[fields.year];
    const latestEstimate = latest[fields.estimate];
    elements["trend-record-count"].textContent = `${formatCount(rows.length)} years · latest ${schoolYear(latestYear)}`;
    elements["trend-latest-value"].textContent = formatSigned(latestEstimate);
    elements["trend-latest-detail"].textContent = `${schoolYear(latestYear)} · ${referenceSide(latestEstimate)}.`;

    for (const baselineYear of BASELINE_YEARS) {
      const comparison = baselineComparison(latestEstimate, latestYear, baselineYear);
      elements[`trend-change-${baselineYear}`].textContent = comparison.value;
      elements[`trend-change-${baselineYear}-detail`].textContent = comparison.detail;
    }
  };

  const renderChart = (rows) => {
    if (document.getElementById("trends-panel").hidden) return;
    const fields = state.indexed.fields;
    const rowsByYear = new Map(rows.map((row) => [row[fields.year], row]));
    const chartRows = CHART_YEARS.map((year) => rowsByYear.get(year) || null);
    const estimates = chartRows.map((row) => row?.[fields.estimate] ?? null);
    const margins = chartRows.map((row) => row ? CRITICAL_VALUE * row[fields.standard_error_within_state] : null);
    const customdata = CHART_YEARS.map((year, index) => {
      const row = chartRows[index];
      return [
        schoolYear(year),
        row ? formatCount(row[fields.tested_count]) : "Not available",
        row?.[fields.tested_count_estimated] === 1 ? "estimated by SEDA" : "reported",
        margins[index]
      ];
    });
    const trace = {
      x: CHART_YEARS,
      y: estimates,
      customdata,
      mode: "lines+markers",
      name: districtName(state.districtId),
      line: { color: "#dc7139", width: 3 },
      marker: { color: "#dc7139", size: 7, line: { color: "#ffffff", width: 1 } },
      fill: "tozeroy",
      fillcolor: "rgba(220,113,57,.09)",
      error_y: {
        type: "data",
        array: margins,
        visible: state.showRange,
        color: "rgba(220,113,57,.7)",
        thickness: 1,
        width: 3
      },
      connectgaps: false,
      hovertemplate: "%{customdata[0]}<br>Estimated average: %{y:.3f}<br>Uncertainty margin: ±%{customdata[3]:.3f}<br>Tests represented: %{customdata[1]} (%{customdata[2]})<extra></extra>"
    };
    const layout = {
      margin: { l: 90, r: 24, t: 36, b: 72 },
      height: 430,
      paper_bgcolor: "#ffffff",
      plot_bgcolor: "#ffffff",
      font: { family: "Inter, Arial, sans-serif", color: "#344852", size: 11 },
      hovermode: "closest",
      showlegend: false,
      xaxis: {
        title: { text: "Year", standoff: 10 },
        automargin: true,
        gridcolor: "#e9edec",
        dtick: 2,
        range: [YEARS[0] - 0.4, YEARS.at(-1) + 0.4]
      },
      yaxis: {
        title: { text: "Average score vs. national reference", standoff: 12 },
        automargin: true,
        gridcolor: "#e9edec",
        zeroline: true,
        zerolinecolor: "#82939a",
        zerolinewidth: 1.5
      },
      shapes: [{
        type: "rect",
        x0: 2019.5,
        x1: 2021.5,
        y0: 0,
        y1: 1,
        yref: "paper",
        fillcolor: "rgba(100,114,124,.10)",
        line: { width: 0 },
        layer: "below"
      }],
      annotations: [
        {
          x: 2020.5,
          y: 1,
          yref: "paper",
          text: "No results released",
          showarrow: false,
          yshift: 10,
          font: { size: 9, color: "#64727c" }
        },
        {
          x: 1,
          xref: "paper",
          xanchor: "right",
          y: 0,
          yref: "y",
          yanchor: "bottom",
          text: "National reference (0)",
          showarrow: false,
          yshift: 4,
          bgcolor: "rgba(255,254,250,.88)",
          font: { size: 9, color: "#52656e" }
        }
      ]
    };
    const latest = rows.at(-1);
    const latestTrace = {
      x: [latest[fields.year]],
      y: [latest[fields.estimate]],
      mode: "markers",
      marker: { color: "#dc7139", size: 13, line: { color: "#123649", width: 2 } },
      hoverinfo: "skip",
      showlegend: false
    };
    window.Plotly.react("trend-chart", [trace, latestTrace], layout, { displaylogo: false, responsive: true, displayModeBar: false });
  };

  const renderRecords = (rows) => {
    const fields = state.indexed.fields;
    elements["trend-records-body"].innerHTML = [...rows].reverse().map((row) => {
      const estimate = row[fields.estimate];
      const margin = CRITICAL_VALUE * row[fields.standard_error_within_state];
      const estimatedCount = row[fields.tested_count_estimated] === 1;
      return `<tr>
        <td>${schoolYear(row[fields.year])}</td>
        <td>${row[fields.year]}</td>
        <td>${formatScore(estimate, 3)}</td>
        <td>${formatScore(estimate - margin, 3)} to ${formatScore(estimate + margin, 3)}</td>
        <td>${formatCount(row[fields.tested_count])}</td>
        <td>${estimatedCount ? '<span class="status-tag warn">Estimated by SEDA</span>' : "Reported"}</td>
      </tr>`;
    }).join("");
  };

  const renderAll = () => {
    if (!state.indexed) return;
    populateDistricts();
    const rows = reportedRows();
    const name = districtName(state.districtId);
    if (!rows.length) {
      elements["trend-results"].hidden = true;
      elements["trend-unavailable"].hidden = false;
      elements["trend-unavailable-copy"].textContent = `${name} has no released ${gradeSubject()} result in this public SEDA slice.`;
      elements["trend-status"].textContent = `No released ${gradeSubject()} result for ${name}.`;
      renderHero();
      updateUrl();
      return;
    }

    elements["trend-unavailable"].hidden = true;
    elements["trend-results"].hidden = false;
    const latest = rows.at(-1);
    const latestYear = latest[state.indexed.fields.year];
    elements["trend-data-note"].hidden = latestYear >= YEARS.at(-1);
    elements["trend-data-note"].textContent = latestYear < YEARS.at(-1)
      ? `No spring ${YEARS.at(-1)} result is available for this selection. Latest: ${schoolYear(latestYear)} (spring ${latestYear}).`
      : "";
    renderHero(latest);
    renderSummary(rows);
    elements["simple-trend-heading"].textContent = `${name}: ${gradeSubject()} by year`;
    elements["trend-chart-caption"].textContent = "Each dot is one spring district estimate. No annual estimates are available for 2020 or 2021.";
    renderRecords(rows);
    renderChart(rows);
    elements["trend-status"].textContent = `${formatCount(rows.length)} years loaded · latest ${schoolYear(latestYear)}`;
    elements["trend-status"].classList.remove("is-error");
    updateUrl();
  };

  const selectGrade = async (grade) => {
    const token = ++state.requestToken;
    const previousGrade = state.grade;
    const previousIndexed = state.indexed;
    setBusy(true, `Loading grade ${grade} district results…`);
    elements["trend-hero-school-year"].textContent = `Loading grade ${grade} ${SUBJECT_LABELS[state.subject]}…`;
    elements["trend-hero-score"].textContent = "…";
    elements["trend-hero-copy"].textContent = "Checking the released annual district records.";
    try {
      const [indexed] = await Promise.all([
        loadGrade(grade, state.stateCode),
        loader.loadPlotly()
      ]);
      if (token !== state.requestToken) return;
      state.grade = grade;
      state.indexed = indexed;
      setBusy(false);
      renderAll();
    } catch (error) {
      if (token !== state.requestToken) return;
      state.grade = previousGrade;
      state.indexed = previousIndexed;
      elements["trend-grade"].value = String(previousGrade);
      setBusy(false);
      if (previousIndexed) renderAll();
      elements["trend-status"].textContent = `${error.message} The previous grade remains active.`;
      elements["trend-status"].classList.add("is-error");
    }
  };

  const copyViewLink = async () => {
    updateUrl();
    try {
      await navigator.clipboard.writeText(window.location.href);
    } catch (_) {
      const input = document.createElement("textarea");
      input.value = window.location.href;
      input.style.position = "fixed";
      input.style.opacity = "0";
      document.body.appendChild(input);
      input.select();
      document.execCommand("copy");
      input.remove();
    }
    elements["trend-status"].textContent = "Link copied.";
  };

  const initialize = () => {
    populateStates();
    elements["trend-grade"].value = String(state.grade);
    elements["trend-subject"].value = state.subject;
    elements["trend-show-range"].checked = state.showRange;

    elements["trend-state"].addEventListener("change", (event) => {
      state.stateCode = event.target.value;
      const candidates = catalog.filter((row) => row[catalogFields.state] === state.stateCode);
      state.districtId = candidates[0]?.[catalogFields.district_id] || state.districtId;
      selectGrade(state.grade);
    });
    elements["trend-district"].addEventListener("change", (event) => {
      state.districtId = event.target.value;
      renderAll();
    });
    elements["trend-grade"].addEventListener("change", (event) => selectGrade(Number(event.target.value)));
    elements["trend-subject"].addEventListener("change", (event) => {
      state.subject = event.target.value;
      renderAll();
    });
    elements["trend-show-range"].addEventListener("change", (event) => {
      state.showRange = event.target.checked;
      renderAll();
    });
    elements["trend-copy"].addEventListener("click", copyViewLink);
    state.initialized = true;
    selectGrade(state.grade);
  };

  window.SEDA_TRENDS = {
    activate() {
      if (!state.initialized) {
        initialize();
        return;
      }
      if (state.indexed) {
        renderChart(reportedRows());
        window.setTimeout(() => {
          const chart = document.getElementById("trend-chart");
          if (chart?.data) window.Plotly?.Plots?.resize(chart);
        }, 0);
      }
    }
  };

  if (!document.getElementById("trends-panel").hidden) initialize();
})();
