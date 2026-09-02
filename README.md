# District Learning Context Explorer

A reproducible, uncertainty-aware way to ask a practical education question:

> How do a district's math and reading estimates compare with districts that are similar on selected public context measures, and how has that pattern changed over time?

The first view focuses on grade 4 because that is where the question became personally meaningful to me as the parent of a fourth-grade daughter. The analytical design covers grades 3 through 8 and keeps the selected district configurable. No family, child, school, or home-district information is stored in the repository.

## What this project demonstrates

- Python orchestration, feature engineering, peer selection, uncertainty calculations, and report generation
- SQL staging, type normalization, dimensional modeling, analytical marts, and quality-control queries
- Large-file ingestion from a 1.03 GB district achievement file
- Stable identifier handling, including seven-character IDs, crosswalk audits, and source-to-stable ID resolution
- Reproducible source manifests, SHA-256 checks, deterministic peer selection, and Git-based CI
- Clear translation from statistical estimates to a district and parent-facing explanation
- Responsible handling of suppression, missingness, measurement error, and limits on causal inference

The project is intentionally not a district ranking. Peers are selected from community context only. Achievement never enters the matching algorithm.

## Design at a glance

```mermaid
flowchart LR
    A[SEDA 2025.2 raw files\nkept local] --> B[Python source contracts\nhash + schema]
    B --> C[DuckDB SQL staging\ntypes + stable IDs]
    C --> D[Context and achievement marts]
    D --> E[Python peer model\nfixed context-only peers]
    E --> F[Uncertainty-aware comparison]
    F --> G[Local interactive HTML profile]
    D --> H[Executable QA checks]
    H --> G
```

DuckDB keeps the demonstration fast and free to reproduce locally. The layered SQL models avoid database-specific procedural code, so the same pattern can move to PostgreSQL, Snowflake, Redshift, or another analytical warehouse.

## Data

Version 0.1 uses three files from the [Stanford Education Data Archive 2025.2 release](https://edopportunity.org/trends/data/downloads/):

1. Administrative district achievement estimates on the Cohort Standardized (CS) scale, long by grade, subject, and year
2. Annual administrative district covariates, with 2024 frozen as the peer-context snapshot
3. The SEDA administrative district identifier crosswalk, used to audit ID changes and resolve external year-specific IDs to the already-stable `sedaadmin` identifier used in the analytical files

The achievement file covers spring 2009 through 2019 and 2022 through 2025. There are no 2020 or 2021 achievement records, so the report shows a visible break instead of drawing a continuous line across those years.

Source files are governed by Stanford's [Data Use Agreement](https://edopportunity.org/trends/data/). They are not included in this repository. The current agreement limits the datasets to permitted noncommercial use and says data files may not be published in full or in part without explicit permission. Because an employment portfolio may implicate those terms, keep all real-data reports and extracts local unless Stanford confirms the intended use in writing. This code-only repository does not grant data rights.

## Quick start

Python 3.11 or newer is required.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"

district-context sources
district-context verify
district-context build
district-context qa
district-context find "district name"
district-context resolve --source-id 0123456 --year 2024
district-context profile --district-id 0123456 --grade 4
```

The administrative crosswalk in this release covers 2022 through 2025, so `resolve` does not imply historical source-ID coverage for 2009 through 2019.

For a neutral smoke test, the demo command chooses the eligible district nearest the state's median grades 3–8 enrollment. It does not choose a district based on achievement.

```powershell
district-context demo --state IL --grade 4
```

Local outputs are written to `data/output/` and are ignored by Git. The HTML profile embeds its chart library once so the local demonstration works without an internet connection. Run `python scripts/check_no_restricted_data.py` before every commit. The public [validation snapshot](reports/validation_snapshot.md) records only aggregate build and QA evidence, never district rows or peer membership.

The supported setup is a cloned repository with the editable install shown above. A standalone wheel is not currently a supported execution mode because the versioned SQL and configuration live at the repository root.

## Peer definition

The primary reference is up to 15 same-state districts. Matching uses four equally weighted domains:

| Domain | Inputs |
|---|---|
| District scale | Log enrollment in grades 3–8 |
| Economic context | Family poverty rate and SEDA socioeconomic status composite |
| Student composition | Race and ethnicity share vector |
| Place | City, suburb, town, and rural share vector |

Numeric differences use robust 5th-to-95th percentile ranges. Composition vectors use Hellinger distance. Matching begins with the same grade-span and locale category, enrollment within a factor of four, and poverty within 15 percentage points. If fewer than ten in-state candidates remain, the relaxation is recorded rather than hidden. A separate national analog panel excludes the target state, uses cross-state adjusted standard errors, and caps the number of peers from any one state. The report exposes domain-level distances rather than calling a peer set “strong” based on count alone.

The SEDA annual file's recent English learner and special education fields are constant at zero across districts, so version 0.1 excludes them from matching and tests match features for real variation. Treating a populated field as informative without checking its distribution would create false sophistication.

See [methodology.md](docs/methodology.md) for the full specification.

## Interpretation rules

- Math and reading are always separate.
- CS values are comparable across places and years only within a fixed grade and subject.
- Annual grade 4 results are repeated district cross-sections, not growth for the same students.
- Missing and suppressed values never become zero.
- Same-state comparisons use SEDA's unadjusted standard error. Cross-state comparisons use its adjusted standard error.
- A comparison requires at least 10 reporting peers and at least 70% coverage of the selected set in that year and subject.
- National analog comparisons remain descriptive because state-level linking errors may be correlated.
- The report says “higher,” “lower,” or “not clearly different,” not “better,” “worse,” or “top ranked.”
- Results are associations and descriptive comparisons, not causal estimates.

## Repository map

```text
config/                    Versioned source and model specifications
sql/models/                Ordered SQL staging, dimension, and mart models
src/district_context/      Pipeline, matching, QA, CLI, and reporting code
tests/                     Test-only software fixtures and contract tests
docs/                      Research specification, methods, lineage, and limits
reports/                   Public documentation and QA catalog, never raw rows
data/raw/                  Local source files, ignored by Git
data/processed/            Local DuckDB database, ignored by Git
data/output/               Local reports and manifests, ignored by Git
```

## Role-relevant evidence

| Work in the role | Evidence here |
|---|---|
| Work with large assessment data | Grade-by-district-by-subject-by-year SEDA fact table |
| Extract, clean, and link data | Python source contracts, SQL staging, crosswalk audit mart and ID resolver |
| Build reproducible pipelines | One CLI, versioned model config, source hashes, ordered models, build manifest |
| Validate and troubleshoot | Grain tests, range checks, suppression rules, QA result table |
| Support research specifications | Versioned peer algorithm and explicit interpretation rules |
| Communicate to varied audiences | Interactive profile plus plain-language evidence limits |
| Use SQL and Python together | DuckDB transformations plus Python analytics and rendering |
| Collaborate in Git | Small modules, automated tests, linting, and restricted-data guard |

Product-event analysis is not claimed in version 0.1. A later module can add a separate public event-log dataset without inventing usage records or mixing product telemetry into an assessment study.

## Citation

Reardon, S. F., Fahle, E. M., Ho, A. D., Shear, B. R., Saliba, J., Min, J., Shim, J., & Kalogrides, D. (2026). *Stanford Education Data Archive (Version SEDA 2025.2).* https://doi.org/10.25740/np279jm6134

The code is MIT licensed. Third-party data and documentation are excluded from that license. This project is independent and is not endorsed by Stanford, HMH, or NWEA.
