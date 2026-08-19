import re

from .model import Edge, Graph, Node

_HEADER = re.compile(r"^\s*flowchart\s+(TD|TB|LR|RL)\s*$")
_NODE = re.compile(r"(?P<id>[A-Za-z_][\w-]*)\s*(?P<open>\[|\{|\(\()(?P<text>.*?)(?P<close>\]|\}|\)\))")
_EDGE = re.compile(
    r"(?P<source>[A-Za-z_][\w-]*)(?:\s*(?:\[.*?\]|\{.*?\}|\(\(.*?\)\)))?"
    r"\s*-->(?:\|(?P<label>[^|]*)\|)?\s*"
    r"(?P<target>[A-Za-z_][\w-]*)(?:\s*(?:\[.*?\]|\{.*?\}|\(\(.*?\)\)))?"
)


def _shape(open_token: str, close_token: str) -> str:
    if open_token == "{" and close_token == "}":
        return "diamond"
    if open_token == "((" and close_token == "))":
        return "ellipse"
    if open_token == "[" and close_token == "]":
        return "rect"
    raise ValueError(f"unsupported node shape: {open_token}{close_token}")


def parse_mermaid(source: str) -> Graph:
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Mermaid source is empty")

    header = _HEADER.match(lines[0])
    if not header:
        raise ValueError("only flowchart TD/TB/LR/RL is supported")

    graph = Graph(direction=header.group(1))

    for line in lines[1:]:
        for match in _NODE.finditer(line):
            node_id = match.group("id")
            graph.nodes[node_id] = Node(
                id=node_id,
                text=match.group("text").replace("<br>", "\n"),
                shape=_shape(match.group("open"), match.group("close")),
            )

        edge = _EDGE.search(line)
        if edge:
            graph.edges.append(
                Edge(
                    source=edge.group("source"),
                    target=edge.group("target"),
                    label=(edge.group("label") or "").strip(),
                )
            )

    return graph
