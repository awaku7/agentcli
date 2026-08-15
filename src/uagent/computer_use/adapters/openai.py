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


class OpenAIComputerAdapter:
    provider = "openai"

    def build_tool(self, capability: Any) -> dict[str, str]:
        if not getattr(capability, "supported", False) or not getattr(
            capability, "native", False
        ):
            raise ComputerUseCapabilityError(
                "OpenAI adapter requires a native Computer Use capability"
            )
        if getattr(capability, "tool_type", None) != "computer":
            raise ComputerUseCapabilityError("OpenAI tool_type must be 'computer'")
        return {"type": "computer"}

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
        output: dict[str, Any]
        if result.screenshot is not None:
            screenshot = result.screenshot
            output = {
                "type": "computer_screenshot",
                "image_url": (
                    "data:"
                    + screenshot.media_type
                    + ";base64,"
                    + base64.b64encode(screenshot.data).decode("ascii")
                ),
            }
        else:
            output = {"type": "computer_screenshot", "image_url": None}
        return {
            "type": "computer_call_output",
            "call_id": call_id,
            "output": output,
        }
