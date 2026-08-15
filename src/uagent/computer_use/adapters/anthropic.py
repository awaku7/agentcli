"""Anthropic native Computer Use adapter."""

from __future__ import annotations

import base64
from typing import Any

from ..actions import ComputerAction, normalize_action
from ..capability import ComputerUseCapabilityError
from ..results import ComputerActionResult


def _get(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


class AnthropicComputerAdapter:
    """Convert Anthropic Computer Tool messages to UAG primitives."""

    provider = "anthropic"

    def build_tool(
        self,
        capability: Any,
        *,
        width: int,
        height: int,
        display_number: int = 1,
    ) -> dict[str, Any]:
        """Build the schema-less native Anthropic Computer Tool payload."""
        if not getattr(capability, "supported", False) or not getattr(
            capability, "native", False
        ):
            raise ComputerUseCapabilityError(
                "Anthropic adapter requires a native Computer Use capability"
            )
        tool_type = getattr(capability, "tool_type", None)
        if not tool_type:
            raise ComputerUseCapabilityError("Anthropic tool_type is missing")
        tool = {
            "type": tool_type,
            "name": "computer",
            "display_width_px": int(width),
            "display_height_px": int(height),
            "display_number": int(display_number),
        }
        if getattr(capability, "enable_zoom", False):
            tool["enable_zoom"] = True
        return tool

    def beta_headers(self, capability: Any) -> list[str]:
        """Return the beta headers required by the capability."""
        header = getattr(capability, "beta_header", None)
        return [str(header)] if header else []

    def parse_actions(self, response: Any) -> list[ComputerAction]:
        """Parse Anthropic ``tool_use`` blocks into normalized actions."""
        actions: list[ComputerAction] = []
        for block in _get(response, "content", []) or []:
            if _get(block, "type") != "tool_use":
                continue
            action_id = _get(block, "id")
            payload = _get(block, "input", {}) or {}
            if not action_id:
                raise ValueError("Anthropic tool_use block has no id")
            actions.append(
                normalize_action(
                    action_id=str(action_id),
                    payload=dict(payload),
                    provider=self.provider,
                )
            )
        return actions

    def build_tool_result(
        self,
        action: ComputerAction,
        result: ComputerActionResult,
    ) -> dict[str, Any]:
        """Build an Anthropic ``tool_result`` content block."""
        if result.action_id != action.action_id:
            raise ValueError("tool result action_id does not match action")
        content: list[dict[str, Any]] = []
        if result.screenshot is not None:
            screenshot = result.screenshot
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": screenshot.media_type,
                        "data": base64.b64encode(screenshot.data).decode("ascii"),
                    },
                }
            )
        if result.error:
            content.append({"type": "text", "text": result.error})
        elif not content:
            content.append({"type": "text", "text": "ok"})
        return {
            "type": "tool_result",
            "tool_use_id": action.action_id,
            "content": content,
            "is_error": not result.success,
        }
