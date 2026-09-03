from __future__ import annotations

import argparse
import json

from district_context.illinois_database import build_illinois_database

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the Illinois Grade 4 DuckDB marts.")
    parser.add_argument("--rebuild-extract", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build_illinois_database(rebuild_extract=args.rebuild_extract), indent=2))
