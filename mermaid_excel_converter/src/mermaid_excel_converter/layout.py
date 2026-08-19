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

    # Cycles or isolated nodes are placed at level zero rather than failing.
    for node_id in graph.nodes:
        levels.setdefault(node_id, 0)

    return levels


def layout_graph(graph: Graph, *, gap_x: float = 180, gap_y: float = 100) -> dict[str, Position]:
    levels = _levels(graph)
    rows: dict[int, list[str]] = defaultdict(list)
    for node_id, level in levels.items():
        rows[level].append(node_id)

    positions: dict[str, Position] = {}
    for level, node_ids in rows.items():
        for row, node_id in enumerate(sorted(node_ids)):
            if graph.direction in {"LR", "RL"}:
                x = level * gap_x
                y = row * gap_y
                if graph.direction == "RL":
                    x = -x
            else:
                x = row * gap_x
                y = level * gap_y
                if graph.direction == "TB":
                    pass
                elif graph.direction == "TD":
                    pass

            positions[node_id] = Position(x=x, y=y)

    return positions
