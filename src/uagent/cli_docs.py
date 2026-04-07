from __future__ import annotations

import sys


def _handle_docs_cli() -> None:
    """Handle `uag docs` subcommand.

    Spec (mode A):
      - `uag docs` => list
      - `uag docs <name>` => show content
      - `uag docs --path <name>` => print filesystem path
      - `uag docs --open <name>` => open with OS default app

    Docs are bundled under `scheck/docs/` and resolved via importlib.resources.
    """
    from . import docs_util

    args = sys.argv[2:]

    if not args:
        print(docs_util.format_docs_list(docs_util.list_docs()))
        return

    if args[0] in ("--help", "-h"):
        print(docs_util.format_docs_list(docs_util.list_docs()))
        return

    if args[0] in ("--path", "--open"):
        if len(args) < 2:
            print("[docs] name is required", file=sys.stderr)
            print(docs_util.format_docs_list(docs_util.list_docs()))
            sys.exit(2)

        name = args[1]
        p = docs_util.get_doc_path(name)
        if args[0] == "--path":
            print(str(p))
            return

        docs_util.open_path_with_os(p)
        return

    name = args[0]
    text = docs_util.read_doc_text(name)
    print(text)
