from __future__ import annotations

import sys

from .env_validate import format_missing_env_message, validate_startup_env
from .i18n import _


def validate_or_exit_startup_env(*, context: str) -> None:
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
            print(
                _("env.warn.prefix", default="[WARN] {message}", message=w),
                file=sys.stderr,
            )
