"""Dispatch noninteractive session commands before CLI startup side effects."""

from __future__ import annotations

import sys


def main() -> int:
    if sys.argv[1:2] == ["setup"]:
        if sys.argv[2:3] == ["--cli"]:
            from .setup_cli import main as setup_cli_main

            return setup_cli_main()
        from .setup_gui import main as setup_gui_main

        return setup_gui_main()
    if sys.argv[1:2] == ["session"]:
        from .session_cli import main as session_main

        return session_main(sys.argv[2:])
    if sys.argv[1:2] == ["admin"]:
        from .admin_pairing import main as admin_main

        return admin_main(sys.argv[2:])
    from .runtime.startup_timing import checkpoint

    checkpoint("cli_entry")
    from .cli import main as interactive_main

    checkpoint("cli_imported")
    return interactive_main()
