"""Dispatch noninteractive session commands before CLI startup side effects."""

from __future__ import annotations

import sys


def main() -> int:
    if sys.argv[1:2] == ["session"]:
        from .session_cli import main as session_main

        return session_main(sys.argv[2:])
    if sys.argv[1:2] == ["admin"]:
        from .admin_pairing import main as admin_main

        return admin_main(sys.argv[2:])
    from .cli import main as interactive_main
    from .runtime.process_registry import clear_tracking

    try:
        return interactive_main()
    finally:
        clear_tracking("cli")
