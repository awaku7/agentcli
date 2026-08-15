"""Custom-harness adapter for OpenAI-compatible/local tool calls."""

from __future__ import annotations

import base64
import json
from typing import Any

from ..actions import ComputerAction, normalize_action
from ..results import ComputerActionResult


def _get(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


class CustomComputerAdapter:
    """Convert ordinary function/tool calls into ComputerAction values."""

    provider = "custom"

    def parse_actions(
        self,
        response: Any,
        *,
        turn_id: str = "custom",
    ) -> list[ComputerAction]:
        actions: list[ComputerAction] = []
        for index, call in enumerate(_get(response, "tool_calls", []) or []):
            call_id = _get(call, "id") or f"{turn_id}:{index}"
            function = _get(call, "function", {}) or {}
            name = _get(function, "name")
            arguments = _get(function, "arguments", {}) or {}
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            actions.append(
                normalize_action(
                    action_id=str(call_id),
                    payload={"action": name, **dict(arguments)},
                    provider=self.provider,
                )
            )
        return actions

    def build_tool_result(
        self,
        action: ComputerAction,
        result: ComputerActionResult,
    ) -> dict[str, Any]:
        content: list[dict[str, Any]] = []
        if result.screenshot is not None:
            screenshot = result.screenshot
            content.append(
                {
                    "type": "image",
                    "media_type": screenshot.media_type,
                    "data": base64.b64encode(screenshot.data).decode("ascii"),
                }
            )
        content.append(
            {
                "type": "text",
                "text": "ok" if result.success else (result.error or "action failed"),
            }
        )
        return {"tool_call_id": action.action_id, "content": content}
