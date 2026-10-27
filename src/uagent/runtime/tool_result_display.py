"""Tool display modes and localized pre-execution action lines.

``UAGENT_SHOW_TOOL_RESULTS`` selects how much context the host shows:

* ``0`` (default): the classic ``[TOOL] <ts> name=<tool> args=<masked-json>``
  trace, and no result line.
* ``1``: the classic trace plus the bounded
  ``[TOOL-RESULT] ... summary=<derived>`` line after execution.
* ``2``: the tool's own localized action sentence replaces the
  ``name=/args=`` body of the pre-execution trace, and no result line is
  printed. The sentence comes from the tool's ``TOOL_DESCRIBER``.

Mode ``2`` degrades to the classic trace body when a tool has no describer,
when the describer raises, or when it returns an empty value. Described text is
always flattened, secret-masked, and length-bounded here, so a tool cannot leak
a raw payload through the display path even if it tries.
"""

from __future__ import annotations

from typing import Any

from ..env_utils import env_get
from ..utils.secret_mask import _mask_inline_secrets

MODE_OFF = 0
MODE_DEFAULT = 1
MODE_LOCALIZED = 2

DEFAULT_MAX_CHARS = 400

_OFF_VALUES = frozenset({"", "0", "false", "no", "off", "none", "disable", "disabled"})
_DEFAULT_VALUES = frozenset({"1", "true", "yes", "on"})
_LOCALIZED_VALUES = frozenset(
    {"2", "summary", "summaries", "localized", "localize", "i18n"}
)


def parse_tool_result_display_mode(value: Any = None) -> int:
    """Return 0, 1, or 2 for a raw display-mode value.

    Unknown values disable both the localized trace and the result line.
    Silently treating an unrecognized value as "on" would change the
    documented opt-in default.
    """

    raw = str("" if value is None else value).strip().lower()
    if raw in _LOCALIZED_VALUES:
        return MODE_LOCALIZED
    if raw in _DEFAULT_VALUES:
        return MODE_DEFAULT
    if raw in _OFF_VALUES:
        return MODE_OFF
    return MODE_OFF


def tool_result_display_mode() -> int:
    """Return the effective tool display mode for this process."""

    return parse_tool_result_display_mode(env_get("UAGENT_SHOW_TOOL_RESULTS", "0"))


def bound_display_text(text: Any, *, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """Flatten, secret-mask, and bound one display line."""

    if max_chars <= 0:
        return ""
    flat = " ".join(str("" if text is None else text).split())
    return _mask_inline_secrets(flat)[:max_chars]
