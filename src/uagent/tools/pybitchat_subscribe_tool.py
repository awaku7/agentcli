"""pybitchat_subscribe_tool: start/stop/monitor the BLE Mesh node."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..util_tools import CommandResult

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
                        default="Comma-separated Nostr relay URLs (default: x.kojira.io, nos.lol, primal.net).",
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
                "mode": {
                    "type": "string",
                    "enum": ["on", "llm", "off"],
                    "description": _(
                        "param.mode.description",
                        default=(
                            "Chat mode (action=chat_mode): 'on' = mesh forwarding only (LLM injection disabled), "
                            "'llm' = mesh forwarding + inject paired peers' DMs to LLM, "
                            "'off' = disabled. Overrides 'on' if both specified."
                        ),
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
            return (
                _(
                    "msg.started",
                    default="pybitchat BLE Mesh node started on %(network)s as %(nickname)s.",
                )
                % {
                    "network": result.get("network", "?"),
                    "nickname": result.get("nickname", "?"),
                }
                + extra
            )
        elif state == "stopped":
            return _("msg.stopped", default="pybitchat BLE Mesh node stopped.")
        else:
            extra = ""
            nostr_state = result.get("nostr", "")
            if nostr_state:
                extra = f" | Nostr: {nostr_state}"
            return (
                _("msg.status", default="pybitchat node state: %(state)s")
                % {"state": state}
                + extra
            )
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
            nickname=nickname,
            network=network,
            nostr=nostr,
            nostr_relays=nostr_relays,
        )
    elif action == "stop":
        result = _stop()
    elif action == "status":
        result = _status()
        result["chat_mode"] = is_chat_mode()
    elif action == "chat_mode":
        mode = args.get("mode")
        if mode is not None:
            result = set_chat_mode(mode)
        else:
            on = args.get("on")
            if on is None:
                result = {
                    "ok": False,
                    "error": "Parameter 'mode' or 'on' is required for chat_mode action",
                }
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


def _cmd_bitchat_start(arg: str, **kwargs) -> "CommandResult":
    """Handle :bitchat start [nickname] [--nostr] [--network <name>]"""
    parts = arg.strip().split()
    nickname = ""
    nostr = False
    network = "mainnet"
    i = 0
    while i < len(parts):
        p = parts[i]
        if p in ("--nostr", "-n"):
            nostr = True
        elif p in ("--network", "-net"):
            i += 1
            if i >= len(parts):
                print(
                    _(
                        "cmd.start.need_network",
                        default="Error: --network requires a value (mainnet|testnet)",
                    )
                )
                from ..util_tools import CommandResult

                return CommandResult()
            network = parts[i]
        elif p.startswith("-"):
            print(
                _("cmd.start.unknown_arg", default="Error: Unknown argument: %(arg)s")
                % {"arg": p}
            )
            from ..util_tools import CommandResult

            return CommandResult()
        elif not nickname:
            nickname = p
        else:
            print(
                _("cmd.start.unknown_arg", default="Error: Unknown argument: %(arg)s")
                % {"arg": p}
            )
            from ..util_tools import CommandResult

            return CommandResult()
        i += 1

    if not _ensure_dependencies():
        print(
            _("cmd.error", default="Error: %(error)s")
            % {"error": "Failed to install dependencies"}
        )
        from ..util_tools import CommandResult

        return CommandResult()

    if not nickname:
        import socket as _socket

        nickname = _socket.gethostname()

    result = _start(nickname=nickname, network=network, nostr=nostr)
    if result.get("ok"):
        if result.get("message") == "Already running":
            print(
                _(
                    "cmd.node_already_running",
                    default="bitchat BLE Mesh node already running as %(nickname)s.",
                )
                % {"nickname": nickname}
            )
        else:
            print(
                _(
                    "cmd.node_started",
                    default="bitchat BLE Mesh node started on %(network)s as %(nickname)s.",
                )
                % {"network": network, "nickname": nickname}
            )
        nostr_state = result.get("nostr", "")
        if nostr_state == "running":
            pubkey = result.get("nostr_pubkey", "")
            print(
                _(
                    "cmd.node_started_nostr",
                    default="  nostr: running pubkey=%(pubkey)s",
                )
                % {"pubkey": pubkey}
            )
        elif nostr_state:
            print(
                _(
                    "cmd.node_started_nostr_failed",
                    default="  nostr: %(state)s",
                )
                % {"state": nostr_state}
            )
    else:
        print(
            _("cmd.error", default="Error: %(error)s")
            % {"error": result.get("error", "unknown")}
        )
    from ..util_tools import CommandResult

    return CommandResult()


def _cmd_bitchat_stop(arg: str, **kwargs) -> "CommandResult":
    """Handle :bitchat stop"""
    result = _stop()
    if result.get("ok"):
        print(_("cmd.node_stopped", default="bitchat BLE Mesh node stopped."))
    else:
        print(
            _("cmd.error", default="Error: %(error)s")
            % {"error": result.get("error", "unknown")}
        )
    from ..util_tools import CommandResult

    return CommandResult()


def _cmd_bitchat_on(arg: str, **kwargs) -> "CommandResult":
    """Handle :bitchat on"""
    from .pybitchat_shared import set_chat_mode as _set_chat_mode

    result = _set_chat_mode("on")
    if result.get("ok"):
        print(
            _("cmd.chat_on", default="bitchat chat mode: ON (mesh forwarding active)")
        )
    else:
        print(
            _("cmd.error", default="Error: %(error)s")
            % {"error": result.get("error", "unknown")}
        )
    from ..util_tools import CommandResult

    return CommandResult()


def _cmd_bitchat_off(arg: str, **kwargs) -> "CommandResult":
    """Handle :bitchat off"""
    from .pybitchat_shared import set_chat_mode as _set_chat_mode

    result = _set_chat_mode(False)
    if result.get("ok"):
        print(_("cmd.chat_off", default="bitchat chat mode: OFF"))
    else:
        print(
            _("cmd.error", default="Error: %(error)s")
            % {"error": result.get("error", "unknown")}
        )
    from ..util_tools import CommandResult

    return CommandResult()


def _cmd_bitchat_llm(arg: str, **kwargs) -> "CommandResult":
    """Handle :bitchat llm"""
    from .pybitchat_shared import set_chat_mode as _set_chat_mode

    result = _set_chat_mode("llm")
    if result.get("ok"):
        print(
            _(
                "cmd.chat_llm",
                default="bitchat chat mode: LLM (LLM injection active)",
            )
        )
    else:
        print(
            _("cmd.error", default="Error: %(error)s")
            % {"error": result.get("error", "unknown")}
        )
    from ..util_tools import CommandResult

    return CommandResult()


def _cmd_bitchat_status(arg: str, **kwargs) -> "CommandResult":
    """Handle :bitchat status"""
    from .pybitchat_shared import is_chat_mode as _is_chat_mode, status as _status

    s = _status()
    chat = _is_chat_mode()
    label = {"off": "OFF", "on": "ON", "llm": "LLM"}.get(chat, chat.upper())
    print(
        _("cmd.status_node", default="bitchat node: %(state)s")
        % {"state": s.get("state", "?")}
    )
    print(_("cmd.status_chat", default="  chat mode: %(mode)s") % {"mode": label})
    peers = s.get("peers", [])
    if peers:
        for p in peers:
            print(
                _("cmd.status_peer", default="  peer: %(name)s")
                % {"name": p.get("nickname", p.get("id", "?"))}
            )
    else:
        print(_("cmd.status_peers_none", default="  peers: none"))
    nostr_state = s.get("nostr", "stopped")
    if nostr_state == "running":
        pubkey = s.get("nostr_pubkey", "")
        relays = s.get("nostr_relays", [])
        conns = s.get("nostr_connections", 0)
        print(
            _(
                "cmd.status_nostr_running",
                default="  nostr: running (%(conns)d relay(s) connected)",
            )
            % {"conns": conns}
        )
        print(
            _("cmd.status_nostr_pubkey", default="  nostr pubkey: %(pubkey)s")
            % {"pubkey": pubkey}
        )
        if relays:
            for r in relays:
                print(
                    _("cmd.status_nostr_relay", default="  nostr relay: %(relay)s")
                    % {"relay": r}
                )
    else:
        print(
            _("cmd.status_nostr_stopped", default="  nostr: %(state)s")
            % {"state": nostr_state}
        )
    from ..util_tools import CommandResult

    return CommandResult()


# ---- :bitchat geo commands -------------------------------------------------


def _cmd_bitchat_geo_join(arg: str, **kwargs) -> "CommandResult":
    """Handle :bitchat geo join [geohash] or [lat] [lng] [precision]"""
    parts = arg.strip().split()
    from . import bitchat_geo as _geo

    target_geohash = None
    lat, lng, precision = None, None, 6

    if len(parts) == 1 and not parts[0].isdigit():
        target_geohash = parts[0]
    elif len(parts) >= 2:
        try:
            lat = float(parts[0])
            lng = float(parts[1])
            precision = int(parts[2]) if len(parts) > 2 else 6
        except ValueError:
            print(
                _("geo.error_invalid_coords", default="Error: lat/lng must be numbers")
            )
            from ..util_tools import CommandResult

            return CommandResult()
    else:
        precision = int(parts[0]) if parts and parts[0].isdigit() else 6
        lat, lng = _auto_detect_position()
        if lat is None:
            print(
                _(
                    "geo.usage_join_auto",
                    default="No GPS position available. Usage: :bitchat geo join <geohash> or :bitchat geo join <lat> <lng> [prec]",
                )
            )
            from ..util_tools import CommandResult

            return CommandResult()

        print(
            _(
                "geo.auto_detected",
                default="Auto-detected position: lat=%(lat)s, lng=%(lng)s (precision=%(precision)d)",
            )
            % {"lat": lat, "lng": lng, "precision": precision}
        )
        print(
            _("geo.channels_header", default="Available Geohash channels in your area:")
        )
        candidates = []
        for p in [2, 4, 5, 6, 8]:
            gh = _geo._geohash_encode(lat, lng, p)
            acc = _geo._GEO_PRECISION.get(p, "")
            candidates.append((gh, acc, p))
            print(
                _(
                    "geo.channel_entry",
                    default="  #%(geohash)s (precision %(precision)d, %(accuracy)s)",
                )
                % {"geohash": gh, "precision": p, "accuracy": acc}
            )
        print(_("geo.mesh_channel", default="  #mesh     (global local mesh channel)"))
        print(
            _(
                "geo.join_hint",
                default=(
                    "\nTo join a channel, run: :bitchat geo join <geohash> "
                    "(e.g. :bitchat geo join #%(geohash)s)"
                ),
            )
            % {"geohash": candidates[3][0]}
        )
        from ..util_tools import CommandResult

        return CommandResult()

    from .pybitchat_shared import _NOSTR as _nt_mod

    # Auto-start Nostr transport if not running
    if _nt_mod is None or not getattr(
        getattr(_nt_mod, "_NOSTR_INSTANCE", None), "is_running", False
    ):
        import socket as _socket

        default_nick = _socket.gethostname()
        from .pybitchat_shared import start as _pybitchat_start

        result = _pybitchat_start(nickname=default_nick, nostr=True)
        if not result.get("nostr") == "running":
            print(
                _(
                    "cmd.node_started_nostr_failed",
                    default="  nostr: %(state)s",
                )
                % {"state": result.get("nostr", "unknown")}
            )
            from ..util_tools import CommandResult

            return CommandResult()
        from .pybitchat_shared import _NOSTR as _nt_mod

        print(
            _(
                "geo.auto_start_nostr",
                default="Auto-started Nostr transport as %(nickname)s",
            )
            % {"nickname": default_nick}
        )
    inst = getattr(_nt_mod, "_NOSTR_INSTANCE", None)
    if target_geohash:
        result = _geo.join_geo_channel_by_hash(inst, target_geohash)
    else:
        result = _geo.join_geo_channel(inst, lat, lng, precision)

    if result.get("ok"):
        gh = result["geohash"]
        acc = result["accuracy"]
        pid = result["peer_id"]
        print(
            _("geo.joined", default="Joined geo channel: %(geohash)s (%(accuracy)s)")
            % {"geohash": gh, "accuracy": acc}
        )
        print(
            _("geo.joined_peer_id", default="  peer_id=%(peer_id)s") % {"peer_id": pid}
        )
        if lat is not None and lng is not None:
            print(
                _(
                    "geo.joined_coords",
                    default="  lat=%(lat)s, lng=%(lng)s, precision=%(precision)d",
                )
                % {"lat": lat, "lng": lng, "precision": precision}
            )
        print(
            _(
                "geo.joined_desc",
                default="  Receiving messages from users in this area via Nostr.",
            )
        )
    else:
        print(
            _("cmd.error", default="Error: %(error)s")
            % {"error": result.get("error", "unknown")}
        )
    from ..util_tools import CommandResult

    return CommandResult()


def _auto_detect_position() -> tuple[float | None, float | None]:
    """Auto-detect current position via GPS sensor or IP geolocation."""
    import re as _re

    # Try the native location provider first
    try:
        from .current_location_tool import run_tool as _gps

        raw = _gps({})
        # Parse a markdown table: "**Latitude**: 34.654"
        lat_m = _re.search(r"\*\*(?:\u7def\u5ea6|Latitude)\*\*:?\s*([\d.-]+)", raw)
        lng_m = _re.search(r"\*\*(?:\u7d4c\u5ea6|Longitude)\*\*:?\s*([\d.-]+)", raw)
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
        print(
            _(
                "geo.error_nostr_not_running",
                default="Error: Nostr transport not running.",
            )
        )
        from ..util_tools import CommandResult

        return CommandResult()
    inst = getattr(_nt_mod, "_NOSTR_INSTANCE", None)
    if inst is None:
        print(
            _(
                "geo.error_nostr_not_running",
                default="Error: Nostr transport not running.",
            )
        )
        from ..util_tools import CommandResult

        return CommandResult()
    result = _geo.leave_geo_channel(inst, geohash)
    if result.get("ok"):
        print(
            _("geo.left", default="Left geo channel: %(geohash)s")
            % {"geohash": geohash}
        )
    else:
        print(
            _("cmd.error", default="Error: %(error)s")
            % {"error": result.get("error", "unknown")}
        )
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
        print(
            _("geo.list_header", default="Active geo channels (%(count)d):")
            % {"count": len(channels)}
        )
        for geohash, info in channels.items():
            pid = info.get("peer_id", "?")
            print(_("geo.list_geohash", default="  %(geohash)s") % {"geohash": geohash})
            print(
                _("geo.list_peer_id", default="    peer_id: %(peer_id)s")
                % {"peer_id": pid}
            )
    from ..util_tools import CommandResult

    return CommandResult()


# ---- End geo commands ------------------------------------------------------


# ---- :bitchat peers command ------------------------------------------------

# The BLE peers shown by the most recent :bitchat peers, in display order:
# (nickname, noise_key_hex) for the entries that carried a number.
# :bitchat pair resolves numbers and nicknames against this list only, so
# a selector can never name a peer the user has not actually seen listed.
_DISPLAYED_BLE_PEERS: list[tuple[str, str]] = []

_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


def _looks_like_noise_key(text: str) -> bool:
    return len(text) == 64 and all(char in _HEX_DIGITS for char in text)


def _displayed_peer_matches(selector: str) -> list[str]:
    """Noise keys of displayed BLE peers matching a :bitchat pair selector.

    A selector is a 1-based number into the displayed list or a nickname.
    Returns every match; the caller decides what zero or several mean.
    """
    if selector.isascii() and selector.isdigit():
        index = int(selector)
        if 1 <= index <= len(_DISPLAYED_BLE_PEERS):
            return [_DISPLAYED_BLE_PEERS[index - 1][1]]
        return []
    return [key for nick, key in _DISPLAYED_BLE_PEERS if nick == selector]


def _cmd_bitchat_peers(arg: str, **kwargs) -> "CommandResult":
    """Handle :bitchat peers - list discovered peers (Nostr + BLE mesh)"""
    global _DISPLAYED_BLE_PEERS
    from . import pybitchat_shared as _shared
    from .pybitchat_shared import _NOSTR as _nt_mod

    printed = False
    inst = getattr(_nt_mod, "_NOSTR_INSTANCE", None) if _nt_mod is not None else None
    if inst is not None and inst.is_running:
        peers = inst.discovered_peers
        if peers:
            printed = True
            print(
                _("peers.list_header", default="Discovered bitchat peers (%(count)d):")
                % {"count": len(peers)}
            )
            for pubkey, nick in sorted(peers.items()):
                print(
                    _("peers.list_entry", default="  %(nick)s (%(pubkey)s)")
                    % {"nick": nick, "pubkey": pubkey}
                )
    # BLE mesh peers, with the Noise key :bitchat pair expects. Peers
    # with a known Noise key are numbered; :bitchat pair resolves those
    # numbers (and nicknames) against exactly this displayed list.
    displayed: list[tuple[str, str]] = []
    ble_peers = sorted(_shared._PEER_NICKNAMES.items())
    if ble_peers:
        printed = True
        print(
            _("peers.ble_header", default="BLE mesh peers (%(count)d):")
            % {"count": len(ble_peers)}
        )
        for peer_id, nick in ble_peers:
            noise_key = _shared._PEER_NOISE_KEYS.get(peer_id)
            if noise_key:
                displayed.append((nick, noise_key.hex()))
                print(
                    _(
                        "peers.ble_entry_numbered",
                        default="  %(index)d. %(nick)s noise=%(noise_key)s",
                    )
                    % {
                        "index": len(displayed),
                        "nick": nick,
                        "noise_key": noise_key.hex(),
                    }
                )
            else:
                print(
                    _("peers.ble_entry", default="  %(nick)s noise=%(noise_key)s")
                    % {"nick": nick, "noise_key": "?"}
                )
    _DISPLAYED_BLE_PEERS = displayed
    if not printed:
        print(_("peers.list_none", default="No bitchat peers discovered yet."))
    from ..util_tools import CommandResult

    return CommandResult()


# ---- End peers command ----------------------------------------------------


# ---- :bitchat pairing commands ---------------------------------------------
#
# Pairing is what lets a peer's DMs reach the LLM in chat_mode='llm'.
# Records live in the BLE pairing registry (bitchat_pairing.py), keyed by
# the peer's Noise static key, with an optional linked Nostr key so a peer
# paired in person can also operate the node over Nostr DMs. These are
# local console commands only; nothing on a receive path can pair.


def _cmd_bitchat_pair(arg: str, **kwargs) -> "CommandResult":
    """Handle :bitchat pair <noise_key_hex | number | nickname> [label]"""
    from ..bitchat_pairing import open_bitchat_pairing_store
    from ..util_tools import CommandResult

    raw = arg.strip()
    if not raw:
        print(
            _(
                "pair.usage",
                default="Usage: :bitchat pair <noise_key_hex | number | nickname> [label]",
            )
        )
        return CommandResult()
    parts = raw.split(None, 1)
    first = parts[0]
    rest = parts[1].strip() if len(parts) > 1 else ""
    if _looks_like_noise_key(first):
        noise_key, label = first, rest
    else:
        # A number or nickname, resolved against the peers the most
        # recent :bitchat peers actually displayed, and nothing else.
        if not _DISPLAYED_BLE_PEERS:
            print(
                _(
                    "pair.not_displayed",
                    default="No BLE peers have been displayed yet. Run :bitchat peers first.",
                )
            )
            return CommandResult()
        selector = first
        label = rest
        if not (first.isascii() and first.isdigit()):
            # A nickname may contain spaces: the longest displayed
            # nickname the input starts with is the selector, and
            # whatever follows it is the label.
            nick = ""
            for name, _key in _DISPLAYED_BLE_PEERS:
                if raw == name or raw.startswith(name + " "):
                    if len(name) > len(nick):
                        nick = name
            if nick:
                selector = nick
                label = raw[len(nick) :].strip()
            else:
                selector = raw
        matches = _displayed_peer_matches(selector)
        if not matches:
            print(
                _(
                    "pair.unknown_peer",
                    default="No displayed BLE peer matches '%(selector)s'. Run :bitchat peers to check the list.",
                )
                % {"selector": selector}
            )
            return CommandResult()
        if len(matches) > 1:
            print(
                _(
                    "pair.ambiguous",
                    default="More than one displayed peer is named '%(selector)s'. Use the number instead.",
                )
                % {"selector": selector}
            )
            return CommandResult()
        noise_key = matches[0]
        if not label:
            label = next(name for name, key in _DISPLAYED_BLE_PEERS if key == noise_key)
    try:
        with open_bitchat_pairing_store() as store:
            record = store.pair(
                noise_key,
                label,
                approved=True,
            )
        print(
            _(
                "pair.success",
                default="Paired bitchat peer: %(noise_key)s (%(label)s)",
                noise_key=record.noise_key,
                label=record.label or "unnamed",
            )
        )
    except Exception as exc:
        print(
            _("pair.error", default="Could not pair bitchat peer: %(error)s")
            % {"error": exc}
        )
    from ..util_tools import CommandResult

    return CommandResult()


def _cmd_bitchat_link(arg: str, **kwargs) -> "CommandResult":
    """Handle :bitchat link <noise_key_hex> <nostr_key_hex>"""
    from ..bitchat_pairing import open_bitchat_pairing_store

    parts = arg.strip().split()
    if len(parts) != 2:
        print(
            _(
                "link.usage",
                default="Usage: :bitchat link <noise_key_hex> <nostr_key_hex>",
            )
        )
        from ..util_tools import CommandResult

        return CommandResult()
    try:
        with open_bitchat_pairing_store() as store:
            record = store.link_nostr(parts[0], parts[1], approved=True)
        print(
            _(
                "link.success",
                default="Linked Nostr key %(nostr_key)s to bitchat peer %(noise_key)s",
                nostr_key=record.nostr_key or "",
                noise_key=record.noise_key,
            )
        )
    except Exception as exc:
        print(
            _("link.error", default="Could not link Nostr key: %(error)s")
            % {"error": exc}
        )
    from ..util_tools import CommandResult

    return CommandResult()


def _cmd_bitchat_revoke(arg: str, **kwargs) -> "CommandResult":
    """Handle :bitchat revoke <noise_key_hex>"""
    from ..bitchat_pairing import open_bitchat_pairing_store

    pubkey = arg.strip()
    if not pubkey or any(char.isspace() for char in pubkey):
        print(_("revoke.usage", default="Usage: :bitchat revoke <noise_key_hex>"))
        from ..util_tools import CommandResult

        return CommandResult()
    try:
        with open_bitchat_pairing_store() as store:
            revoked = store.revoke(pubkey)
        print(
            _("revoke.done", default="Bitchat peer revoked.")
            if revoked
            else _(
                "revoke.none",
                default="No active pairing for that Noise key.",
            )
        )
    except Exception as exc:
        print(
            _("revoke.error", default="Could not revoke bitchat peer: %(error)s")
            % {"error": exc}
        )
    from ..util_tools import CommandResult

    return CommandResult()


def _cmd_bitchat_bind(arg: str, **kwargs) -> "CommandResult":
    """Handle :bitchat bind <noise_key_hex> attach|room"""
    from ..bitchat_pairing import open_bitchat_pairing_store

    parts = arg.strip().split()
    if len(parts) != 2 or parts[1].lower() not in ("attach", "room"):
        print(
            _(
                "bind.usage",
                default="Usage: :bitchat bind <noise_key_hex> attach|room",
            )
        )
        from ..util_tools import CommandResult

        return CommandResult()
    try:
        with open_bitchat_pairing_store() as store:
            changed = store.set_binding(parts[0], parts[1].lower())
        print(
            _(
                "bind.success",
                default="Bitchat peer chat binding: %(binding)s",
                binding=parts[1].lower(),
            )
            if changed
            else _(
                "bind.none",
                default="No active pairing for that Noise key.",
            )
        )
    except Exception as exc:
        print(
            _(
                "bind.error",
                default="Could not set bitchat peer chat binding: %(error)s",
            )
            % {"error": exc}
        )
    from ..util_tools import CommandResult

    return CommandResult()


def _cmd_bitchat_devices(arg: str, **kwargs) -> "CommandResult":
    """Handle :bitchat devices [all] - list paired bitchat peers"""
    from ..bitchat_pairing import open_bitchat_pairing_store

    option = arg.strip().lower()
    if option not in ("", "all"):
        print(_("devices.usage", default="Usage: :bitchat devices [all]"))
        from ..util_tools import CommandResult

        return CommandResult()
    try:
        with open_bitchat_pairing_store() as store:
            records = store.list_devices(include_revoked=option == "all")
    except Exception as exc:
        print(
            _("devices.error", default="Could not list bitchat peers: %(error)s")
            % {"error": exc}
        )
        from ..util_tools import CommandResult

        return CommandResult()
    if not records:
        print(_("devices.none", default="No paired bitchat peers."))
    for record in records:
        line = _(
            "devices.entry",
            default="  %(label)s noise=%(noise_key)s",
            label=record.label or "unnamed",
            noise_key=record.noise_key,
        )
        if record.nostr_key:
            line += " " + _(
                "devices.entry_nostr",
                default="nostr=%(nostr_key)s",
                nostr_key=record.nostr_key,
            )
        if record.revoked_at is None:
            line += " " + _(
                "devices.entry_binding",
                default="chat=%(binding)s",
                binding=record.binding,
            )
        if record.revoked_at is not None:
            line += " " + _("devices.revoked", default="(revoked)")
        print(line)
    from ..util_tools import CommandResult

    return CommandResult()


# ---- End pairing commands --------------------------------------------------


def _cmd_help(syntax: str, key: str, default: str) -> str:
    return f"  {syntax:<55} {_(key, default=default)}"


CMD_SPECS = [
    {
        "command": "bitchat",
        "subcommand": "start",
        "handler": _cmd_bitchat_start,
        "help_text": _cmd_help(
            ":bitchat start [nickname] [--nostr] [--network <mainnet|testnet>]",
            "help.start",
            "Start the BLE Mesh node",
        ),
    },
    {
        "command": "bitchat",
        "subcommand": "stop",
        "handler": _cmd_bitchat_stop,
        "help_text": _cmd_help(":bitchat stop", "help.stop", "Stop the BLE Mesh node"),
    },
    {
        "command": "bitchat",
        "subcommand": "on",
        "handler": _cmd_bitchat_on,
        "help_text": _cmd_help(
            ":bitchat on",
            "help.on",
            "Enable chat mode (user input forwarded to mesh)",
        ),
    },
    {
        "command": "bitchat",
        "subcommand": "off",
        "handler": _cmd_bitchat_off,
        "help_text": _cmd_help(":bitchat off", "help.off", "Disable chat mode"),
    },
    {
        "command": "bitchat",
        "subcommand": "status",
        "handler": _cmd_bitchat_status,
        "help_text": _cmd_help(
            ":bitchat status",
            "help.status",
            "Show node and chat mode status",
        ),
    },
    {
        "command": "bitchat",
        "subcommand": "llm",
        "handler": _cmd_bitchat_llm,
        "help_text": _cmd_help(
            ":bitchat llm",
            "help.llm",
            "LLM chat mode (paired peers' DMs are sent to the LLM; pairing alone enables it)",
        ),
    },
    {
        "command": "bitchat",
        "subcommand": "pair",
        "handler": _cmd_bitchat_pair,
        "help_text": _cmd_help(
            ":bitchat pair <noise_key_hex | number | nickname> [label]",
            "help.pair",
            "Pair a bitchat peer by Noise key, number, or nickname (allows their DMs to reach the LLM)",
        ),
    },
    {
        "command": "bitchat",
        "subcommand": "link",
        "handler": _cmd_bitchat_link,
        "help_text": _cmd_help(
            ":bitchat link <noise_key_hex> <nostr_key_hex>",
            "help.link",
            "Link a paired peer's Nostr key so they can also use Nostr DMs",
        ),
    },
    {
        "command": "bitchat",
        "subcommand": "revoke",
        "handler": _cmd_bitchat_revoke,
        "help_text": _cmd_help(
            ":bitchat revoke <noise_key_hex>",
            "help.revoke",
            "Revoke a bitchat peer pairing",
        ),
    },
    {
        "command": "bitchat",
        "subcommand": "devices",
        "handler": _cmd_bitchat_devices,
        "help_text": _cmd_help(
            ":bitchat devices [all]",
            "help.devices",
            "List paired bitchat peers",
        ),
    },
    {
        "command": "bitchat",
        "subcommand": "bind",
        "handler": _cmd_bitchat_bind,
        "help_text": _cmd_help(
            ":bitchat bind <noise_key_hex> attach|room",
            "help.bind",
            "Set a paired peer's chat binding (attach = main session, room = its own session)",
        ),
    },
    # Geo channel commands
    {
        "command": "bitchat",
        "subcommand": "geo join",
        "handler": _cmd_bitchat_geo_join,
        "help_text": _cmd_help(
            ":bitchat geo join [<geohash>|lat lng [prec]]",
            "help.geo_join",
            "Join geohash channel (shows candidates if no args)",
        ),
    },
    {
        "command": "bitchat",
        "subcommand": "geo leave",
        "handler": _cmd_bitchat_geo_leave,
        "help_text": _cmd_help(
            ":bitchat geo leave <geohash>",
            "help.geo_leave",
            "Leave a geohash channel",
        ),
    },
    {
        "command": "bitchat",
        "subcommand": "geo list",
        "handler": _cmd_bitchat_geo_list,
        "help_text": _cmd_help(
            ":bitchat geo list",
            "help.geo_list",
            "List active geo channels",
        ),
    },
    {
        "command": "bitchat",
        "subcommand": "peers",
        "handler": _cmd_bitchat_peers,
        "help_text": _cmd_help(
            ":bitchat peers",
            "help.peers",
            "List discovered Nostr bitchat peers",
        ),
    },
]
