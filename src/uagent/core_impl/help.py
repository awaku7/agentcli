"""Help text (split from core.py)."""

from __future__ import annotations

import sys

from ..i18n import _


def print_help(topic: str | None = None) -> None:
    """Print help for the :help command.

    Single source of truth: uagent.util_tools.format_help().
    Optional topic enables detailed help (:help tools, :help skills install).
    """

    try:
        from .. import util_tools

        text = util_tools.format_help(core=sys.modules[__name__], topic=topic)
        print(text)
    except Exception as e:
        # Fallback: minimal help (avoid breaking interactive use)
        print(
            _(":help  (help unavailable: %(err)s)")
            % {"err": f"{type(e).__name__}: {e}"}
        )
