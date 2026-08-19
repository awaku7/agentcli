from collections import defaultdict, deque
from dataclasses import dataclass

from .model import Graph


@dataclass(frozen=True)
class Position:
    x: float
    y: float
    width: float = 120
    height: float = 50


def _levels(graph: Graph) -> dict[str, int]:
    incoming = {node_id: 0 for node_id in graph.nodes}
    outgoing: dict[str, list[str]] = defaultdict(list)

    for edge in graph.edges:
        outgoing[edge.source].append(edge.target)
        incoming.setdefault(edge.target, 0)
        incoming[edge.target] += 1

    roots = deque(node_id for node_id, count in incoming.items() if count == 0)
    levels = {node_id: 0 for node_id in roots}

    while roots:
        current = roots.popleft()
        for target in outgoing[current]:
            levels[target] = max(levels.get(target, 0), levels[current] + 1)
            incoming[target] -= 1
            if incoming[target] == 0:
                roots.append(target)

    for node_id in graph.nodes:
        levels.setdefault(node_id, 0)
    return levels


def _text_size(text: str, shape: str) -> tuple[float, float]:
    """Estimate a safe shape size; enlarge only when the default is too small."""
    lines = text.replace("<br>", "\n").splitlines() or [""]
    max_width = max(
        sum(14 if ord(ch) > 0x3000 else 8 for ch in line) for line in lines
    )
    width = max(120.0, max_width + 32.0)
    height = max(50.0, len(lines) * 20.0 + 20.0)
    if shape == "diamond":
        width = max(width, 140.0)
        height = max(height, 70.0)
    return width, height


def layout_graph(graph: Graph, *, gap_x: float = 180, gap_y: float = 100) -> dict[str, Position]:
    levels = _levels(graph)
    rows: dict[int, list[str]] = defaultdict(list)
    for node_id, level in levels.items():
        rows[level].append(node_id)

    sizes = {node_id: _text_size(node.text, node.shape) for node_id, node in graph.nodes.items()}
    positions: dict[str, Position] = {}

    if graph.direction in {"LR", "RL"}:
        level_widths = {
            level: max((sizes[node_id][0] for node_id in node_ids), default=120.0)
            for level, node_ids in rows.items()
        }
        level_x: dict[int, float] = {}
        cursor = 0.0
        for level in sorted(rows):
            level_x[level] = cursor
            cursor += level_widths[level] + gap_x
        for level, node_ids in rows.items():
            y = 0.0
            for node_id in sorted(node_ids):
                width, height = sizes[node_id]
                positions[node_id] = Position(level_x[level], y, width, height)
                y += height + gap_y
        if graph.direction == "RL":
            max_x = max((p.x + p.width for p in positions.values()), default=0)
            positions = {
                node_id: Position(max_x - pos.x - pos.width, pos.y, pos.width, pos.height)
                for node_id, pos in positions.items()
            }
    else:
        level_heights = {
            level: max((sizes[node_id][1] for node_id in node_ids), default=50.0)
            for level, node_ids in rows.items()
        }
        level_y: dict[int, float] = {}
        cursor = 0.0
        for level in sorted(rows):
            level_y[level] = cursor
            cursor += level_heights[level] + gap_y
        for level, node_ids in rows.items():
            x = 0.0
            for node_id in sorted(node_ids):
                width, height = sizes[node_id]
                positions[node_id] = Position(x, level_y[level], width, height)
                x += width + gap_x

    return positions
