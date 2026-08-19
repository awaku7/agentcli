from mermaid_excel_converter.drawingml import generate_drawing_xml
from mermaid_excel_converter.layout import layout_graph
from mermaid_excel_converter.parser import parse_mermaid


def test_drawing_contains_node_text_and_geometry():
    graph = parse_mermaid("""
    flowchart LR
        A[開始]
    """)

    xml = generate_drawing_xml(graph, layout_graph(graph))

    assert "開始" in xml
    assert 'prst="rect"' in xml
    assert "node_A" in xml


def test_drawing_contains_connector_and_arrow():
    graph = parse_mermaid("""
    flowchart LR
        A[開始] --> B[終了]
    """)

    xml = generate_drawing_xml(graph, layout_graph(graph))

    assert "edge_A_B" in xml
    assert "cxnSp" in xml
    assert "triangle" in xml
