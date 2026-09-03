# Illinois Grade 4 Growth Explorer: initial research specification

## Scope

The first release is restricted to Illinois public school-level Grade 4 English language arts and mathematics results for Report Card years 2022 through 2025. School-level enrollment, student composition, mobility, and chronic absenteeism provide context.

## Outcome hierarchy

1. **Primary:** published Grade 4 mean Student Growth Percentile (SGP), when Illinois publishes it at that grain.
2. **Secondary:** Grade 4 proficiency rate, with an explicit metric-version break in 2025.
3. **Context:** participation, enrollment, mobility, chronic absenteeism, low-income share, English learner share, and IEP share.

The public files do not contain student identifiers or assessment histories. This project therefore does not construct matched student panels. An SGP is student-linked inside the state system before Illinois publishes it as an aggregate; the project consumes that published aggregate.

## Schema finding that governs the first build

- The 2022–2024 annual IAR sheets publish Grade 4 performance-level distributions. The pipeline derives the then-current proficiency rate as Levels 4 plus 5.
- The 2025 IAR sheet publishes Grade 4 proficiency, participation, and growth fields directly.
- The separate 2022–2024 cohort-versus-baseline workbooks publish school-level SGP comparisons across the tested grade span, not a Grade 4-only result. They are retained as reference sources but are not relabeled as Grade 4 growth.

Consequently, the initial analytical table leaves Grade 4 SGP missing for 2022–2024 and reports it for 2025. This is a source limitation, not an imputation target. Longitudinal Grade 4 proficiency remains available for all four years, with the 2025 comparability break displayed.

## Grain

One row per:

`report_card_year × RCDTS × school × subject × grade`

The first release has only Grade 4 and the subjects `ela` and `math`.

## Interpretation rules

- Preserve `*` as `suppressed`; never convert it to zero.
- Preserve unavailable fields as `not_published` or `missing`, as appropriate.
- Do not average annual SGP values into an amount of learning.
- Do not describe associations with mobility or chronic absenteeism as causal.
- Do not bridge an RCDTS change until the entity relationship is documented.
- Normalize punctuation-only RCDTS formatting changes while retaining the source value.
- Do not compare 2025 proficiency to prior years without displaying the metric-version warning.

## Next build increments

1. Produce and QA the normalized Grade 4 school-year extract.
2. Add the archived Entity Profile System directories and a reviewed RCDTS crosswalk.
3. Build the first district/school profile using North Palos School District 117 as the default view.
4. Replace the current SEDA dashboard data layer only after the Illinois extract and identity audit pass.

## Initial local-area dashboard

The first interactive dashboard defaults to North Palos SD 117 and includes three nearby
elementary districts: Indian Springs SD 109, Palos CCSD 118, and Worth SD 127. This is a
geographic convenience set, not a statistically matched comparison group. Every current
school in those districts appears in the selector; schools outside Grade 4 display an
explicit not-applicable state.
