from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "site" / "data" / "dashboard-data.js"
PREFIX = "window.DISTRICT_DASHBOARD_DATA="
SUFFIX = ";\n"


def main() -> None:
    required = [
        ROOT / "site" / "index.html",
        ROOT / "site" / "assets" / "styles.css",
        ROOT / "site" / "assets" / "dashboard.js",
        ROOT / "site" / "assets" / "plotly-3.1.0.min.js",
        DATA_PATH,
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise SystemExit(f"Public dashboard files are missing: {', '.join(missing)}")

    script = DATA_PATH.read_text(encoding="utf-8")
    if not script.startswith(PREFIX) or not script.endswith(SUFFIX):
        raise SystemExit("Dashboard data does not use the expected inert assignment wrapper")
    if DATA_PATH.stat().st_size >= 95_000_000:
        raise SystemExit("Dashboard bundle is too close to GitHub's per-file size limit")
    forbidden = (
        "C:\\\\Users\\\\",
        "source_row_hash",
        "seda_admindist_long_cs_2025.2.csv",
        "seda_cov_admindist_annual_2025.2.csv",
        "seda_crosswalk_2025.2.csv",
    )
    exposed = [marker for marker in forbidden if marker in script]
    if exposed:
        raise SystemExit(f"Dashboard bundle contains forbidden local/source detail: {exposed}")

    payload = json.loads(script[len(PREFIX) : -len(SUFFIX)])
    if payload.get("schema_version") != 1:
        raise SystemExit("Dashboard data schema version is not supported")
    technical = payload["technical"]
    expected_counts = {
        "published_catalog_rows": len(payload["catalog"]),
        "published_context_rows": len(payload["context"]),
        "published_achievement_rows": len(payload["achievement"]),
    }
    mismatches = {
        name: (technical.get(name), expected)
        for name, expected in expected_counts.items()
        if technical.get(name) != expected
    }
    if mismatches:
        raise SystemExit(f"Dashboard metadata counts do not match its arrays: {mismatches}")
    district_index = payload["catalog_fields"].index("district_id")
    if payload["default_district_id"] not in {
        row[district_index] for row in payload["catalog"]
    }:
        raise SystemExit("Default district is absent from the dashboard catalog")
    if not all(source["hash_verified"] for source in technical["sources"]):
        raise SystemExit("Dashboard claims a build whose source hashes were not verified")
    print(
        "PASS: public dashboard bundle is present, internally consistent, and free of "
        "raw filenames or local paths"
    )


if __name__ == "__main__":
    main()
