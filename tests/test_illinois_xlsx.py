from zipfile import ZIP_DEFLATED, ZipFile

from district_context.illinois_xlsx import XlsxReader, _column_index


def _write_minimal_workbook(path):
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
              xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
              <sheets><sheet name="Data" sheetId="1" r:id="rId1"/></sheets>
            </workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
              <Relationship Id="rId1" Target="worksheets/sheet1.xml"
                Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>
            </Relationships>""",
        )
        archive.writestr(
            "xl/sharedStrings.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
              count="4" uniqueCount="4">
              <si><t>RCDTS</t></si><si><t>Value</t></si><si><t>01-001</t></si><si><t>*</t></si>
            </sst>""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
              <sheetData>
                <row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>
                <row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2"><v>51.5</v></c></row>
                <row r="3"><c r="A3" t="inlineStr"><is><t>02-002</t></is></c>
                  <c r="B3" t="s"><v>3</v></c></row>
              </sheetData>
            </worksheet>""",
        )


def test_column_index_supports_wide_report_card_columns():
    assert _column_index("A1") == 0
    assert _column_index("Z1") == 25
    assert _column_index("AA1") == 26
    assert _column_index("UY1") == 570


def test_reader_loads_only_requested_columns(tmp_path):
    path = tmp_path / "fixture.xlsx"
    _write_minimal_workbook(path)
    with XlsxReader(path) as workbook:
        assert workbook.sheet_names == ["Data"]
        assert workbook.header("Data") == ["RCDTS", "Value"]
        assert list(workbook.records("Data", ["RCDTS", "Value"])) == [
            {"RCDTS": "01-001", "Value": 51.5},
            {"RCDTS": "02-002", "Value": "*"},
        ]
