"""OpenAI Responses API Computer Use adapter."""

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


OPENAI_COMPUTER_ACTIONS = frozenset(
    {
        "click",
        "double_click",
        "scroll",
        "type",
        "wait",
        "keypress",
        "drag",
        "move",
        "screenshot",
    }
)


class OpenAIComputerAdapter:
    provider = "openai"

    @staticmethod
    def _validate_action_payload(payload: dict[str, Any], action_name: str) -> None:
        if action_name in {"click", "double_click", "move", "scroll"}:
            if "x" not in payload or "y" not in payload:
                raise ValueError(f"OpenAI {action_name} action requires x and y")
        if action_name == "click" and payload.get("button") not in {
            None,
            "left",
            "right",
            "wheel",
            "back",
            "forward",
        }:
            raise ValueError("OpenAI click action has an unsupported button")
        if action_name == "type" and "text" not in payload:
            raise ValueError("OpenAI type action requires text")
        if action_name == "keypress" and not payload.get("keys"):
            raise ValueError("OpenAI keypress action requires keys")
        if action_name == "drag":
            path = payload.get("path")
            if not isinstance(path, (list, tuple)) or len(path) < 2:
                raise ValueError("OpenAI drag action requires a path with at least two points")

    def build_tool(self, capability: Any) -> dict[str, Any]:
        if not getattr(capability, "supported", False) or not getattr(
            capability, "native", False
        ):
            raise ComputerUseCapabilityError(
                "OpenAI adapter requires a native Computer Use capability"
            )
        tool_type = getattr(capability, "tool_type", None)
        if tool_type not in {"computer", "computer_use_preview"}:
            raise ComputerUseCapabilityError(
                "OpenAI tool_type must be 'computer' or 'computer_use_preview'"
            )
        return {"type": tool_type}

    def parse_actions(self, response: Any) -> list[ComputerAction]:
        actions: list[ComputerAction] = []
        for item in _get(response, "output", []) or []:
            if _get(item, "type") != "computer_call":
                continue
            call_id = _get(item, "call_id") or _get(item, "id")
            if not call_id:
                raise ValueError("OpenAI computer_call has no call_id")
            for index, payload in enumerate(_get(item, "actions", []) or []):
                action_payload = dict(payload)
                action_name = str(
                    action_payload.get("type") or action_payload.get("action") or ""
                )
                if action_name not in OPENAI_COMPUTER_ACTIONS:
                    raise ValueError(
                        f"unsupported OpenAI Computer Use action: {action_name or '<empty>'}"
                    )
                self._validate_action_payload(action_payload, action_name)
                action_id = f"{call_id}:{index}"
                actions.append(
                    normalize_action(
                        action_id=action_id,
                        payload=action_payload,
                        provider=self.provider,
                    )
                )
        return actions

    def build_tool_result(
        self,
        action: ComputerAction,
        result: ComputerActionResult,
    ) -> dict[str, Any]:
        if result.action_id != action.action_id:
            raise ValueError("tool result action_id does not match action")
        call_id = action.action_id.rsplit(":", 1)[0]
        if result.screenshot is None:
            raise ValueError("OpenAI computer_call_output requires a screenshot")
        screenshot = result.screenshot
        output: dict[str, Any] = {
            "type": "computer_screenshot",
            "image_url": (
                "data:"
                + screenshot.media_type
                + ";base64,"
                + base64.b64encode(screenshot.data).decode("ascii")
            ),
            "detail": "original",
        }
        return {
            "type": "computer_call_output",
            "call_id": call_id,
            "output": output,
        }
