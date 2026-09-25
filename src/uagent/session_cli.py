"""Portable package commands, without loading a provider or executing tools."""

from __future__ import annotations

import argparse
import getpass
import os
import queue
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


def _getpass_no_echo(prompt: str) -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        return getpass.getpass(prompt)


def read_passphrase(*, confirm: bool = False, prompt_fn=None) -> str:
    # Never silently fall back to echoed stdin (including a Web worker).
    prompt_fn = prompt_fn or _getpass_no_echo
    value = prompt_fn("Package passphrase: ")
    if confirm and value != prompt_fn("Confirm passphrase: "):
        raise ValueError("passphrases do not match")
    return value


def read_cli_passphrase(core, prompt: str) -> str:
    """Request a hidden passphrase through the CLI's single stdin owner.

    The main command dispatcher must not call getpass directly: stdin_loop is
    already reading the same terminal in another thread. Reuse its existing
    password-reply channel so only that loop consumes terminal input.
    """
    lock = getattr(core, "human_ask_lock", None)
    if lock is None:
        raise RuntimeError("CLI password input is unavailable")

    reply_queue = queue.Queue(maxsize=1)
    with lock:
        if getattr(core, "human_ask_active", False):
            raise RuntimeError("another interactive input is already active")
        core.human_ask_queue = reply_queue
        core.human_ask_active = True
        core.human_ask_is_password = True
        core.human_ask_multiline_active = False
        core.human_ask_prompt = prompt
        lines = getattr(core, "human_ask_lines", None)
        if lines is not None:
            lines.clear()

    try:
        # Releasing BUSY lets stdin_loop relinquish its normal prompt and
        # enter the secure human_ask password path.
        set_status = getattr(core, "set_status", None)
        if callable(set_status):
            set_status(False, "")

        try:
            timeout = float(os.environ.get("UAGENT_HUMAN_ASK_TIMEOUT_SEC", "300"))
        except (TypeError, ValueError):
            timeout = 300.0
        if timeout <= 0:
            timeout = 300.0
        try:
            value = reply_queue.get(timeout=timeout)
        except queue.Empty as exc:
            raise TimeoutError("passphrase input timed out") from exc
        if value is None:
            raise ValueError("passphrase input cancelled")
        return str(value)
    finally:
        with lock:
            # Do not clear a newer request if ownership changed unexpectedly.
            if getattr(core, "human_ask_queue", None) is reply_queue:
                core.human_ask_active = False
                core.human_ask_is_password = False
                core.human_ask_multiline_active = False
                core.human_ask_prompt = ""
                core.human_ask_queue = None


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
