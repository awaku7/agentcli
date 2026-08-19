from mermaid_excel_converter.parser import parse_mermaid


def test_parse_rectangle_node():
    graph = parse_mermaid("""
    flowchart LR
        A[開始]
    """)

    assert graph.direction == "LR"
    assert graph.nodes["A"].text == "開始"
    assert graph.nodes["A"].shape == "rect"


def test_parse_diamond_and_edges():
    graph = parse_mermaid("""
    flowchart TD
        A[開始] --> B{確認}
        B -->|Yes| C[処理]
    """)

    assert graph.direction == "TD"
    assert graph.nodes["B"].shape == "diamond"
    assert graph.edges[0].source == "A"
    assert graph.edges[0].target == "B"
    assert graph.edges[1].label == "Yes"
