"""User-visible compatibility helpers for legacy context recovery paths."""

from __future__ import annotations

from typing import Any

from ..i18n import _
from .context_recovery import ContextRecoveryManager


def rollback_largest_recent_history(
    messages: list[dict[str, Any]], *, lookback: int = 10
) -> dict[str, int] | None:
    """Apply the bounded legacy rollback with the shared translated notice."""

    def _notice(lookback_count: int, removed: int, size: int) -> dict[str, Any]:
        return {
            "role": "system",
            "content": _(
                "context.rollback_notice",
                default=(
                    "The context limit was exceeded. The largest message among the "
                    "last %(lookback)d messages and all following messages were removed "
                    "(%(removed)d message(s), largest size %(size)d bytes). "
                    "Re-plan any removed tool operation; do not assume it completed."
                ),
                lookback=lookback_count,
                removed=removed,
                size=size,
            ),
            "_uagent_internal": True,
        }

    return ContextRecoveryManager.apply_legacy_bounded_rollback(
        messages,
        lookback=lookback,
        notice_builder=_notice,
    )


__all__ = ["rollback_largest_recent_history"]
