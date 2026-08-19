from html import escape
from xml.etree.ElementTree import Element, SubElement, tostring, register_namespace

from .layout import Position
from .model import Graph

XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"

register_namespace("xdr", XDR)
register_namespace("a", A)


def _tag(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}"


def _marker(parent: Element, name: str, col: int, row: int) -> None:
    marker = SubElement(parent, _tag(XDR, name))
    SubElement(marker, _tag(XDR, "col")).text = str(col)
    SubElement(marker, _tag(XDR, "colOff")).text = "0"
    SubElement(marker, _tag(XDR, "row")).text = str(row)
    SubElement(marker, _tag(XDR, "rowOff")).text = "0"


def _shape_type(shape: str) -> str:
    return {
        "rect": "rect",
        "diamond": "diamond",
        "ellipse": "ellipse",
    }.get(shape, "rect")


def _add_text(parent: Element, text: str) -> None:
    tx_body = SubElement(parent, _tag(XDR, "txBody"))
    SubElement(tx_body, _tag(A, "bodyPr"))
    SubElement(tx_body, _tag(A, "lstStyle"))
    for line in text.splitlines() or [""]:
        paragraph = SubElement(tx_body, _tag(A, "p"))
        run = SubElement(paragraph, _tag(A, "r"))
        SubElement(run, _tag(A, "rPr"), lang="ja-JP")
        SubElement(run, _tag(A, "t")).text = line


def _add_shape(root: Element, node_id: str, text: str, shape: str, pos: Position, index: int) -> None:
    anchor = SubElement(root, _tag(XDR, "twoCellAnchor"))
    _marker(anchor, "from", round(pos.x / 64), round(pos.y / 20))
    _marker(anchor, "to", round((pos.x + pos.width) / 64), round((pos.y + pos.height) / 20))

    sp = SubElement(anchor, _tag(XDR, "sp"))
    nv = SubElement(sp, _tag(XDR, "nvSpPr"))
    SubElement(nv, _tag(XDR, "cNvPr"), id=str(index), name=f"node_{node_id}")
    SubElement(nv, _tag(XDR, "cNvSpPr"))

    sp_pr = SubElement(sp, _tag(XDR, "spPr"))
    geom = SubElement(sp_pr, _tag(A, "prstGeom"), prst=_shape_type(shape))
    SubElement(geom, _tag(A, "avLst"))
    fill = SubElement(sp_pr, _tag(A, "solidFill"))
    SubElement(fill, _tag(A, "srgbClr"), val="E8F1FF")
    _add_text(sp, text)
    SubElement(anchor, _tag(XDR, "clientData"))


def _add_connector(root: Element, edge_index: int, source: Position, target: Position, name: str) -> None:
    anchor = SubElement(root, _tag(XDR, "twoCellAnchor"))
    _marker(anchor, "from", round((source.x + source.width / 2) / 64), round((source.y + source.height) / 20))
    _marker(anchor, "to", round((target.x + target.width / 2) / 64), round(target.y / 20))

    # Use a regular line shape rather than xdr:cxnSp.  This remains
    # editable in Excel while avoiding connector-specific repair issues.
    connector = SubElement(anchor, _tag(XDR, "sp"))
    nv = SubElement(connector, _tag(XDR, "nvSpPr"))
    SubElement(nv, _tag(XDR, "cNvPr"), id=str(edge_index), name=name)
    SubElement(nv, _tag(XDR, "cNvSpPr"))

    sp_pr = SubElement(connector, _tag(XDR, "spPr"))
    sx = source.x + source.width / 2
    sy = source.y + source.height
    tx = target.x + target.width / 2
    ty = target.y
    xfrm = SubElement(sp_pr, _tag(A, "xfrm"))
    SubElement(xfrm, _tag(A, "off"), x=str(round(min(sx, tx) * 12700)), y=str(round(min(sy, ty) * 12700)))
    SubElement(xfrm, _tag(A, "ext"), cx=str(max(1, round(abs(tx - sx) * 12700))), cy=str(max(1, round(abs(ty - sy) * 12700))))
    geom = SubElement(sp_pr, _tag(A, "prstGeom"), prst="line")
    SubElement(geom, _tag(A, "avLst"))
    line = SubElement(sp_pr, _tag(A, "ln"), w="12700")
    solid = SubElement(line, _tag(A, "solidFill"))
    SubElement(solid, _tag(A, "srgbClr"), val="4472C4")
    SubElement(line, _tag(A, "tailEnd"), type="triangle")
    SubElement(anchor, _tag(XDR, "clientData"))


def generate_drawing_xml(graph: Graph, positions: dict[str, Position]) -> str:
    root = Element(_tag(XDR, "wsDr"))
    index = 1

    for node_id, node in graph.nodes.items():
        _add_shape(root, node_id, node.text, node.shape, positions[node_id], index)
        index += 1

    for edge in graph.edges:
        _add_connector(
            root,
            index,
            positions[edge.source],
            positions[edge.target],
            f"edge_{edge.source}_{edge.target}",
        )
        index += 1

    return tostring(root, encoding="unicode")
