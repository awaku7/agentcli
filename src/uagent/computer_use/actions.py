"""Provider-independent Computer Use action representations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_SUPPORTED_ACTIONS = frozenset(
    {
        "screenshot",
        "click",
        "right_click",
        "middle_click",
        "double_click",
        "triple_click",
        "move",
        "type",
        "keypress",
        "scroll",
        "drag",
        "wait",
        "zoom",
    }
)

_ACTION_ALIASES = {
    "left_click": "click",
    "mouse_move": "move",
    "key": "keypress",
    "left_click_drag": "drag",
}


@dataclass(frozen=True)
class ComputerAction:
    """A normalized action independent of the LLM provider protocol."""

    action_id: str
    action: str
    provider: str = ""
    coordinate: tuple[int, int] | None = None
    text: str | None = None
    key: str | None = None
    button: str | None = None
    scroll_x: int | None = None
    scroll_y: int | None = None
    region: tuple[int, int, int, int] | None = None


def _coordinate(value: Any) -> tuple[int, int] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("computer action coordinate must contain two numbers")
    return int(value[0]), int(value[1])


def _region(value: Any) -> tuple[int, int, int, int] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("computer action region must contain four numbers")
    return int(value[0]), int(value[1]), int(value[2]), int(value[3])


def normalize_action(
    *,
    action_id: str,
    payload: dict[str, Any],
    provider: str = "",
) -> ComputerAction:
    """Normalize a provider action payload into :class:`ComputerAction`.

    ``required_actions`` and capability action names use the normalized names.
    Provider-specific aliases are accepted at this boundary only.
    """
    raw_action = str(payload.get("action") or payload.get("type") or "").strip()
    action = _ACTION_ALIASES.get(raw_action, raw_action)
    if action not in _SUPPORTED_ACTIONS:
        raise ValueError(f"unsupported computer action: {raw_action or '<empty>'}")

    coordinate = payload.get("coordinate")
    if coordinate is None and "x" in payload and "y" in payload:
        coordinate = [payload["x"], payload["y"]]

    return ComputerAction(
        action_id=str(action_id),
        action=action,
        provider=str(provider or ""),
        coordinate=_coordinate(coordinate),
        text=payload.get("text"),
        key=payload.get("key") or payload.get("keys"),
        button=payload.get("button"),
        scroll_x=payload.get("scroll_x"),
        scroll_y=payload.get("scroll_y"),
        region=_region(payload.get("region")),
    )
