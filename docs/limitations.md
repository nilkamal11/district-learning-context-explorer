# Limitations and responsible use

1. SEDA values are modeled aggregate estimates built from state proficiency counts and NAEP linking. They are not individual scores.
2. Yearly grade-specific results are repeated cross-sections. They do not follow the same students over time.
3. Context matching is descriptive. Unmeasured differences remain and no causal interpretation is warranted.
4. The administrative-district universe includes charter, virtual, state-agency, and other specialized operators. A later CCD extension should make agency type an explicit filter.
5. Public data suppression is not random. Small districts and student groups can have less complete histories.
6. The 2009–2019 and 2022–2025 source periods differ in source collection and privacy-noise treatment.
7. SEDA's 2025 estimates use estimated NAEP anchor values. A 2024-endpoint sensitivity view is appropriate for high-stakes conclusions.
8. The profile does not evaluate instructional quality, curricula, teachers, schools, or individual students.
9. A good district-level comparison should begin a question, not end one. Local evidence and qualitative context still matter.
10. The fixed 2024 peers may not have been equally similar to the target in earlier years.
11. Stanford confirmed that this project owner's Git portfolio use is permitted. Raw inputs, the local DuckDB database, and unrestricted working outputs remain local; only selected derived fields needed by the public dashboard and workbench are published.
12. The workbench is not the complete SEDA 2025.2 file library. It covers administrative districts, all students, the Cohort Standardized scale, grades 3–8, and math and reading. It does not expose schools, geographic districts, subgroups, learning-rate parameters, or other scales.
13. The 2025 endpoint has fewer reporting districts than many earlier years, and state availability varies. The workbench defaults each state and subject to its latest available display year instead of treating an absent 2025 record as zero.
