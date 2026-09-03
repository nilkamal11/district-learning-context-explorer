# Six-minute interview walkthrough

## 1. Start with the question

“I wanted to build something that begins with a real decision-maker question, not a tool demonstration. As the parent of a fourth-grade daughter, I found myself asking how to interpret a district result fairly. A state average alone does not tell me whether the comparison is contextually meaningful.”

## 2. Explain the data problem

“I used the publicly accessible, DUA-governed SEDA 2025.2 release rather than making up student data. The primary file is just over one gigabyte and contains district, subject, grade, and year estimates. The analytical files already use stable seven-character SEDA IDs, so I use the crosswalk for source-ID resolution and change audits rather than remapping those rows. I keep suppressed values missing and fingerprint every retrieved input.”

## 3. Show the technical path

“Python handles orchestration, the peer algorithm, uncertainty propagation, and report generation. SQL does the large-file staging, typing, dimensional model, coverage checks, and crosswalk audit. Each refresh builds a fresh DuckDB database and runs QA before replacing the prior version. The repository also has source contracts, deterministic matching, tests, linting, CI, and a build manifest.”

## 4. Explain the analytical choice

“Peers are matched on four context domains with equal domain weights. An explicit allowlist prevents outcome columns from entering matching, because using achievement would make the later comparison circular. I found that two seemingly useful recent fields were constant at zero, so I excluded them and added variation tests. Same-state and cross-state peers stay separate, yearly comparisons need enough reporting peers, and the national panel remains descriptive because linking errors may be correlated.”

## 5. End with judgment

“The strongest part of the project is the interpretation boundary. It does not rank districts, measure a child, or claim causes. It shows what the data support, what they do not support, and exactly how each number was produced.”

## 6. Show the research-support extension

“The Research Extensions page shows the work between a question and a model. The example asks whether changes in instructional spending per student are associated with later changes in fourth-grade math. SEDA cannot answer that alone, so I specify a year-aware join to federal finance, enrollment, staffing, and inflation data. Before modeling, I would align fiscal and outcome years, audit changing district IDs, normalize spending, preserve missingness, carry uncertainty, and agree on the sensitivity checks. The researcher receives an analysis-ready file, the join and coverage audits, reproducible SQL and Python, and a plain-language interpretation memo. I am demonstrating the data engineering and analytical judgment behind research support, not presenting a result I did not calculate.”

## Two useful debugging stories

**A sample passed but the full file failed.** DuckDB's CSV autodetection saw mostly unquoted names, then failed more than one million rows into the file on a quoted district name containing a comma. I reproduced the failure and made delimiter, quote, escape, and string typing explicit. The lesson was to validate the full extraction path, not just a convenient sample.

**Populated columns were not informative.** Recent English learner and special education fields were present but constant at zero. I removed them from matching and added distribution checks. The lesson was that schema presence is not the same as analytical signal.

## Likely follow-up questions

**Why DuckDB instead of a cloud warehouse?**

It makes a large, publicly accessible research dataset reproducible without warehouse credentials or cost while respecting its DUA. The SQL is layered and portable, so production deployment can map raw storage to object storage, models to a warehouse, orchestration to the team's scheduler, and the manifest to its catalog.

**Why CS rather than a grade-equivalent scale?**

SEDA recommends CS or YS for research. CS avoids extra vertical-linking assumptions. The cost is that I must keep grades and subjects separate, which the report enforces.

**What would you add first in production?**

CCD agency type and status, SAIPE poverty as a sensitivity measure, stronger crosswalk quarantine rules, access controls, incremental builds, monitoring, and review with a quantitative researcher. I would retain the provider's portfolio-use confirmation with the project record and seek updated guidance before materially expanding the published data scope.

**What does this not demonstrate?**

It does not claim access to internal product-event data or completed product-efficacy findings. The Research Extensions page shows how I would specify that work using governed licenses, rosters, implementation dates, product events, and outcomes, while keeping the public portfolio’s evidence boundary clear.
