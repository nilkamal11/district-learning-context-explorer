# Validation snapshot

Validated locally on 2026-09-02 against SEDA 2025.2. This is an aggregate engineering record, not a data extract. It contains no district estimates, source rows, or peer membership.

## Source contracts

- All three required files matched the project-computed SHA-256 fingerprints pinned in `config/sources.yml`.
- Achievement staging: 1,827,973 district-subject-grade-year rows.
- Annual context staging: 296,040 district-year rows.
- Administrative crosswalk staging: 52,770 source-year mappings, including 174 mappings where the source and stable IDs differ.
- Analytical achievement mart: 1,827,384 rows after documented scope and completeness rules.
- Coverage mart: 7,805 state-year-grade-subject rows.

The fingerprints identify the exact retrieved files used for this run. They are not provider-issued checksums.

## Quality and software checks

- 18 error-level data checks passed.
- 2 diagnostic warnings were retained rather than hidden:
  - 1,841 2024 administrative-district rows have a released urbanicity category different from the largest locale share. Matching preserves the released category and keeps the recomputation for audit.
  - 589 multi-component rows across 41 districts in AZ, NM, and UT from 2016–2019 are excluded from the within-state design and recorded in `mart_exclusion_audit`.
- 19 software tests passed, including all SQL models, source-manifest behavior, clean-clone CLI routing, outcome allowlisting, state-cap-aware national relaxation, sparse-peer gates, pool-specific precision, and a strict full-report render.
- Ruff completed with no findings.

## Rendered-report checks

- Full desktop report inspected visually.
- Phone-size layout inspected at 390 × 844.
- The chart library is embedded once, so the local report does not depend on a CDN.
- The peer-details control opened successfully and displayed all 15 selected in-state peers.
- Browser console warnings and errors: 0.
- National analogs were verified to exclude the target state.

## Publication boundary

The real-data HTML profile, peer CSV, JSON summary, source files, and DuckDB database remain local and ignored by Git. Stanford's Data Use Agreement should be clarified in writing before any real-data output is used as public employment-portfolio evidence.
