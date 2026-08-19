from dataclasses import dataclass, field


@dataclass(frozen=True)
class Node:
    id: str
    text: str
    shape: str = "rect"


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    label: str = ""


@dataclass
class Graph:
    direction: str
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
