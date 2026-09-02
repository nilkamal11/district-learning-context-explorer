# Validation snapshot

Validated locally on 2026-09-02 against SEDA 2025.2. This is an aggregate engineering record, not a data extract. It contains no district estimates, source rows, or peer membership.

## Source contracts

- All three required files matched the project-computed SHA-256 fingerprints pinned in `config/sources.yml`.
- Achievement staging: 1,827,973 long-form district-grade-subject-year rows.
- Annual context staging: 296,040 district-year rows.
- Administrative crosswalk staging: 52,770 source-year mappings, including 174 mappings where the source and stable IDs differ.
- Analytical achievement mart: 1,827,384 long-form estimate rows after documented scope and completeness rules.
- Coverage mart: 7,805 state-year-grade-subject rows.

The fingerprints identify the exact retrieved files used for this run. They are not provider-issued checksums.

## Quality and software checks

- 18 error-level data checks passed.
- 2 diagnostic warnings were retained rather than hidden:
  - 1,841 2024 administrative-district rows have a released urbanicity category different from the largest locale share. Matching preserves the released category and keeps the recomputation for audit.
  - 589 multi-component rows across 41 districts in AZ, NM, and UT from 2016–2019 are excluded from the within-state design and recorded in `mart_exclusion_audit`.
- 24 software test cases passed, including all SQL models, source-manifest behavior, clean-clone CLI routing, outcome allowlisting, state-cap-aware national relaxation, sparse-peer gates, pool-specific precision, dashboard and workbench serialization, the lazy-loader markup contract, the fixed grade-4 publication contract, and a strict full-report render.
- Ruff completed with no findings.
- The public-site contract check passed for the initial dashboard bundle and all five lazy workbench slices. It verified inert wrappers, schema and field consistency, grades 3–8 coverage, exact row and byte totals, per-file size limits, source-hash provenance, and the absence of raw filenames and local paths.
- The tracked-file publication guard passed with no restricted raw, processed, or unapproved output data tracked.

## Rendered-report checks

- Full desktop report inspected visually.
- Phone-size layout inspected at 390 × 844.
- The chart library is embedded once, so the local report does not depend on a CDN.
- The peer-details control opened successfully and displayed all 15 selected in-state peers.
- Browser console warnings and errors: 0.
- National analogs were verified to exclude the target state.

## Interactive-dashboard checks

- The public bundle contains 19,461 catalog districts, 17,852 context rows, and 311,427 grade-4 district-subject-year estimate rows in 21.90 MB.
- Five lazy-loaded workbench files add 1,515,957 long-form estimate rows in 84.52 MB. Across all six grade files, the workbench exposes 1,827,384 district-grade-subject-year estimates in 106,420,280 bytes (106.42 MB):

  | Grade | Long-form estimate rows | Published file size |
  |---:|---:|---:|
  | 3 | 313,372 | 17.45 MB |
  | 4 | 311,427 | 21.90 MB |
  | 5 | 323,925 | 18.06 MB |
  | 6 | 321,292 | 17.92 MB |
  | 7 | 289,152 | 16.13 MB |
  | 8 | 268,216 | 14.96 MB |

  The grade-4 file is larger because it is also the initial dashboard bundle and includes the district catalog, 2024 context, model settings, and technical metadata.
- Browser calculations for the neutral Illinois demonstration district reproduced the Python peer IDs, context distances, latest estimates, peer summaries, uncertainty intervals, and national sensitivity results.
- State and district selection was exercised for Illinois and Pennsylvania, including both same-state and national-fallback primary pools.
- The workbench lazy-loaded grades 3 and 5 through 8, switched between mathematics and reading, and retained independent reference-distribution and district-state controls.
- A two-state comparison switched from within-state to adjusted cross-state standard errors; the 2024 sensitivity control, filtered CSV export, copied share link, and URL-state restoration were exercised.
- Argo CHSD 217 remains selectable and correctly displays a grade-4-unavailable explanation, zero selected grade-subject-year estimates, and 15 visibly missing year cells instead of substituting another district.
- The Explore, SEDA Workbench, and Technical Process tabs were inspected at desktop size, and the workbench was inspected at 390 x 844 without horizontal page overflow.
- Browser console warnings and errors: 0.

## Publication boundary

Stanford confirmed to the project owner that this Git portfolio use is permitted. The public site contains checked, field-limited derived bundles for the all-student, administrative-district Cohort Standardized estimates across grades 3–8. Grade 4 is included in the initial dashboard bundle, while the other grades load on demand. Raw source files, the DuckDB database, single-district working reports, peer CSV files, and unrestricted JSON outputs remain local and ignored by Git.
