"""Meta Responses API native Computer Use adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..actions import ComputerAction, normalize_action
from ..capability import ComputerUseCapabilityError

META_COMPUTER_ACTIONS = frozenset(
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


def _get(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


@dataclass(frozen=True)
class MetaComputerCall:
    """Validated Meta ``computer_call`` item and its safety metadata."""

    call_id: str
    actions: tuple[ComputerAction, ...]
    raw_actions: tuple[dict[str, Any], ...]
    pending_safety_checks: tuple[dict[str, Any], ...]
    meta_safety_replay_receipt: Any = None


class MetaComputerAdapter:
    """Build Meta's tool definition and translate Responses calls/results."""

    provider = "meta"

    def build_tool(self, capability: Any) -> dict[str, Any]:
        if not getattr(capability, "supported", False) or not getattr(
            capability, "native", False
        ):
            raise ComputerUseCapabilityError(
                "Meta adapter requires a native Computer Use capability"
            )
        if getattr(capability, "provider", None) != "meta":
            raise ComputerUseCapabilityError(
                "Meta Computer Use capability provider must be 'meta'"
            )
        if getattr(capability, "api_type", None) != "responses":
            raise ComputerUseCapabilityError(
                "Meta Computer Use requires the Responses API"
            )
        if getattr(capability, "tool_type", None) != "computer":
            raise ComputerUseCapabilityError(
                "Meta Computer Use tool_type must be 'computer'"
            )
        return {"type": "computer"}

    def parse_call(self, item: Any) -> MetaComputerCall:
        """Validate and normalize one Meta ``computer_call`` output item."""
        if _get(item, "type") != "computer_call":
            raise ValueError("Meta Computer Use item must be a computer_call")
        call_id = _get(item, "call_id") or _get(item, "id")
        if not call_id:
            raise ValueError("Meta computer_call has no call_id")
        raw_actions = _get(item, "actions", []) or []
        if not isinstance(raw_actions, (list, tuple)) or not raw_actions:
            raise ValueError("Meta computer_call must contain at least one action")

        parsed_actions: list[ComputerAction] = []
        raw_action_dicts: list[dict[str, Any]] = []
        for index, raw_action in enumerate(raw_actions):
            action_payload = dict(raw_action) if isinstance(raw_action, dict) else None
            if action_payload is None:
                raise ValueError("Meta computer_call actions must be objects")
            action_name = str(action_payload.get("type") or "")
            if action_name not in META_COMPUTER_ACTIONS:
                raise ValueError(
                    f"unsupported Meta Computer Use action: {action_name or '<empty>'}"
                )
            if action_name in {"click", "double_click", "move", "scroll"}:
                if "x" not in action_payload or "y" not in action_payload:
                    raise ValueError(f"Meta {action_name} action requires x and y")
            if action_name == "type" and not isinstance(
                action_payload.get("text"), str
            ):
                raise ValueError("Meta type action requires text")
            if action_name == "keypress" and not action_payload.get("keys"):
                raise ValueError("Meta keypress action requires keys")
            if action_name == "drag":
                path = action_payload.get("path")
                if not isinstance(path, (list, tuple)) or len(path) < 2:
                    raise ValueError(
                        "Meta drag action requires a path with at least two points"
                    )
            if action_name == "click" and action_payload.get("button") not in {
                None,
                "left",
                "right",
                "wheel",
                "back",
                "forward",
            }:
                raise ValueError("Meta click action has an unsupported button")
            parsed_actions.append(
                normalize_action(
                    action_id=f"{call_id}:{index}",
                    payload=action_payload,
                    provider=self.provider,
                )
            )
            raw_action_dicts.append(action_payload)

        checks_value = _get(item, "pending_safety_checks", []) or []
        if not isinstance(checks_value, (list, tuple)):
            raise ValueError("Meta pending_safety_checks must be a list")
        checks: list[dict[str, Any]] = []
        for check in checks_value:
            if not isinstance(check, dict) or not all(
                key in check for key in ("id", "code", "message")
            ):
                raise ValueError(
                    "Meta safety checks must include id, code, and message"
                )
            checks.append(dict(check))

        return MetaComputerCall(
            call_id=str(call_id),
            actions=tuple(parsed_actions),
            raw_actions=tuple(raw_action_dicts),
            pending_safety_checks=tuple(checks),
            meta_safety_replay_receipt=_get(item, "meta_safety_replay_receipt"),
        )

    def build_tool_result(
        self,
        *,
        call_id: str,
        image_url: str,
        acknowledged_safety_checks: (
            list[dict[str, Any]] | tuple[dict[str, Any], ...]
        ) = (),
        meta_safety_replay_receipt: Any = None,
    ) -> dict[str, Any]:
        """Build one Meta ``computer_call_output`` with a required screenshot."""
        if (
            not isinstance(image_url, str)
            or not image_url.startswith(
                ("data:image/png;base64,", "data:image/jpeg;base64,")
            )
            or not image_url.split(",", 1)[1]
        ):
            raise ValueError("Meta computer_call_output requires an image data URL")
        if not call_id:
            raise ValueError("Meta computer_call_output requires call_id")
        if not isinstance(acknowledged_safety_checks, (list, tuple)):
            raise ValueError("acknowledged_safety_checks must be a list")
        result: dict[str, Any] = {
            "type": "computer_call_output",
            "call_id": str(call_id),
            "acknowledged_safety_checks": [
                dict(check) for check in acknowledged_safety_checks
            ],
            "output": {"type": "computer_screenshot", "image_url": image_url},
        }
        if meta_safety_replay_receipt is not None:
            result["meta_safety_replay_receipt"] = meta_safety_replay_receipt
        return result
