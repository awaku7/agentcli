"""pybitchat_subscribe_tool: start/stop/monitor the BLE Mesh node."""

from __future__ import annotations

import json
from typing import Any

from .i18n_helper import make_tool_translator
from .pybitchat_shared import (
    ensure_dependencies,
    is_chat_mode,
    set_chat_mode,
    start as _start,
    status as _status,
    stop as _stop,
)

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:pybitchat_subscribe"


TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "comm",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "pybitchat_subscribe",
        "description": _(
            "tool.description",
            default=(
                "Start/stop/monitor the pybitchat BLE Mesh node. "
                "Peer discovery events are shown as [INFO] notifications in the terminal."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "pybitchat",
                "bitchat",
                "BLE",
                "mesh",
                "subscribe",
                "pybitchat_subscribe",
            ],
        ),
        "x_search_terms_en": [
            "pybitchat",
            "bitchat",
            "BLE",
            "mesh",
            "subscribe",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["start", "stop", "status", "chat_mode"],
                    "description": _(
                        "param.action.description",
                        default=(
                            "Action: start (begin BLE scan/advertise), "
                            "stop (shutdown), status (current state)."
                        ),
                    ),
                },
                "nickname": {
                    "type": "string",
                    "description": _(
                        "param.nickname.description",
                        default="Node nickname shown to peers.",
                    ),
                },
                "network": {
                    "type": "string",
                    "enum": ["mainnet", "testnet"],
                    "default": "mainnet",
                    "description": _(
                        "param.network.description",
                        default="Network: mainnet or testnet.",
                    ),
                },
                "on": {
                    "type": "boolean",
                    "description": _(
                        "param.on.description",
                        default="Enable/disable bitchat chat mode (action=chat_mode).",
                    ),
                },
                "on_message_prompt": {
                    "type": "string",
                    "description": _(
                        "param.on_message_prompt.description",
                        default=(
                            "Optional prompt injected into the LLM "
                            "when a message arrives."
                        ),
                    ),
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
}


def _format_text(result: dict[str, Any]) -> str:
    state = result.get("state", "?")
    if result.get("ok"):
        if state == "running":
            return _(
                "msg.started",
                default="pybitchat BLE Mesh node started on %(network)s as %(nickname)s.",
            ) % {
                "network": result.get("network", "?"),
                "nickname": result.get("nickname", "?"),
            }
        elif state == "stopped":
            return _("msg.stopped", default="pybitchat BLE Mesh node stopped.")
        else:
            return _("msg.status", default="pybitchat node state: %(state)s") % {
                "state": state
            }
    return f"Error: {result.get('error', 'unknown')}"


def _ensure_dependencies() -> bool:
    """Auto-install required packages if missing."""
    return ensure_dependencies()


def run_tool(args: dict[str, Any]) -> str:
    action = str(args.get("action") or "").strip()
    nickname = str(args.get("nickname") or "").strip()
    network = str(args.get("network") or "mainnet").strip()
    output_format = "json"

    if action == "start":
        if not _ensure_dependencies():
            return json.dumps(
                {"ok": False, "error": "Failed to install dependencies"},
                ensure_ascii=False,
            )
        result = _start(nickname=nickname, network=network)
    elif action == "stop":
        result = _stop()
    elif action == "status":
        result = _status()
        result["chat_mode"] = is_chat_mode()
    elif action == "chat_mode":
        on = args.get("on")
        if on is None:
            result = {"ok": False, "error": "Parameter 'on' (true/false) is required for chat_mode action"}
        else:
            result = set_chat_mode(on)
    else:
        err = _("err.unknown_action", default="Unknown action: %(action)s") % {
            "action": action
        }
        return json.dumps({"ok": False, "error": err}, ensure_ascii=False)

    if output_format == "text":
        return _format_text(result)
    return json.dumps(result, ensure_ascii=False)


# ---- :bitchat dynamic command -----------------------------------------------

def _cmd_bitchat_on(arg: str, **kwargs) -> "CommandResult":
    """Handle :bitchat on"""
    from .pybitchat_shared import set_chat_mode as _set_chat_mode, is_chat_mode as _is_chat_mode
    result = _set_chat_mode(True)
    if result.get("ok"):
        print(f"bitchat chat mode: ON (mesh forwarding active)")
    else:
        print(f"Error: {result.get('error', 'unknown')}")
    from ..util_tools import CommandResult
    return CommandResult()


def _cmd_bitchat_off(arg: str, **kwargs) -> "CommandResult":
    """Handle :bitchat off"""
    from .pybitchat_shared import set_chat_mode as _set_chat_mode
    result = _set_chat_mode(False)
    if result.get("ok"):
        print("bitchat chat mode: OFF")
    else:
        print(f"Error: {result.get('error', 'unknown')}")
    from ..util_tools import CommandResult
    return CommandResult()


def _cmd_bitchat_status(arg: str, **kwargs) -> "CommandResult":
    """Handle :bitchat status"""
    from .pybitchat_shared import is_chat_mode as _is_chat_mode, status as _status
    s = _status()
    chat = _is_chat_mode()
    print(f"bitchat node: {s.get('state', '?')}")
    print(f"  chat mode: {'ON' if chat else 'OFF'}")
    peers = s.get("peers", [])
    if peers:
        for p in peers:
            print(f"  peer: {p.get('nickname', p.get('id', '?'))}")
    else:
        print("  peers: none")
    from ..util_tools import CommandResult
    return CommandResult()


CMD_SPECS = [
    {
        "command": "bitchat",
        "subcommand": "on",
        "handler": _cmd_bitchat_on,
        "help_text": "  :bitchat on       Enable chat mode (user input forwarded to mesh)",
    },
    {
        "command": "bitchat",
        "subcommand": "off",
        "handler": _cmd_bitchat_off,
        "help_text": "  :bitchat off      Disable chat mode",
    },
    {
        "command": "bitchat",
        "subcommand": "status",
        "handler": _cmd_bitchat_status,
        "help_text": "  :bitchat status   Show node and chat mode status",
    },
]
