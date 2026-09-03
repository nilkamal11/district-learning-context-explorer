from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from district_context.illinois_xlsx import XlsxReader

DEFAULT_PATTERN = (
    r"RCDTS|^Level$|School Name|^District$|Enrollment.*Grade 4|Mobility Rate$|"
    r"Chronic Absenteeism(?:$| - Grade 4$)|Student Enrollment - (?:IEP|EL|Low Income)$|"
    r"(?:ELA|Math).*(?:Proficiency|Participation|Growth Percentile).*Grade 4.*(?:Total)?$"
)


def inspect_workbook(path: Path, pattern: str, *, all_sheets: bool = False) -> dict[str, object]:
    matcher = re.compile(pattern, re.IGNORECASE)
    with XlsxReader(path) as workbook:
        sheets: dict[str, list[str]] = {}
        for sheet_name in workbook.sheet_names:
            if not all_sheets and sheet_name not in {"General", "General (2)", "IAR", "IAR (2)"}:
                continue
            matches = [column for column in workbook.header(sheet_name) if matcher.search(column)]
            if matches:
                sheets[sheet_name] = matches
        return {"file": path.name, "sheet_names": workbook.sheet_names, "matched_columns": sheets}


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect Illinois Report Card XLSX schemas")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--pattern", default=DEFAULT_PATTERN)
    parser.add_argument("--all-sheets", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = [
        inspect_workbook(path, args.pattern, all_sheets=args.all_sheets) for path in args.files
    ]
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
