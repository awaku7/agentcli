"""Tree-sitter backed symbol extraction for :mod:`code_map`.

The language pack is optional.  It is installed lazily on the first supported
source file so importing ``code_map`` remains cheap and environments that only
use the non-source features do not pay the dependency cost.  If installation,
parser loading, or parsing fails, callers can safely fall back to the legacy
regular-expression extractor.
"""

from __future__ import annotations

import os
import threading
from typing import Any

from ..._pip_auto import install_with_status

# The pack provides pre-built grammars and a compatible tree-sitter Parser API.
# Keep this list deliberately conservative: languages without a known parser
# mapping continue to use the existing regex implementation.
TREE_SITTER_LANGUAGE_BY_SOURCE: dict[str, str] = {
    "Python": "python",
    "TypeScript": "typescript",
    "TypeScript (React)": "tsx",
    "JavaScript": "javascript",
    "JavaScript (React)": "tsx",
    "Go": "go",
    "Rust": "rust",
    "C": "c",
    "C++": "cpp",
    "C/C++ Header": "c",
    "C++ Header": "cpp",
    "C#": "csharp",
    "Java": "java",
    "Kotlin": "kotlin",
    "Kotlin Script": "kotlin",
    "Swift": "swift",
    "Ruby": "ruby",
    "PHP": "php",
    "Scala": "scala",
    "Dart": "dart",
    "Lua": "lua",
}

_FUNCTION_NODE_TYPES = {
    "function_definition",
    "function_declaration",
    "function_item",
    "method_definition",
    "method_declaration",
    "constructor_declaration",
    "operator_declaration",
    "function_expression",
    "generator_function",
    "generator_function_declaration",
    "lambda_expression",
    "method",
    "singleton_method",
    "init_declaration",
}

_CLASS_NODE_TYPES = {
    "class_definition",
    "class_declaration",
    "class_specifier",
    "record_declaration",
    "class",
}

_INTERFACE_NODE_TYPES = {
    "interface_declaration",
    "protocol_declaration",
}

_STRUCT_NODE_TYPES = {
    "struct_specifier",
    "struct_item",
    "struct_declaration",
}

_ENUM_NODE_TYPES = {
    "enum_specifier",
    "enum_declaration",
}

_MODULE_NODE_TYPES = {
    "namespace_definition",
    "namespace_declaration",
    "module",
    "module_declaration",
    "object_declaration",
    "trait_item",
    "impl_item",
    "extension_declaration",
    "mod_item",
    "object_definition",
    "trait_definition",
    "mixin_declaration",
}

_ALIAS_NODE_TYPES = {
    "type_alias_declaration",
    "type_declaration",
    "type_item",
}

_VARIABLE_NODE_TYPES = {
    "variable_declarator",
    "const_spec",
    "var_spec",
    "property_declaration",
}

_NAME_NODE_TYPES = {
    "identifier",
    "type_identifier",
    "field_identifier",
    "property_identifier",
    "namespace_identifier",
    "constant",
    "name",
}

# Installation and parser loading can happen concurrently when a caller scans
# several files.  Keep the one-time operation serialized and cache both the
# successful module and a failed attempt for the lifetime of the process.
_PACK_LOCK = threading.Lock()
_PACK: Any | None = None
_PACK_ATTEMPTED = False


def _load_language_pack() -> Any | None:
    """Return the optional language pack, installing it once if necessary."""
    global _PACK, _PACK_ATTEMPTED

    if _PACK_ATTEMPTED:
        return _PACK
    with _PACK_LOCK:
        if _PACK_ATTEMPTED:
            return _PACK
        _PACK_ATTEMPTED = True

        if os.environ.get("UAGENT_CODE_MAP_TREE_SITTER", "1").lower() in {
            "0",
            "false",
            "no",
            "off",
        }:
            return None

        if not install_with_status(
            "tree-sitter-language-pack",
            "tree_sitter_language_pack",
            display_name="tree-sitter-language-pack",
            version_spec=">=1.14.3",
        ):
            return None
        try:
            import tree_sitter_language_pack as pack
        except Exception:
            return None
        _PACK = pack
        return _PACK


def _node_type(node: Any) -> str:
    """Get a node type across supported tree-sitter Python bindings."""
    value = getattr(node, "type", None)
    if value is None:
        value = getattr(node, "kind", "")
    return str(value)


def _node_children(node: Any) -> list[Any]:
    """Return named children without depending on one binding's API shape."""
    children = getattr(node, "named_children", None)
    if children is not None:
        try:
            return list(children)
        except TypeError:
            pass
    children = getattr(node, "children", ())
    return [child for child in children if getattr(child, "is_named", True)]


def _field_child(node: Any, field_name: str) -> Any | None:
    try:
        return node.child_by_field_name(field_name)
    except (AttributeError, TypeError, ValueError):
        return None


def _find_name_node(node: Any, depth: int = 0) -> Any | None:
    """Find the semantic name child used by common Tree-sitter grammars."""
    for field_name in ("name", "declarator", "type", "left"):
        child = _field_child(node, field_name)
        if child is not None:
            if _node_type(child) in _NAME_NODE_TYPES:
                return child
            if depth < 4:
                nested = _find_name_node(child, depth + 1)
                if nested is not None:
                    return nested

    for child in _node_children(node):
        if _node_type(child) in _NAME_NODE_TYPES:
            return child
    if depth >= 4:
        return None
    for child in _node_children(node):
        nested = _find_name_node(child, depth + 1)
        if nested is not None:
            return nested
    return None


def _node_text(node: Any, source: bytes) -> str:
    """Read node text, supporting bindings with and without ``Node.text``."""
    value = getattr(node, "text", None)
    if value is not None:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)
    try:
        return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
    except (AttributeError, TypeError):
        return ""


def _symbol_type(node_type: str, source_language: str) -> str | None:
    if node_type in _FUNCTION_NODE_TYPES:
        return "function"
    if node_type in _CLASS_NODE_TYPES:
        return "class"
    if node_type in _INTERFACE_NODE_TYPES:
        return "interface"
    if node_type in _STRUCT_NODE_TYPES:
        return "struct"
    if node_type in _ENUM_NODE_TYPES:
        return "enum"
    if node_type in _MODULE_NODE_TYPES and not (
        node_type == "module" and source_language == "Python"
    ):
        return "module"
    if node_type in _ALIAS_NODE_TYPES:
        return "type"
    if node_type in _VARIABLE_NODE_TYPES:
        return "symbol"
    return None


def extract_tree_sitter_symbols(
    filepath: str, source_language: str
) -> list[dict[str, Any]]:
    """Extract symbols with Tree-sitter, or return an empty list on failure.

    The empty-list contract is intentional: ``symbols.extract_symbols`` uses it
    to select the established regex fallback when a grammar is unavailable or
    a source file is not understood by the parser.
    """
    language_name = TREE_SITTER_LANGUAGE_BY_SOURCE.get(source_language)
    if language_name is None:
        return []

    try:
        with open(filepath, "rb") as source_file:
            source = source_file.read()
    except OSError:
        return []

    pack = _load_language_pack()
    if pack is None:
        return []

    try:
        parser = pack.get_parser(language_name)
        tree = parser.parse(source)
        root = tree.root_node
    except Exception:
        return []

    symbols: list[dict[str, Any]] = []
    seen: set[str] = set()

    def visit(node: Any) -> None:
        node_type = _node_type(node)
        symbol_type = _symbol_type(node_type, source_language)
        if symbol_type is not None:
            name_node = _find_name_node(node)
            if name_node is not None:
                name = _node_text(name_node, source).strip()
                if (
                    name
                    and name not in seen
                    and name
                    not in {
                        "if",
                        "else",
                        "for",
                        "while",
                        "switch",
                        "return",
                        "import",
                        "from",
                    }
                ):
                    start_point = getattr(node, "start_point", (0, 0))
                    symbols.append(
                        {
                            "name": name,
                            "line": int(start_point[0]) + 1,
                            "type": symbol_type,
                        }
                    )
                    seen.add(name)
        for child in _node_children(node):
            visit(child)

    try:
        visit(root)
    except Exception:
        return []
    return symbols


__all__ = ["extract_tree_sitter_symbols"]
