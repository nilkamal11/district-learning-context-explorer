# Analytical data dictionary

## Identifiers and grain

| Field | Meaning |
|---|---|
| `district_id` | Stable seven-character SEDA administrative district ID |
| `source_district_id` | Seven-character district ID before mapping through the SEDA crosswalk |
| `subject` | `mth` or `rla` |
| `grade` | Tested grade, 3 through 8 |
| `year` | Spring of the tested school year |

`mart_achievement` must be unique at district, subject, grade, and year. `stg_context` must be unique at district and year.

## Achievement

| Field | Meaning |
|---|---|
| `achievement_cs` | Released all-student CS achievement estimate |
| `standard_error_within_state` | Standard error for within-state comparison |
| `standard_error_cross_state` | Adjusted standard error for cross-state comparison |
| `tested_count` | Number of assessments represented |
| `tested_count_estimated_flag` | 1 when the test count, not the score, was estimated |
| `multi_component_flag` | 1 for a unit drawing on more than one assessment component |
| `low_precision_flag` | Base within-state communication flag in the mart; the report recalculates it with the standard error for the displayed pool |

## Peer context

| Field | Meaning |
|---|---|
| `enrollment_grades_3_8` | CCD enrollment in grades 3 through 8 |
| `family_poverty_rate` | ACS-based, empirical-Bayes family poverty rate |
| `socioeconomic_status_composite` | SEDA empirical-Bayes composite of family socioeconomic conditions |
| `share_*` | Proportion from 0 to 1, despite source labels sometimes saying percent |
| `dominant_locale` | Released SEDA `urbanicity` category used for the hard match caliper |
| `share_argmax_locale` | Audit category based on the largest city, suburb, town, or rural share |
| `grade_span_bucket` | Broad operational grouping for peer eligibility |
| `context_distance` | Weighted contextual dissimilarity; smaller is more similar |

Context distance is not a performance score and must not be described as a ranking.

`source_perell` and `source_perspeced` retain the released fields for source audit only. Recent rows are constant at zero, while historical values do not consistently behave like 0-to-1 proportions. The project therefore does not label them as shares, validate them under the blanket proportion rule, or use them in matching.
