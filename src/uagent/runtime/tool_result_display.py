"""Tool display modes and localized pre-execution action lines.

``UAGENT_SHOW_TOOL_RESULTS`` selects how much context the host shows:

* ``0``: the classic ``[TOOL] <ts> name=<tool> args=<masked-json>`` trace,
  and no result line.
* ``1``: the classic trace plus the bounded
  ``[TOOL-RESULT] ... summary=<derived>`` line after execution.
* ``2`` (default): a localized pre-execution action replaces the
  ``name=/args=`` trace body. Tools with a ``TOOL_DESCRIBER`` supply the
  action; other tools use the generic summary. On the CLI the display is
  a tree: when a describer supplied the action, a content tier under it
  lists the important arguments, and the result follows as the third
  tier (nested under its call, or naming the tool when other traces
  intervened, as with parallel batches).

Displayed text is flattened, secret-masked, and length-bounded so raw secrets
are not exposed through the display path.

The ``[TOOL]`` trace line's wall-clock timestamp is opt-in via
``UAGENT_TOOL_TRACE_TIMESTAMP``: it is noise in the common case, so it is
shown only when explicitly enabled (``1``/``true``/``yes``/``on``).
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
    Silently treating an unrecognized value as enabled could make a typo
    unexpectedly show tool activity.
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

    return parse_tool_result_display_mode(env_get("UAGENT_SHOW_TOOL_RESULTS", "2"))


_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def tool_trace_timestamp_enabled() -> bool:
    """Whether ``[TOOL]`` trace lines carry a wall-clock timestamp.

    Opt-in via ``UAGENT_TOOL_TRACE_TIMESTAMP``; unset or any other
    value keeps the timestamp off.
    """

    raw = str(env_get("UAGENT_TOOL_TRACE_TIMESTAMP", "") or "").strip().lower()
    return raw in _TRUE_VALUES


def bound_display_text(text: Any, *, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """Secret-mask, flatten, and bound one display line.

    Masking runs on the raw text first: several header patterns anchor
    to line boundaries, which flattening would destroy (a multi-line
    summary's ``Authorization:`` line would slip past them). It runs
    again after flattening to catch anything the join creates.
    """

    if max_chars <= 0:
        return ""
    masked = _mask_inline_secrets(str("" if text is None else text))
    flat = " ".join(masked.split())
    return _mask_inline_secrets(flat)[:max_chars]
