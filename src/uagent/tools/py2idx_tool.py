from __future__ import annotations

import ast
import os
import sys
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "type": "function",
    "tool_genre": "devel",
    "function": {
        "name": "py2idx",
        "description": _(
            "tool.description",
            default=(
                "Parse a Python file into functions, classes, and methods and return "
                "a numbered index or a specific definition section. Use this when you "
                "need to read a large Python file: first call with mode='index' to get "
                "the table of contents, then call with mode='section' and the section "
                "number to retrieve only the definition you need. "
                "This saves tokens compared to reading the entire file."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "read python file",
                "python file index",
                "python source code",
                "function list",
                "class index",
                "source code navigation",
                "Pythonファイルを読む",
                "関数一覧",
                "クラス一覧",
                "ソースコード解析",
            ],
        ),
        "x_search_terms_en": [
            "read python file",
            "python file index",
            "python source code",
            "function list",
            "class index",
            "source code navigation",
        ],
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the Python file.",
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["index", "section"],
                    "description": _(
                        "param.mode.description",
                        default=(
                            '"index" returns a numbered table of contents with line numbers. '
                            '"section" returns a specific definition by number.'
                        ),
                    ),
                },
                "section": {
                    "type": "integer",
                    "description": _(
                        "param.section.description",
                        default=(
                            "Section number to retrieve (used only when mode='section'). "
                            "Get the number from the index output."
                        ),
                    ),
                },
            },
            "required": ["path", "mode"],
            "additionalProperties": False,
        },
    },
}


class _PyIndexBuilder:
    """AST-based Python file section parser.

    Walks the AST to find top-level classes and functions, plus methods inside classes.
    Skips private entries starting with underscore unless they have a docstring.
    """

    def __init__(self, source: str, filepath: str = ""):
        self.source = source
        self.filepath = filepath
        self.lines = source.split("\n")
        self.entries: list[dict[str, Any]] = []
        self._parse()

    def _get_docstring(self, node: ast.AST) -> str:
        """Extract first line of docstring from a node."""
        body = getattr(node, "body", [])
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            doc = body[0].value.value
            if doc:
                return doc.strip().split("\n")[0][:80]
        return ""

    def _decorator_names(self, node: ast.AST) -> list[str]:
        """Return decorator names as strings."""
        names = []
        for dec in getattr(node, "decorator_list", []):
            if isinstance(dec, ast.Name):
                names.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                parts = []
                cur = dec
                while isinstance(cur, ast.Attribute):
                    parts.append(cur.attr)
                    cur = cur.value
                if isinstance(cur, ast.Name):
                    parts.append(cur.id)
                names.append(".".join(reversed(parts)))
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    names.append(dec.func.id)
                elif isinstance(dec.func, ast.Attribute):
                    names.append(dec.func.attr)
        return names

    def _node_label(self, node: ast.AST) -> str:
        label = type(node).__name__
        if isinstance(node, ast.FunctionDef):
            suffixes = []
            if node.name.startswith("_"):
                suffixes.append("private")
            decos = self._decorator_names(node)
            if decos:
                suffixes.append(f"@{','.join(decos)}")
            suffix = f" ({', '.join(suffixes)})" if suffixes else ""
            return f"def {node.name}{suffix}"
        elif isinstance(node, ast.AsyncFunctionDef):
            return f"async def {node.name}"
        elif isinstance(node, ast.ClassDef):
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(base.attr)
            base_str = f"({', '.join(bases)})" if bases else ""
            return f"class {node.name}{base_str}"
        return label

    def _is_public_or_documented(self, name: str, node: ast.AST) -> bool:
        """Include if public, or if private but has a docstring."""
        if not name.startswith("_"):
            return True
        return bool(self._get_docstring(node))

    def _parse(self):
        try:
            tree = ast.parse(self.source, filename=self.filepath)
        except SyntaxError as e:
            self.entries = [{"name": f"[SyntaxError] {e}", "line": e.lineno or 1, "end_line": e.lineno or 1, "level": 0, "label": "error"}]
            return

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not self._is_public_or_documented(node.name, node):
                    continue
                self.entries.append({
                    "name": node.name,
                    "line": node.lineno,
                    "end_line": node.end_lineno or node.lineno,
                    "level": 0,
                    "label": self._node_label(node),
                    "node": node,
                })
            elif isinstance(node, ast.ClassDef):
                if not self._is_public_or_documented(node.name, node):
                    continue
                methods = []
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not self._is_public_or_documented(child.name, child):
                            continue
                        methods.append({
                            "name": child.name,
                            "line": child.lineno,
                            "end_line": child.end_lineno or child.lineno,
                            "level": 1,
                            "label": self._node_label(child),
                            "node": child,
                        })
                self.entries.append({
                    "name": node.name,
                    "line": node.lineno,
                    "end_line": node.end_lineno or node.lineno,
                    "level": 0,
                    "label": self._node_label(node),
                    "node": node,
                    "methods": methods,
                })

    def build_index(self) -> str:
        if not self.entries:
            return _("msg.no_entries", default="(no public definitions found)")

        lines: list[str] = []
        idx = 0
        for entry in self.entries:
            idx += 1
            label = entry["label"]
            doc = self._get_docstring(entry["node"]) if "node" in entry else ""
            doc_str = f"  # {doc}" if doc else ""
            lines.append(f"  {idx}. L{entry['line']} {label}{doc_str}")
            for method in entry.get("methods", []):
                idx += 1
                mlabel = method["label"]
                mdoc = self._get_docstring(method["node"]) if "node" in method else ""
                mdoc_str = f"  # {mdoc}" if mdoc else ""
                lines.append(f"      {idx}. L{method['line']} {mlabel}{mdoc_str}")
        return "\n".join(lines)

    def _source_lines(self, entry: dict) -> str:
        """Extract source code lines for an entry."""
        start = entry["line"] - 1
        end = entry.get("end_line", entry["line"])
        code_lines = self.lines[start:end]
        # Strip trailing empty lines
        while code_lines and not code_lines[-1].strip():
            code_lines.pop()
        return "\n".join(code_lines)

    def get_section(self, number: int) -> str | None:
        """Return source code for the given section number (1-based)."""
        if number < 1:
            return None

        flat: list[dict] = []
        for entry in self.entries:
            flat.append(entry)
            flat.extend(entry.get("methods", []))

        if number > len(flat):
            return None

        target = flat[number - 1]
        return self._source_lines(target)

    def section_count(self) -> int:
        count = 0
        for entry in self.entries:
            count += 1
            count += len(entry.get("methods", []))
        return count


def run_tool(args: dict[str, Any]) -> str:
    path = args.get("path", "")
    mode = args.get("mode", "index")

    if not path:
        return _("err.path_required", default="Error: 'path' is required.")

    if not os.path.isfile(path):
        return _("err.file_not_found", default="Error: File not found: {path}", path=path)

    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception as e:
        return _("err.read_error", default="Error reading file: {e}", e=str(e))

    try:
        builder = _PyIndexBuilder(source, filepath=path)
    except Exception as e:
        return _("err.parse_error", default="Error parsing Python file: {e}", e=str(e))

    if mode == "index":
        toc = builder.build_index()
        total = builder.section_count()
        return _(
            "msg.index_output",
            default=(
                "Index for: {path}\n"
                "---\n"
                "{toc}\n"
                "---\n"
                "Total definitions: {total}\n"
                "To retrieve a definition, call py2idx with mode='section' and the section number."
            ),
            path=path,
            total=total,
            toc=toc,
        )

    elif mode == "section":
        section_num = args.get("section")
        if section_num is None:
            return _("err.section_required", default="Error: 'section' (integer) is required when mode='section'.")

        try:
            section_num = int(section_num)
        except (TypeError, ValueError):
            return _("err.section_invalid", default="Error: 'section' must be an integer.", section_num=repr(section_num))

        content = builder.get_section(section_num)
        if content is None:
            total = builder.section_count()
            return _(
                "err.section_not_found",
                default="Error: Section {section_num} not found. Valid range: 1..{last}.",
                section_num=section_num,
                last=total,
            )

        return content

    else:
        return _("err.invalid_mode", default="Error: Invalid mode '{mode}'. Use 'index' or 'section'.", mode=mode)
