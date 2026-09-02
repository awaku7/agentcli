"""Output renderers for code_map."""

from __future__ import annotations

import hashlib
import re
import urllib.request
from pathlib import Path
from typing import Any


def _make_uri(path: str, root: str) -> str:
    root_path = Path(root).resolve()
    path_obj = Path(path)
    if not path_obj.is_absolute():
        path_obj = root_path / path_obj
    try:
        rel = path_obj.resolve().relative_to(root_path)
    except ValueError:
        absolute = str(path_obj.resolve())
        digest = hashlib.sha256(absolute.encode("utf-8")).hexdigest()[:16]
        rel = Path("__external__") / digest / Path(path).name
    return f"uag:file/{rel.as_posix()}"


def _extract_semantic_relations(
    core_result: dict[str, Any], file_uri_map: dict[str, str], root: str
) -> list[dict[str, Any]]:
    """Extract conservative, resolved symbol-level call/inheritance edges."""
    symbol_index: dict[str, list[str]] = {}
    symbol_lines: dict[str, tuple[int, int]] = {}
    for entry in core_result.get("files", []):
        file_uri = file_uri_map.get(
            str((Path(root) / Path(entry.get("path", ""))).resolve())
        )
        if not file_uri:
            continue
        for ordinal, symbol in enumerate(entry.get("symbols", [])):
            uri = _make_symbol_uri(
                symbol["name"],
                file_uri,
                int(symbol.get("line", 0)),
                str(symbol.get("type", "")),
                ordinal,
            )
            symbol_index.setdefault(symbol["name"], []).append(uri)
            start_line = int(symbol.get("line", 0))
            end_line = int(symbol.get("end_line", start_line))
            symbol_lines[uri] = (start_line, max(start_line, end_line))

    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, int]] = set()
    keywords = {
        "if",
        "for",
        "while",
        "switch",
        "catch",
        "return",
        "class",
        "def",
        "fn",
        "new",
        "super",
    }
    inheritance = (
        re.compile(r"\bclass\s+(\w+)\s*\(([^)]*)\)"),
        re.compile(
            r"\bclass\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w ,]+))?"
        ),
        re.compile(r"\b(?:class|struct)\s+(\w+)\s*:\s*([^\{]+)"),
    )
    for entry in core_result.get("files", []):
        path = entry.get("path", "")
        file_uri = file_uri_map.get(str((Path(root) / Path(path)).resolve()))
        if not file_uri:
            continue
        source_path = Path(path)
        if not source_path.is_absolute():
            source_path = Path(root) / source_path
        try:
            source = source_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = source.splitlines()
        local = {
            s["name"]: _make_symbol_uri(
                s["name"],
                file_uri,
                int(s.get("line", 0)),
                str(s.get("type", "")),
                ordinal,
            )
            for ordinal, s in enumerate(entry.get("symbols", []))
        }
        for pattern in inheritance:
            for match in pattern.finditer(source):
                child = local.get(match.group(1))
                if not child:
                    continue
                line = source[: match.start()].count("\n") + 1
                for base in re.split(
                    r"[, ]+",
                    " ".join(group or "" for group in match.groups()[1:]).strip(),
                ):
                    candidates = symbol_index.get(base, [])
                    if base in keywords or len(candidates) != 1:
                        continue
                    key = ("inherits", child, candidates[0], line)
                    if key not in seen:
                        seen.add(key)
                        result.append(
                            {
                                "kind": "inherits",
                                "source": child,
                                "target": candidates[0],
                                "line": line,
                            }
                        )
        for match in re.finditer(r"\b([A-Za-z_]\w*)\s*\(", source):
            name = match.group(1)
            candidates = [u for u in symbol_index.get(name, []) if u != local.get(name)]
            if name in keywords or len(candidates) != 1:
                continue
            line = source[: match.start()].count("\n") + 1
            stripped = lines[line - 1].strip() if 0 < line <= len(lines) else ""
            if stripped.startswith(
                (
                    "#",
                    "//",
                    "/*",
                    "*",
                    "def ",
                    "function ",
                    "fn ",
                    "func ",
                    "class ",
                    "interface ",
                )
            ):
                continue
            callers = [
                u
                for u, (start_line, end_line) in symbol_lines.items()
                if u.startswith(file_uri + "#") and start_line <= line <= end_line
            ]
            if not callers:
                continue
            caller = max(callers, key=lambda u: symbol_lines[u][0])
            key = ("calls", caller, candidates[0], line)
            if key not in seen:
                seen.add(key)
                result.append(
                    {
                        "kind": "calls",
                        "source": caller,
                        "target": candidates[0],
                        "line": line,
                    }
                )
    return result


def _make_symbol_uri(
    symbol_name: str,
    file_uri: str,
    line: int = 0,
    symbol_type: str = "",
    ordinal: int = 0,
) -> str:
    """Create a stable URI that distinguishes same-named declarations."""
    identity = f"{symbol_name}|{line}|{symbol_type}|{ordinal}"
    suffix = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"{file_uri}#{symbol_name}@{suffix}"


def build_ontology(
    core_result: dict[str, Any],
    relations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a JSON-LD ontology graph from code_map results and relations."""
    root = core_result["root"]
    graph: list[dict[str, Any]] = []

    # File nodes
    file_uri_map: dict[str, str] = {}  # absolute path → URI
    file_nodes: dict[str, dict[str, Any]] = {}

    for entry in core_result["files"]:
        fpath = entry["path"]
        uri = _make_uri(fpath, root)
        canonical_path = Path(fpath)
        if not canonical_path.is_absolute():
            canonical_path = Path(root) / canonical_path
        file_uri_map[str(canonical_path.resolve())] = uri

        # File node
        file_node: dict[str, Any] = {
            "@id": uri,
            "@type": "uag:SourceFile",
            "uag:language": entry.get("language", "Unknown"),
            "uag:relative_path": entry.get("relative_path", ""),
        }
        graph.append(file_node)
        file_nodes[uri] = file_node

        # Symbol nodes
        for ordinal, sym in enumerate(entry.get("symbols", [])):
            sym_uri = _make_symbol_uri(
                sym["name"],
                uri,
                int(sym.get("line", 0)),
                str(sym.get("type", "")),
                ordinal,
            )
            sym_type = _symbol_type_to_ontology(sym.get("type", "symbol"))
            sym_node: dict[str, Any] = {
                "@id": sym_uri,
                "@type": sym_type,
                "uag:file": {"@id": uri},
                "uag:line": sym.get("line", 0),
                "uag:end_line": sym.get("end_line", sym.get("line", 0)),
                "uag:name": sym["name"],
            }
            graph.append(sym_node)

    # Symbol-level relations are emitted only when both endpoints resolve.
    for semantic in _extract_semantic_relations(core_result, file_uri_map, root):
        key = "|".join(
            (
                semantic["kind"],
                semantic["source"],
                semantic["target"],
                str(semantic["line"]),
            )
        )
        relation_id = (
            "uag:"
            + semantic["kind"]
            + "/"
            + hashlib.sha256(key.encode("utf-8")).hexdigest()
        )
        graph.append(
            {
                "@id": relation_id,
                "@type": (
                    "uag:CallRelation"
                    if semantic["kind"] == "calls"
                    else "uag:InheritanceRelation"
                ),
                "uag:source": {"@id": semantic["source"]},
                "uag:target": {"@id": semantic["target"]},
                "uag:source_line": semantic["line"],
            }
        )

    # Relation edges
    relation_ids: set[str] = set()
    for rel in relations:
        source_uri = file_uri_map.get(str(Path(rel["source"]).resolve()))
        target_uri = file_uri_map.get(str(Path(rel["target"]).resolve()))
        if source_uri and target_uri:
            # Include the source line and module in the ID.  The old ID only
            # used the target basename, so distinct imports collided.
            relation_key = "|".join(
                (
                    source_uri,
                    target_uri,
                    str(rel.get("source_line", 0)),
                    str(rel.get("module", "")),
                )
            )
            relation_id = (
                "uag:import/" + hashlib.sha256(relation_key.encode("utf-8")).hexdigest()
            )
            if relation_id in relation_ids:
                continue
            relation_ids.add(relation_id)
            rel_node: dict[str, Any] = {
                "@id": relation_id,
                "@type": "uag:ImportRelation",
                "uag:source": {"@id": source_uri},
                "uag:target": {"@id": target_uri},
                "uag:module": rel.get("module", ""),
                "uag:source_line": rel.get("source_line", 0),
            }
            graph.append(rel_node)
            imports = file_nodes[source_uri].setdefault("uag:imports", [])
            target_ref = {"@id": target_uri}
            if target_ref not in imports:
                imports.append(target_ref)

    # Add explicit inverse-friendly definitions from files to symbols.
    for node in graph:
        if node.get("@type") in {
            "uag:Function",
            "uag:Class",
            "uag:Interface",
            "uag:Struct",
            "uag:Enum",
            "uag:Symbol",
        }:
            file_ref = node.get("uag:file", {}).get("@id")
            if file_ref in file_nodes:
                definitions = file_nodes[file_ref].setdefault("uag:defines", [])
                symbol_ref = {"@id": node["@id"]}
                if symbol_ref not in definitions:
                    definitions.append(symbol_ref)

    for node in file_nodes.values():
        for key in ("uag:imports", "uag:defines"):
            if key in node:
                node[key].sort(key=lambda ref: ref["@id"])

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

    # Vocabulary declarations make the output useful as a small, self-describing
    # ontology rather than only as an instance graph.
    vocabulary: list[dict[str, Any]] = [
        {
            "@id": "uag:CodeOntology",
            "@type": "owl:Ontology",
            "rdfs:label": "UAG Code Ontology",
            "rdfs:comment": "Ontology generated from project source structure and static import relations.",
        }
    ]
    classes = (
        "Project",
        "SourceFile",
        "Function",
        "Class",
        "Interface",
        "Struct",
        "Enum",
        "Symbol",
        "ImportRelation",
        "CallRelation",
        "InheritanceRelation",
        "ScanStats",
    )
    for class_name in classes:
        vocabulary.append(
            {
                "@id": f"uag:{class_name}",
                "@type": "owl:Class",
                "rdfs:label": class_name,
            }
        )
    properties = {
        "file": ("file containing a symbol", "uag:Symbol", "uag:SourceFile"),
        "line": ("source line of a symbol", "uag:Symbol", "schema:Integer"),
        "end_line": ("ending source line of a symbol", "uag:Symbol", "schema:Integer"),
        "name": ("declared name", "uag:Symbol", "schema:Text"),
        "language": ("implementation language", "uag:SourceFile", "schema:Text"),
        "relative_path": ("project-relative path", "uag:SourceFile", "schema:Text"),
        "source": ("source entity of a relation", "schema:Thing", "schema:Thing"),
        "target": ("target entity of a relation", "schema:Thing", "schema:Thing"),
        "calls": ("calls relation between symbols", "uag:CallRelation", "uag:Function"),
        "inherits": (
            "inheritance relation between types",
            "uag:InheritanceRelation",
            "uag:Class",
        ),
        "module": ("imported module name", "uag:ImportRelation", "schema:Text"),
        "source_line": (
            "line containing import",
            "uag:ImportRelation",
            "schema:Integer",
        ),
        "defines": ("symbols defined by a file", "uag:SourceFile", "uag:Symbol"),
        "imports": ("files imported by a file", "uag:SourceFile", "uag:SourceFile"),
    }
    for prop_name, (label, domain, value_range) in properties.items():
        vocabulary.append(
            {
                "@id": f"uag:{prop_name}",
                "@type": "rdf:Property",
                "rdfs:label": label,
                "rdfs:domain": {"@id": domain},
                "rdfs:range": {"@id": value_range},
            }
        )

    # Stable ordering makes generated files diff-friendly.
    graph = vocabulary + sorted(graph, key=lambda node: node.get("@id", ""))
    return {
        "@context": {
            "schema": "https://schema.org/",
            "uag": "https://uagent.local/ontology/",
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "owl": "http://www.w3.org/2002/07/owl#",
            "file": {"@id": "uag:file", "@type": "@id"},
            "source": {"@id": "uag:source", "@type": "@id"},
            "target": {"@id": "uag:target", "@type": "@id"},
            "defines": {"@id": "uag:defines", "@type": "@id"},
            "imports": {"@id": "uag:imports", "@type": "@id"},
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


def build_tree(file_list: list[str], root: str, max_depth: int) -> list[dict[str, Any]]:
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
        return "Failed to get image data"
    except Exception as exc:
        return f"Image render failed: {exc}"
