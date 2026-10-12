"""Trusted tool execution status kept separate from a string result body.

Raw file and HTTP payloads can be arbitrary JSON or translated text; they must
not be interpreted as the status of the tool that retrieved them.
"""

from __future__ import annotations

from typing import Any


class ToolExecutionText(str):
    """A string-compatible result with an explicit, non-serialized outcome."""

    def __new__(cls, text: str, *, status: str = "success") -> "ToolExecutionText":
        if status not in {"success", "failed", "timeout", "cancelled"}:
            raise ValueError(f"unsupported tool execution status: {status}")
        obj = super().__new__(cls, text)
        obj._uag_execution_status = status
        return obj

    def format(self, *args: Any, **kwargs: Any) -> "ToolExecutionText":
        """Keep the trusted outcome across deferred translated formatting."""
        return ToolExecutionText(
            super().format(*args, **kwargs), status=self._uag_execution_status
        )

    def __mod__(self, value: Any) -> "ToolExecutionText":
        return ToolExecutionText(
            super().__mod__(value), status=self._uag_execution_status
        )
