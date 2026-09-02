# Data lineage

| Layer | Object | Purpose |
|---|---|---|
| Raw | `seda_admindist_long_cs_2025.2.csv` | Released district achievement estimates |
| Raw | `seda_cov_admindist_annual_2025.2.csv` | District demographic and socioeconomic context |
| Raw | `seda_crosswalk_2025.2.csv` | Source IDs to stable SEDA IDs |
| Contract | `source_inventory.json` | Size, header, SHA-256, version, and verification time |
| Staging | `stg_achievement` | Narrow typed score table with normalized IDs |
| Staging | `stg_context` | Typed context fields and numeric grade span |
| Staging | `stg_crosswalk_admin` | Administrative district rows with raw and stable IDs |
| Dimension | `dim_district` | One row per stable district ID |
| Mart | `mart_context_snapshot` | Peer features, locale, grade span, and completeness flags |
| Mart | `mart_achievement` | In-scope released outcomes, labels, periods, and base precision flag |
| Mart | `mart_data_coverage` | State, year, grade, and subject coverage audit |
| Mart | `mart_crosswalk_audit` | Year and state mapping counts, stable-ID changes, and flag availability |
| Mart | `mart_exclusion_audit` | Counts and scope of intentionally excluded multi-component units |
| Python | peer membership | Fixed context-only same-state and national peer sets |
| Output | local HTML profile | Aggregated, uncertainty-aware district comparison |

All source rows and local analytical databases remain outside Git. The build manifest records source hashes, SQL model order, row counts, timestamps, QA status, and the Git commit when available. SHA-256 values are project-computed fingerprints of the retrieved files, not provider-issued checksums. A skipped hash is stored as unverified rather than being presented as observed.

The analytical source files already use stable `sedaadmin` identifiers. The crosswalk is therefore not reapplied to those rows. It supports an explicit source-ID resolver and an audit mart for year-specific ID changes. Its administrative-district rows cover 2022 through 2025, not the earlier achievement years.

CSV parsing is explicit about commas, quotes, and escapes. This matters because most rows do not quote the district name, while names containing commas do. Automatic dialect detection can therefore appear correct on a sample and fail deep into the file.

Database builds run against a fresh temporary DuckDB file. QA must complete without errors before the new file replaces the prior database, so a failed refresh cannot leave a partially rebuilt analytical store.
