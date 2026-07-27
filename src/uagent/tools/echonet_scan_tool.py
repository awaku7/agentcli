from __future__ import annotations

import json
import random
import socket
import struct
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

from .echonet_cache_shared import cache_get, cache_set
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:echonet_scan"

_MULTICAST_ADDR = ("224.0.23.0", 3610)
_DEFAULT_TIMEOUT = 4
_DEFAULT_RETRY = 1
_DEFAULT_LIMIT = 50
_CACHE_TTL_SECONDS = 600
_DEFAULT_USER_EOJ = bytes.fromhex("05FF01")
_NODE_PROFILE_EOJ = bytes.fromhex("0EF001")
_EPC_NODE_PROFILE = {0xD5, 0xD6, 0xD7, 0x8A, 0x83}

# Manufacturer code -> name mapping (from ECHONET Consortium)
_MANUFACTURER_NAMES: dict[str, str] = {
    "000001": "Hitachi",
    "000005": "Sharp",
    "000006": "Mitsubishi Electric",
    "000008": "DAIKIN",
    "000009": "NEC",
    "000012": "Oi Electric",
    "000015": "Daikin Systems&Solutions",
    "000016": "Toshiba",
    "000017": "Carrier Japan",
    "000022": "Hitachi Global Life Solutions",
    "000023": "NTT COMWARE",
    "000025": "LIXIL",
    "000034": "Mitsubishi Electric Engineering",
    "000035": "Toshiba Toko Meter",
    "000036": "NISSIN SYSTEMS",
    "000040": "Hitachi High-Tech",
    "000041": "ENEGATE",
    "000043": "Toshiba D&E",
    "000044": "Hitachi Industrial Equipment",
    "000047": "NTT East",
    "000048": "Oki Electric",
    "000050": "TOTO",
    "000051": "Fuji IT",
    "000052": "OSAKI ELECTRIC",
    "000053": "Ubiquitous AI",
    "000054": "NORITZ",
    "000055": "FAMILYNET JAPAN",
    "000056": "iND",
    "000057": "ELIIYPower",
    "000058": "Mediotec",
    "000059": "Rinnai",
    "000060": "Sony CSL",
    "000061": "NTT DATA INTELLILINK",
    "000063": "Kawamura Electric",
    "000064": "OMRON SOCIAL SOLUTIONS",
    "000067": "CORONA",
    "000068": "AISIN",
    "000069": "Toshiba Lifestyle",
    "000071": "NIHON SANGYO",
    "000072": "Eneres",
    "000073": "NEC Platforms",
    "000076": "TSP",
    "000077": "Kanagawa IT",
    "000078": "Maxell",
    "000079": "Anritsu Engineering",
    "000080": "DIAMOND&ZEBRA ELECTRIC",
    "000081": "IWATSU ELECTRIC",
    "000082": "PURPOSE",
    "000083": "Melco Techno Yokohama",
    "000085": "TAKAOKA TOKO",
    "000086": "NTT West",
    "000087": "I-O DATA",
    "000088": "CHOFU SEISAKUSHO",
    "000090": "Fujitsu Component",
    "000091": "NEC Platforms",
    "000093": "SATORI ELECTRIC",
    "000095": "Yamato Denki",
    "000096": "Azbil",
    "000097": "Future Tech Labs",
    "000099": "TEPCO",
    "000100": "Smart Solar",
    "000101": "Sunpot",
    "000102": "NICHICON",
    "000103": "Data Technology",
    "000104": "Next Energy",
    "000105": "Mitsubishi Electric Lighting",
    "000106": "Nature",
    "000107": "SEIKO ELECTRIC",
    "000108": "SOUSEI Technology",
    "000109": "DENSO",
    "000110": "ASUKA SOLUTION",
    "000111": "Topre",
    "000112": "NICHIEI INTEC",
    "000113": "EBARA JITSUGYO",
    "000114": "OkayaKiden",
    "000115": "HUAWEI JAPAN",
    "000116": "Sungrow",
    "000117": "WWB",
    "000118": "NEC Magnus",
    "000119": "DAIHEN",
    "000120": "Meisei electric",
    "000121": "TOYOTA MOTOR",
    "000122": "Hanwha Q CELLS Japan",
    "000123": "Contec",
    "000124": "TISI",
    "000125": "LiveSmart",
    "000126": "Togami Electric",
    "000127": "Paloma",
    "000128": "SAIKOH ENGINEERING",
    "000129": "GoodWe Japan",
    "000130": "COOLDESIGN",
    "000131": "Shenzhen Eternalplanet",
    "000132": "EX4Energy",
    "000133": "afterFIT",
    "000134": "GoodWe Technologies",
    "000135": "LinkJapan",
    "000136": "Chuo Bussan",
    "000137": "OkayaKiden",
    "000138": "TRENDE",
    "000139": "RATOC Systems",
    "000140": "Landis+Gyr",
    "000141": "DAIKO ELECTRIC",
    "000142": "Yanekara",
    "000143": "Deye Energy Japan",
    "000144": "Sky Electric Japan",
    "000145": "Tesla Japan",
    "000146": "NOEX",
    "000147": "Haiot",
    "000148": "TIGER",
    "000149": "SYNCOMM",
}

# EOJ class code -> (English name, Japanese name) mapping (from pyhems MRA data)
# Direct mapping from common eoj_list values (as seen in device responses)
# to class codes, for cases where byte ordering is non-standard
_EOJ_RAW_MAP: dict[str, int] = {
    "010130": 0x0130,  # SHARP air conditioner D7 reports 010130 instead of 013001
}

_EOJ_CLASS_NAMES: dict[int, tuple[str, str]] = {
    0x0002: ("Crime prevention sensor", "防犯センサ"),
    0x0003: ("Emergency button", "非常ボタン"),
    0x0007: ("Human detection sensor", "人体検知センサ"),
    0x0011: ("Temperature sensor", "温度センサ"),
    0x0012: ("Humidity sensor", "湿度センサ"),
    0x0016: ("Bath heating status sensor", "風呂沸き上がりセンサ"),
    0x001B: ("CO2 sensor", "CO2センサ"),
    0x001D: ("VOC sensor", "VOCセンサ"),
    0x0022: ("Electric energy sensor", "電力量センサ"),
    0x0023: ("Current sensor", "電流センサ"),
    0x00D0: ("Illuminance sensor", "照度センサ"),
    0x0130: ("Home air conditioner", "家庭用エアコン"),
    0x0133: ("Ventilation fan", "換気扇"),
    0x0134: ("Air conditioner ventilation fan", "空調換気扇"),
    0x0135: ("Air cleaner", "空気清浄器"),
    0x0156: ("Commercial AC indoor unit", "業務用エアコン室内機"),
    0x0157: ("Commercial AC outdoor unit", "業務用エアコン室外機"),
    0x0260: ("Electrically operated blind/shade", "電動ブラインド・日よけ"),
    0x0263: ("Electrically operated shutter", "電動雨戸・シャッター"),
    0x026B: ("Electric water heater", "電気温水器"),
    0x026F: ("Electric lock", "電気錠"),
    0x0272: ("Instantaneous water heater", "瞬間式給湯器"),
    0x0273: ("Bathroom heater dryer", "浴室暖房乾燥機"),
    0x0279: ("Household solar power generation", "住宅用太陽光発電"),
    0x027A: ("Cold/hot water heat source", "冷温水熱源機"),
    0x027B: ("Floor heater", "床暖房"),
    0x027C: ("Fuel cell", "燃料電池"),
    0x027D: ("Storage battery", "蓄電池"),
    0x027E: ("EV charger/discharger", "電気自動車充放電器"),
    0x0280: ("Watt-hour meter", "電力量メータ"),
    0x0281: ("Water flowmeter", "水流量メータ"),
    0x0282: ("Gas meter", "ガスメータ"),
    0x0287: ("Power distribution meter", "分電盤メータリング"),
    0x0288: ("Low-voltage smart meter", "低圧スマート電力量メータ"),
    0x028A: ("High-voltage smart meter", "高圧スマート電力量メータ"),
    0x028D: ("Smart sub-meter", "スマート電力量サブメータ"),
    0x028E: ("Distributed generator meter", "分散型電源電力量メータ"),
    0x028F: ("Bidirectional HV smart meter", "双方向対応高圧スマート電力量メータ"),
    0x0290: ("General lighting", "一般照明"),
    0x0291: ("Mono functional lighting", "単機能照明"),
    0x02A1: ("EV Charger", "電気自動車充電器"),
    0x02A3: ("Lighting system", "照明システム"),
    0x02A4: ("Extended lighting system", "拡張照明システム"),
    0x02A5: ("Multiple input PCS", "マルチ入力PCS"),
    0x02A6: ("Hybrid water heater", "ハイブリッド給湯機"),
    0x02A7: ("Frequency regulation", "周波数制御"),
    0x03B7: ("Refrigerator", "冷凍冷蔵庫"),
    0x03B9: ("Cooking heater", "クッキングヒータ"),
    0x03BB: ("Rice cooker", "炊飯器"),
    0x03CE: ("Commercial showcase", "業務用ショーケース"),
    0x03D3: ("Washer/dryer", "洗濯乾燥機"),
    0x03D4: ("Commercial showcase outdoor unit", "業務用ショーケース向け室外機"),
    0x05FD: ("Switch (JEM-A/HA)", "スイッチ (JEM-A/HA端子対応)"),
    0x05FF: ("Controller", "コントローラ"),
    0x0602: ("Television", "テレビ"),
}

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "echonet_scan",
        "description": _(
            "tool.description",
            default=(
                "Discover ECHONET Lite nodes on the local network and return a JSON or text list."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "echonet scan",
                "echonet_scan",
                "echonet",
                "ECHONET",
                "discover",
                "nodes",
                "local",
                "network",
            ],
        ),
        "x_search_terms_en": [
            "echonet scan",
            "echonet_scan",
            "echonet",
            "ECHONET",
            "discover",
            "nodes",
            "local",
            "network",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "timeout": {
                    "type": "integer",
                    "default": _DEFAULT_TIMEOUT,
                    "minimum": 1,
                    "description": _(
                        "param.timeout.description",
                        default="Receive wait time in seconds for ECHONET Lite discovery.",
                    ),
                },
                "interface": {
                    "type": "string",
                    "description": _(
                        "param.interface.description",
                        default=("Local interface IPv4/name (optional)."),
                    ),
                },
                "retry": {
                    "type": "integer",
                    "default": _DEFAULT_RETRY,
                    "minimum": 1,
                    "description": _(
                        "param.retry.description",
                        default="Discovery rounds.",
                    ),
                },
                "limit": {
                    "type": "integer",
                    "default": _DEFAULT_LIMIT,
                    "minimum": 0,
                    "description": _(
                        "param.limit.description",
                        default="Maximum number of nodes to return. 0 means unlimited.",
                    ),
                },
                "refresh": {
                    "type": "boolean",
                    "description": _(
                        "param.refresh.description",
                        default="If true, bypass cache and force a fresh scan.",
                    ),
                },
                "scope": {
                    "type": "string",
                    "enum": ["all", "local", "external", "self", "local_other"],
                    "default": "all",
                    "description": _(
                        "param.scope.description",
                        default=(
                            "Filter discovered nodes by network scope. "
                            "all=no filter; local=same LAN subnet (+ self); "
                            "external=public/WAN addresses; self=bind host only; "
                            "local_other=private but different subnet."
                        ),
                    ),
                },
                "fmt": {
                    "type": "string",
                    "enum": ["json", "text"],
                    "default": "json",
                    "description": _(
                        "param.fmt.description",
                        default="Format: json or text.",
                    ),
                },
            },
            "additionalProperties": False,
        },
    },
}


_EPC_NAMES = {
    0xD5: "self_node_instance_list_s",
    0xD6: "self_node_class_list_s",
    0xD7: "self_node_instance_list",
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
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _normalize_int(value: Any, default: int, minimum: int = 1) -> int:
    try:
        result = int(value)
    except Exception:
        return default
    if result < minimum:
        return default if default >= minimum else minimum
    return result


def _is_ipv4_address(value: str) -> bool:
    try:
        socket.inet_aton(value)
        return value.count(".") == 3
    except Exception:
        return False


def _ip_to_int(ip: str) -> int | None:
    try:
        parts = [int(p) for p in ip.split(".")]
        if len(parts) != 4 or any(p < 0 or p > 255 for p in parts):
            return None
        return (parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]
    except Exception:
        return None


def _is_loopback_ipv4(ip: str) -> bool:
    return ip.startswith("127.")


def _is_link_local_ipv4(ip: str) -> bool:
    return ip.startswith("169.254.")


def _is_multicast_ipv4(ip: str) -> bool:
    n = _ip_to_int(ip)
    if n is None:
        return False
    return (n & 0xF0000000) == 0xE0000000


def _is_private_ipv4(ip: str) -> bool:
    n = _ip_to_int(ip)
    if n is None:
        return False
    if (n & 0xFF000000) == 0x0A000000:
        return True
    if (n & 0xFFF00000) == 0xAC100000:
        return True
    if (n & 0xFFFF0000) == 0xC0A80000:
        return True
    if (n & 0xFFC00000) == 0x64400000:
        return True
    return False


def _netmask_prefix_for_ip(ip: str) -> int | None:
    if not ip or not _is_ipv4_address(ip):
        return None
    try:
        import psutil  # type: ignore
    except ImportError:
        try:
            from .._pip_auto import install_with_status as _install_ps

            if not _install_ps("psutil"):
                return None
            import psutil  # type: ignore
        except Exception:
            return None
    try:
        for _name, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if getattr(addr, "family", None) != socket.AF_INET:
                    continue
                if (addr.address or "").strip() != ip:
                    continue
                mask = (getattr(addr, "netmask", None) or "").strip()
                mn = _ip_to_int(mask) if mask else None
                if mn is None:
                    return None
                return bin(mn).count("1")
    except Exception:
        return None
    return None


def _default_prefix_for_ip(ip: str) -> int:
    if ip.startswith("10."):
        return 8
    if ip.startswith("192.168."):
        return 24
    n = _ip_to_int(ip)
    if n is not None and (n & 0xFFF00000) == 0xAC100000:
        return 12
    if n is not None and (n & 0xFFC00000) == 0x64400000:
        return 10
    return 24


def _same_subnet(ip: str, bind_ip: str | None, prefix: int | None = None) -> bool:
    if not bind_ip or not _is_ipv4_address(ip) or not _is_ipv4_address(bind_ip):
        return False
    a = _ip_to_int(ip)
    b = _ip_to_int(bind_ip)
    if a is None or b is None:
        return False
    if prefix is None:
        prefix = _netmask_prefix_for_ip(bind_ip)
    if prefix is None:
        prefix = _default_prefix_for_ip(bind_ip)
    prefix = max(0, min(32, int(prefix)))
    if prefix == 0:
        return True
    mask = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
    return (a & mask) == (b & mask)


def _classify_node_scope(ip: str | None, bind_ip: str | None) -> dict[str, Any]:
    raw = (ip or "").strip()
    if not raw or not _is_ipv4_address(raw):
        return {
            "scope": "unknown",
            "on_lan": False,
            "is_self": False,
            "is_private": False,
            "same_subnet": False,
        }

    is_self = bool(bind_ip and raw == bind_ip)
    is_private = (
        _is_private_ipv4(raw) or _is_link_local_ipv4(raw) or _is_loopback_ipv4(raw)
    )
    same = _same_subnet(raw, bind_ip) if bind_ip else is_private
    if is_self:
        scope = "self"
        on_lan = True
    elif _is_multicast_ipv4(raw):
        scope = "unknown"
        on_lan = False
    elif is_private and (same or not bind_ip):
        scope = "local"
        on_lan = True
    elif is_private and not same:
        scope = "local_other"
        on_lan = False
    else:
        scope = "external"
        on_lan = False

    return {
        "scope": scope,
        "on_lan": on_lan,
        "is_self": is_self,
        "is_private": is_private,
        "same_subnet": same,
    }


def _normalize_scope_filter(value: Any) -> str:
    raw = str(value or "all").strip().lower()
    aliases = {
        "": "all",
        "all": "all",
        "*": "all",
        "any": "all",
        "local": "local",
        "lan": "local",
        "private": "local",
        "external": "external",
        "wan": "external",
        "public": "external",
        "remote": "external",
        "self": "self",
        "local_other": "local_other",
        "other": "local_other",
    }
    return aliases.get(raw, "all")


def _scope_matches(scope: str, wanted: str) -> bool:
    if wanted == "all":
        return True
    if wanted == "local":
        return scope in ("local", "self")
    return scope == wanted


def _resolve_interface(interface: str | None) -> tuple[str | None, str | None]:
    raw = (interface or "").strip()

    def _is_virtual_name(name: str) -> bool:
        low = name.lower()
        return any(
            token in low
            for token in (
                "bluetooth",
                "loopback",
                "virtual",
                "vmware",
                "hyper-v",
                "teredo",
                "isatap",
                "tunnel",
                "tap",
                "vpn",
            )
        )

    def _score_interface(name: str, addr: str) -> int:
        low = name.lower()
        score = 0
        if _is_virtual_name(name):
            score -= 100
        if any(token in low for token in ("ethernet", "wi-fi", "wifi", "wlan")):
            score += 20
        if low.startswith(("eth", "en", "lan")):
            score += 10
        if addr.startswith("192.168."):
            score += 15
        elif addr.startswith("10."):
            score += 12
        elif addr.startswith("172."):
            try:
                second = int(addr.split(".", 2)[1])
            except Exception:
                second = -1
            if 16 <= second <= 31:
                score += 12
        elif addr.startswith("169.254."):
            score -= 20
        elif addr.startswith("127."):
            score -= 50
        return score

    def _first_ipv4_for_name(target: str) -> tuple[str | None, str | None]:
        try:
            import psutil  # type: ignore
        except ImportError:
            from .._pip_auto import install_with_status as _install_ps

            if not _install_ps("psutil"):
                raise
            import psutil

        try:
            for name, addrs in psutil.net_if_addrs().items():
                if name.lower() != target:
                    continue
                if _is_virtual_name(name):
                    continue
                for addr in addrs:
                    if getattr(addr, "family", None) == socket.AF_INET and addr.address:
                        ip = addr.address.strip()
                        if _is_ipv4_address(ip):
                            return ip, name
        except Exception:
            pass
        return None, None

    if raw:
        if _is_ipv4_address(raw):
            return raw, raw

        ip, name = _first_ipv4_for_name(raw.lower())
        if ip:
            return ip, name

        try:
            resolved = socket.gethostbyname(raw)
            if _is_ipv4_address(resolved):
                return resolved, raw
        except Exception:
            pass

        raise ValueError(
            _(  # type: ignore[used-before-def]  # noqa: F823
                "err.invalid_interface",
                default=(
                    "Error: Could not resolve interface '{interface}' to a local IPv4 address."
                ),
                interface=raw,
            )
        )

    try:
        import psutil  # type: ignore
    except ImportError:
        from .._pip_auto import install_with_status as _install_ps

        if not _install_ps("psutil"):
            raise
        import psutil

    try:
        candidates: list[tuple[int, str, str]] = []
        for name, addrs in psutil.net_if_addrs().items():
            if _is_virtual_name(name):
                continue
            for addr in addrs:
                if getattr(addr, "family", None) != socket.AF_INET or not addr.address:
                    continue
                ip = addr.address.strip()
                if not _is_ipv4_address(ip):
                    continue
                candidates.append((_score_interface(name, ip), name, ip))

        if candidates:
            candidates.sort(key=lambda item: (item[0], item[1].lower()), reverse=True)
            _score, best_name, best_ip = candidates[0]
            return best_ip, best_name
    except Exception:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            local_ip = sock.getsockname()[0]
            if _is_ipv4_address(local_ip):
                return local_ip, local_ip
    except Exception:
        pass

    return None, None


def _normalize_eoj(text: str | None) -> str | None:
    if text is None:
        return None
    raw = str(text).strip()
    if not raw:
        return None
    raw = raw.replace("0x", "").replace("0X", "")
    for sep in (" ", ":", "-", "."):
        raw = raw.replace(sep, "")
    raw = raw.upper()
    if len(raw) != 6:
        return None
    try:
        bytes.fromhex(raw)
    except Exception:
        return None
    return raw


def _eoj_bytes(text: str | None) -> bytes | None:
    normalized = _normalize_eoj(text)
    if normalized is None:
        return None
    return bytes.fromhex(normalized)


def _build_get_request(
    target_eoj: bytes, epcs: list[int], tid: int | None = None
) -> bytes:
    tid_bytes = (
        struct.pack(">H", tid & 0xFFFF)
        if tid is not None
        else struct.pack(">H", random.randint(1, 0xFFFF))
    )
    props: list[bytes] = []
    for epc in epcs:
        props.append(bytes([epc & 0xFF, 0x00]))
    return b"".join(
        [
            b"\x10\x81",
            tid_bytes,
            _DEFAULT_USER_EOJ,
            target_eoj,
            b"\x62",
            bytes([len(props)]),
            *props,
        ]
    )


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


def _decode_eoj_list(data: bytes) -> list[str]:
    if not data:
        return []
    items: list[str] = []
    for start in range(0, len(data) - (len(data) % 3), 3):
        chunk = data[start : start + 3]
        if len(chunk) == 3:
            items.append(chunk.hex().upper())
    return items


def _property_value(epc: int, edt: bytes) -> tuple[Any, str]:
    if epc in {0xD5, 0xD6, 0xD7}:
        return _decode_eoj_list(edt), "eoj_list"
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


def _query_frames(
    *,
    packet: bytes,
    destination: tuple[str, int],
    bind_ip: str | None,
    timeout: int,
    retry: int,
    limit: int,
) -> list[dict[str, Any]]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception:
            pass
        # Bind to ECHONET port to receive multicast responses
        bind_to = bind_ip if bind_ip else "0.0.0.0"
        try:
            sock.bind((bind_to, 3610))
        except Exception:
            try:
                sock.bind(("0.0.0.0", 3610))
            except Exception:
                sock.bind(("0.0.0.0", 0))

        # Join multicast group so we receive device responses
        mcast_addr = destination[0] if destination else "224.0.23.0"
        iface_ip = bind_ip if bind_ip else "0.0.0.0"
        try:
            mreq = struct.pack(
                "4s4s", socket.inet_aton(mcast_addr), socket.inet_aton(iface_ip)
            )
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except Exception:
            pass

        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        except Exception:
            pass
        try:
            sock.setsockopt(
                socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(iface_ip)
            )
        except Exception:
            pass
        sock.settimeout(0.25)

        frames: list[dict[str, Any]] = []
        seen: set[tuple[Any, ...]] = set()
        for attempt in range(retry):
            try:
                sock.sendto(packet, destination)
            except Exception:
                break
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    data, source = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                except OSError:
                    break
                parsed = _parse_frame(data)
                if not parsed:
                    continue
                parsed["source_ip"] = source[0] if source else None
                parsed["source_port"] = source[1] if source else None
                key = (
                    parsed.get("source_ip"),
                    parsed.get("seoj"),
                    parsed.get("deoj"),
                    parsed.get("esv"),
                    tuple(
                        (prop.get("epc"), prop.get("raw_hex"))
                        for prop in parsed.get("properties", [])
                    ),
                )
                if key in seen:
                    continue
                seen.add(key)
                frames.append(parsed)
                if limit > 0 and len(frames) >= limit:
                    return frames
            if limit > 0 and len(frames) >= limit:
                break
            if attempt + 1 < retry:
                time.sleep(0.15)
        return frames
    finally:
        sock.close()


def _property_map(properties: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for prop in properties:
        epc = str(prop.get("epc") or "").upper()
        if not epc:
            continue
        if epc in mapped:
            if prop.get("raw_hex") and prop.get("raw_hex") != mapped[epc].get(
                "raw_hex"
            ):
                continue
        mapped[epc] = dict(prop)
    return mapped


def _merge_properties(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for group in groups:
        for prop in group:
            key = (str(prop.get("epc") or ""), str(prop.get("raw_hex") or ""))
            if key[0]:
                merged[key] = dict(prop)
    return list(merged.values())


def _summarize_node_item(
    source_ip: str | None,
    frames: list[dict[str, Any]],
    *,
    bind_ip: str | None = None,
) -> dict[str, Any]:
    properties = _merge_properties(*(frame.get("properties") or [] for frame in frames))
    node_profile_props = _property_map(properties)
    eoj_list: list[str] = []
    for epc in ("D5", "D6", "D7"):
        prop = node_profile_props.get(epc)
        if prop and isinstance(prop.get("value"), list):
            eoj_list.extend([str(v).upper() for v in prop.get("value") if v])
    eoj_list = sorted({v for v in eoj_list if v})

    manufacturer = None
    manufacturer_name = None
    if node_profile_props.get("8A"):
        raw = node_profile_props["8A"].get("raw_hex") or node_profile_props["8A"].get(
            "value"
        )
        manufacturer = str(raw) if raw is not None else None
        if manufacturer is not None:
            manufacturer_name = _MANUFACTURER_NAMES.get(manufacturer)
    model = None
    for candidate in ("83", "8B", "8C"):
        if node_profile_props.get(candidate):
            model = node_profile_props[candidate].get("raw_hex") or node_profile_props[
                candidate
            ].get("value")
            break

    node_profile = {
        "eoj": frames[0].get("seoj") if frames else "0EF001",
        "properties": properties,
    }

    scope_info = _classify_node_scope(source_ip, bind_ip)
    return {
        "ip": source_ip,
        "node_id": source_ip,
        "node_profile": node_profile,
        "manufacturer": manufacturer,
        "manufacturer_name": manufacturer_name,
        "model": model,
        "eoj_list": eoj_list,
        "reachable": bool(frames),
        "scope": scope_info.get("scope"),
        "on_lan": scope_info.get("on_lan"),
        "is_self": scope_info.get("is_self"),
        "is_private": scope_info.get("is_private"),
        "same_subnet": scope_info.get("same_subnet"),
        "last_seen": _now_iso(),
    }


def _format_text(payload: dict[str, Any]) -> str:
    lines = [
        _(
            "msg.summary",
            default="ECHONET Lite discovery completed: {count} node(s) found in {elapsed_ms} ms.",
            count=payload.get("count", 0),
            elapsed_ms=payload.get("elapsed_ms", 0),
        )
    ]
    if payload.get("interface_used"):
        lines.append(f"Interface: {payload.get('interface_used')}")
    if payload.get("bind_ip"):
        lines.append(f"Bind IP: {payload.get('bind_ip')}")
    lines.append(f"Retry: {payload.get('retry')}")
    lines.append(f"Timeout: {payload.get('timeout')} s")
    if payload.get("scope_filter"):
        lines.append(f"Scope filter: {payload.get('scope_filter')}")
    summary = payload.get("summary") or {}
    if summary:
        lines.append(
            "Counts: local="
            + str(summary.get("local", 0))
            + " external="
            + str(summary.get("external", 0))
            + " self="
            + str(summary.get("self", 0))
            + " local_other="
            + str(summary.get("local_other", 0))
            + " unknown="
            + str(summary.get("unknown", 0))
        )
    lines.append("")

    items = payload.get("items") or []
    if not items:
        lines.append(_("msg.no_devices", default="No ECHONET Lite nodes were found."))
        return "\n".join(lines).strip()

    for idx, item in enumerate(items, 1):
        ip_label = item.get("ip") or item.get("ip_address") or "(unknown)"
        eoj_items = item.get("eoj_list") or []
        dev_name = ""
        for eoj_code in eoj_items:
            dev_name = _eoj_class_name(eoj_code)
            if dev_name:
                break
        if dev_name:
            lines.append(f"[{idx}] {dev_name} ({ip_label})")
        else:
            lines.append(f"[{idx}] {ip_label}")
        if item.get("scope"):
            scope_label = str(item.get("scope"))
            if item.get("on_lan") is True:
                scope_label += " (LAN)"
            elif item.get("scope") == "external":
                scope_label += " (WAN/public)"
            lines.append(f"  scope: {scope_label}")
        if item.get("node_id"):
            lines.append(f"  node_id: {item.get('node_id')}")
        if item.get("manufacturer"):
            mfr_code = item.get("manufacturer")
            mfr_name = item.get("manufacturer_name")
            if mfr_name:
                lines.append(f"  manufacturer: {mfr_name} ({mfr_code})")
            else:
                lines.append(f"  manufacturer: {mfr_code}")
        if item.get("model"):
            lines.append(f"  model: {item.get('model')}")
        if item.get("eoj_list"):
            eoj_items = item.get("eoj_list") or []
            eoj_parts = []
            for eoj_code in eoj_items:
                name = _eoj_class_name(eoj_code)
                if name:
                    eoj_parts.append(f"{eoj_code} ({name})")
                else:
                    eoj_parts.append(eoj_code)
            lines.append(f"  eoj_list: {', '.join(eoj_parts)}")
        lines.append(f"  reachable: {item.get('reachable')}")
        if item.get("last_seen"):
            lines.append(f"  last_seen: {item.get('last_seen')}")
        node_profile = item.get("node_profile") or {}
        props = node_profile.get("properties") or []
        lines.append(f"  node_profile_properties: {len(props)}")
        lines.append("")
    return "\n".join(lines).strip()


def _get_eoj_localized_name(en_name: str, lang: str) -> str:
    """Look up localized EOJ class name from tool JSON for a given language.

    Normalizes lang tag (e.g., 'zh-cn' -> 'zh_CN') before lookup.
    Returns empty string if not found.
    """
    import json
    from pathlib import Path

    _json_path = Path(__file__).with_name("echonet_scan_tool.json")
    if not _json_path.is_file():
        return ""
    try:
        _tr_data = json.loads(_json_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    # Normalize lang tag
    norm = lang.replace("-", "_")
    entries = _tr_data.get(norm)
    if not entries:
        # Try first part fallback (e.g., 'zh' -> 'zh_CN')
        short = norm.split("_")[0] if "_" in norm else ""
        if short:
            for k, v in _tr_data.items():
                if k.startswith(short) and isinstance(v, dict) and en_name in v:
                    return v[en_name]
        return ""
    if isinstance(entries, dict) and en_name in entries:
        return entries[en_name]
    return ""


def _eoj_class_name(eoj_code: str) -> str:
    """Get localized EOJ class name for display.

    Returns Japanese name directly for ja locale.
    Looks up translations from tool JSON for other languages (34 langs).
    Falls back to English name if translation not available.
    """
    from ..i18n import detect_lang as _dl

    en_name = ""
    ja_name = ""
    mapped = _EOJ_RAW_MAP.get(eoj_code)
    if mapped is not None:
        entry = _EOJ_CLASS_NAMES.get(mapped)
        if entry:
            en_name, ja_name = entry[0], entry[1]
    else:
        combined = eoj_code[:4] if len(eoj_code) >= 4 else eoj_code
        try:
            ecc = int(combined, 16)
            entry = _EOJ_CLASS_NAMES.get(ecc)
            if entry:
                en_name, ja_name = entry[0], entry[1]
        except ValueError:
            pass
    if not en_name:
        return ""
    lang = _dl()
    if lang.startswith("ja"):
        return ja_name
    # Look up localized name from tool JSON translations
    localized = _get_eoj_localized_name(en_name, lang)
    if localized:
        return localized
    return en_name


def run_tool(args: dict[str, Any]) -> str:
    timeout = _normalize_int(args.get("timeout", _DEFAULT_TIMEOUT), _DEFAULT_TIMEOUT, 1)
    retry = _normalize_int(args.get("retry", _DEFAULT_RETRY), _DEFAULT_RETRY, 1)
    limit = _normalize_int(args.get("limit", _DEFAULT_LIMIT), _DEFAULT_LIMIT, 0)
    output_format = str(args.get("fmt") or "json").strip().lower()
    refresh = bool(args.get("refresh", False))
    interface_arg = args.get("interface")
    interface = str(interface_arg).strip() if interface_arg is not None else ""
    scope_filter = _normalize_scope_filter(args.get("scope", "all"))

    if timeout < 1:
        timeout = _DEFAULT_TIMEOUT
    if retry < 1:
        retry = _DEFAULT_RETRY
    if limit < 0:
        limit = _DEFAULT_LIMIT

    start_time = time.monotonic()
    cache_key = {
        "timeout": timeout,
        "interface": interface,
        "retry": retry,
        "limit": limit,
        "scope": scope_filter,
    }
    cached = (
        None
        if refresh
        else cache_get("scan", cache_key, ttl_seconds=_CACHE_TTL_SECONDS)
    )
    if cached is not None:
        payload = dict(cached.get("value") or {})
        payload["cache"] = {
            "hit": True,
            "age_ms": cached.get("age_ms"),
            "namespace": cached.get("namespace"),
            "key": cached.get("key"),
        }
        if output_format == "text":
            return _format_text(payload)
        return json.dumps(payload, ensure_ascii=False)
    try:
        bind_ip, interface_used = _resolve_interface(interface)
        packet = _build_get_request(_NODE_PROFILE_EOJ, sorted(_EPC_NODE_PROFILE))
        frames = _query_frames(
            packet=packet,
            destination=_MULTICAST_ADDR,
            bind_ip=bind_ip,
            timeout=timeout,
            retry=retry,
            limit=limit,
        )

        grouped: dict[str, list[dict[str, Any]]] = {}
        for frame in frames:
            source_ip = str(frame.get("source_ip") or frame.get("source_port") or "")
            if not source_ip:
                continue
            grouped.setdefault(source_ip, []).append(frame)

        items = [
            _summarize_node_item(source_ip, grouped[source_ip], bind_ip=bind_ip)
            for source_ip in sorted(grouped.keys())
        ]

        # Unicast fallback: if multicast found nothing, probe each IP directly
        if not items and bind_ip:
            _unicast_fallback_start = time.monotonic()
            subnet_base = ".".join(bind_ip.split(".")[:3])
            _epcs_simple = [0xD6]  # EPC list - minimal: just instance list
            probe_pkt = _build_get_request(_NODE_PROFILE_EOJ, _epcs_simple)

            def _unicast_probe(ip: str) -> dict[str, Any] | None:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(timeout)
                try:
                    sock.sendto(probe_pkt, (ip, 3610))
                    data, source = sock.recvfrom(65535)
                    parsed = _parse_frame(data)
                    if parsed:
                        parsed["source_ip"] = source[0] if source else None
                        parsed["source_port"] = source[1] if source else None
                        return parsed
                except Exception:
                    pass
                finally:
                    sock.close()
                return None

            max_w = min(64, 254)
            with ThreadPoolExecutor(max_workers=max_w) as ex:
                fut_map = {}
                for i in range(1, 255):
                    ip = f"{subnet_base}.{i}"
                    fut_map[ex.submit(_unicast_probe, ip)] = ip
                for fut in as_completed(fut_map):
                    try:
                        frame = fut.result()
                        if frame:
                            si = str(frame.get("source_ip") or "")
                            if si:
                                grouped.setdefault(si, []).append(frame)
                    except Exception:
                        pass

            items = [
                _summarize_node_item(source_ip, grouped[source_ip], bind_ip=bind_ip)
                for source_ip in sorted(grouped.keys())
            ]

        # Scope classification summary (before filter)
        summary = {
            "local": 0,
            "external": 0,
            "self": 0,
            "local_other": 0,
            "unknown": 0,
            "total": len(items),
        }
        for it in items:
            key = str(it.get("scope") or "unknown")
            if key not in summary:
                key = "unknown"
            summary[key] = int(summary.get(key, 0)) + 1

        if scope_filter != "all":
            items = [
                it
                for it in items
                if _scope_matches(str(it.get("scope") or "unknown"), scope_filter)
            ]
        if limit > 0:
            items = items[:limit]

        payload = {
            "ok": True,
            "count": len(items),
            "items": items,
            "summary": summary,
            "scope_filter": scope_filter,
            "interface_used": interface_used,
            "bind_ip": bind_ip,
            "timeout": timeout,
            "retry": retry,
            "limit": limit,
            "elapsed_ms": int((time.monotonic() - start_time) * 1000),
            "cache": {
                "hit": False,
                "namespace": "scan",
                "key": json.dumps(cache_key, ensure_ascii=False, sort_keys=True),
            },
        }
        cache_set("scan", cache_key, payload)
        if output_format == "text":
            return _format_text(payload)
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        err_payload = {
            "ok": False,
            "error": {
                "code": "communication_failed",
                "message": str(exc),
            },
            "elapsed_ms": int((time.monotonic() - start_time) * 1000),
        }
        if output_format == "text":
            return f"Error: {exc}"
        return json.dumps(err_payload, ensure_ascii=False)
