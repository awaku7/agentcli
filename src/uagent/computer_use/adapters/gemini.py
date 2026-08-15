"""Google Gemini Computer Use adapter."""

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


_ENVIRONMENTS = {
    "browser": "ENVIRONMENT_BROWSER",
    "mobile": "ENVIRONMENT_MOBILE",
    "desktop": "ENVIRONMENT_DESKTOP",
}


class GeminiComputerAdapter:
    provider = "google"

    def build_tool(
        self,
        capability: Any,
        *,
        environment: str = "browser",
        prompt_injection_detection: bool = True,
    ) -> dict[str, Any]:
        if not getattr(capability, "supported", False) or not getattr(
            capability, "native", False
        ):
            raise ComputerUseCapabilityError(
                "Gemini adapter requires a native Computer Use capability"
            )
        if environment not in _ENVIRONMENTS:
            raise ValueError(f"unsupported Gemini environment: {environment}")
        return {
            "computer_use": {
                "environment": _ENVIRONMENTS[environment],
                "enable_prompt_injection_detection": prompt_injection_detection,
            }
        }

    def parse_actions(
        self,
        response: Any,
        *,
        turn_id: str = "gemini",
    ) -> list[ComputerAction]:
        calls: list[dict[str, Any]] = []
        direct = _get(response, "function_call")
        if direct is not None:
            calls.append(direct)
        for candidate in _get(response, "candidates", []) or []:
            content = _get(candidate, "content", {})
            for part in _get(content, "parts", []) or []:
                function_call = _get(part, "function_call")
                if function_call is not None:
                    calls.append(function_call)
        for call in _get(response, "function_calls", []) or []:
            calls.append(call)

        actions: list[ComputerAction] = []
        for index, call in enumerate(calls):
            name = _get(call, "name")
            args = dict(_get(call, "args", {}) or {})
            if not name:
                raise ValueError("Gemini function_call has no name")
            actions.append(
                normalize_action(
                    action_id=f"{turn_id}:{index}",
                    payload={"action": name, **args},
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
        response_parts: list[dict[str, Any]] = []
        if result.screenshot is not None:
            screenshot = result.screenshot
            response_parts.append(
                {
                    "inline_data": {
                        "mime_type": screenshot.media_type,
                        "data": base64.b64encode(screenshot.data).decode("ascii"),
                    }
                }
            )
        response_parts.append(
            {"text": "ok" if result.success else (result.error or "action failed")}
        )
        return {
            "function_response": {
                "name": action.action,
                "response": {"parts": response_parts},
            }
        }
