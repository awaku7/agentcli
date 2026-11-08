"""Preload optional Tree-sitter grammar assets before the CI test suite.

Recent language-pack releases fetch parser data on first use. Download it
during setup, with explicit retry and version diagnostics, not from pytest.
"""

from __future__ import annotations

from importlib.metadata import version
from time import sleep

from tree_sitter_language_pack import get_parser


def main() -> None:
    print(
        f"Preloading tree-sitter-language-pack {version('tree-sitter-language-pack')}",
        flush=True,
    )
    samples = {
        "python": "class Demo:\n    pass\n",
        "javascript": "class Demo {}\n",
    }
    for language, source in samples.items():
        for attempt in range(1, 4):
            try:
                parser = get_parser(language)
                parse_bytes = getattr(parser, "parse_bytes", None)
                tree = (
                    parse_bytes(source.encode("utf-8"))
                    if callable(parse_bytes)
                    else parser.parse(source.encode("utf-8"))
                )
                if tree is None:
                    raise RuntimeError("parser returned no tree")
                root = getattr(tree, "root_node", None)
                if callable(root):
                    root = root()
                if root is None:
                    raise RuntimeError("parsed tree has no root")
            except Exception as error:
                print(
                    f"{language} grammar preload attempt {attempt}/3 failed: "
                    f"{type(error).__name__}: {error}",
                    flush=True,
                )
                if attempt == 3:
                    raise
                sleep(attempt * 3)
            else:
                print(f"{language} grammar ready", flush=True)
                break


if __name__ == "__main__":
    main()
