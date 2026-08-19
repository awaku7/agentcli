from xml.etree.ElementTree import Element, SubElement, tostring, register_namespace

from .layout import Position
from .model import Graph

"""Generate Excel DrawingML for editable Mermaid flowcharts.

Excel-specific constraints learned from repair-log comparisons:

* ``twoCellAnchor`` markers must be normalized from top-left to bottom-right,
  even when an edge logically travels from right to left.
* Shape IDs start at 2 and carry the Office 2014 ``creationId`` extension.
* Empty text paragraphs use ``a:endParaRPr`` rather than an empty run.
* Lines are emitted as regular ``xdr:sp`` shapes instead of ``xdr:cxnSp``;
  this is more tolerant of Excel's repair rules while remaining editable.
"""

XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
A16 = "http://schemas.microsoft.com/office/drawing/2014/main"

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


def _add_creation_id(parent: Element, shape_id: int) -> None:
    ext_lst = SubElement(parent, _tag(A, "extLst"))
    ext = SubElement(
        ext_lst,
        _tag(A, "ext"),
        uri="{FF2B5EF4-FFF2-40B4-BE49-F238E27FC236}",
    )
    creation = SubElement(ext, _tag(A16, "creationId"))
    creation.set("id", f"{{00000000-0008-0000-0000-{shape_id:06d}000000}}")


def _add_text(parent: Element, text: str) -> None:
    tx_body = SubElement(parent, _tag(XDR, "txBody"))
    SubElement(tx_body, _tag(A, "bodyPr"), wrap="none")
    SubElement(tx_body, _tag(A, "lstStyle"))
    if not text:
        paragraph = SubElement(tx_body, _tag(A, "p"))
        SubElement(paragraph, _tag(A, "endParaRPr"))
        return
    for line in text.splitlines():
        paragraph = SubElement(tx_body, _tag(A, "p"))
        run = SubElement(paragraph, _tag(A, "r"))
        SubElement(run, _tag(A, "rPr"), lang="ja-JP")
        SubElement(run, _tag(A, "t")).text = line


def _add_shape(
    root: Element,
    node_id: str,
    text: str,
    shape: str,
    pos: Position,
    index: int,
    style: dict[str, str] | None = None,
) -> None:
    anchor = SubElement(root, _tag(XDR, "twoCellAnchor"))
    _marker(anchor, "from", round(pos.x / 64), round(pos.y / 20))
    _marker(
        anchor, "to", round((pos.x + pos.width) / 64), round((pos.y + pos.height) / 20)
    )

    sp = SubElement(anchor, _tag(XDR, "sp"), macro="", textlink="")
    nv = SubElement(sp, _tag(XDR, "nvSpPr"))
    c_nv_pr = SubElement(nv, _tag(XDR, "cNvPr"), id=str(index), name=f"node_{node_id}")
    _add_creation_id(c_nv_pr, index)
    SubElement(nv, _tag(XDR, "cNvSpPr"))

    sp_pr = SubElement(sp, _tag(XDR, "spPr"))
    geom = SubElement(sp_pr, _tag(A, "prstGeom"), prst=_shape_type(shape))
    SubElement(geom, _tag(A, "avLst"))
    style = style or {}
    fill = SubElement(sp_pr, _tag(A, "solidFill"))
    SubElement(
        fill, _tag(A, "srgbClr"), val=style.get("fill", "E8F1FF").lstrip("#").upper()
    )
    line = SubElement(sp_pr, _tag(A, "ln"), w="12700")
    line_fill = SubElement(line, _tag(A, "solidFill"))
    SubElement(
        line_fill,
        _tag(A, "srgbClr"),
        val=style.get("stroke", "4472C4").lstrip("#").upper(),
    )
    _add_text(sp, text)
    SubElement(anchor, _tag(XDR, "clientData"))


def _add_edge_label(
    root: Element, label_id: int, text: str, source: Position, target: Position
) -> None:
    """Add an editable, transparent text box near an edge label."""
    sx = source.x + source.width / 2
    sy = source.y + source.height / 2
    tx = target.x + target.width / 2
    ty = target.y + target.height / 2
    lines = text.replace("<br>", "\n").splitlines() or [""]
    width = max(42.0, max(len(line) for line in lines) * 14.0 + 16.0)
    height = max(22.0, len(lines) * 20.0 + 4.0)
    x = (sx + tx) / 2 - width / 2
    y = (sy + ty) / 2 - height / 2

    anchor = SubElement(root, _tag(XDR, "twoCellAnchor"))
    _marker(anchor, "from", round(x / 64), round(max(0, y) / 20))
    _marker(anchor, "to", round((x + width) / 64), round(max(0, y + height) / 20))
    shape = SubElement(anchor, _tag(XDR, "sp"), macro="", textlink="")
    nv = SubElement(shape, _tag(XDR, "nvSpPr"))
    c_nv_pr = SubElement(
        nv, _tag(XDR, "cNvPr"), id=str(label_id), name=f"label_{label_id}"
    )
    _add_creation_id(c_nv_pr, label_id)
    SubElement(nv, _tag(XDR, "cNvSpPr"))
    sp_pr = SubElement(shape, _tag(XDR, "spPr"))
    SubElement(sp_pr, _tag(A, "noFill"))
    line = SubElement(sp_pr, _tag(A, "ln"))
    SubElement(line, _tag(A, "noFill"))
    _add_text(shape, text)
    SubElement(anchor, _tag(XDR, "clientData"))


def _add_connector(
    root: Element,
    edge_index: int,
    source_id: str,
    target_id: str,
    source_shape_id: int,
    target_shape_id: int,
    source: Position,
    target: Position,
    name: str,
    direction: str = "TD",
) -> None:
    anchor = SubElement(root, _tag(XDR, "twoCellAnchor"))
    scx = source.x + source.width / 2
    scy = source.y + source.height / 2
    tcx = target.x + target.width / 2
    tcy = target.y + target.height / 2
    dx = tcx - scx
    dy = tcy - scy

    if direction in {"LR", "RL"}:
        # Left-to-right/right-to-left flow uses side connections.
        if dx >= 0:
            sx, sy = source.x + source.width, scy
            tx, ty = target.x, tcy
        else:
            sx, sy = source.x, scy
            tx, ty = target.x + target.width, tcy
    else:
        # Top-to-bottom flow uses bottom-to-top attachment. Same-level
        # branches leave from the side and enter at the target top.
        if target.y > source.y:
            sx, sy = scx, source.y + source.height
            tx, ty = tcx, target.y
        elif target.y < source.y:
            sx, sy = scx, source.y
            tx, ty = tcx, target.y + target.height
        elif dx >= 0:
            sx, sy = source.x + source.width, scy
            tx, ty = tcx, target.y
        else:
            sx, sy = source.x, scy
            tx, ty = tcx, target.y

    # twoCellAnchor requires from <= to in both axes, even when the
    # logical edge travels from right to left.
    _marker(anchor, "from", round(min(sx, tx) / 64), round(min(sy, ty) / 20))
    _marker(anchor, "to", round(max(sx, tx) / 64), round(max(sy, ty) / 20))

    # Use a real Excel connector and bind it to the source/target shapes.
    connector = SubElement(anchor, _tag(XDR, "cxnSp"))
    nv = SubElement(connector, _tag(XDR, "nvCxnSpPr"))
    c_nv_pr = SubElement(nv, _tag(XDR, "cNvPr"), id=str(edge_index), name=name)
    _add_creation_id(c_nv_pr, edge_index)
    c_nv_cxn = SubElement(nv, _tag(XDR, "cNvCxnSpPr"))
    if direction in {"LR", "RL"}:
        source_idx, target_idx = (2, 4) if dx >= 0 else (4, 2)
    elif target.y > source.y:
        source_idx, target_idx = 3, 1  # bottom -> top
    elif target.y < source.y:
        source_idx, target_idx = 1, 3  # top -> bottom
    elif dx >= 0:
        source_idx, target_idx = 2, 1  # right -> top (same-level branch)
    else:
        source_idx, target_idx = 4, 1  # left -> top
    SubElement(c_nv_cxn, _tag(A, "stCxn"), id=str(source_shape_id), idx=str(source_idx))
    SubElement(
        c_nv_cxn, _tag(A, "endCxn"), id=str(target_shape_id), idx=str(target_idx)
    )

    sp_pr = SubElement(connector, _tag(XDR, "spPr"))
    transform_attrs = {}
    if dx < 0:
        transform_attrs["flipH"] = "1"
    if dy < 0:
        transform_attrs["flipV"] = "1"
    xfrm = SubElement(sp_pr, _tag(A, "xfrm"), **transform_attrs)
    SubElement(
        xfrm,
        _tag(A, "off"),
        x=str(round(min(sx, tx) * 12700)),
        y=str(round(min(sy, ty) * 12700)),
    )
    SubElement(
        xfrm,
        _tag(A, "ext"),
        cx=str(max(1, round(abs(tx - sx) * 12700))),
        cy=str(max(1, round(abs(ty - sy) * 12700))),
    )
    geom = SubElement(sp_pr, _tag(A, "prstGeom"), prst="straightConnector1")
    SubElement(geom, _tag(A, "avLst"))
    line = SubElement(sp_pr, _tag(A, "ln"), w="12700")
    solid = SubElement(line, _tag(A, "solidFill"))
    SubElement(solid, _tag(A, "srgbClr"), val="4472C4")
    SubElement(line, _tag(A, "tailEnd"), type="triangle")
    SubElement(anchor, _tag(XDR, "clientData"))


def _add_subgraph_frame(
    root: Element, frame_id: int, name: str, node_positions: list[Position]
) -> None:
    """Draw a light editable frame around a parsed Mermaid subgraph."""
    if not node_positions:
        return
    pad = 24.0
    x = min(pos.x for pos in node_positions) - pad
    y = min(pos.y for pos in node_positions) - pad
    right = max(pos.x + pos.width for pos in node_positions) + pad
    bottom = max(pos.y + pos.height for pos in node_positions) + pad
    anchor = SubElement(root, _tag(XDR, "twoCellAnchor"))
    _marker(anchor, "from", round(max(0, x) / 64), round(max(0, y) / 20))
    _marker(anchor, "to", round(right / 64), round(bottom / 20))
    shape = SubElement(anchor, _tag(XDR, "sp"), macro="", textlink="")
    nv = SubElement(shape, _tag(XDR, "nvSpPr"))
    c_nv_pr = SubElement(
        nv, _tag(XDR, "cNvPr"), id=str(frame_id), name=f"subgraph_{frame_id}"
    )
    _add_creation_id(c_nv_pr, frame_id)
    SubElement(nv, _tag(XDR, "cNvSpPr"))
    sp_pr = SubElement(shape, _tag(XDR, "spPr"))
    geom = SubElement(sp_pr, _tag(A, "prstGeom"), prst="roundRect")
    SubElement(geom, _tag(A, "avLst"))
    SubElement(sp_pr, _tag(A, "noFill"))
    line = SubElement(sp_pr, _tag(A, "ln"), w="12700")
    fill = SubElement(line, _tag(A, "solidFill"))
    SubElement(fill, _tag(A, "srgbClr"), val="A6A6A6")
    _add_text(shape, name)
    SubElement(anchor, _tag(XDR, "clientData"))


def generate_drawing_xml(graph: Graph, positions: dict[str, Position]) -> str:
    root = Element(_tag(XDR, "wsDr"))
    # Excel's own drawings start shape IDs at 2; keep the same convention.
    index = 2

    for node_id, node in graph.nodes.items():
        _add_shape(
            root, node_id, node.text, node.shape, positions[node_id], index, node.style
        )
        index += 1

    shape_ids = {node_id: 2 + i for i, node_id in enumerate(graph.nodes)}
    for edge in graph.edges:
        _add_connector(
            root,
            index,
            edge.source,
            edge.target,
            shape_ids[edge.source],
            shape_ids[edge.target],
            positions[edge.source],
            positions[edge.target],
            f"edge_{edge.source}_{edge.target}",
            graph.direction,
        )
        index += 1
        if edge.label:
            _add_edge_label(
                root, index, edge.label, positions[edge.source], positions[edge.target]
            )
            index += 1

    for name, node_ids in graph.subgraphs.items():
        _add_subgraph_frame(
            root,
            index,
            name,
            [positions[node_id] for node_id in node_ids if node_id in positions],
        )
        index += 1

    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + tostring(
        root, encoding="unicode"
    )
