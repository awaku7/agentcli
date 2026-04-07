from __future__ import annotations

import sys

from .env_validate import format_missing_env_message, validate_startup_env


def validate_or_exit_startup_env(*, context: str) -> None:
    """Validate required env vars at startup; print all missing items then exit."""

    provider, missing, warnings = validate_startup_env()

    if missing:
        msg = format_missing_env_message(
            missing=missing, warnings=warnings, context=context
        )
        sys.__stderr__.write(msg)
        try:
            sys.__stderr__.flush()
        except Exception:
            pass
        sys.exit(2)

    if warnings:
        for w in warnings:
            print(f"[WARN] {w}", file=sys.stderr)
