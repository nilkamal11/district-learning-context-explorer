# Research specification

## Primary question

How do a district's grade-specific mathematics and reading achievement estimates compare with a fixed set of districts similar on selected public context measures, and how has that relationship changed over reported years?

## Unit and scope

- Unit: SEDA administrative school district
- Population: Districts serving the selected grade with complete core peer context
- Grades: 3 through 8, with grade 4 as the default
- Subjects: Mathematics and reading/language arts, reported separately
- Years: 2009 through 2019 and 2022 through 2025
- Subgroup: All students for version 0.1
- Primary scale: Cohort Standardized (CS)
- Context snapshot: 2024, fixed for all historical comparisons

## Estimands

This is a descriptive profile, not a causal study. The output includes:

1. The district's released grade-by-subject-by-year achievement estimate and configured confidence interval.
2. The median and middle 50% among fixed, context-matched peers.
3. For same-state peers, the district minus equal-weight peer mean difference with an uncertainty interval.
4. Match diagnostics and peer data coverage by year.
5. A separate descriptive cross-state sensitivity panel that excludes the target state.

## Decision rules

- Do not combine math and reading.
- Do not combine grades on the CS scale.
- Do not select peers using achievement or change in achievement.
- Do not include a nominal match feature unless its released distribution has usable variation.
- Do not classify a low-precision estimate as clearly higher or lower without an uncertainty check.
- Require at least 10 reporting peers and 70% coverage of the selected set for a year-subject comparison.
- Use unadjusted standard errors within state and adjusted standard errors across states.
- Keep national analog comparisons descriptive because adjusted errors can share state-level linking uncertainty.
- Keep 2020 and 2021 as explicit missing assessment years.
- Never replace unavailable or suppressed results with zero.
- Describe changes as aggregate district patterns, not individual student growth.

## Planned extensions

- 2024 SAIPE poverty for a boundary-aligned federal sensitivity measure
- 2024–25 CCD agency type and operational-status filters
- An optional pooled-grades district-leader panel using released SEDA annual-by-subject estimates
- A separate real product-event dataset to demonstrate event telemetry analysis without fabricating records
