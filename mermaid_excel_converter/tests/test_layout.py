from mermaid_excel_converter.layout import layout_graph
from mermaid_excel_converter.parser import parse_mermaid


def test_layout_lr_places_nodes_from_left_to_right():
    graph = parse_mermaid("""
    flowchart LR
        A[開始] --> B[終了]
    """)

    positions = layout_graph(graph)

    assert positions["A"].x < positions["B"].x
    assert positions["A"].y == positions["B"].y


def test_layout_td_places_nodes_from_top_to_bottom():
    graph = parse_mermaid("""
    flowchart TD
        A[開始] --> B[終了]
    """)

    positions = layout_graph(graph)

    assert positions["A"].y < positions["B"].y
    assert positions["A"].x == positions["B"].x
