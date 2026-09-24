"""Portable package commands, without loading a provider or executing tools."""

from __future__ import annotations

import argparse
import getpass
import sys
import warnings


def restore_imported_session(core, store, messages: list, session_id: str) -> None:
    """Restore dialogue under freshly initialized local instructions/context."""
    from .runtime.session_portability import snapshot
    from .runtime.session_restore import bind_session, clear_response_continuation_state

    if store is None or store.get_portable_metadata(session_id) is None:
        raise ValueError("portable session unavailable")
    if store.get_session(session_id).get("principal_id"):
        raise ValueError("identity-bound sessions require Web authorization")
    conversation = snapshot(store, session_id)["conversation"]
    clear_response_continuation_state(core)
    messages.extend(conversation)
    bind_session(core=core, store=store, session_id=session_id)


def read_passphrase(*, confirm: bool = False) -> str:
    # Never silently fall back to echoed stdin (including a Web worker).
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        value = getpass.getpass("Package passphrase: ")
        if confirm and value != getpass.getpass("Confirm passphrase: "):
            raise ValueError("passphrases do not match")
    return value


def main(argv: list[str] | None = None) -> int:
    from .runtime.session_portability import export_file, import_file
    from .runtime.session_store import SessionStore

    parser = argparse.ArgumentParser(prog="uag session")
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export", help="export an encrypted .uag package")
    export.add_argument("session_id")
    export.add_argument("-o", "--output", required=True)
    imp = sub.add_parser("import", help="import into a new detached session")
    imp.add_argument("path")
    resume = sub.add_parser("resume", help="resume an imported local session")
    resume.add_argument("session_id")
    args = parser.parse_args(argv)
    try:
        store = SessionStore.from_environment()
        if store is None:
            raise ValueError("Session store is not enabled")
        with store:
            if args.command == "export":
                export_file(
                    store, args.session_id, args.output, read_passphrase(confirm=True)
                )
                print("Encrypted session exported.")
            elif args.command == "import":
                session = import_file(store, args.path, read_passphrase())
                print(session.session_id)
            else:
                if store.get_portable_metadata(args.session_id) is None:
                    raise ValueError("use :sessions load for a non-portable session")
                # Authenticated Web sessions must be resumed through Web policy.
                if store.get_session(args.session_id).get("principal_id"):
                    raise ValueError("resume this identity-bound session through Web")
        if args.command == "resume":
            sys.argv = [sys.argv[0]]
            from . import cli

            cli.core._portable_resume_id = args.session_id
            return cli.main()
        return 0
    except (ValueError, RuntimeError, OSError, getpass.GetPassWarning) as exc:
        print(f"Session operation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
