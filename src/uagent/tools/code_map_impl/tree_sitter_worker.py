"""Line-based worker protocol for native Tree-sitter symbol extraction."""

from __future__ import annotations

import json
import sys

from .tree_sitter_symbols import extract_tree_sitter_symbols


def main() -> None:
    for line in sys.stdin:
        try:
            request = json.loads(line)
            symbols = extract_tree_sitter_symbols(request["path"], request["language"])
        except Exception:
            symbols = []
        sys.stdout.write(json.dumps(symbols, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
