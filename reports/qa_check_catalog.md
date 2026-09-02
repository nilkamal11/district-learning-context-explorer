# Quality-control catalog

The pipeline executes and stores checks for:

- unique achievement and context grains;
- seven-character normalized district IDs;
- expected subjects, grades, and assessment years;
- an explicit absence of 2020 and 2021 long-form district-grade-subject-year achievement rows;
- nonnegative within-state and cross-state standard errors;
- released-row test-count and standard-error disclosure bounds;
- locale, poverty, and race/ethnicity proportions within 0 to 1;
- plausible race/ethnicity composition totals and variation in every match feature;
- a visible warning when released urbanicity differs from the largest locale share;
- plausible source and analytical row volumes;
- a usable 2024 peer-context universe;
- year-specific crosswalk uniqueness and evidence that stable-ID changes are represented;
- unique state-year-grade-subject coverage-mart keys;
- a visible warning and audit mart for excluded multi-component units;
- source file size, required columns, and SHA-256;
- explicit CSV delimiter, quote, and escape behavior for names containing commas;
- achievement leakage into the peer model;
- deterministic peer selection and exclusion of the target from its own peers;
- a Git-level guard against committing raw files, the local database, or unapproved output data;
- a public-site contract check for the initial dashboard bundle and all five lazy workbench slices, including inert wrappers, schema and field consistency, complete grade coverage, exact row and byte totals, per-file size limits, source verification, raw-filename leakage, and local-path leakage.

Full run artifacts remain local. The published site uses separately checked, permission-approved, selected derived fields. Grade 4 travels with the initial dashboard bundle; grade 3 and grades 5 through 8 load only when selected. Across the six grade slices, the workbench covers all 1,827,384 long-form district-grade-subject-year estimate rows in the analytical achievement mart without publishing the original source files or their full schema.
