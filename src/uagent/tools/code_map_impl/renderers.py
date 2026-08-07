"""Output renderers for code_map."""
from __future__ import annotations

import datetime
import json
import os
import urllib.request
from pathlib import Path
from typing import Any


def _make_uri(path: str, root: str) -> str:
    root_path = Path(root).resolve()
    try:
        rel = Path(path).resolve().relative_to(root_path)
    except ValueError:
        rel = Path(path).name
    return f"uag:file/{rel.as_posix()}"


def _make_symbol_uri(symbol_name: str, file_uri: str) -> str:
    return f"{file_uri}#{symbol_name}"

def build_ontology(
    core_result: dict[str, Any],
    relations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a JSON-LD ontology graph from code_map results and relations."""
    root = core_result["root"]
    graph: list[dict[str, Any]] = []

    # File nodes
    file_uri_map: dict[str, str] = {}  # absolute path → URI

    for entry in core_result["files"]:
        fpath = entry["path"]
        uri = _make_uri(fpath, root)
        file_uri_map[fpath] = uri

        # File node
        file_node: dict[str, Any] = {
            "@id": uri,
            "@type": "uag:SourceFile",
            "uag:language": entry.get("language", "Unknown"),
            "uag:relative_path": entry.get("relative_path", ""),
        }
        graph.append(file_node)

        # Symbol nodes
        for sym in entry.get("symbols", []):
            sym_uri = _make_symbol_uri(sym["name"], uri)
            sym_type = _symbol_type_to_ontology(sym.get("type", "symbol"))
            sym_node: dict[str, Any] = {
                "@id": sym_uri,
                "@type": sym_type,
                "uag:file": {"@id": uri},
                "uag:line": sym["line"],
                "uag:name": sym["name"],
            }
            graph.append(sym_node)

    # Relation edges
    for rel in relations:
        source_uri = file_uri_map.get(rel["source"])
        target_uri = file_uri_map.get(rel["target"])
        if source_uri and target_uri:
            rel_node: dict[str, Any] = {
                "@id": f"{source_uri}/imports/{Path(rel['target']).name}",
                "@type": "uag:ImportRelation",
                "uag:source": {"@id": source_uri},
                "uag:target": {"@id": target_uri},
                "uag:module": rel.get("module", ""),
                "uag:source_line": rel.get("source_line", 0),
            }
            graph.append(rel_node)

    # Project metadata node
    project_info = core_result.get("project")
    if project_info:
        graph.append(
            {
                "@id": "uag:project",
                "@type": "uag:Project",
                "uag:project_type": project_info.get("type"),
                "uag:root": root,
                "uag:total_files": core_result.get("total_files", 0),
            }
        )

    # Stats node
    graph.append(
        {
            "@id": "uag:stats",
            "@type": "uag:ScanStats",
            "uag:total_files": core_result.get("total_files", 0),
            "uag:total_relations": len(relations),
            "uag:root": root,
        }
    )

    return {
        "@context": {
            "schema": "https://schema.org/",
            "uag": "https://uagent.local/ontology/",
        },
        "@graph": graph,
    }


def _symbol_type_to_ontology(symbol_type: str) -> str:
    """Map code_map symbol types to ontology types."""
    mapping = {
        "function": "uag:Function",
        "class": "uag:Class",
        "interface": "uag:Interface",
        "struct": "uag:Struct",
        "enum": "uag:Enum",
        "symbol": "uag:Symbol",
    }
    return mapping.get(symbol_type, "uag:Symbol")


# ---------------------------------------------------------------------------
# Tree builder
# ---------------------------------------------------------------------------


def build_tree(
    file_list: list[str], root: str, max_depth: int
) -> list[dict[str, Any]]:
    """Build a nested tree structure from flat file list."""
    root_path = Path(root).resolve()
    tree: list[dict[str, Any]] = []

    for fpath in file_list:
        p = Path(fpath).resolve()
        try:
            rel = p.relative_to(root_path)
        except ValueError:
            continue
        parts = rel.parts
        if max_depth > 0 and len(parts) > max_depth:
            continue

        current = tree
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                # File node
                current.append(
                    {
                        "name": part,
                        "type": "file",
                        "path": str(p),
                    }
                )
            else:
                # Directory node
                existing = [
                    n
                    for n in current
                    if n.get("name") == part and n.get("type") == "dir"
                ]
                if existing:
                    current = existing[0].setdefault("children", [])
                else:
                    new_dir = {"name": part, "type": "dir", "children": []}
                    current.append(new_dir)
                    current = new_dir["children"]

    return tree


def _escape_mermaid_label(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("|", "&#124;")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def tree_to_mermaid(tree: list[dict[str, Any]], root_name: str = "root") -> str:
    """Convert a nested tree structure to Mermaid graph TD format."""
    lines = ["graph TD"]
    node_id = [0]

    def _add_node(node: dict[str, Any], parent_id: str | None = None) -> str:
        node_id[0] += 1
        nid = f"n{node_id[0]}"
        name = node.get("name", "")
        safe_name = _escape_mermaid_label(name)

        if node.get("type") == "dir":
            label = f"{safe_name}/"
            lines.append(f'    {nid}["{label}"]')
        else:
            label = safe_name
            lines.append(f'    {nid}["{label}"]')

        if parent_id:
            lines.append(f"    {parent_id} --> {nid}")

        for child in node.get("children", []):
            _add_node(child, nid)

        return nid

    for child in tree:
        _add_node(child, None)

    return "\n".join(lines)


def render_mermaid_to_image(mermaid_code: str, output_path: str) -> str | None:
    """Render Mermaid diagram to PNG and save to file.

    Returns None on success, or an error message string on failure.
    Uses mermaid-cli (playwright-based) if available, falls back to Mermaid.ink API.
    """
    mermaid_cli_hint = "Install mermaid-cli: pip install mermaid-cli"
    from .._pip_auto import install_with_status

    # Try mermaid-cli Python package first (local playwright rendering)
    if install_with_status("mermaid-cli", "mermaid_cli"):
        try:
            import asyncio
            from mermaid_cli import render_mermaid

            async def _render():
                _, _, png_bytes = await render_mermaid(
                    mermaid_code, output_format="png"
                )
                if png_bytes:
                    with open(output_path, "wb") as f:
                        f.write(png_bytes)
                    return None
                return "render returned no data"

            return asyncio.run(_render())
        except Exception:
            pass

    # Fallback: Mermaid.ink API via base64 GET
    try:
        import base64

        encoded = base64.urlsafe_b64encode(mermaid_code.encode("utf-8")).decode("ascii")
        url = f"https://mermaid.ink/img/{encoded}"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=30) as resp:
            png_bytes = resp.read()
            if png_bytes:
                with open(output_path, "wb") as f:
                    f.write(png_bytes)
                return None
            return "Mermaid.ink returned no data"
    except Exception:
        pass

    return f"Render failed (try: {mermaid_cli_hint})"


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


