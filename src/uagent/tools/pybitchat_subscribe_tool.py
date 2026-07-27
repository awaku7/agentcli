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
                "nostr": {
                    "type": "boolean",
                    "default": False,
                    "description": _(
                        "param.nostr.description",
                        default="Enable Nostr relay transport in addition to BLE.",
                    ),
                },
                "nostr_relays": {
                    "type": "string",
                    "default": "",
                    "description": _(
                        "param.nostr_relays.description",
                        default="Comma-separated Nostr relay URLs (default: damus.io, nos.lol, snort.social).",
                    ),
                },
                "nostr_nsec": {
                    "type": "string",
                    "default": "",
                    "description": _(
                        "param.nostr_nsec.description",
                        default="Optional Nostr nsec private key hex (auto-generated if not set).",
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
            extra = ""
            nostr_state = result.get("nostr", "")
            if nostr_state == "running":
                pubkey = result.get("nostr_pubkey", "")
                extra = f" [Nostr: running pubkey={pubkey[:16]}...]"
            elif nostr_state:
                extra = f" [Nostr: {nostr_state}]"
            return _(
                "msg.started",
                default="pybitchat BLE Mesh node started on %(network)s as %(nickname)s.",
            ) % {
                "network": result.get("network", "?"),
                "nickname": result.get("nickname", "?"),
            } + extra
        elif state == "stopped":
            return _("msg.stopped", default="pybitchat BLE Mesh node stopped.")
        else:
            extra = ""
            nostr_state = result.get("nostr", "")
            if nostr_state:
                extra = f" | Nostr: {nostr_state}"
            return _("msg.status", default="pybitchat node state: %(state)s") % {
                "state": state
            } + extra
    return f"Error: {result.get('error', 'unknown')}"


def _ensure_dependencies() -> bool:
    """Auto-install required packages if missing."""
    return ensure_dependencies()


def run_tool(args: dict[str, Any]) -> str:
    action = str(args.get("action") or "").strip()
    nickname = str(args.get("nickname") or "").strip()
    network = str(args.get("network") or "mainnet").strip()
    nostr = args.get("nostr", False)
    nostr_relays_raw = str(args.get("nostr_relays") or "").strip()
    nostr_relays: list[str] | None = None
    if nostr_relays_raw:
        nostr_relays = [r.strip() for r in nostr_relays_raw.split(",") if r.strip()]
    output_format = "json"

    if action == "start":
        if not _ensure_dependencies():
            return json.dumps(
                {"ok": False, "error": "Failed to install dependencies"},
                ensure_ascii=False,
            )
        result = _start(
            nickname=nickname, network=network,
            nostr=nostr, nostr_relays=nostr_relays,
        )
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
    from .pybitchat_shared import set_chat_mode as _set_chat_mode
    result = _set_chat_mode(True)
    if result.get("ok"):
        print(_("cmd.chat_on", default="bitchat chat mode: ON (mesh forwarding active)"))
    else:
        print(_("cmd.error", default="Error: %(error)s") % {"error": result.get("error", "unknown")})
    from ..util_tools import CommandResult
    return CommandResult()


def _cmd_bitchat_off(arg: str, **kwargs) -> "CommandResult":
    """Handle :bitchat off"""
    from .pybitchat_shared import set_chat_mode as _set_chat_mode
    result = _set_chat_mode(False)
    if result.get("ok"):
        print(_("cmd.chat_off", default="bitchat chat mode: OFF"))
    else:
        print(_("cmd.error", default="Error: %(error)s") % {"error": result.get("error", "unknown")})
    from ..util_tools import CommandResult
    return CommandResult()


def _cmd_bitchat_status(arg: str, **kwargs) -> "CommandResult":
    """Handle :bitchat status"""
    from .pybitchat_shared import is_chat_mode as _is_chat_mode, status as _status
    s = _status()
    chat = _is_chat_mode()
    print(_("cmd.status_node", default="bitchat node: %(state)s") % {"state": s.get("state", "?")})
    print(_("cmd.status_chat", default="  chat mode: %(mode)s") % {"mode": "ON" if chat else "OFF"})
    peers = s.get("peers", [])
    if peers:
        for p in peers:
            print(_("cmd.status_peer", default="  peer: %(name)s") % {"name": p.get("nickname", p.get("id", "?"))})
    else:
        print(_("cmd.status_peers_none", default="  peers: none"))
    nostr_state = s.get("nostr", "stopped")
    if nostr_state == "running":
        pubkey = s.get("nostr_pubkey", "")
        relays = s.get("nostr_relays", [])
        conns = s.get("nostr_connections", 0)
        print(_("cmd.status_nostr_running", default="  nostr: running (%(conns)d relay(s) connected)") % {"conns": conns})
        print(_("cmd.status_nostr_pubkey", default="  nostr pubkey: %(pubkey)s") % {"pubkey": pubkey})
        if relays:
            for r in relays:
                print(_("cmd.status_nostr_relay", default="  nostr relay: %(relay)s") % {"relay": r})
    else:
        print(_("cmd.status_nostr_stopped", default="  nostr: %(state)s") % {"state": nostr_state})
    from ..util_tools import CommandResult
    return CommandResult()


# ---- :bitchat geo commands -------------------------------------------------

def _cmd_bitchat_geo_join(arg: str, **kwargs) -> "CommandResult":
    """Handle :bitchat geo join [lat] [lng] [precision] — auto GPS if no args"""
    parts = arg.strip().split()
    if len(parts) >= 2:
        try:
            lat = float(parts[0])
            lng = float(parts[1])
            precision = int(parts[2]) if len(parts) > 2 else 6
        except ValueError:
            print(_("geo.error_invalid_coords", default="Error: lat/lng must be numbers"))
            from ..util_tools import CommandResult
            return CommandResult()
    else:
        # Auto-detect GPS position
        precision = int(parts[0]) if parts and parts[0].isdigit() else 6
        lat, lng = _auto_detect_position()
        if lat is None:
            print(_("geo.usage_join_auto", default="No GPS position available. Usage: :bitchat geo join <lat> <lng> [precision=6]"))
            from ..util_tools import CommandResult
            return CommandResult()
        print(_("geo.auto_detected", default="Auto-detected position: lat=%(lat)s, lng=%(lng)s (precision=%(precision)d)") % {"lat": lat, "lng": lng, "precision": precision})

    from . import bitchat_geo as _geo
    from .pybitchat_shared import _NOSTR as _nt_mod, get_identity
    # Auto-start Nostr transport if not running
    if _nt_mod is None or not getattr(
        getattr(_nt_mod, "_NOSTR_INSTANCE", None), "is_running", False
    ):
        import socket as _socket
        default_nick = _socket.gethostname()
        from .pybitchat_shared import start as _pybitchat_start
        result = _pybitchat_start(nickname=default_nick, nostr=True)
        if not result.get("nostr") == "running":
            print(_("geo.error_nostr_not_running", default="Error: Could not start Nostr transport: %(error)s") % {"error": result.get("nostr", "unknown")})
            from ..util_tools import CommandResult
            return CommandResult()
        from .pybitchat_shared import _NOSTR as _nt_mod
        print(_("geo.auto_start_nostr", default="Auto-started Nostr transport as %(nickname)s") % {"nickname": default_nick})
    inst = getattr(_nt_mod, "_NOSTR_INSTANCE", None)
    result = _geo.join_geo_channel(inst, lat, lng, precision)
    if result.get("ok"):
        gh = result["geohash"]
        acc = result["accuracy"]
        pid = result["peer_id"]
        print(_("geo.joined", default="Joined geo channel: %(geohash)s (%(accuracy)s)") % {"geohash": gh, "accuracy": acc})
        print(_("geo.joined_peer_id", default="  peer_id=%(peer_id)s") % {"peer_id": pid})
        print(_("geo.joined_coords", default="  lat=%(lat)s, lng=%(lng)s, precision=%(precision)d") % {"lat": lat, "lng": lng, "precision": precision})
        print(_("geo.joined_desc", default="  Receiving messages from users in this area via Nostr."))
    else:
        print(_("cmd.error", default="Error: %(error)s") % {"error": result.get("error", "unknown")})
    from ..util_tools import CommandResult
    return CommandResult()


def _auto_detect_position() -> tuple[float | None, float | None]:
    """Auto-detect current position via GPS sensor or IP geolocation."""
    import re as _re

    # Try Windows GPS sensor first
    try:
        from .windows_gps_tool import run_tool as _gps
        raw = _gps({})
        # Parse markdown table: "**緯度**: 34.654" or "**Latitude**: 34.654"
        lat_m = _re.search(r'\*\*(?:緯度|Latitude)\*\*:?\s*([\d.-]+)', raw)
        lng_m = _re.search(r'\*\*(?:経度|Longitude)\*\*:?\s*([\d.-]+)', raw)
        if lat_m and lng_m:
            return float(lat_m.group(1)), float(lng_m.group(1))
    except Exception:
        pass

    # Fallback: IP geolocation
    try:
        from .get_geoip_tool import run_tool as _geoip
        raw = _geoip({"format": "json"})
        result = json.loads(raw)
        # ipinfo.io format: {"loc": "34.6850,135.8048"}
        loc = result.get("loc", "")
        if loc and "," in loc:
            parts = loc.split(",")
            return float(parts[0].strip()), float(parts[1].strip())
        # Other formats with lat/lng keys
        lat = result.get("lat") or result.get("latitude")
        lng = result.get("lng") or result.get("longitude") or result.get("lon")
        if lat is not None and lng is not None:
            return float(lat), float(lng)
    except Exception:
        pass

    return None, None


def _cmd_bitchat_geo_leave(arg: str, **kwargs) -> "CommandResult":
    """Handle :bitchat geo leave <geohash>"""
    geohash = arg.strip()
    if not geohash:
        print(_("geo.usage_leave", default="Usage: :bitchat geo leave <geohash>"))
        from ..util_tools import CommandResult
        return CommandResult()
    from . import bitchat_geo as _geo
    from .pybitchat_shared import _NOSTR as _nt_mod
    if _nt_mod is None:
        print(_("geo.error_nostr_not_running", default="Error: Nostr transport not running."))
        from ..util_tools import CommandResult
        return CommandResult()
    inst = getattr(_nt_mod, "_NOSTR_INSTANCE", None)
    if inst is None:
        print(_("geo.error_nostr_not_running", default="Error: Nostr transport not running."))
        from ..util_tools import CommandResult
        return CommandResult()
    result = _geo.leave_geo_channel(inst, geohash)
    if result.get("ok"):
        print(_("geo.left", default="Left geo channel: %(geohash)s") % {"geohash": geohash})
    else:
        print(_("cmd.error", default="Error: %(error)s") % {"error": result.get("error", "unknown")})
    from ..util_tools import CommandResult
    return CommandResult()


def _cmd_bitchat_geo_list(arg: str, **kwargs) -> "CommandResult":
    """Handle :bitchat geo list"""
    from . import bitchat_geo as _geo
    result = _geo.list_geo_channels()
    channels = result.get("channels", {})
    if not channels:
        print(_("geo.list_none", default="No active geo channels."))
    else:
        print(_("geo.list_header", default="Active geo channels (%(count)d):") % {"count": len(channels)})
        for geohash, info in channels.items():
            pid = info.get("peer_id", "?")
            print(_("geo.list_geohash", default="  %(geohash)s") % {"geohash": geohash})
            print(_("geo.list_peer_id", default="    peer_id: %(peer_id)s") % {"peer_id": pid})
    from ..util_tools import CommandResult
    return CommandResult()


# ---- End geo commands ------------------------------------------------------


# ---- :bitchat peers command ------------------------------------------------

def _cmd_bitchat_peers(arg: str, **kwargs) -> "CommandResult":
    """Handle :bitchat peers - list discovered Nostr bitchat peers"""
    from .pybitchat_shared import _NOSTR as _nt_mod
    if _nt_mod is None:
        print("Error: Nostr transport not running.")
        from ..util_tools import CommandResult
        return CommandResult()
    inst = getattr(_nt_mod, "_NOSTR_INSTANCE", None)
    if inst is None or not inst.is_running:
        print("Error: Nostr transport not running.")
        from ..util_tools import CommandResult
        return CommandResult()
    peers = inst.discovered_peers
    if not peers:
        print(_("peers.list_none", default="No bitchat peers discovered yet."))
    else:
        print(_("peers.list_header", default="Discovered bitchat peers (%(count)d):") % {"count": len(peers)})
        for pubkey, nick in sorted(peers.items()):
            print(_("peers.list_entry", default="  %(nick)s (%(pubkey)s)") % {"nick": nick, "pubkey": pubkey[:16] + "..."})
    from ..util_tools import CommandResult
    return CommandResult()

# ---- End peers command ----------------------------------------------------


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
    # Geo channel commands
    {
        "command": "bitchat",
        "subcommand": "geo join",
        "handler": _cmd_bitchat_geo_join,
        "help_text": "  :bitchat geo join [lat] [lng] [prec]  Join a geohash channel (auto GPS if no args, default prec=6 ~1.2km)",
    },
    {
        "command": "bitchat",
        "subcommand": "geo leave",
        "handler": _cmd_bitchat_geo_leave,
        "help_text": "  :bitchat geo leave <geohash>       Leave a geohash channel",
    },
    {
        "command": "bitchat",
        "subcommand": "geo list",
        "handler": _cmd_bitchat_geo_list,
        "help_text": "  :bitchat geo list                  List active geo channels",
    },
]
