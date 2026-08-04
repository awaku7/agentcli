"""Local PCAP analysis and filtered extraction tool.

The tool intentionally returns metadata only. Packet bytes and payloads remain local.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .._pip_auto import install_with_status
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

# IANA/common service ports are a classification aid, not a security allowlist.
# Site-specific ports can be supplied through thresholds.allowed_destination_ports.
WELL_KNOWN_SERVICES = {
    20: "ftp-data", 21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp",
    53: "dns", 67: "dhcp-server", 68: "dhcp-client", 69: "tftp",
    80: "http", 110: "pop3", 119: "nntp", 123: "ntp", 135: "msrpc",
    137: "netbios-ns", 138: "netbios-dgm", 139: "netbios-ssn", 143: "imap",
    161: "snmp", 162: "snmp-trap", 389: "ldap", 443: "https", 445: "smb",
    465: "smtps", 500: "isakmp", 514: "syslog", 587: "submission",
    636: "ldaps", 993: "imaps", 995: "pop3s", 1433: "ms-sql",
    1521: "oracle", 1723: "pptp", 1900: "ssdp", 2049: "nfs",
    2375: "docker", 2376: "docker-tls", 3306: "mysql", 3389: "rdp",
    4500: "ipsec-nat-t", 5000: "app/http-alt", 5222: "xmpp-client",
    5228: "google-play", 5229: "google-services", 5353: "mdns",
    5432: "postgresql", 5672: "amqp", 5900: "vnc", 6379: "redis",
    6443: "kubernetes-api", 8000: "http-alt", 8080: "http-proxy",
    8443: "https-alt", 9000: "app/http-alt", 9200: "elasticsearch",
    11211: "memcached", 27017: "mongodb",
}
BUILTIN_WELL_KNOWN_PORTS = set(WELL_KNOWN_SERVICES)


def _scapy_modules():
    try:
        from scapy.layers.inet import IP, TCP, UDP
        from scapy.layers.inet6 import IPv6
        from scapy.layers.l2 import Ether
        from scapy.utils import PcapReader, PcapWriter
    except ImportError:
        if not install_with_status("scapy", "scapy", version_spec=">=2.6.0"):
            raise RuntimeError("scapy is unavailable")
        from scapy.layers.inet import IP, TCP, UDP
        from scapy.layers.inet6 import IPv6
        from scapy.layers.l2 import Ether
        from scapy.utils import PcapReader, PcapWriter
    return IP, IPv6, TCP, UDP, Ether, PcapReader, PcapWriter


def _iter_packets(path: str) -> Iterable[Any]:
    *_, PcapReader, _PcapWriter = _scapy_modules()
    return PcapReader(path)


def _open_writer(path: str) -> Any:
    *_, PcapWriter = _scapy_modules()
    return PcapWriter(path, append=False, sync=False)


def _write_packet(writer: Any, packet: Any) -> None:
    writer.write(packet)


def _close_reader(reader: Any) -> None:
    close = getattr(reader, "close", None)
    if callable(close):
        close()


def _close_writer(writer: Any) -> None:
    close = getattr(writer, "close", None)
    if callable(close):
        close()


def _pcap_cache_path(source: Path) -> Path:
    configured_root = os.environ.get("UAGENT_PCAP_CACHE_DIR")
    root = Path(configured_root).expanduser() if configured_root else Path.home() / ".uag" / "cache" / "pcap"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    return root / f"{digest}.sqlite"


def _is_real_pcap(source: Path) -> bool:
    try:
        with source.open("rb") as handle:
            return handle.read(4) in {
                b"\xd4\xc3\xb2\xa1",
                b"\xa1\xb2\xc3\xd4",
                b"\x4d\x3c\xb2\xa1",
                b"\xa1\xb2\x3c\x4d",
                b"\x0a\x0d\x0d\x0a",
            }
    except OSError:
        return False


def _metadata_records(source: Path) -> list[dict[str, Any]] | None:
    """Return cached packet metadata, or None when caching is not applicable."""
    if not _is_real_pcap(source):
        return None
    cache = _pcap_cache_path(source)
    cache.parent.mkdir(parents=True, exist_ok=True)
    signature = (str(source.stat().st_size), str(source.stat().st_mtime_ns))
    try:
        with sqlite3.connect(cache) as db:
            db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS packets (id INTEGER PRIMARY KEY, data TEXT NOT NULL)")
            row = db.execute("SELECT value FROM meta WHERE key='signature'").fetchone()
            if row and row[0] == "|".join(signature):
                return [json.loads(item[0]) for item in db.execute("SELECT data FROM packets ORDER BY id")]
            db.execute("DELETE FROM packets")
            db.execute("DELETE FROM meta")
            reader = _iter_packets(str(source))
            records: list[dict[str, Any]] = []
            try:
                for packet in reader:
                    record = _packet_info(packet)
                    records.append(record)
                    db.execute("INSERT INTO packets(data) VALUES (?)", (json.dumps(record, ensure_ascii=False),))
            finally:
                _close_reader(reader)
            db.execute("INSERT INTO meta(key, value) VALUES ('signature', ?)", ("|".join(signature),))
            db.commit()
            return records
    except (OSError, sqlite3.Error, ValueError, TypeError):
        return None


def _get(packet: Any, key: str, default: Any = None) -> Any:
    if isinstance(packet, dict):
        return packet.get(key, default)
    return getattr(packet, key, default)


def _packet_info(packet: Any) -> dict[str, Any]:
    """Extract only safe metadata; never include payload bytes."""
    if isinstance(packet, dict):
        return {
            "src_ip": packet.get("src_ip"),
            "dst_ip": packet.get("dst_ip"),
            "protocol": str(packet.get("protocol", "")).lower(),
            "src_port": packet.get("src_port"),
            "dst_port": packet.get("dst_port"),
            "length": int(packet.get("length", 0) or 0),
            "timestamp": float(packet.get("timestamp", 0.0) or 0.0),
            "dns_rcode": packet.get("dns_rcode"),
            "dns_query_length": packet.get("dns_query_length"),
            "tcp_flags": packet.get("tcp_flags"),
            "tcp_seq": packet.get("tcp_seq"),
            "tcp_payload_length": packet.get("tcp_payload_length", 0),
            "rtt_ms": packet.get("rtt_ms"),
            "ip_ttl": packet.get("ip_ttl"),
        }

    IP, IPv6, TCP, UDP, _Ether, *_ = _scapy_modules()
    info: dict[str, Any] = {
        "src_ip": None,
        "dst_ip": None,
        "protocol": "other",
        "src_port": None,
        "dst_port": None,
        "length": int(len(packet)),
        "timestamp": float(getattr(packet, "time", 0.0) or 0.0),
    }
    if packet.haslayer(IP):
        layer = packet[IP]
        info.update(src_ip=layer.src, dst_ip=layer.dst)
    elif packet.haslayer(IPv6):
        layer = packet[IPv6]
        info.update(src_ip=layer.src, dst_ip=layer.dst)
    if packet.haslayer(TCP):
        layer = packet[TCP]
        info.update(
            protocol="tcp",
            src_port=int(layer.sport),
            dst_port=int(layer.dport),
            tcp_seq=int(layer.seq),
            tcp_payload_length=int(len(layer.payload)),
            tcp_flags=str(layer.flags),
        )
    elif packet.haslayer(UDP):
        layer = packet[UDP]
        info.update(protocol="udp", src_port=int(layer.sport), dst_port=int(layer.dport))
    elif info["src_ip"] or info["dst_ip"]:
        info["protocol"] = "ip"
    return info


def _matches(info: dict[str, Any], spec: dict[str, Any]) -> bool:
    protocol = str(spec.get("protocol", "")).lower()
    if protocol and info.get("protocol") != protocol:
        return False

    for field in ("src_ip", "dst_ip"):
        expected = spec.get(field)
        if expected and info.get(field) != expected:
            return False

    for field in ("src_cidr", "dst_cidr"):
        expected = spec.get(field)
        value = info.get(field.removesuffix("_cidr"))
        if expected:
            try:
                if value is None or ipaddress.ip_address(value) not in ipaddress.ip_network(expected):
                    return False
            except ValueError:
                return False

    for field in ("src_port", "dst_port"):
        expected = spec.get(field)
        if expected is not None and info.get(field) != int(expected):
            return False

    port = spec.get("port")
    if port is not None and int(port) not in (info.get("src_port"), info.get("dst_port")):
        return False

    length = int(info.get("length", 0) or 0)
    if spec.get("min_length") is not None and length < int(spec["min_length"]):
        return False
    if spec.get("max_length") is not None and length > int(spec["max_length"]):
        return False
    return True


def _artifact(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"kind": "pcap", "name": path.name, "local": True, "size": path.stat().st_size, "sha256": digest}


def _error(code: str, message: str) -> str:
    return json.dumps({"ok": False, "error": {"code": code, "message": message}}, ensure_ascii=False)


def _extract(args: dict[str, Any]) -> str:
    source_text = str(args.get("pcap_path", "")).strip()
    output_text = str(args.get("output_path", "")).strip()
    if not source_text:
        return _error("INPUT_REQUIRED", "pcap_path is required.")
    if not output_text:
        return _error("OUTPUT_REQUIRED", "output_path is required.")
    source = Path(source_text).expanduser()
    output = Path(output_text).expanduser()
    if not source.is_file():
        return _error("INPUT_NOT_FOUND", "The input pcap file was not found.")
    if not output:
        return _error("OUTPUT_REQUIRED", "output_path is required.")
    try:
        if source.resolve() == output.resolve():
            return _error("INPUT_OUTPUT_SAME", "Input and output paths must be different.")
    except OSError:
        return _error("INVALID_PATH", "The input or output path is invalid.")
    if output.exists() and not bool(args.get("overwrite", False)):
        return _error("OUTPUT_EXISTS", "The output file already exists.")
    output.parent.mkdir(parents=True, exist_ok=True)

    limit = max(1, min(int(args.get("limit", 10000)), 100000))
    reader = _iter_packets(str(source))
    writer = _open_writer(str(output))
    read_packets = written_packets = 0
    truncated = False
    try:
        for packet in reader:
            read_packets += 1
            if not _matches(_packet_info(packet), dict(args.get("filter") or {})):
                continue
            if written_packets >= limit:
                truncated = True
                break
            _write_packet(writer, packet)
            written_packets += 1
    finally:
        _close_reader(reader)
        _close_writer(writer)

    return json.dumps(
        {
            "ok": True,
            "operation": "extract",
            "input_name": source.name,
            "output_name": output.name,
            "read_packets": read_packets,
            "written_packets": written_packets,
            "skipped_packets": read_packets - written_packets,
            "bytes_written": output.stat().st_size,
            "truncated": truncated,
            "artifact": _artifact(output),
        },
        ensure_ascii=False,
    )


def _summary(args: dict[str, Any]) -> str:
    source_text = str(args.get("pcap_path", "")).strip()
    if not source_text:
        return _error("INPUT_REQUIRED", "pcap_path is required.")
    source = Path(source_text).expanduser()
    if not source.is_file():
        return _error("INPUT_NOT_FOUND", "The input pcap file was not found.")

    limit = max(1, min(int(args.get("limit", 10000)), 100000))
    filter_spec = dict(args.get("filter") or {})
    reader = _iter_packets(str(source))
    packet_count = total_bytes = read_packets = 0
    protocols: dict[str, int] = {}
    truncated = False
    try:
        for packet in reader:
            read_packets += 1
            info = _packet_info(packet)
            if not _matches(info, filter_spec):
                continue
            if packet_count >= limit:
                truncated = True
                break
            packet_count += 1
            total_bytes += int(info.get("length", 0) or 0)
            protocol = str(info.get("protocol") or "other")
            protocols[protocol] = protocols.get(protocol, 0) + 1
    finally:
        _close_reader(reader)

    return json.dumps(
        {
            "ok": True,
            "operation": "summary",
            "packet_count": packet_count,
            "total_bytes": total_bytes,
            "protocols": protocols,
            "truncated": truncated,
        },
        ensure_ascii=False,
    )


def _packets(args: dict[str, Any]) -> str:
    source_text = str(args.get("pcap_path", "")).strip()
    if not source_text:
        return _error("INPUT_REQUIRED", "pcap_path is required.")
    source = Path(source_text).expanduser()
    if not source.is_file():
        return _error("INPUT_NOT_FOUND", "The input pcap file was not found.")

    detail_level = max(0, min(int(args.get("detail_level", 1)), 2))
    limit = max(1, min(int(args.get("limit", 100)), 10000))
    filter_spec = dict(args.get("filter") or {})
    selected: list[dict[str, Any]] = []
    read_index = 0
    truncated = False
    reader = _iter_packets(str(source))
    try:
        for packet in reader:
            index = read_index
            read_index += 1
            info = _packet_info(packet)
            if not _matches(info, filter_spec):
                continue
            if len(selected) >= limit:
                truncated = True
                break
            item = {
                "index": index,
                "timestamp": info.get("timestamp", 0.0),
                "src_ip": info.get("src_ip"),
                "dst_ip": info.get("dst_ip"),
                "src_port": info.get("src_port"),
                "dst_port": info.get("dst_port"),
                "protocol": info.get("protocol"),
                "length": info.get("length", 0),
            }
            if detail_level >= 2:
                for key in ("tcp_flags", "tcp_seq", "tcp_payload_length", "dns_rcode", "dns_query_length"):
                    if info.get(key) is not None:
                        item[key] = info[key]
            selected.append(item)
    finally:
        _close_reader(reader)

    return json.dumps(
        {
            "ok": True,
            "operation": "packets",
            "packets": selected,
            "returned_packets": len(selected),
            "truncated": truncated,
        },
        ensure_ascii=False,
    )


def _statistics(args: dict[str, Any]) -> str:
    source_text = str(args.get("pcap_path", "")).strip()
    if not source_text:
        return _error("INPUT_REQUIRED", "pcap_path is required.")
    source = Path(source_text).expanduser()
    if not source.is_file():
        return _error("INPUT_NOT_FOUND", "The input pcap file was not found.")

    packet_count = total_bytes = 0
    first_seen: float | None = None
    last_seen: float | None = None
    protocols: dict[str, int] = {}
    reader = _iter_packets(str(source))
    try:
        for packet in reader:
            info = _packet_info(packet)
            timestamp = float(info.get("timestamp", 0.0) or 0.0)
            packet_count += 1
            total_bytes += int(info.get("length", 0) or 0)
            first_seen = timestamp if first_seen is None else min(first_seen, timestamp)
            last_seen = timestamp if last_seen is None else max(last_seen, timestamp)
            protocol = str(info.get("protocol") or "other")
            protocols[protocol] = protocols.get(protocol, 0) + 1
    finally:
        _close_reader(reader)

    duration = 0.0 if first_seen is None or last_seen is None else last_seen - first_seen
    return json.dumps(
        {
            "ok": True,
            "operation": "statistics",
            "packet_count": packet_count,
            "total_bytes": total_bytes,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "duration_seconds": round(duration, 6),
            "protocols": protocols,
        },
        ensure_ascii=False,
    )


def _flows(args: dict[str, Any]) -> str:
    source_text = str(args.get("pcap_path", "")).strip()
    if not source_text:
        return _error("INPUT_REQUIRED", "pcap_path is required.")
    source = Path(source_text).expanduser()
    if not source.is_file():
        return _error("INPUT_NOT_FOUND", "The input pcap file was not found.")

    limit = max(1, min(int(args.get("limit", 1000)), 10000))
    filter_spec = dict(args.get("filter") or {})
    flow_map: dict[tuple[Any, ...], dict[str, Any]] = {}
    reader = _iter_packets(str(source))
    try:
        for packet in reader:
            info = _packet_info(packet)
            if not _matches(info, filter_spec):
                continue
            key = (
                info.get("src_ip"),
                info.get("dst_ip"),
                info.get("src_port"),
                info.get("dst_port"),
                info.get("protocol"),
            )
            timestamp = float(info.get("timestamp", 0.0) or 0.0)
            entry = flow_map.setdefault(
                key,
                {
                    "src_ip": info.get("src_ip"),
                    "dst_ip": info.get("dst_ip"),
                    "src_port": info.get("src_port"),
                    "dst_port": info.get("dst_port"),
                    "protocol": info.get("protocol"),
                    "packets": 0,
                    "bytes": 0,
                    "first_seen": timestamp,
                    "last_seen": timestamp,
                },
            )
            entry["packets"] += 1
            entry["bytes"] += int(info.get("length", 0) or 0)
            entry["first_seen"] = min(entry["first_seen"], timestamp)
            entry["last_seen"] = max(entry["last_seen"], timestamp)
    finally:
        _close_reader(reader)

    flows = []
    for entry in list(flow_map.values())[:limit]:
        item = dict(entry)
        item["duration_seconds"] = round(item.pop("last_seen") - item["first_seen"], 6)
        flows.append(item)
    return json.dumps(
        {
            "ok": True,
            "operation": "flows",
            "flow_count": len(flow_map),
            "flows": flows,
            "truncated": len(flow_map) > limit,
        },
        ensure_ascii=False,
    )


def _detect(args: dict[str, Any]) -> str:
    source_text = str(args.get("pcap_path", "")).strip()
    if not source_text:
        return _error("INPUT_REQUIRED", "pcap_path is required.")
    source = Path(source_text).expanduser()
    if not source.is_file():
        return _error("INPUT_NOT_FOUND", "The input pcap file was not found.")

    rules = list(args.get("rules") or ["port_scan"])
    supported = {"port_scan", "connection_burst", "beaconing", "suspicious_dns", "large_transfer", "cleartext_protocol", "repeated_failure", "host_scan", "unusual_port", "tcp_retransmission", "long_lived_connection", "broadcast_anomaly", "syn_flood_candidate", "rtt_anomaly", "protocol_anomaly"}
    unknown = [str(rule) for rule in rules if str(rule) not in supported]
    if unknown:
        return _error("UNKNOWN_DETECTION_RULE", f"Unsupported detection rule: {unknown[0]}")

    thresholds = dict(args.get("thresholds") or {})
    if "unusual_port" in rules:
        configured_ports = thresholds.get("allowed_destination_ports")
        allowed_destination_ports = (
            {int(port) for port in configured_ports}
            if configured_ports
            else set(BUILTIN_WELL_KNOWN_PORTS)
        )
        port_registry = "custom" if configured_ports else "builtin"
    port_threshold = max(2, int(thresholds.get("port_scan_distinct_ports", 20)))
    window = max(1.0, float(thresholds.get("port_scan_window_seconds", 10)))
    limit = max(1, min(int(args.get("limit", 100)), 1000))
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    packets_analyzed = 0
    cached_records = _metadata_records(source)
    if cached_records is not None:
        packet_records = cached_records
    else:
        reader = _iter_packets(str(source))
        packet_records = []
        try:
            for packet in reader:
                packet_records.append(_packet_info(packet))
        finally:
            _close_reader(reader)

    for info in packet_records:
        packets_analyzed += 1
        if info.get("protocol") not in {"tcp", "udp", "dns", "http", "ftp", "telnet", "smtp", "imap", "pop3"}:
            continue
        src = str(info.get("src_ip") or "")
        dst = str(info.get("dst_ip") or "")
        if not src or not dst:
            continue
        if info.get("protocol") != "dns" and info.get("dst_port") is None:
            continue
        groups.setdefault((src, dst), []).append(info)

    findings: list[dict[str, Any]] = []
    if "port_scan" in rules:
        for (src, dst), events in groups.items():
            events = [event for event in events if event.get("protocol") == "tcp"]
            events.sort(key=lambda item: float(item.get("timestamp", 0.0) or 0.0))
            for start in range(len(events)):
                first_time = float(events[start].get("timestamp", 0.0) or 0.0)
                window_events = [
                    event for event in events[start:]
                    if float(event.get("timestamp", 0.0) or 0.0) - first_time <= window
                ]
                ports = {int(event["dst_port"]) for event in window_events if event.get("dst_port") is not None}
                if len(ports) < port_threshold:
                    continue
                last_time = max(float(event.get("timestamp", 0.0) or 0.0) for event in window_events)
                confidence = min(0.99, 0.5 + (len(ports) - port_threshold) / max(port_threshold, 1) * 0.1)
                findings.append(
                    {
                        "id": f"finding-{len(findings) + 1:03d}",
                        "category": "port_scan",
                        "severity": "medium",
                        "confidence": round(confidence, 2),
                        "src": src,
                        "dst": dst,
                        "distinct_ports": len(ports),
                        "first_seen": first_time,
                        "last_seen": last_time,
                        "evidence": {"window_seconds": window, "event_count": len(window_events)},
                        "recommendation": "Review the source host and intended scan activity.",
                    }
                )
                break
            if len(findings) >= limit:
                break

    if "connection_burst" in rules:
        burst_threshold = max(2, int(thresholds.get("connection_burst_events", 100)))
        burst_window = max(1.0, float(thresholds.get("connection_burst_window_seconds", 10)))
        for (src, dst), events in groups.items():
            events = [event for event in events if event.get("protocol") in {"tcp", "udp"}]
            events.sort(key=lambda item: float(item.get("timestamp", 0.0) or 0.0))
            for start in range(len(events)):
                first_time = float(events[start].get("timestamp", 0.0) or 0.0)
                window_events = [
                    event for event in events[start:]
                    if float(event.get("timestamp", 0.0) or 0.0) - first_time <= burst_window
                ]
                if len(window_events) < burst_threshold:
                    continue
                last_time = max(float(event.get("timestamp", 0.0) or 0.0) for event in window_events)
                findings.append(
                    {
                        "id": f"finding-{len(findings) + 1:03d}",
                        "category": "connection_burst",
                        "severity": "medium",
                        "confidence": round(min(0.99, 0.5 + (len(window_events) - burst_threshold) / max(burst_threshold, 1) * 0.1), 2),
                        "src": src,
                        "dst": dst,
                        "event_count": len(window_events),
                        "first_seen": first_time,
                        "last_seen": last_time,
                        "evidence": {"window_seconds": burst_window, "event_count": len(window_events)},
                        "recommendation": "Review the connection burst and expected application behavior.",
                    }
                )
                break
            if len(findings) >= limit:
                break

    if "beaconing" in rules:
        min_events = max(4, int(thresholds.get("beaconing_min_events", 5)))
        jitter_ratio = max(0.0, min(float(thresholds.get("beaconing_jitter_ratio", 0.2)), 1.0))
        min_interval = max(0.1, float(thresholds.get("beaconing_min_interval_seconds", 1)))
        for (src, dst), events in groups.items():
            events = [event for event in events if event.get("protocol") in {"tcp", "udp"}]
            events.sort(key=lambda item: float(item.get("timestamp", 0.0) or 0.0))
            if len(events) < min_events:
                continue
            timestamps = [float(event.get("timestamp", 0.0) or 0.0) for event in events]
            intervals = [right - left for left, right in zip(timestamps, timestamps[1:])]
            intervals = [interval for interval in intervals if interval >= min_interval]
            if len(intervals) < min_events - 1:
                continue
            average = sum(intervals) / len(intervals)
            if average <= 0:
                continue
            jitter = max(abs(interval - average) for interval in intervals) / average
            if jitter > jitter_ratio:
                continue
            findings.append(
                {
                    "id": f"finding-{len(findings) + 1:03d}",
                    "category": "beaconing",
                    "severity": "low",
                    "confidence": round(min(0.95, 0.55 + (1.0 - jitter) * 0.2), 2),
                    "src": src,
                    "dst": dst,
                    "event_count": len(events),
                    "interval_seconds": round(average, 3),
                    "jitter_ratio": round(jitter, 3),
                    "first_seen": timestamps[0],
                    "last_seen": timestamps[-1],
                    "evidence": {"intervals": len(intervals), "jitter_ratio": round(jitter, 3)},
                    "recommendation": "Review the periodic communication and its expected application behavior.",
                }
            )
            if len(findings) >= limit:
                break

    if "suspicious_dns" in rules:
        dns_min_queries = max(2, int(thresholds.get("dns_min_queries", 10)))
        nxdomain_ratio_threshold = max(0.0, min(float(thresholds.get("dns_nxdomain_ratio", 0.5)), 1.0))
        for (src, dst), events in groups.items():
            dns_events = [event for event in events if event.get("protocol") == "dns"]
            if len(dns_events) < dns_min_queries:
                continue
            nxdomain_count = sum(1 for event in dns_events if str(event.get("dns_rcode", "")).upper() == "NXDOMAIN")
            ratio = nxdomain_count / len(dns_events)
            if ratio < nxdomain_ratio_threshold:
                continue
            timestamps = [float(event.get("timestamp", 0.0) or 0.0) for event in dns_events]
            findings.append(
                {
                    "id": f"finding-{len(findings) + 1:03d}",
                    "category": "suspicious_dns",
                    "severity": "medium",
                    "confidence": round(min(0.95, 0.5 + ratio * 0.4), 2),
                    "src": src,
                    "dst": dst,
                    "query_count": len(dns_events),
                    "nxdomain_count": nxdomain_count,
                    "nxdomain_ratio": round(ratio, 3),
                    "first_seen": min(timestamps),
                    "last_seen": max(timestamps),
                    "evidence": {"nxdomain_ratio": round(ratio, 3)},
                    "recommendation": "Review DNS activity and the requesting host; NXDOMAIN volume alone is not proof of malicious activity.",
                }
            )
            if len(findings) >= limit:
                break

    if "large_transfer" in rules:
        transfer_threshold = max(1, int(thresholds.get("large_transfer_bytes", 100_000_000)))
        transfer_groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for (src, dst), events in groups.items():
            transfer_events = [event for event in events if event.get("protocol") in {"tcp", "udp"}]
            if transfer_events:
                transfer_groups[(src, dst)] = transfer_events
        for (src, dst), events in transfer_groups.items():
            total_bytes = sum(int(event.get("length", 0) or 0) for event in events)
            if total_bytes < transfer_threshold:
                continue
            timestamps = [float(event.get("timestamp", 0.0) or 0.0) for event in events]
            findings.append(
                {
                    "id": f"finding-{len(findings) + 1:03d}",
                    "category": "large_transfer",
                    "severity": "low",
                    "confidence": round(min(0.95, 0.5 + total_bytes / max(transfer_threshold, 1) * 0.1), 2),
                    "src": src,
                    "dst": dst,
                    "event_count": len(events),
                    "total_bytes": total_bytes,
                    "first_seen": min(timestamps),
                    "last_seen": max(timestamps),
                    "evidence": {"threshold_bytes": transfer_threshold},
                    "recommendation": "Review whether the transfer is expected for this source and destination.",
                }
            )
            if len(findings) >= limit:
                break

    if "cleartext_protocol" in rules:
        cleartext = {"http", "ftp", "telnet", "smtp", "imap", "pop3"}
        for (src, dst), events in groups.items():
            for protocol in sorted({str(event.get("protocol")) for event in events} & cleartext):
                matching = [event for event in events if event.get("protocol") == protocol]
                timestamps = [float(event.get("timestamp", 0.0) or 0.0) for event in matching]
                findings.append(
                    {
                        "id": f"finding-{len(findings) + 1:03d}",
                        "category": "cleartext_protocol",
                        "severity": "medium",
                        "confidence": 0.95,
                        "src": src,
                        "dst": dst,
                        "protocol": protocol,
                        "event_count": len(matching),
                        "first_seen": min(timestamps),
                        "last_seen": max(timestamps),
                        "evidence": {"protocol": protocol},
                        "recommendation": "Review whether cleartext communication is expected; prefer encrypted alternatives.",
                    }
                )
                if len(findings) >= limit:
                    break
            if len(findings) >= limit:
                break

    if "repeated_failure" in rules:
        failure_threshold = max(2, int(thresholds.get("repeated_failure_events", 10)))
        for (src, dst), events in groups.items():
            failures = [
                event
                for event in events
                if event.get("protocol") == "tcp" and "R" in str(event.get("tcp_flags") or "").upper()
            ]
            if len(failures) < failure_threshold:
                continue
            timestamps = [float(event.get("timestamp", 0.0) or 0.0) for event in failures]
            findings.append(
                {
                    "id": f"finding-{len(findings) + 1:03d}",
                    "category": "repeated_failure",
                    "severity": "medium",
                    "confidence": round(min(0.95, 0.5 + len(failures) / max(failure_threshold, 1) * 0.1), 2),
                    "src": src,
                    "dst": dst,
                    "event_count": len(failures),
                    "first_seen": min(timestamps),
                    "last_seen": max(timestamps),
                    "evidence": {"tcp_reset_events": len(failures)},
                    "recommendation": "Review repeated TCP resets and the expected availability of the destination service.",
                }
            )
            if len(findings) >= limit:
                break

    if "host_scan" in rules:
        host_threshold = max(2, int(thresholds.get("host_scan_distinct_hosts", 20)))
        host_window = max(1.0, float(thresholds.get("host_scan_window_seconds", 10)))
        by_source: dict[str, list[dict[str, Any]]] = {}
        for events in groups.values():
            for event in events:
                if event.get("protocol") in {"tcp", "udp"}:
                    by_source.setdefault(str(event.get("src_ip")), []).append(event)
        for src, events in by_source.items():
            events.sort(key=lambda item: float(item.get("timestamp", 0.0) or 0.0))
            for start in range(len(events)):
                first_time = float(events[start].get("timestamp", 0.0) or 0.0)
                window_events = [
                    event for event in events[start:]
                    if float(event.get("timestamp", 0.0) or 0.0) - first_time <= host_window
                ]
                hosts = {str(event.get("dst_ip")) for event in window_events if event.get("dst_ip")}
                if len(hosts) < host_threshold:
                    continue
                last_time = max(float(event.get("timestamp", 0.0) or 0.0) for event in window_events)
                findings.append(
                    {
                        "id": f"finding-{len(findings) + 1:03d}",
                        "category": "host_scan",
                        "severity": "medium",
                        "confidence": round(min(0.95, 0.5 + (len(hosts) - host_threshold) / max(host_threshold, 1) * 0.1), 2),
                        "src": src,
                        "distinct_hosts": len(hosts),
                        "event_count": len(window_events),
                        "first_seen": first_time,
                        "last_seen": last_time,
                        "evidence": {"window_seconds": host_window, "event_count": len(window_events)},
                        "recommendation": "Review the source host and intended discovery activity.",
                    }
                )
                break
            if len(findings) >= limit:
                break

    if "unusual_port" in rules:
        allowed_ports = allowed_destination_ports
        # For TCP, identify the service side from the initial SYN. Reverse
        # packets normally expose the client's ephemeral port as dst_port.
        tcp_service_keys: set[tuple[str, str, int]] = set()
        tcp_syn_seen = False
        for events in groups.values():
            for event in events:
                if event.get("protocol") != "tcp":
                    continue
                flags = str(event.get("tcp_flags") or "").upper()
                if "S" in flags and "A" not in flags and event.get("dst_port") is not None:
                    tcp_syn_seen = True
                    tcp_service_keys.add(
                        (str(event.get("src_ip")), str(event.get("dst_ip")), int(event["dst_port"]))
                    )

        seen_ports: set[tuple[str, str, int]] = set()
        for events in groups.values():
            for event in events:
                protocol = str(event.get("protocol") or "")
                port = event.get("dst_port")
                if port is None or int(port) in allowed_ports:
                    continue
                key = (str(event.get("src_ip")), str(event.get("dst_ip")), int(port))
                if protocol == "tcp" and (not tcp_syn_seen or key not in tcp_service_keys):
                    # A partial TCP capture without an initial SYN cannot
                    # establish the server/client direction safely.
                    continue
                if protocol not in {"tcp", "udp"} or key in seen_ports:
                    continue
                seen_ports.add(key)
                direction_basis = "tcp_initial_syn" if protocol == "tcp" and tcp_syn_seen else "packet_destination"
                findings.append(
                    {
                        "id": f"finding-{len(findings) + 1:03d}",
                        "category": "unusual_port",
                        "severity": "low",
                        "confidence": 0.7,
                        "src": key[0],
                        "dst": key[1],
                        "dst_port": key[2],
                        "service": WELL_KNOWN_SERVICES.get(key[2]),
                        "port_registry": port_registry,
                        "protocol": protocol,
                        "direction": "server_bound" if protocol == "tcp" else "datagram_destination",
                        "evidence": {
                            "allowed_destination_ports": sorted(allowed_ports),
                            "direction_basis": direction_basis,
                        },
                        "recommendation": "Review whether the server-side destination port is expected in this environment.",
                    }
                )
                if len(findings) >= limit:
                    break
            if len(findings) >= limit:
                break

    if "tcp_retransmission" in rules:
        retransmission_groups: dict[tuple[str, str, int, int], list[dict[str, Any]]] = {}
        for events in groups.values():
            for event in events:
                if event.get("protocol") != "tcp" or not event.get("tcp_payload_length") or event.get("tcp_seq") is None:
                    continue
                key = (
                    str(event.get("src_ip")),
                    str(event.get("dst_ip")),
                    int(event.get("src_port") or 0),
                    int(event.get("dst_port") or 0),
                )
                retransmission_groups.setdefault(key, []).append(event)
        for (src, dst, src_port, dst_port), events in retransmission_groups.items():
            sequence_counts: dict[tuple[int, int], int] = {}
            for event in events:
                key = (int(event["tcp_seq"]), int(event["tcp_payload_length"]))
                sequence_counts[key] = sequence_counts.get(key, 0) + 1
            retransmission_count = sum(count - 1 for count in sequence_counts.values() if count > 1)
            if retransmission_count <= 0:
                continue
            timestamps = [float(event.get("timestamp", 0.0) or 0.0) for event in events]
            findings.append(
                {
                    "id": f"finding-{len(findings) + 1:03d}",
                    "category": "tcp_retransmission",
                    "severity": "low",
                    "confidence": round(min(0.95, 0.5 + retransmission_count / max(len(events), 1) * 0.5), 2),
                    "src": src,
                    "dst": dst,
                    "src_port": src_port,
                    "dst_port": dst_port,
                    "event_count": len(events),
                    "retransmission_count": retransmission_count,
                    "first_seen": min(timestamps),
                    "last_seen": max(timestamps),
                    "evidence": {"repeated_sequence_ranges": len([count for count in sequence_counts.values() if count > 1])},
                    "recommendation": "Review packet loss, congestion, link quality, and TCP endpoint behavior.",
                }
            )
            if len(findings) >= limit:
                break

    if "suspicious_dns" in rules:
        long_query_threshold = max(1, int(thresholds.get("dns_long_query_length", 200)))
        for (src, dst), events in groups.items():
            long_queries = [event for event in events if event.get("protocol") == "dns" and int(event.get("dns_query_length", 0) or 0) >= long_query_threshold]
            if not long_queries:
                continue
            findings.append(
                {
                    "id": f"finding-{len(findings) + 1:03d}",
                    "category": "suspicious_dns_long_query",
                    "severity": "low",
                    "confidence": 0.7,
                    "src": src,
                    "dst": dst,
                    "query_count": len(long_queries),
                    "max_query_length": max(int(event.get("dns_query_length", 0) or 0) for event in long_queries),
                    "evidence": {"threshold_length": long_query_threshold},
                    "recommendation": "Review long DNS queries without exposing the queried domain to the LLM.",
                }
            )
            if len(findings) >= limit:
                break

    if "long_lived_connection" in rules:
        long_threshold = max(1.0, float(thresholds.get("long_lived_seconds", 3600)))
        for (src, dst), events in groups.items():
            events = [event for event in events if event.get("protocol") in {"tcp", "udp"}]
            if len(events) < 2:
                continue
            timestamps = [float(event.get("timestamp", 0.0) or 0.0) for event in events]
            duration = max(timestamps) - min(timestamps)
            if duration < long_threshold:
                continue
            findings.append(
                {
                    "id": f"finding-{len(findings) + 1:03d}",
                    "category": "long_lived_connection",
                    "severity": "low",
                    "confidence": 0.8,
                    "src": src,
                    "dst": dst,
                    "duration_seconds": round(duration, 3),
                    "event_count": len(events),
                    "evidence": {"threshold_seconds": long_threshold},
                    "recommendation": "Review whether the long-lived connection is expected.",
                }
            )
            if len(findings) >= limit:
                break

    if "broadcast_anomaly" in rules:
        broadcast_threshold = max(2, int(thresholds.get("broadcast_events", 100)))
        excluded_broadcast_ports = {
            int(port)
            for port in thresholds.get("broadcast_excluded_ports", [137, 138, 1900, 5353, 17500])
        }
        broadcasts: dict[str, list[dict[str, Any]]] = {}
        for events in groups.values():
            for event in events:
                dst = str(event.get("dst_ip") or "")
                port_values = {
                    int(port)
                    for port in (event.get("src_port"), event.get("dst_port"))
                    if port is not None
                }
                if (
                    (dst == "255.255.255.255" or dst.endswith(".255") or dst.startswith("224."))
                    and not port_values.intersection(excluded_broadcast_ports)
                ):
                    broadcasts.setdefault(str(event.get("src_ip")), []).append(event)
        for src, events in broadcasts.items():
            if len(events) < broadcast_threshold:
                continue
            findings.append(
                {
                    "id": f"finding-{len(findings) + 1:03d}",
                    "category": "broadcast_anomaly",
                    "severity": "medium",
                    "confidence": 0.75,
                    "src": src,
                    "event_count": len(events),
                    "evidence": {"threshold_events": broadcast_threshold},
                    "recommendation": "Review broadcast or multicast volume and expected discovery protocols.",
                }
            )
            if len(findings) >= limit:
                break

    if "syn_flood_candidate" in rules:
        syn_threshold = max(2, int(thresholds.get("syn_events", 100)))
        for (src, dst), events in groups.items():
            tcp_events = [event for event in events if event.get("protocol") == "tcp"]
            syn_only = [
                event
                for event in tcp_events
                if "S" in str(event.get("tcp_flags") or "").upper()
                and "A" not in str(event.get("tcp_flags") or "").upper()
            ]
            if not syn_only:
                continue
            # SYN-ACKs are sent in the reverse direction. Count a handshake
            # only when the reverse packet matches the original port pair.
            reverse_events = groups.get((dst, src), [])
            reverse_syn_ack = {
                (int(event.get("src_port") or 0), int(event.get("dst_port") or 0))
                for event in reverse_events
                if event.get("protocol") == "tcp"
                and "S" in str(event.get("tcp_flags") or "").upper()
                and "A" in str(event.get("tcp_flags") or "").upper()
            }
            syn_keys = {
                (int(event.get("src_port") or 0), int(event.get("dst_port") or 0))
                for event in syn_only
            }
            syn_ack_count = sum(1 for src_port, dst_port in syn_keys if (dst_port, src_port) in reverse_syn_ack)
            if len(syn_keys) < syn_threshold or len(syn_keys) <= syn_ack_count * 2:
                continue
            findings.append(
                {
                    "id": f"finding-{len(findings) + 1:03d}",
                    "category": "syn_flood_candidate",
                    "severity": "high",
                    "confidence": 0.8,
                    "src": src,
                    "dst": dst,
                    "syn_count": len(syn_keys),
                    "syn_ack_count": syn_ack_count,
                    "evidence": {"threshold_syn_events": syn_threshold},
                    "recommendation": "Review incomplete TCP handshakes and confirm whether the traffic is authorized.",
                }
            )
            if len(findings) >= limit:
                break

    if "rtt_anomaly" in rules:
        rtt_threshold = max(1.0, float(thresholds.get("rtt_ms", 100)))
        for (src, dst), events in groups.items():
            rtts = [float(event["rtt_ms"]) for event in events if event.get("rtt_ms") is not None]
            if not rtts or sum(rtts) / len(rtts) < rtt_threshold:
                continue
            findings.append(
                {
                    "id": f"finding-{len(findings) + 1:03d}",
                    "category": "rtt_anomaly",
                    "severity": "low",
                    "confidence": 0.7,
                    "src": src,
                    "dst": dst,
                    "samples": len(rtts),
                    "avg_rtt_ms": round(sum(rtts) / len(rtts), 3),
                    "max_rtt_ms": max(rtts),
                    "evidence": {"threshold_ms": rtt_threshold},
                    "recommendation": "Review latency, congestion, routing, and link quality.",
                }
            )
            if len(findings) >= limit:
                break

    if "protocol_anomaly" in rules:
        for (src, dst), events in groups.items():
            anomalies = [event for event in events if event.get("protocol") == "tcp" and ("S" in str(event.get("tcp_flags") or "").upper() and "F" in str(event.get("tcp_flags") or "").upper() or str(event.get("tcp_flags") or "").upper() in {"", "NULL"})]
            if not anomalies:
                continue
            findings.append(
                {
                    "id": f"finding-{len(findings) + 1:03d}",
                    "category": "protocol_anomaly",
                    "severity": "medium",
                    "confidence": 0.8,
                    "src": src,
                    "dst": dst,
                    "event_count": len(anomalies),
                    "evidence": {"tcp_flag_anomaly": True},
                    "recommendation": "Review unusual TCP flag combinations and capture validity.",
                }
            )
            if len(findings) >= limit:
                break

    findings = findings[:limit]
    counts = {level: sum(1 for item in findings if item["severity"] == level) for level in ("high", "medium", "low")}
    return json.dumps(
        {
            "ok": True,
            "operation": "detect",
            "findings": findings,
            "summary": {"packets_analyzed": packets_analyzed, "findings": len(findings), **counts},
        },
        ensure_ascii=False,
    )


def _impact(args: dict[str, Any]) -> str:
    source_text = str(args.get("pcap_path", "")).strip()
    if not source_text:
        return _error("INPUT_REQUIRED", "pcap_path is required.")
    source = Path(source_text).expanduser()
    if not source.is_file():
        return _error("INPUT_NOT_FOUND", "The input pcap file was not found.")
    limit = max(1, min(int(args.get("limit", 20)), 100))
    records = _metadata_records(source)
    if records is None:
        reader = _iter_packets(str(source))
        records = []
        try:
            for packet in reader:
                records.append(_packet_info(packet))
        finally:
            _close_reader(reader)

    hosts: dict[str, dict[str, Any]] = {}
    seen_payloads: set[tuple[Any, ...]] = set()
    for event in records:
        src = str(event.get("src_ip") or "")
        dst = str(event.get("dst_ip") or "")
        if not src or not dst:
            continue
        length = int(event.get("length", 0) or 0)
        protocol = str(event.get("protocol") or "")
        flags = str(event.get("tcp_flags") or "").upper()
        connection_key = (src, dst, event.get("src_port"), event.get("dst_port"), protocol)
        for host, peer, is_source in ((src, dst, True), (dst, src, False)):
            item = hosts.setdefault(
                host,
                {
                    "device": host,
                    "packets": 0,
                    "bytes": 0,
                    "connections": set(),
                    "peers": set(),
                    "retransmissions": 0,
                    "resets": 0,
                    "syn_count": 0,
                    "broadcast_packets": 0,
                    "destinations": {},
                },
            )
            item["packets"] += 1
            item["bytes"] += length
            item["connections"].add(connection_key if is_source else (dst, src, event.get("dst_port"), event.get("src_port"), protocol))
            item["peers"].add(peer)
            if is_source:
                item["destinations"][peer] = item["destinations"].get(peer, 0) + length
            if "R" in flags:
                item["resets"] += 1
            if "S" in flags and "A" not in flags:
                item["syn_count"] += 1
            if dst == "255.255.255.255" or dst.endswith(".255") or dst.startswith("224.") or dst.startswith("ff02:"):
                item["broadcast_packets"] += 1
            if protocol == "tcp" and event.get("tcp_payload_length"):
                payload_key = (src, dst, event.get("src_port"), event.get("dst_port"), event.get("tcp_seq"), event.get("tcp_payload_length"))
                if payload_key in seen_payloads:
                    item["retransmissions"] += 1
                seen_payloads.add(payload_key)

    max_bytes = max((int(item["bytes"]) for item in hosts.values()), default=1)
    max_packets = max((int(item["packets"]) for item in hosts.values()), default=1)
    ranked = []
    for item in hosts.values():
        score = (
            40 * item["bytes"] / max_bytes
            + 20 * item["packets"] / max_packets
            + min(15, len(item["connections"]))
            + min(10, item["retransmissions"] / 5)
            + min(5, item["resets"] / 5)
            + min(5, item["syn_count"] / 20)
            + min(5, item["broadcast_packets"] / 100)
        )
        ranked.append(
            {
                "device": item["device"],
                "impact_score": round(min(100, score), 2),
                "packets": item["packets"],
                "bytes": item["bytes"],
                "connections": len(item["connections"]),
                "retransmissions": item["retransmissions"],
                "resets": item["resets"],
                "syn_count": item["syn_count"],
                "broadcast_packets": item["broadcast_packets"],
                "top_destinations": [
                    {"ip": ip, "bytes": bytes_}
                    for ip, bytes_ in sorted(item["destinations"].items(), key=lambda pair: pair[1], reverse=True)[:5]
                ],
            }
        )
    ranked.sort(key=lambda item: item["impact_score"], reverse=True)
    return json.dumps(
        {"ok": True, "operation": "impact", "devices": ranked[:limit], "device_count": len(ranked)},
        ensure_ascii=False,
    )


def run_tool(args: dict[str, Any]) -> str:
    operation = str(args.get("operation", "summary")).lower()
    try:
        if operation == "extract":
            return _extract(args)
        if operation == "summary":
            return _summary(args)
        if operation == "packets":
            return _packets(args)
        if operation == "flows":
            return _flows(args)
        if operation == "statistics":
            return _statistics(args)
        if operation == "detect":
            return _detect(args)
        if operation == "impact":
            return _impact(args)
        return _error("UNSUPPORTED_OPERATION", "Unsupported operation.")
    except Exception as exc:
        return _error("PCAP_ANALYZE_FAILED", str(exc))


TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "pcap_analyze",
        "description": _(
            "tool.description",
            default="Analyze a pcap locally and extract matching packets to another pcap.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pcap_path": {"type": "string", "description": "Input pcap path."},
                "operation": {"type": "string", "enum": ["summary", "statistics", "flows", "packets", "extract", "detect", "impact"], "description": "Operation."},
                "detail_level": {"type": "integer", "minimum": 0, "maximum": 2, "default": 1},
                "rules": {"type": "array", "items": {"type": "string", "enum": ["port_scan", "connection_burst", "beaconing", "suspicious_dns", "large_transfer", "cleartext_protocol", "repeated_failure", "host_scan", "unusual_port", "tcp_retransmission", "long_lived_connection", "broadcast_anomaly", "syn_flood_candidate", "rtt_anomaly", "protocol_anomaly"]}},
                "thresholds": {"type": "object", "description": "Detection thresholds."},
                "output_path": {"type": "string", "description": "Output pcap path."},
                "filter": {"type": "object", "description": "Filter fields."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100000},
                "overwrite": {"type": "boolean", "default": False},
            },
            "required": ["pcap_path", "operation", "output_path"],
        },
    },
}
