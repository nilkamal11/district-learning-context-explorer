# Methodology

## Why a matched context comparison

A raw state or national average answers whether two estimates differ, but it does not answer whether districts serve similar communities. This project creates a transparent contextual reference group while keeping outcomes entirely out of the matching process.

The result is still descriptive. Context matching reduces obvious mismatch; it does not reproduce a randomized experiment or justify causal claims.

## Outcome

The profile uses `cs_mn_all` from SEDA's long administrative district CS file. Each record is one administrative district, subject, grade, and spring assessment year. The CS unit is one student-level standard deviation relative to SEDA's national reference cohorts.

Valid comparisons are across places and years within the same subject and grade. Math and reading cannot be compared to one another, and grade 4 cannot be compared directly with grade 5 on this scale.

The long file supplies two standard errors:

- `cs_mn_se_all` for within-state comparisons
- `cs_mn_se_adj_all` for comparisons across states, including NAEP-linking uncertainty

The configured confidence interval uses the corresponding normal critical value. Version 0.1 uses 95%, which is approximately the released estimate plus or minus `1.959964 × SE`.

## Context snapshot

The peer set uses the 2024 row from SEDA's annual administrative district covariate file. This is deliberate:

- It freezes peers so historical charts are not partly driven by changing peer membership.
- The most recent ACS-based fields are available in 2024 but not 2025.
- It provides a clean later hook for SAIPE 2024 and CCD 2024–25 validation.

This creates a retrospective limitation: the fixed set represents districts similar on 2024 context, not necessarily districts that served equally similar communities in every earlier year.

Enrollment is grades 3–8 enrollment, not total K–12 enrollment. Variables labeled as percentages in the source are represented as proportions from 0 to 1.

## Eligibility

The target and candidate must:

- serve the selected grade;
- have positive grades 3–8 enrollment;
- have family poverty, socioeconomic status, race and ethnicity shares, and four broad locale shares;
- share the target's broad grade-span bucket;
- have complete values for all four match domains.

Outcome availability can affect how many selected peers contribute to a displayed year, but achievement values do not affect selection.

## Distance

Four domains each receive weight 0.25:

1. district scale;
2. economic context;
3. student composition;
4. place.

For a numeric feature, the distance is:

```text
min(abs(candidate - target) / (national P95 - national P05), 1)
```

Enrollment is transformed with `log(1 + enrollment)` first. Economic-context distance is the mean available distance for family poverty and SEDA's socioeconomic status composite, keeping correlated measures inside one domain rather than allowing them to dominate the model.

Student-composition and locale vectors use Hellinger distance:

```text
sqrt(0.5 × sum((sqrt(candidate share) - sqrt(target share))²))
```

All four domains are required. The hard locale caliper uses SEDA's released `urbanicity` category. The project also recomputes the largest locale share as an audit field; those two classifications disagree for some districts, so the released category is preserved and the discrepancy appears as a diagnostic warning. SEDA's recent annual English learner and special education fields are constant at zero, so they are excluded rather than treated as meaningful match features. Executable QA checks confirm that the included features vary and stay in plausible ranges in the selected context year.

## Staged calipers

Same-state matching starts with:

- exact grade-span bucket;
- same dominant locale;
- enrollment between one-quarter and four times the target;
- poverty within 15 percentage points.

If fewer than ten candidates remain, locale becomes a distance contribution instead of a hard rule. If the pool is still too small, the final stage allows enrollment between one-eighth and eight times the target and poverty within 25 points. Every relaxation is saved in the peer-set output.

The preferred same-state set contains 15 peers. Sets of 10 through 14 are usable with caveats. Fewer than 10 are insufficient, so the report uses the separate national analog panel as its primary descriptive reference. A full count is not labeled a strong match by itself; the report exposes the median distance for every weighted domain.

National matching excludes the target state, uses the same staged rules, selects 20 peers, and limits any state to three selected districts.

## Uncertainty

The profile displays the target district's released estimate with the configured interval, alongside the peer mean, median, and interquartile range. The chart uses the median and interquartile range; the cards and sensitivity table also expose the mean used as the same-state comparison benchmark. A year-subject comparison requires at least 10 reporting peers and at least 70% coverage of the selected peer set.

For the same-state panel, the target-minus-equal-weight-peer-mean interval propagates the target variance and peer variances. National analogs use adjusted standard errors for displayed district uncertainty but remain descriptive: state-level NAEP-linking uncertainty may be shared, so the project does not use a naive independence formula to classify the national comparison as higher or lower.

## Precision flag

The report marks a result for extra caution when any of these are true:

- fewer than 50 tested students;
- the tested count was estimated;
- the configured interval margin exceeds 0.50 CS standard deviations.

This flag is calculated with the standard error applicable to the displayed pool. It is an added communication rule, not a substitute for SEDA's own suppression criteria.

## Version-specific cautions

- SEDA suppresses long estimates based on minimum cell size and imprecision.
- Version 0.1 excludes `multi_comp_all = 1` rows. The codebook describes these as interstate units or units containing Bureau of Indian Education waiver schools. Their unadjusted within-state standard errors are unavailable, so they do not fit the primary within-state comparison design. `mart_exclusion_audit` records the affected rows, districts, years, and states rather than dropping them silently.
- Pre-2020 public long estimates include a small amount of privacy noise; the 2022–2025 public-data estimates do not receive that added noise.
- Arkansas RLA is removed where the underlying reporting was not comparable.
- SEDA 2025.2 uses estimated 2025 NAEP anchor values because official 2026 NAEP values were not yet available.
- Administrative districts include special operators that do not always correspond to a residential geographic boundary.
