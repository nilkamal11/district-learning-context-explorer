from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from district_context.config import database_path, project_config
from district_context.dashboard import build_dashboard
from district_context.database import build_database, connect
from district_context.qa import has_failures, run_qa
from district_context.report import build_profile
from district_context.sources import source_locations, verify_sources
from district_context.utils import normalize_district_id


def _print_sources() -> None:
    print(
        "Download each source from its official URL after reviewing the provider's data agreement:"
    )
    for item in source_locations():
        print(f"\n{item['source_id']} ({item['version']})")
        print(f"  file: {item['filename']}")
        print(f"  url:  {item['official_url']}")
    print("\nPlace the files in data/raw/seda_2025_2/. Raw data are intentionally gitignored.")


def _verify(skip_hash: bool) -> bool:
    results = verify_sources(compute_hashes=not skip_hash)
    for result in results:
        status = "PASS" if result["valid"] else "FAIL"
        size = f"{result.get('size_bytes', 0):,} bytes" if result["exists"] else "missing"
        hash_note = "hash verified" if result.get("hash_verified") else "hash not computed"
        print(f"{status:4}  {result['source_id']:<20} {size}; {hash_note}")
        for error in result.get("errors", []):
            print(f"      {error}")
    return all(result["valid"] for result in results)


def _find_district(query: str, limit: int) -> None:
    with connect(read_only=True) as connection:
        rows = connection.execute(
            """
            SELECT district_id, district_name, state_abbreviation, first_year, last_year
            FROM dim_district
            WHERE lower(district_name) LIKE '%' || lower(?) || '%'
               OR district_id = ?
            ORDER BY state_abbreviation, district_name
            LIMIT ?
            """,
            [query, query.zfill(7) if query.isdigit() else query, limit],
        ).fetchall()
    if not rows:
        print("No districts matched that search.")
        return
    print("district_id  state  district_name  years")
    for district_id, district_name, state, first_year, last_year in rows:
        print(f"{district_id}  {state:>2}     {district_name}  {first_year}-{last_year}")


def _resolve_source_id(source_id: str, year: int | None) -> None:
    normalized = normalize_district_id(source_id)
    with connect(read_only=True) as connection:
        rows = connection.execute(
            """
            SELECT source_district_id, stable_district_id, year, district_name,
                   state_abbreviation, imputed_flag, latest_virtual_flag
            FROM stg_crosswalk_admin
            WHERE source_district_id = ?
              AND (? IS NULL OR year = ?)
            ORDER BY year
            """,
            [normalized, year, year],
        ).fetchall()
    if not rows:
        suffix = f" in {year}" if year is not None else ""
        print(f"No administrative-district mapping found for {normalized}{suffix}.")
        return
    print("source_id  stable_id  year  state  imputed  virtual_flag  district_name")
    for source, stable, row_year, name, state, imputed, virtual in rows:
        imputed_label = "N/A" if imputed is None else str(imputed)
        virtual_label = "N/A" if virtual is None else str(virtual)
        print(
            f"{source}  {stable}  {row_year}  {state:>2}     "
            f"{imputed_label:>3}      {virtual_label:>3}           {name}"
        )


def _choose_demo_district(state: str, grade: int) -> str:
    cfg = project_config()
    context_year = int(cfg["analysis"]["context_year"])
    with connect(read_only=True) as connection:
        row = connection.execute(
            """
            WITH state_subject_years AS (
                SELECT year
                FROM mart_achievement
                WHERE state_abbreviation = upper(?) AND grade = ?
                GROUP BY year
                HAVING count(DISTINCT subject) = 2
            ), latest_state_year AS (
                SELECT max(year) AS year FROM state_subject_years
            ), eligible AS (
                SELECT c.*
                FROM mart_context_snapshot AS c, latest_state_year AS latest
                WHERE c.year = ?
                  AND c.state_abbreviation = upper(?)
                  AND c.has_core_peer_context
                  AND c.grade_low <= ? AND c.grade_high >= ?
                  AND EXISTS (
                      SELECT 1 FROM mart_achievement AS a
                      WHERE a.district_id = c.district_id
                        AND a.grade = ? AND a.year = latest.year AND a.subject = 'mth'
                  )
                  AND EXISTS (
                      SELECT 1 FROM mart_achievement AS a
                      WHERE a.district_id = c.district_id
                        AND a.grade = ? AND a.year = latest.year AND a.subject = 'rla'
                  )
            ), benchmark AS (
                SELECT median(ln(1 + total_enrollment_grades_3_8)) AS median_log_enrollment
                FROM eligible
            )
            SELECT district_id
            FROM eligible, benchmark
            ORDER BY abs(ln(1 + total_enrollment_grades_3_8) - median_log_enrollment), district_id
            LIMIT 1
            """,
            [state, grade, context_year, state, grade, grade, grade, grade],
        ).fetchone()
    if row is None:
        raise RuntimeError(f"No eligible demonstration district was found in {state.upper()}")
    return row[0]


def _run_profile(target_id: str, grade: int, output: str | None) -> Path:
    destination = Path(output).resolve() if output else None
    with connect() as connection:
        path = build_profile(
            connection,
            normalize_district_id(target_id),
            grade=grade,
            destination=destination,
        )
    print(f"Profile written to {path}")
    return path


def build_parser() -> argparse.ArgumentParser:
    default_grade = int(project_config()["analysis"]["default_grade"])
    parser = argparse.ArgumentParser(
        prog="district-context",
        description="Build district comparisons from SEDA 2025.2.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("sources", help="Show official source locations and required filenames")

    verify = subparsers.add_parser("verify", help="Validate local source files")
    verify.add_argument("--skip-hash", action="store_true", help="Skip SHA-256 for a faster check")

    build = subparsers.add_parser("build", help="Build the DuckDB analytical model")
    build.add_argument("--skip-hash", action="store_true", help="Skip SHA-256 for a faster build")

    subparsers.add_parser("qa", help="Run executable data-quality checks")

    find = subparsers.add_parser("find", help="Search the district catalog")
    find.add_argument("query")
    find.add_argument("--limit", type=int, default=20)

    resolve = subparsers.add_parser(
        "resolve", help="Resolve a source district ID to the stable SEDA ID"
    )
    resolve.add_argument("--source-id", required=True)
    resolve.add_argument("--year", type=int)

    profile = subparsers.add_parser("profile", help="Render one local district profile")
    profile.add_argument("--district-id", required=True)
    profile.add_argument("--grade", type=int, default=default_grade, choices=range(3, 9))
    profile.add_argument("--output")

    demo = subparsers.add_parser(
        "demo",
        help=(
            "Render a non-cherry-picked demo using the median-sized eligible district in a state"
        ),
    )
    demo.add_argument("--state", default="IL")
    demo.add_argument("--grade", type=int, default=default_grade, choices=range(3, 9))

    dashboard = subparsers.add_parser(
        "dashboard", help="Build the static district dashboard and SEDA workbench"
    )
    dashboard.add_argument("--district-id", default="1700044")
    dashboard.add_argument(
        "--grade",
        type=int,
        default=4,
        choices=(4,),
        help="Initial embedded grade; the public site currently uses grade 4",
    )
    dashboard.add_argument("--output-dir", default="site")

    run_all = subparsers.add_parser("run-all", help="Build, test, and render a profile")
    run_all.add_argument("--district-id")
    run_all.add_argument("--demo-state", default="IL")
    run_all.add_argument("--grade", type=int, default=default_grade, choices=range(3, 9))
    run_all.add_argument("--skip-hash", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "sources":
        _print_sources()
        return
    if args.command == "verify":
        raise SystemExit(0 if _verify(args.skip_hash) else 1)
    if args.command == "build":
        manifest = build_database(compute_hashes=not args.skip_hash)
        print(json.dumps(manifest["table_counts"], indent=2))
        return
    if args.command == "run-all":
        manifest = build_database(compute_hashes=not args.skip_hash)
        print(json.dumps(manifest["table_counts"], indent=2))
        with connect() as connection:
            results = run_qa(connection)
        if has_failures(results):
            raise SystemExit("QA failed; profile rendering stopped.")
        target_id = args.district_id or _choose_demo_district(args.demo_state, args.grade)
        _run_profile(target_id, args.grade, None)
        return
    if not database_path().is_file():
        raise SystemExit("Database not found. Run `district-context build` first.")
    if args.command == "qa":
        with connect() as connection:
            results = run_qa(connection)
        for row in results:
            print(f"{row['status'].upper():4}  {row['name']}")
        raise SystemExit(1 if has_failures(results) else 0)
    if args.command == "find":
        _find_district(args.query, args.limit)
        return
    if args.command == "resolve":
        _resolve_source_id(args.source_id, args.year)
        return
    if args.command == "profile":
        _run_profile(args.district_id, args.grade, args.output)
        return
    if args.command == "demo":
        target_id = _choose_demo_district(args.state, args.grade)
        print(f"Selected demonstration district {target_id} by the documented median-size rule.")
        _run_profile(target_id, args.grade, None)
        return
    if args.command == "dashboard":
        destination = Path(args.output_dir).resolve()
        with connect(read_only=True) as connection:
            page = build_dashboard(
                connection,
                grade=args.grade,
                default_district_id=normalize_district_id(args.district_id),
                destination=destination,
            )
        print(f"Dashboard data written for {page}")
        return
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main(sys.argv[1:])
