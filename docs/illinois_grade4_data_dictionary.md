# Illinois Grade 4 analytical extract

The local build writes `data/processed/illinois_grade4_school_year.csv`. Raw and processed data are intentionally excluded from Git.

It also writes `data/processed/illinois_school_roster.csv`, one row per Report Card year
and RCDTS from the `General` sheet. The roster is intentionally separate from assessment
results so schools that do not serve Grade 4 remain visible instead of disappearing.

| Column | Meaning |
|---|---|
| `report_card_year` | Illinois Report Card release year |
| `rcdts` | Canonical 15-character RCDTS with separators removed; letters are preserved |
| `rcdts_formatted` | Canonical display form `RR-CCC-DDDD-TT-SSSS` |
| `rcdts_source` | Identifier exactly as stored in that year's workbook |
| `school_name`, `district_name` | Annual source labels; not assumed to be stable identifiers |
| `grade` | Fixed at 4 in this release |
| `subject` | `ela` or `math` |
| `proficiency_rate` | Published or reproducibly derived Grade 4 proficiency percentage |
| `proficiency_status` | `reported`, `suppressed`, `missing`, or `invalid` |
| `proficiency_metric_version` | Identifies the pre-2025 five-level definition or 2025 four-level definition |
| `participation_rate` | Published Grade 4 participation percentage; currently available in the 2025 layout |
| `participation_status` | Includes `not_published` when the annual file lacks the metric at this grain |
| `growth_percentile` | Published Grade 4 mean Student Growth Percentile; currently available in the 2025 layout |
| `growth_status` | Includes `not_published` for 2022–2024 rather than treating those cells as ordinary missing data |
| `school_enrollment` | Total school enrollment |
| `grade4_enrollment` | Grade 4 enrollment where published |
| `pct_iep`, `pct_el`, `pct_low_income` | School context percentages |
| `mobility_rate` | School-level student mobility rate |
| `chronic_absenteeism_rate` | School-level chronic absenteeism rate |
| `chronic_absenteeism_grade4_rate` | Grade 4 chronic absenteeism rate where published |
| `*_status` | Field-specific missingness or suppression state for contextual metrics |
| `source_file`, `source_sheet` | Data-lineage fields |

Percentages are stored on a 0–100 scale. Suppressed values are null numerically and remain explicitly labeled as `suppressed`.

The current dashboard uses the latest roster record for each RCDTS and flags whether that
school has any Grade 4 assessment results in the analytical extract.
