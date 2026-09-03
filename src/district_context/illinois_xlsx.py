from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def _column_index(cell_reference: str) -> int:
    letters = "".join(character for character in cell_reference if character.isalpha())
    result = 0
    for character in letters.upper():
        result = result * 26 + ord(character) - ord("A") + 1
    return result - 1


def _relationship_target(target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return str(PurePosixPath("xl") / target)


class XlsxReader:
    """Small, read-only XLSX reader optimized for selected columns in wide sheets."""

    def __init__(self, path: Path):
        self.path = path
        self._archive: ZipFile | None = None
        self._sheet_paths: dict[str, str] = {}
        self._shared_strings: list[str] = []

    def __enter__(self) -> XlsxReader:
        self._archive = ZipFile(self.path)
        self._sheet_paths = self._load_sheet_paths()
        self._shared_strings = self._load_shared_strings()
        return self

    def __exit__(self, *_: object) -> None:
        if self._archive is not None:
            self._archive.close()
        self._archive = None

    @property
    def sheet_names(self) -> list[str]:
        return list(self._sheet_paths)

    def _require_archive(self) -> ZipFile:
        if self._archive is None:
            raise RuntimeError("XlsxReader must be used as a context manager")
        return self._archive

    def _load_sheet_paths(self) -> dict[str, str]:
        archive = self._require_archive()
        workbook = ET.parse(archive.open("xl/workbook.xml"))
        relationships = ET.parse(archive.open("xl/_rels/workbook.xml.rels"))
        targets = {
            relationship.attrib["Id"]: _relationship_target(relationship.attrib["Target"])
            for relationship in relationships.findall(f"{{{PACKAGE_REL_NS}}}Relationship")
        }
        return {
            sheet.attrib["name"]: targets[sheet.attrib[f"{{{REL_NS}}}id"]]
            for sheet in workbook.findall(f".//{{{MAIN_NS}}}sheet")
        }

    def _load_shared_strings(self) -> list[str]:
        archive = self._require_archive()
        if "xl/sharedStrings.xml" not in archive.namelist():
            return []
        strings: list[str] = []
        with archive.open("xl/sharedStrings.xml") as stream:
            for _event, element in ET.iterparse(stream, events=("end",)):
                if element.tag == f"{{{MAIN_NS}}}si":
                    strings.append(
                        "".join(node.text or "" for node in element.iterfind(f".//{{{MAIN_NS}}}t"))
                    )
                    element.clear()
        return strings

    def _cell_value(self, cell: ET.Element) -> Any:
        cell_type = cell.attrib.get("t")
        if cell_type == "inlineStr":
            return "".join(node.text or "" for node in cell.iterfind(f".//{{{MAIN_NS}}}t"))
        value_node = cell.find(f"{{{MAIN_NS}}}v")
        if value_node is None or value_node.text is None:
            return None
        raw = value_node.text
        if cell_type == "s":
            return self._shared_strings[int(raw)]
        if cell_type in {"str", "e"}:
            return raw
        try:
            return float(raw) if any(character in raw for character in ".eE") else int(raw)
        except ValueError:
            return raw

    def _rows(self, sheet_name: str) -> Iterator[dict[int, Any]]:
        archive = self._require_archive()
        if sheet_name not in self._sheet_paths:
            raise KeyError(f"Worksheet not found: {sheet_name}")
        with archive.open(self._sheet_paths[sheet_name]) as stream:
            for _event, element in ET.iterparse(stream, events=("end",)):
                if element.tag != f"{{{MAIN_NS}}}row":
                    continue
                values: dict[int, Any] = {}
                for cell in element.findall(f"{{{MAIN_NS}}}c"):
                    reference = cell.attrib.get("r", "")
                    values[_column_index(reference)] = self._cell_value(cell)
                yield values
                element.clear()

    def header(self, sheet_name: str) -> list[str]:
        first_row = next(self._rows(sheet_name), {})
        if not first_row:
            return []
        width = max(first_row) + 1
        return [str(first_row.get(index) or "").strip() for index in range(width)]

    def records(self, sheet_name: str, columns: Sequence[str]) -> Iterator[dict[str, Any]]:
        rows = self._rows(sheet_name)
        first_row = next(rows, {})
        headers = {str(value or "").strip(): index for index, value in first_row.items()}
        missing = [column for column in columns if column not in headers]
        if missing:
            raise ValueError(f"Missing columns in {sheet_name}: {', '.join(missing)}")
        selected = {headers[column]: column for column in columns}
        for row in rows:
            yield {name: row.get(index) for index, name in selected.items()}
