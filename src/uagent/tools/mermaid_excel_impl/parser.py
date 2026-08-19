import re
from dataclasses import replace

from .model import Edge, Graph, Node

_HEADER = re.compile(r"^\s*flowchart\s+(TD|TB|LR|RL)\s*$")
_NODE = re.compile(
    r"(?P<id>[A-Za-z_][\w-]*)\s*(?P<open>\[|\{|\(\()(?P<text>.*?)(?P<close>\]|\}|\)\))"
)
_EDGE = re.compile(
    r"(?P<source>[A-Za-z_][\w-]*)(?:\s*(?:\[.*?\]|\{.*?\}|\(\(.*?\)\)))?"
    r"\s*-->(?:\|(?P<label>[^|]*)\|)?\s*"
    r"(?P<target>[A-Za-z_][\w-]*)(?:\s*(?:\[.*?\]|\{.*?\}|\(\(.*?\)\)))?"
)
_CLASS_DEF = re.compile(r"^classDef\s+(?P<name>[\w-]+)\s+(?P<body>.+)$")
_CLASS_USE = re.compile(r"^class\s+(?P<nodes>[^ ]+)\s+(?P<name>[\w-]+)$")
_SUBGRAPH = re.compile(r"^subgraph\s+(?P<name>.+)$")


def _shape(open_token: str, close_token: str) -> str:
    if open_token == "{" and close_token == "}":
        return "diamond"
    if open_token == "((" and close_token == "))":
        return "ellipse"
    if open_token == "[" and close_token == "]":
        return "rect"
    raise ValueError(f"unsupported node shape: {open_token}{close_token}")


def _parse_style(body: str) -> dict[str, str]:
    result = {}
    for item in body.split(","):
        if ":" in item:
            key, value = item.split(":", 1)
            result[key.strip()] = value.strip()
    return result


def parse_mermaid(source: str) -> Graph:
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Mermaid source is empty")
    header = _HEADER.match(lines[0])
    if not header:
        raise ValueError("only flowchart TD/TB/LR/RL is supported")

    graph = Graph(direction=header.group(1))
    style_defs: dict[str, dict[str, str]] = {}
    style_users: dict[str, str] = {}
    active_subgraphs: list[str] = []

    for line in lines[1:]:
        subgraph = _SUBGRAPH.match(line)
        if subgraph:
            name = subgraph.group("name").strip().strip('"')
            graph.subgraphs.setdefault(name, [])
            active_subgraphs.append(name)
            continue
        if line.lower() == "end":
            if active_subgraphs:
                active_subgraphs.pop()
            continue
        class_def = _CLASS_DEF.match(line)
        if class_def:
            style_defs[class_def.group("name")] = _parse_style(class_def.group("body"))
            continue
        class_use = _CLASS_USE.match(line)
        if class_use:
            for node_id in class_use.group("nodes").split(","):
                style_users[node_id.strip()] = class_use.group("name")
            continue
        for match in _NODE.finditer(line):
            node_id = match.group("id")
            graph.nodes[node_id] = Node(
                id=node_id,
                text=match.group("text").replace("<br>", "\n"),
                shape=_shape(match.group("open"), match.group("close")),
            )
            for name in active_subgraphs:
                if node_id not in graph.subgraphs[name]:
                    graph.subgraphs[name].append(node_id)
        edge = _EDGE.search(line)
        if edge:
            graph.edges.append(
                Edge(
                    edge.group("source"),
                    edge.group("target"),
                    (edge.group("label") or "").strip(),
                )
            )

    for node_id, style_name in style_users.items():
        if node_id in graph.nodes:
            graph.nodes[node_id] = replace(
                graph.nodes[node_id], style=style_defs.get(style_name, {})
            )
    return graph
