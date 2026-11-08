from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from uagent.tools.code_map_impl import tree_sitter_symbols as tree_sitter_module
from uagent.tools.code_map_impl.symbols import extract_symbols
from uagent.tools.code_map_impl.tree_sitter_symbols import (
    extract_tree_sitter_symbols,
)


@pytest.mark.parametrize(
    ("filename", "language", "source", "expected"),
    [
        (
            "sample.py",
            "Python",
            "class Demo:\n    def greet(self):\n        return 1\n",
            {"Demo": (1, "class"), "greet": (2, "function")},
        ),
        (
            "sample.js",
            "JavaScript",
            "class Demo {}\nfunction greet() {}\nconst value = 1;\n",
            {
                "Demo": (1, "class"),
                "greet": (2, "function"),
                "value": (3, "symbol"),
            },
        ),
    ],
)
def test_tree_sitter_extracts_symbols(
    tmp_path: Path,
    filename: str,
    language: str,
    source: str,
    expected: dict[str, tuple[int, str]],
) -> None:
    pytest.importorskip("tree_sitter_language_pack")
    path = tmp_path / filename
    path.write_text(source, encoding="utf-8")

    pack = tree_sitter_module._load_language_pack()
    assert pack is not None, "Optional Tree-sitter pack failed to initialize"
    try:
        parser = pack.get_parser(tree_sitter_module.TREE_SITTER_LANGUAGE_BY_SOURCE[language])
        raw = path.read_bytes()
        parse_bytes = getattr(parser, "parse_bytes", None)
        tree = parse_bytes(raw) if callable(parse_bytes) else parser.parse(raw)
        assert tree is not None
        root = tree_sitter_module._node_value(tree, "root_node")
        assert root is not None
    except Exception as exc:
        pytest.fail(f"Language-pack parser preflight failed: {type(exc).__name__}: {exc!r}")

    symbols = extract_tree_sitter_symbols(str(path), language)
    actual = {item["name"]: (item["line"], item["type"]) for item in symbols}
    assert actual == expected, (
        f"root={root!r}, root_type={tree_sitter_module._node_type(root)!r}, "
        f"named_children={len(tree_sitter_module._node_children(root))}"
    )


def test_vba_and_lotusscript_keep_regex_support(tmp_path: Path) -> None:
    vba = tmp_path / "module.bas"
    lotus = tmp_path / "agent.lss"
    vba.write_text("Public Sub RunReport()\nEnd Sub\n", encoding="utf-8")
    lotus.write_text("Function BuildAgent()\nEnd Function\n", encoding="utf-8")

    assert extract_symbols(str(vba)) == [
        {"name": "RunReport", "line": 1, "type": "function"}
    ]
    assert extract_symbols(str(lotus)) == [
        {"name": "BuildAgent", "line": 1, "type": "function"}
    ]


def test_tree_sitter_new_method_based_binding(monkeypatch, tmp_path: Path) -> None:
    """The modern pack accepts bytes via parse_bytes and uses node methods."""
    source = "class Demo:\n    def greet(self):\n        return 1\n"
    source_bytes = source.encode("utf-8")
    path = tmp_path / "new.py"
    path.write_text(source, encoding="utf-8")

    class Node:
        def __init__(self, kind, text, row, children=(), name=None):
            self._kind = kind
            self._text = text
            self._row = row
            self._children = list(children)
            self._name = name

        def kind(self):
            return self._kind

        def named_child_count(self):
            return len(self._children)

        def named_child(self, index):
            return self._children[index]

        def child_by_field_name(self, field):
            return self._name if field == "name" else None

        def start_byte(self):
            return source_bytes.index(self._text.encode("utf-8"))

        def end_byte(self):
            return self.start_byte() + len(self._text.encode("utf-8"))

        def start_position(self):
            return SimpleNamespace(row=self._row)

        def end_position(self):
            return SimpleNamespace(row=self._row)

    name_cls = Node("identifier", "Demo", 0)
    name_fn = Node("identifier", "greet", 1)
    method = Node("function_definition", "def greet", 1, [name_fn], name_fn)
    cls = Node("class_definition", "class Demo", 0, [name_cls, method], name_cls)
    root = Node("module", "class Demo", 0, [cls])

    class Tree:
        def root_node(self):
            return root

    class Parser:
        def parse_bytes(self, data):
            assert data == source_bytes
            return Tree()

    monkeypatch.setattr(
        tree_sitter_module,
        "_load_language_pack",
        lambda: SimpleNamespace(get_parser=lambda language: Parser()),
    )

    symbols = extract_tree_sitter_symbols(str(path), "Python")
    assert {(item["name"], item["line"], item["type"]) for item in symbols} == {
        ("Demo", 1, "class"),
        ("greet", 2, "function"),
    }


def test_tree_sitter_legacy_property_binding(monkeypatch, tmp_path: Path) -> None:
    """The old core tree-sitter Parser/Node attributes remain supported."""
    path = tmp_path / "legacy.py"
    source = b"class Demo:\n"
    path.write_bytes(source)
    identifier = SimpleNamespace(
        type="identifier",
        text=b"Demo",
        named_children=[],
        start_point=(0, 6),
        end_point=(0, 10),
    )
    cls = SimpleNamespace(
        type="class_definition",
        named_children=[identifier],
        child_by_field_name=lambda field: identifier if field == "name" else None,
        start_point=(0, 0),
        end_point=(0, 11),
    )
    root = SimpleNamespace(
        type="module",
        named_children=[cls],
    )

    class Parser:
        def parse(self, data):
            assert data == source
            return SimpleNamespace(root_node=root)

    monkeypatch.setattr(
        tree_sitter_module,
        "_load_language_pack",
        lambda: SimpleNamespace(get_parser=lambda language: Parser()),
    )

    symbols = extract_tree_sitter_symbols(str(path), "Python")
    assert [(item["name"], item["line"], item["type"]) for item in symbols] == [
        ("Demo", 1, "class")
    ]
