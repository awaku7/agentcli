from zipfile import ZipFile

from mermaid_excel_converter.drawingml import generate_drawing_xml
from mermaid_excel_converter.layout import layout_graph
from mermaid_excel_converter.parser import parse_mermaid
from mermaid_excel_converter.xlsx import write_xlsx


def test_write_xlsx_contains_drawing(tmp_path):
    graph = parse_mermaid("""
    flowchart LR
        A[開始]
    """)
    drawing_xml = generate_drawing_xml(graph, layout_graph(graph))
    output = tmp_path / "diagram.xlsx"

    write_xlsx(output, drawing_xml)

    with ZipFile(output) as archive:
        names = set(archive.namelist())
        assert "xl/drawings/drawing1.xml" in names
        assert "xl/worksheets/sheet1.xml" in names
        assert "開始" in archive.read("xl/drawings/drawing1.xml").decode("utf-8")
