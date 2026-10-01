"""Anthropic native Computer Use adapter."""

from __future__ import annotations

import base64
from typing import Any

from ..actions import ComputerAction, normalize_action
from ..capability import ComputerUseCapabilityError
from ..results import ComputerActionResult

ANTHROPIC_COMPUTER_TOOLSET = "computer_toolset_20260801"
ANTHROPIC_COMPUTER_MEMBERS = frozenset(
    {
        "screenshot",
        "left_click",
        "right_click",
        "middle_click",
        "double_click",
        "triple_click",
        "left_click_drag",
        "mouse_move",
        "scroll",
        "type",
        "key",
        "wait",
    }
)
ANTHROPIC_DISABLED_MEMBERS = frozenset(
    {"zoom", "left_mouse_down", "left_mouse_up", "cursor_position", "hold_key"}
)
ANTHROPIC_NOT_EXECUTED = "Not executed: an earlier computer action in this turn failed."


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
        if tool_type == ANTHROPIC_COMPUTER_TOOLSET:
            return {
                "type": ANTHROPIC_COMPUTER_TOOLSET,
                "configs": {
                    name: {"enabled": False}
                    for name in sorted(ANTHROPIC_DISABLED_MEMBERS)
                },
            }
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
        """Parse legacy Computer Tool and toolset member calls."""
        actions: list[ComputerAction] = []
        for block in _get(response, "content", []) or []:
            if _get(block, "type") != "tool_use":
                continue
            action_id = _get(block, "id")
            payload = _get(block, "input", {}) or {}
            if not action_id:
                raise ValueError("Anthropic tool_use block has no id")
            toolset_name = _get(block, "toolset_name")
            if toolset_name is not None:
                if toolset_name != "computer":
                    continue
                member = str(_get(block, "name") or "")
                if member not in ANTHROPIC_COMPUTER_MEMBERS:
                    raise ValueError(
                        f"unsupported Anthropic computer toolset member: {member or '<empty>'}"
                    )
                payload = self._normalize_member_input(member, dict(payload))
            actions.append(
                normalize_action(
                    action_id=str(action_id),
                    payload=dict(payload),
                    provider=self.provider,
                )
            )
        return actions

    @staticmethod
    def _normalize_member_input(member: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Map toolset member arguments into the common action vocabulary."""
        normalized = dict(payload)
        normalized["action"] = member
        if member in {
            "left_click",
            "right_click",
            "middle_click",
            "double_click",
            "triple_click",
            "mouse_move",
            "scroll",
        }:
            if "coordinate" in normalized:
                coordinate = normalized["coordinate"]
                if not isinstance(coordinate, (list, tuple)) or len(coordinate) != 2:
                    raise ValueError(
                        f"Anthropic {member} coordinate must contain two values"
                    )
            if normalized.get("text"):
                normalized["keys"] = [
                    part.strip()
                    for part in str(normalized["text"]).split("+")
                    if part.strip()
                ]
        if member == "left_click_drag":
            start = normalized.get("start_coordinate")
            end = normalized.get("coordinate")
            if not isinstance(start, (list, tuple)) or len(start) != 2:
                raise ValueError("Anthropic left_click_drag requires start_coordinate")
            if not isinstance(end, (list, tuple)) or len(end) != 2:
                raise ValueError("Anthropic left_click_drag requires coordinate")
            normalized["path"] = [start, end]
            if normalized.get("text"):
                normalized["keys"] = [
                    part.strip()
                    for part in str(normalized["text"]).split("+")
                    if part.strip()
                ]
        elif member == "scroll":
            direction = str(normalized.get("scroll_direction") or "").lower()
            if direction not in {"up", "down", "left", "right"}:
                raise ValueError("Anthropic scroll requires a valid scroll_direction")
            try:
                scroll_amount = int(normalized.get("scroll_amount", 1))
            except (TypeError, ValueError) as exc:
                raise ValueError("Anthropic scroll_amount must be an integer") from exc
            if not 1 <= scroll_amount <= 100:
                raise ValueError("Anthropic scroll_amount must be between 1 and 100")
            amount = scroll_amount * 100
            normalized["scroll_x"] = (
                amount
                if direction == "right"
                else -amount if direction == "left" else 0
            )
            normalized["scroll_y"] = (
                amount if direction == "down" else -amount if direction == "up" else 0
            )
        elif member == "key":
            key = normalized.pop("text", None)
            if not isinstance(key, str) or not key.strip():
                raise ValueError("Anthropic key requires text")
            normalized["keys"] = [
                part.strip() for part in key.split("+") if part.strip()
            ]
            try:
                repeat = int(normalized.get("repeat", 1))
            except (TypeError, ValueError) as exc:
                raise ValueError("Anthropic key repeat must be an integer") from exc
            if not 1 <= repeat <= 100:
                raise ValueError("Anthropic key repeat must be between 1 and 100")
            normalized["repeat"] = repeat
        elif member == "wait":
            duration = normalized.pop("duration", None)
            if duration is None:
                raise ValueError("Anthropic wait requires duration")
            normalized["text"] = str(duration)
        elif member == "type" and not isinstance(normalized.get("text"), str):
            raise ValueError("Anthropic type requires text")
        return normalized

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
