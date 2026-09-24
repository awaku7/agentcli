"""Dispatch noninteractive session commands before CLI startup side effects."""

from __future__ import annotations

import sys


def main() -> int:
    if sys.argv[1:2] == ["session"]:
        from .session_cli import main as session_main

        return session_main(sys.argv[2:])
    from .cli import main as interactive_main

    return interactive_main()
