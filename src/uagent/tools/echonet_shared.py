"""ECHONET Lite shared resources: background INF listener thread.

Listens for unsolicited INF (0x73) / INFC (0x74) notifications
from ECHONET Lite devices and queues changes to SchedulerStore.
"""

from __future__ import annotations

import socket
import threading
import time
from typing import Any

_MULTICAST_ADDR = ("224.0.23.0", 3610)
_LISTENERS: dict[str, dict[str, Any]] = {}
_LISTENERS_LOCK = threading.Lock()
_LISTENER_THREAD: threading.Thread | None = None
_STOP_EVENT = threading.Event()

_EPC_NAMES: dict[int, str] = {
    0x80: "operation_status",
    0x81: "installation_location",
    0x82: "standard_version_information",
    0x83: "identification_number",
    0x8A: "manufacturer_code",
    0x8B: "product_code",
    0x8C: "property_map",
    0x9D: "set_property_map",
    0x9E: "get_property_map",
    0x9F: "inf_property_map",
    0xD5: "self_node_instance_list_s",
    0xD6: "self_node_class_list_s",
    0xD7: "self_node_instance_list",
}

_EOJ_CLASS_NAMES: dict[str, str] = {
    "0130": "air_conditioner",
    "0290": "lighting",
    "0260": "curtain_or_blind",
    "026F": "lock",
    "0EF0": "node_profile",
    "0288": "electric_lock",
    "02A0": "window",
    "0280": "general_lighting",
    "0281": "ceiling_lighting",
    "0282": "wall_lighting",
    "0283": "desk_lighting",
    "0284": "emergency_lighting",
    "0285": "outdoor_lighting",
    "0286": "sign_lighting",
    "0287": "incandescent_lighting",
}


def _property_value(epc: int, edt: bytes) -> tuple[Any, str]:
    if epc in {0xD5, 0xD6, 0xD7}:
        items: list[str] = []
        for start in range(0, len(edt) - (len(edt) % 3), 3):
            chunk = edt[start : start + 3]
            if len(chunk) == 3:
                items.append(chunk.hex().upper())
        return items, "eoj_list"
    if not edt:
        return None, "empty"
    if len(edt) == 1:
        return edt[0], "uint8"
    if len(edt) == 2:
        return int.from_bytes(edt, "big"), "uint16"
    if len(edt) == 3:
        return int.from_bytes(edt, "big"), "uint24"
    if len(edt) == 4:
        return int.from_bytes(edt, "big"), "uint32"
    return edt.hex().upper(), "hex"


def _parse_frame(raw: bytes) -> dict[str, Any] | None:
    if len(raw) < 12:
        return None
    if raw[0] != 0x10 or raw[1] != 0x81:
        return None
    seoj = raw[4:7].hex().upper()
    deoj = raw[7:10].hex().upper()
    esv = raw[10]
    opc = raw[11]
    idx = 12
    properties: list[dict[str, Any]] = []
    for _i in range(opc):
        if idx + 2 > len(raw):
            break
        epc = raw[idx]
        pdc = raw[idx + 1]
        idx += 2
        edt = raw[idx : idx + pdc]
        idx += pdc
        properties.append(
            {
                "epc": f"{epc:02X}",
                "name": _EPC_NAMES.get(epc, f"epc_{epc:02X}"),
                "value": _property_value(epc, edt)[0],
                "format": _property_value(epc, edt)[1],
                "access": "read",
                "raw_hex": edt.hex().upper(),
            }
        )
    return {
        "seoj": seoj,
        "deoj": deoj,
        "esv": f"{esv:02X}",
        "opc": opc,
        "properties": properties,
        "raw_hex": raw.hex().upper(),
    }


def _listener_loop(bind_ip: str | None) -> None:
    """Background thread: listen for INF/INFC multicast frames."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except Exception:
                pass
        sock.bind(("0.0.0.0", 3610))
        mreq = socket.inet_aton("224.0.23.0") + socket.inet_aton(bind_ip or "0.0.0.0")
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.settimeout(1.0)

        while not _STOP_EVENT.is_set():
            try:
                data, source = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break

            parsed = _parse_frame(data)
            if not parsed:
                continue

            esv = parsed.get("esv", "")
            # INF = 0x73, INFC = 0x74
            if esv not in ("73", "74"):
                continue

            source_ip = source[0]
            seoj = parsed.get("seoj", "")
            class_code = seoj[:4] if len(seoj) >= 4 else ""
            class_name = _EOJ_CLASS_NAMES.get(class_code, f"class_{class_code}")
            label = f"ECHONET {class_name}@{source_ip}"

            # Check if any listener is interested
            matched = False
            with _LISTENERS_LOCK:
                for listener_id, info in _LISTENERS.items():
                    if not info.get("enabled", True):
                        continue
                    # Filter: ip match
                    lip = info.get("ip", "")
                    if lip and lip != source_ip:
                        continue
                    # Filter: eoj match
                    leoj = info.get("eoj", "")
                    if leoj and leoj.upper() != seoj and leoj.upper()[:4] != seoj[:4]:
                        continue
                    matched = True
                    break

            if not matched:
                continue

            # Build notification text
            props = parsed.get("properties", [])
            prop_texts = [f"{p.get('epc')}={p.get('value')}" for p in props]

            from ..scheduler import (
                SchedulerStore,
                ScheduleItem,
                format_iso_datetime,
                utc_now,
            )
            from uuid import uuid4
            from datetime import timedelta

            prompt = f"ECHONET Lite device {label} sent notification: {', '.join(prop_texts)}"
            item = ScheduleItem(
                id=str(uuid4()),
                type="once",
                at=format_iso_datetime(utc_now() + timedelta(seconds=1)),
                message=f"[ECHONET] {label}: {', '.join(prop_texts)}",
                llm_prompt=prompt,
                interval_sec=0,
                enabled=True,
            )
            SchedulerStore().add_item(item)

    except Exception:
        pass
    finally:
        try:
            sock.close()
        except Exception:
            pass


def _ensure_listener(bind_ip: str | None = None) -> None:
    """Start the background listener thread if not already running."""
    global _LISTENER_THREAD
    with _LISTENERS_LOCK:
        if _LISTENER_THREAD is not None and _LISTENER_THREAD.is_alive():
            return
        _STOP_EVENT.clear()
        _LISTENER_THREAD = threading.Thread(
            target=_listener_loop,
            args=(bind_ip,),
            daemon=True,
            name="echonet-inf",
        )
        _LISTENER_THREAD.start()


def subscribe(
    ip: str,
    eoj: str = "",
    label: str = "",
    on_change_prompt: str = "",
    bind_ip: str | None = None,
) -> dict[str, Any]:
    """Subscribe to ECHONET Lite INF notifications from a device."""
    _ensure_listener(bind_ip)

    listener_id = f"echonet_{ip}_{eoj or '*'}_{int(time.time())}"
    info = {
        "ip": ip,
        "eoj": eoj.upper() if eoj else "",
        "label": label or f"ECHONET@{ip}",
        "on_change_prompt": on_change_prompt,
        "enabled": True,
    }
    with _LISTENERS_LOCK:
        _LISTENERS[listener_id] = info

    return {
        "ok": True,
        "listener_id": listener_id,
        "subscription": info,
    }


def unsubscribe(listener_id: str) -> dict[str, Any]:
    """Unsubscribe from ECHONET Lite INF notifications."""
    with _LISTENERS_LOCK:
        if listener_id not in _LISTENERS:
            return {"ok": False, "error": f"listener_id '{listener_id}' not found"}
        info = _LISTENERS.pop(listener_id)
    return {"ok": True, "listener_id": listener_id, "subscription": info}


def list_subscriptions() -> dict[str, Any]:
    """List all active ECHONET Lite subscriptions."""
    with _LISTENERS_LOCK:
        subs = [{"listener_id": k, **v} for k, v in _LISTENERS.items()]
    return {"ok": True, "count": len(subs), "subscriptions": subs}


def stop() -> None:
    """Stop the background listener thread."""
    global _LISTENER_THREAD
    _STOP_EVENT.set()
    if _LISTENER_THREAD is not None:
        _LISTENER_THREAD.join(timeout=3)
        _LISTENER_THREAD = None
    with _LISTENERS_LOCK:
        _LISTENERS.clear()
