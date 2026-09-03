(function () {
  "use strict";

  const source = window.DISTRICT_DASHBOARD_DATA;
  if (!source) return;

  const scriptPromises = new Map();

  const loadScript = (relativePath, cacheKey, version) => {
    if (scriptPromises.has(cacheKey)) return scriptPromises.get(cacheKey);
    const promise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      const scriptUrl = new URL(relativePath, document.baseURI);
      scriptUrl.searchParams.set("v", version);
      script.src = scriptUrl.href;
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error(`${relativePath} could not be loaded.`));
      document.head.appendChild(script);
    }).finally(() => scriptPromises.delete(cacheKey));
    scriptPromises.set(cacheKey, promise);
    return promise;
  };

  const hasExpectedScope = (bundle, grade) => (
    bundle
    && bundle.schema_version === source.schema_version
    && bundle.release === source.workbench.release
    && bundle.geography === source.workbench.geography
    && bundle.subgroup === source.workbench.subgroup
    && bundle.scale === source.workbench.scale
    && bundle.grade === grade
    && JSON.stringify(bundle.achievement_fields) === JSON.stringify(source.achievement_fields)
    && Array.isArray(bundle.achievement)
    && bundle.row_count === bundle.achievement.length
  );

  const validateWorkbenchGrade = (grade, bundle) => {
    const expectedRows = source.technical.workbench_grade_rows?.[String(grade)];
    if (!hasExpectedScope(bundle, grade) || bundle.row_count !== expectedRows) {
      throw new Error(`Grade ${grade} data failed its release and row-count checks.`);
    }
    return bundle;
  };

  const validateAchievementState = (grade, state, bundle) => {
    const expectedRows = source.technical.achievement_state_rows?.[state];
    if (
      !hasExpectedScope(bundle, grade)
      || bundle.state !== state
      || bundle.row_count !== expectedRows
    ) {
      throw new Error(`Grade ${grade} ${state} data failed its release and row-count checks.`);
    }
    return bundle;
  };

  const loadWorkbenchGrade = async (grade) => {
    const knownGrades = source.technical.workbench_grade_rows || {};
    if (!Object.hasOwn(knownGrades, String(grade))) {
      throw new Error(`Grade ${grade} is outside this dashboard’s published scope.`);
    }
    const cached = window.SEDA_WORKBENCH_GRADES?.[grade];
    if (cached) {
      try {
        return validateWorkbenchGrade(grade, cached);
      } catch (error) {
        delete window.SEDA_WORKBENCH_GRADES[grade];
      }
    }
    await loadScript(
      `data/workbench-grade-${grade}.js`,
      `workbench:${grade}`,
      source.generated_at_utc
    );
    try {
      return validateWorkbenchGrade(grade, window.SEDA_WORKBENCH_GRADES?.[grade]);
    } catch (error) {
      if (window.SEDA_WORKBENCH_GRADES) delete window.SEDA_WORKBENCH_GRADES[grade];
      throw error;
    }
  };

  const loadAchievementState = async (grade, state) => {
    const normalizedState = String(state || "").toUpperCase();
    const knownStates = source.technical.achievement_state_rows || {};
    if (grade !== source.grade || !/^[A-Z]{2}$/.test(normalizedState) || !Object.hasOwn(knownStates, normalizedState)) {
      throw new Error(`Grade ${grade} ${normalizedState || "state"} data is outside this dashboard’s published scope.`);
    }
    const cached = window.SEDA_ACHIEVEMENT_STATES?.[grade]?.[normalizedState];
    if (cached) {
      try {
        return validateAchievementState(grade, normalizedState, cached);
      } catch (error) {
        delete window.SEDA_ACHIEVEMENT_STATES[grade][normalizedState];
      }
    }
    await loadScript(
      `data/achievement-grade-${grade}-${normalizedState}.js`,
      `state:${grade}:${normalizedState}`,
      source.generated_at_utc
    );
    try {
      return validateAchievementState(
        grade,
        normalizedState,
        window.SEDA_ACHIEVEMENT_STATES?.[grade]?.[normalizedState]
      );
    } catch (error) {
      if (window.SEDA_ACHIEVEMENT_STATES?.[grade]) {
        delete window.SEDA_ACHIEVEMENT_STATES[grade][normalizedState];
      }
      throw error;
    }
  };

  const loadPlotly = async () => {
    if (window.Plotly?.react) return window.Plotly;
    await loadScript(
      "assets/plotly-cartesian-3.7.0.min.js",
      "plotly",
      source.generated_at_utc
    );
    if (!window.Plotly?.react) throw new Error("The chart library did not initialize.");
    return window.Plotly;
  };

  window.SEDA_DATA_LOADER = {
    loadAchievementState,
    loadPlotly,
    loadWorkbenchGrade
  };
})();
