# Quality-control catalog

The pipeline executes and stores checks for:

- unique achievement and context grains;
- seven-character normalized district IDs;
- expected subjects, grades, and assessment years;
- an explicit absence of 2020 and 2021 achievement rows;
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
- a public-dashboard contract check for schema, counts, source verification, size, and local-path leakage.

Full run artifacts remain local. The published dashboard uses the separately checked, permission-approved, grade-4 derived bundle.
