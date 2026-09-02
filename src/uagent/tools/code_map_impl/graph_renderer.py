"""Visual interactive HTML generator for code_map ontology data."""

from __future__ import annotations

import json
from typing import Any


def generate_ontology_html(
    ontology_data: dict[str, Any], title: str = "Codebase Ontology Graph"
) -> str:
    """Generate a self-contained interactive HTML visualization using vis-network (embedded/CDN)."""
    graph_nodes: list[dict[str, Any]] = []
    graph_edges: list[dict[str, Any]] = []

    nodes = ontology_data.get("@graph", [])

    # Type color mapping and styling
    type_styles = {
        "uag:SourceFile": {
            "color": "#4A90E2",
            "shape": "dot",
            "size": 18,
            "group": "SourceFile",
        },
        "uag:Class": {
            "color": "#E67E22",
            "shape": "diamond",
            "size": 16,
            "group": "Class",
        },
        "uag:Function": {
            "color": "#2ECC71",
            "shape": "dot",
            "size": 10,
            "group": "Function",
        },
        "uag:Interface": {
            "color": "#9B59B6",
            "shape": "square",
            "size": 14,
            "group": "Interface",
        },
        "uag:Struct": {
            "color": "#F39C12",
            "shape": "triangle",
            "size": 14,
            "group": "Struct",
        },
        "uag:Enum": {
            "color": "#1ABC9C",
            "shape": "hexagon",
            "size": 14,
            "group": "Enum",
        },
        "uag:Symbol": {
            "color": "#95A5A6",
            "shape": "dot",
            "size": 8,
            "group": "Symbol",
        },
        "uag:Project": {
            "color": "#E74C3C",
            "shape": "star",
            "size": 24,
            "group": "Project",
        },
    }

    # Edges styling
    edge_styles = {
        "uag:ImportRelation": {
            "color": "#3498DB",
            "arrows": "to",
            "dashes": False,
            "label": "imports",
        },
        "uag:CallRelation": {
            "color": "#2ECC71",
            "arrows": "to",
            "dashes": True,
            "label": "calls",
        },
        "uag:InheritanceRelation": {
            "color": "#E67E22",
            "arrows": "to",
            "dashes": False,
            "label": "inherits",
        },
    }

    node_set = set()

    for item in nodes:
        item_type = item.get("@type", "")
        item_id = item.get("@id", "")

        # Skip ontology vocabulary / schema declarations
        if item_type in {"owl:Ontology", "owl:Class", "rdf:Property", "uag:ScanStats"}:
            continue

        # Handle relations (edges)
        if item_type in edge_styles:
            source = (
                item.get("uag:source", {}).get("@id")
                if isinstance(item.get("uag:source"), dict)
                else item.get("uag:source")
            )
            target = (
                item.get("uag:target", {}).get("@id")
                if isinstance(item.get("uag:target"), dict)
                else item.get("uag:target")
            )
            if source and target:
                style = edge_styles[item_type]
                edge_entry = {
                    "from": source,
                    "to": target,
                    "color": {"color": style["color"], "highlight": "#ff0000"},
                    "arrows": style["arrows"],
                    "dashes": style["dashes"],
                    "title": f"{item_type.replace('uag:', '')} (Line: {item.get('uag:source_line', '')})",
                }
                graph_edges.append(edge_entry)
            continue

        # Handle entities (nodes)
        style = type_styles.get(
            item_type,
            {"color": "#BDC3C7", "shape": "dot", "size": 10, "group": "Other"},
        )
        label = (
            item.get("uag:name")
            or item.get("uag:relative_path")
            or item_id.split("/")[-1]
        )

        tooltip_lines = [
            f"<b>{label}</b>",
            f"Type: {item_type.replace('uag:', '')}",
            f"ID: {item_id}",
        ]
        if "uag:language" in item:
            tooltip_lines.append(f"Language: {item['uag:language']}")
        if "uag:line" in item:
            tooltip_lines.append(
                f"Lines: {item['uag:line']} - {item.get('uag:end_line', item['uag:line'])}"
            )

        node_entry = {
            "id": item_id,
            "label": label,
            "group": style["group"],
            "shape": style["shape"],
            "size": style["size"],
            "color": style["color"],
            "title": "<br>".join(tooltip_lines),
        }
        graph_nodes.append(node_entry)
        node_set.add(item_id)

    # Filter edges to valid nodes only
    valid_edges = [
        e for e in graph_edges if e["from"] in node_set and e["to"] in node_set
    ]

    # Render template with embedded vis.js
    nodes_json = json.dumps(graph_nodes, ensure_ascii=False)
    edges_json = json.dumps(valid_edges, ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style>
    body, html {{
      margin: 0;
      padding: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: #1a1a24;
      color: #e0e0e0;
    }}
    #header {{
      position: absolute;
      top: 10px;
      left: 15px;
      z-index: 10;
      background: rgba(30, 30, 45, 0.85);
      padding: 12px 20px;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      backdrop-filter: blur(8px);
      border: 1px solid rgba(255,255,255,0.1);
    }}
    h1 {{
      margin: 0 0 6px 0;
      font-size: 1.1rem;
      font-weight: 600;
      color: #fff;
    }}
    #stats {{
      font-size: 0.8rem;
      color: #aaa;
    }}
    #controls {{
      margin-top: 10px;
      display: flex;
      gap: 10px;
    }}
    button, select {{
      background: #2b2b3d;
      color: #fff;
      border: 1px solid #444;
      padding: 5px 10px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 0.8rem;
    }}
    button:hover, select:hover {{
      background: #3b3b52;
    }}
    #legend {{
      position: absolute;
      bottom: 15px;
      left: 15px;
      z-index: 10;
      background: rgba(30, 30, 45, 0.85);
      padding: 10px 15px;
      border-radius: 8px;
      font-size: 0.75rem;
      display: flex;
      gap: 12px;
      backdrop-filter: blur(8px);
      border: 1px solid rgba(255,255,255,0.1);
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 5px;
    }}
    .legend-color {{
      width: 12px;
      height: 12px;
      border-radius: 50%;
      display: inline-block;
    }}
    #network {{
      width: 100%;
      height: 100%;
    }}
  </style>
</head>
<body>
  <div id="header">
    <h1>{title}</h1>
    <div id="stats">Nodes: <span id="node-count">{len(graph_nodes)}</span> | Edges: <span id="edge-count">{len(valid_edges)}</span></div>
    <div id="controls">
      <select id="group-filter" onchange="filterGroup(this.value)">
        <option value="ALL">Show All Groups</option>
        <option value="SourceFile">Files Only</option>
        <option value="Class">Classes Only</option>
        <option value="Function">Functions Only</option>
      </select>
      <button onclick="network.fit({{animation: true}})">Fit View</button>
      <button onclick="togglePhysics()">Toggle Physics</button>
    </div>
  </div>

  <div id="legend">
    <div class="legend-item"><span class="legend-color" style="background: #4A90E2;"></span> File</div>
    <div class="legend-item"><span class="legend-color" style="background: #E67E22;"></span> Class</div>
    <div class="legend-item"><span class="legend-color" style="background: #2ECC71;"></span> Function</div>
    <div class="legend-item"><span class="legend-color" style="background: #9B59B6;"></span> Interface</div>
    <div class="legend-item"><span class="legend-color" style="background: #3498DB;"></span> Import</div>
    <div class="legend-item"><span class="legend-color" style="background: #2ECC71;"></span> Call</div>
  </div>

  <div id="network"></div>

  <script type="text/javascript">
    const rawNodes = {nodes_json};
    const rawEdges = {edges_json};

    const container = document.getElementById('network');
    const nodes = new vis.DataSet(rawNodes);
    const edges = new vis.DataSet(rawEdges);

    const data = {{ nodes: nodes, edges: edges }};
    const options = {{
      nodes: {{
        font: {{ color: '#e0e0e0', size: 12 }},
        borderWidth: 1,
      }},
      edges: {{
        width: 1,
        smooth: {{ type: 'continuous' }}
      }},
      physics: {{
        stabilization: {{ iterations: 100 }},
        barnesHut: {{
          gravitationalConstant: -3000,
          springConstant: 0.04,
          springLength: 95
        }}
      }},
      interaction: {{
        hover: true,
        tooltipDelay: 100,
        navigationButtons: true,
        keyboard: true
      }}
    }};

    const network = new vis.Network(container, data, options);
    let physicsEnabled = true;

    function togglePhysics() {{
      physicsEnabled = !physicsEnabled;
      network.setOptions({{ physics: {{ enabled: physicsEnabled }} }});
    }}

    function filterGroup(group) {{
      if (group === "ALL") {{
        nodes.clear();
        nodes.add(rawNodes);
      }} else {{
        const filtered = rawNodes.filter(n => n.group === group);
        nodes.clear();
        nodes.add(filtered);
      }}
      document.getElementById('node-count').innerText = nodes.length;
    }}
  </script>
</body>
</html>
"""
    return html_content
