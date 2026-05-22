from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

import functools
import json
import os
import platform
import shutil
from datetime import datetime, timezone
from typing import Any, Optional

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_system_specs",
        "description": _(
            "tool.description",
            default="Get system specs (CPU/RAM/disks/volumes) in a best-effort cross-platform way.",
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "This tool is used for the following purpose: gather system specs such as OS, CPU, "
                "RAM size, storage disks (best-effort), and volume free space."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "system specs",
                "get_system_specs",
                "system specifications",
            ],
        ),
        "x_search_terms_en": [
            "system specs",
            "get_system_specs",
            "system specifications",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "include_volumes": {
                    "type": "boolean",
                    "description": _(
                        "param.include_volumes.description",
                        default="Include mounted volume usage information.",
                    ),
                    "default": True,
                },
                "include_disks": {
                    "type": "boolean",
                    "description": _(
                        "param.include_disks.description",
                        default="Include physical disk information when available (best-effort).",
                    ),
                    "default": True,
                },
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    "is_agent_content": False,
}

BUSY_LABEL = False


def _safe_int(x: Any) -> Optional[int]:
    try:
        return int(x)
    except Exception:
        return None


def _add_volume(
    out: dict[str, Any],
    mountpoint: str,
    *,
    fstype: str | None = None,
    device: str | None = None,
) -> None:
    try:
        du = shutil.disk_usage(mountpoint)
        out["volumes"].append(
            {
                "mountpoint": mountpoint,
                "fstype": fstype,
                "device": device,
                "total_bytes": du.total,
                "free_bytes": du.free,
                "used_bytes": du.used,
            }
        )
    except Exception:
        # ignore inaccessible mountpoints
        return


@functools.lru_cache(maxsize=1)
def _linux_sys_block_map() -> dict[str, dict[str, Any]]:
    sys_block = "/sys/block"
    out: dict[str, dict[str, Any]] = {}
    if not os.path.isdir(sys_block):
        return out

    for dev in os.listdir(sys_block):
        if dev.startswith(("loop", "ram", "dm-")):
            continue

        base = os.path.join(sys_block, dev)

        size_sectors = None
        try:
            with open(os.path.join(base, "size"), "r", encoding="utf-8") as f:
                size_sectors = int(f.read().strip())
        except Exception:
            pass

        size_bytes = size_sectors * 512 if size_sectors is not None else None

        model = vendor = None
        for pth, key in (
            (os.path.join(base, "device/model"), "model"),
            (os.path.join(base, "device/vendor"), "vendor"),
        ):
            try:
                with open(pth, "r", encoding="utf-8", errors="ignore") as f:
                    val = f.read().strip()
                if key == "model":
                    model = val
                else:
                    vendor = val
            except Exception:
                pass

        rotational = None
        try:
            with open(
                os.path.join(base, "queue/rotational"), "r", encoding="utf-8"
            ) as f:
                rotational = int(f.read().strip())
        except Exception:
            pass

        out[dev] = {
            "model": model,
            "vendor": vendor,
            "size_bytes": size_bytes,
            "rotational": rotational,  # 0=SSD-ish, 1=HDD-ish
        }

    return out


def _linux_collect_disks(out: dict[str, Any]) -> None:
    # Reuse cached /sys/block data to avoid repeated directory scans.
    sys_block = "/sys/block"
    if not os.path.isdir(sys_block):
        out["notes"].append("Linux: /sys/block not found; disks not collected.")
        return

    sysmap = _linux_sys_block_map()
    for dev, info in sysmap.items():
        out["disks"].append({"name": dev, **info})


def _darwin_sysctl(libc: Any, name: str) -> Optional[int]:
    import ctypes

    val = ctypes.c_uint64(0)
    size = ctypes.c_size_t(ctypes.sizeof(val))
    if (
        libc.sysctlbyname(name.encode(), ctypes.byref(val), ctypes.byref(size), None, 0)
        != 0
    ):
        return None
    return int(val.value)


def _darwin_sysctl_str(libc: Any, name: str) -> Optional[str]:
    import ctypes

    size = ctypes.c_size_t(0)
    if libc.sysctlbyname(name.encode(), None, ctypes.byref(size), None, 0) != 0:
        return None
    buf = ctypes.create_string_buffer(size.value)
    if libc.sysctlbyname(name.encode(), buf, ctypes.byref(size), None, 0) != 0:
        return None
    return buf.value.decode(errors="ignore").rstrip("\x00")


def _darwin_collect_volumes(out: dict[str, Any]) -> None:
    import ctypes
    import ctypes.util

    libc_path = ctypes.util.find_library("c")
    if not libc_path:
        out["notes"].append("macOS: libc not found; volumes not collected.")
        return
    libc = ctypes.CDLL(libc_path)

    class StatFs(ctypes.Structure):
        _fields_ = [
            ("f_bsize", ctypes.c_uint32),
            ("f_iosize", ctypes.c_int32),
            ("f_blocks", ctypes.c_uint64),
            ("f_bfree", ctypes.c_uint64),
            ("f_bavail", ctypes.c_uint64),
            ("f_files", ctypes.c_uint64),
            ("f_ffree", ctypes.c_uint64),
            ("f_fsid", ctypes.c_int32 * 2),
            ("f_owner", ctypes.c_uint32),
            ("f_type", ctypes.c_uint32),
            ("f_flags", ctypes.c_uint32),
            ("f_fssubtype", ctypes.c_uint32),
            ("f_fstypename", ctypes.c_char * 16),
            ("f_mntonname", ctypes.c_char * 1024),
            ("f_mntfromname", ctypes.c_char * 1024),
            ("f_reserved", ctypes.c_uint32 * 8),
        ]

    getmntinfo = libc.getmntinfo
    getmntinfo.argtypes = [ctypes.POINTER(ctypes.POINTER(StatFs)), ctypes.c_int]
    getmntinfo.restype = ctypes.c_int

    MNT_NOWAIT = 2
    bufp = ctypes.POINTER(StatFs)()
    n = getmntinfo(ctypes.byref(bufp), MNT_NOWAIT)
    if n <= 0:
        out["notes"].append("macOS: getmntinfo failed; volumes not collected.")
        return

    for i in range(n):
        st = bufp[i]
        mp = st.f_mntonname.decode(errors="ignore").rstrip("\x00")
        fstype = st.f_fstypename.decode(errors="ignore").rstrip("\x00")
        device = st.f_mntfromname.decode(errors="ignore").rstrip("\x00")
        if mp:
            _add_volume(out, mp, fstype=fstype, device=device)


def _init_system_specs_output() -> dict[str, Any]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "os": {
            "platform": os.name,
            "sys_platform": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
        },
        "cpu": {
            "model": None,
            "logical_cores": os.cpu_count(),
            "physical_cores": None,
            "max_mhz": None,
        },
        "memory": {
            "total_bytes": None,
        },
        "volumes": [],  # type: ignore[assignment]
        "disks": [],  # type: ignore[assignment]
        "notes": [],  # type: ignore[assignment]
    }


def _psutil_to_dict(obj: Any) -> Any:
    if hasattr(obj, "_asdict"):
        return obj._asdict()
    try:
        return dict(obj)
    except Exception:
        return obj


def _psutil_collect_boot(out: dict[str, Any], psutil: Any) -> None:
    try:
        bt = float(psutil.boot_time())
        out["boot"] = {
            "boot_time_epoch": bt,
            "boot_time_utc": datetime.fromtimestamp(bt, tz=timezone.utc).isoformat(),
            "uptime_seconds": max(0.0, datetime.now(timezone.utc).timestamp() - bt),
        }
    except Exception:
        out["notes"].append("psutil: failed to read boot time.")


def _psutil_collect_cpu(out: dict[str, Any], psutil: Any) -> None:
    try:
        out["cpu"]["logical_cores"] = psutil.cpu_count(logical=True)
        out["cpu"]["physical_cores"] = psutil.cpu_count(logical=False)
    except Exception:
        pass

    try:
        freq = psutil.cpu_freq()
        out["cpu"]["max_mhz"] = int(freq.max) if freq and freq.max else None
        out["cpu"]["min_mhz"] = int(freq.min) if freq and freq.min else None
        out["cpu"]["current_mhz"] = int(freq.current) if freq and freq.current else None
    except Exception:
        pass

    try:
        out["cpu"]["percent"] = psutil.cpu_percent(interval=None)
    except Exception:
        out["notes"].append("psutil: failed to read cpu_percent().")

    try:
        out["cpu"]["percpu_percent"] = psutil.cpu_percent(interval=None, percpu=True)
    except Exception:
        pass

    try:
        out["cpu"]["times"] = _psutil_to_dict(psutil.cpu_times())
    except Exception:
        pass

    try:
        out["cpu"]["stats"] = _psutil_to_dict(psutil.cpu_stats())
    except Exception:
        pass

    try:
        la = os.getloadavg()
        out["cpu"]["loadavg"] = {"1m": la[0], "5m": la[1], "15m": la[2]}
    except Exception:
        # Not available on Windows
        pass


def _psutil_collect_memory(out: dict[str, Any], psutil: Any) -> None:
    try:
        vm = psutil.virtual_memory()
        out["memory"]["total_bytes"] = int(vm.total)
        out["memory"]["virtual"] = _psutil_to_dict(vm)
    except Exception:
        pass

    try:
        out["memory"]["swap"] = _psutil_to_dict(psutil.swap_memory())
    except Exception:
        pass


def _psutil_collect_volumes(out: dict[str, Any], psutil: Any) -> None:
    try:
        out["volumes_psutil"] = []
        seen = set()
        for p in psutil.disk_partitions(all=False):
            if not p.mountpoint or p.mountpoint in seen:
                continue
            seen.add(p.mountpoint)
            try:
                du = psutil.disk_usage(p.mountpoint)
            except Exception:
                continue
            v = {
                "mountpoint": p.mountpoint,
                "fstype": getattr(p, "fstype", None),
                "device": getattr(p, "device", None),
                "opts": getattr(p, "opts", None),
                "total_bytes": int(du.total),
                "free_bytes": int(du.free),
                "used_bytes": int(du.used),
                "percent": float(getattr(du, "percent", 0.0)),
            }
            out["volumes"].append(
                {
                    "mountpoint": v["mountpoint"],
                    "fstype": v["fstype"],
                    "device": v["device"],
                    "total_bytes": v["total_bytes"],
                    "free_bytes": v["free_bytes"],
                    "used_bytes": v["used_bytes"],
                }
            )
            out["volumes_psutil"].append(v)
    except Exception:
        out["notes"].append("psutil: failed to enumerate volumes.")


def _psutil_collect_disks(out: dict[str, Any], psutil: Any, *, system: str) -> None:
    try:
        try:
            tot = psutil.disk_io_counters(perdisk=False)
            out["disks_total_io"] = _psutil_to_dict(tot)
        except Exception:
            out["disks_total_io"] = None
    except Exception:
        out["notes"].append("psutil: failed to read total disk I/O counters.")
        out["disks_total_io"] = None

    # Per-disk counters are skipped for speed; best-effort disk metadata is kept instead.
    if system == "Linux":
        try:
            sysmap = _linux_sys_block_map()
            for name, info in sysmap.items():
                out["disks"].append({"name": name, **info})
        except Exception:
            out["notes"].append("Linux: failed to collect disks from /sys/block.")
    else:
        out["notes"].append("psutil: per-disk I/O counters skipped for speed.")


def _psutil_collect_network(out: dict[str, Any], psutil: Any, *, system: str) -> None:
    try:
        out["network"] = {
            "if_addrs": {},
            "if_stats": {},
            "io": None,
            "connections": None,
            "connections_truncated": False,
        }

        if system != "Windows":
            try:
                addrs = psutil.net_if_addrs()
                for ifname, items in addrs.items():
                    out["network"]["if_addrs"][ifname] = [
                        {
                            "family": int(getattr(a.family, "value", a.family)),
                            "address": getattr(a, "address", None),
                            "netmask": getattr(a, "netmask", None),
                            "broadcast": getattr(a, "broadcast", None),
                            "ptp": getattr(a, "ptp", None),
                        }
                        for a in items
                    ]
            except Exception:
                out["notes"].append("psutil: failed to read net_if_addrs().")

            try:
                stats = psutil.net_if_stats()
                for ifname, st in stats.items():
                    out["network"]["if_stats"][ifname] = _psutil_to_dict(st)
            except Exception:
                out["notes"].append("psutil: failed to read net_if_stats().")
        else:
            out["notes"].append(
                "Windows: skipped net_if_addrs()/net_if_stats() for speed."
            )

        try:
            nio = psutil.net_io_counters(pernic=False)
            out["network"]["io"] = _psutil_to_dict(nio)
        except Exception:
            out["notes"].append("psutil: failed to read net_io_counters(pernic=False).")

        try:
            # Keep this best-effort and narrower than kind='all' for speed.
            conns = psutil.net_connections(kind="inet")
            max_conns = 2000
            if len(conns) > max_conns:
                conns = conns[:max_conns]
                out["network"]["connections_truncated"] = True
            out["network"]["connections"] = [
                {
                    "fd": getattr(c, "fd", None),
                    "family": int(getattr(c.family, "value", c.family)),
                    "type": int(getattr(c.type, "value", c.type)),
                    "laddr": getattr(
                        getattr(c, "laddr", None),
                        "_asdict",
                        lambda: getattr(c, "laddr", None),
                    )(),
                    "raddr": getattr(
                        getattr(c, "raddr", None),
                        "_asdict",
                        lambda: getattr(c, "raddr", None),
                    )(),
                    "status": getattr(c, "status", None),
                    "pid": getattr(c, "pid", None),
                }
                for c in conns
            ]
        except Exception:
            out["notes"].append("psutil: failed to read net_connections(kind='inet').")

    except Exception:
        out["notes"].append("psutil: failed to collect network information.")


def _psutil_collect_users(out: dict[str, Any], psutil: Any) -> None:
    try:
        out["users"] = [_psutil_to_dict(u) for u in psutil.users()]
    except Exception:
        pass


def _psutil_collect_sensors(out: dict[str, Any], psutil: Any, *, system: str) -> None:
    try:
        out["sensors"] = {}
        try:
            bat = psutil.sensors_battery()
            out["sensors"]["battery"] = (
                bat._asdict()
                if bat and hasattr(bat, "_asdict")
                else (bat if bat is None else dict(bat))
            )
        except Exception:
            pass

        # Temperatures/fans are comparatively expensive; skip them on Windows.
        if system == "Windows":
            return

        try:
            temps = psutil.sensors_temperatures(fahrenheit=False)
            if temps:
                out["sensors"]["temperatures"] = {
                    k: [_psutil_to_dict(t) for t in v] for k, v in temps.items()
                }
                try:
                    fans = psutil.sensors_fans()
                    if fans:
                        out["sensors"]["fans"] = {
                            k: [_psutil_to_dict(f) for f in v] for k, v in fans.items()
                        }
                except Exception:
                    pass
        except Exception:
            pass
    except Exception:
        pass


def _collect_with_psutil(
    out: dict[str, Any],
    *,
    include_volumes: bool,
    include_disks: bool,
    system: str,
) -> bool:
    try:
        import psutil  # type: ignore
    except Exception:
        return False

    _psutil_collect_boot(out, psutil)
    _psutil_collect_cpu(out, psutil)
    _psutil_collect_memory(out, psutil)

    if include_volumes:
        _psutil_collect_volumes(out, psutil)

    if include_disks:
        _psutil_collect_disks(out, psutil, system=system)

    _psutil_collect_network(out, psutil, system=system)
    _psutil_collect_users(out, psutil)
    _psutil_collect_sensors(out, psutil, system=system)

    if include_disks:
        out["notes"].append(
            "psutil: physical disk model/serial is not available; disk entries are best-effort."
        )
    return True


def _collect_windows_specs(
    out: dict[str, Any], *, include_volumes: bool, include_disks: bool
) -> None:
    if include_volumes:
        try:
            import ctypes

            # GetLogicalDrives returns a bitmask of available drives.
            mask = ctypes.windll.kernel32.GetLogicalDrives()
            for i in range(26):
                if mask & (1 << i):
                    letter = chr(ord("A") + i)
                    mp = f"{letter}:\\"
                    if os.path.exists(mp):
                        _add_volume(out, mp)
        except Exception:
            out["notes"].append("Windows: failed to enumerate volumes.")

    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
        ) as k:
            out["cpu"]["model"] = winreg.QueryValueEx(k, "ProcessorNameString")[0]
            out["cpu"]["max_mhz"] = _safe_int(winreg.QueryValueEx(k, "~MHz")[0])
    except Exception:
        out["notes"].append("Windows: failed to read CPU model from registry.")

    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        out["memory"]["total_bytes"] = int(stat.ullTotalPhys)
    except Exception:
        out["notes"].append("Windows: failed to read total memory via WinAPI.")

    if include_disks:
        out["notes"].append(
            "Windows: physical disk model/type detection is not implemented (stdlib-only)."
        )


def _collect_linux_specs(
    out: dict[str, Any], *, include_volumes: bool, include_disks: bool
) -> None:
    # CPU model / max MHz / physical cores best-effort
    try:
        model = None
        max_mhz = None
        phys_cores = None
        with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                ll = line.lower()
                if model is None and ll.startswith("model name"):
                    model = line.split(":", 1)[1].strip()
                elif ll.startswith("cpu mhz"):
                    v = line.split(":", 1)[1].strip()
                    try:
                        mhz = int(float(v))
                        max_mhz = max(max_mhz or 0, mhz)
                    except Exception:
                        pass
                elif phys_cores is None and ll.startswith("cpu cores"):
                    # may represent cores per physical CPU package
                    phys_cores = _safe_int(line.split(":", 1)[1].strip())
        out["cpu"]["model"] = model
        out["cpu"]["max_mhz"] = max_mhz
        out["cpu"]["physical_cores"] = phys_cores
    except Exception:
        out["notes"].append("Linux: failed to read /proc/cpuinfo.")

    # Memory total
    try:
        with open("/proc/meminfo", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    out["memory"]["total_bytes"] = kb * 1024
                    break
    except Exception:
        out["notes"].append("Linux: failed to read /proc/meminfo.")

    # Volumes
    if include_volumes:
        pseudo = {
            "proc",
            "sysfs",
            "tmpfs",
            "devtmpfs",
            "devpts",
            "cgroup",
            "cgroup2",
            "pstore",
            "securityfs",
            "debugfs",
            "tracefs",
            "overlay",
            "squashfs",
            "autofs",
            "mqueue",
            "hugetlbfs",
            "fusectl",
            "rpc_pipefs",
        }
        try:
            mounts: list[tuple[str, str, str]] = []
            with open("/proc/mounts", "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 3:
                        device, mp, fstype = parts[0], parts[1], parts[2]
                        if fstype in pseudo:
                            continue
                        mounts.append((mp, fstype, device))

            seen = set()
            for mp, fstype, device in mounts:
                if mp in seen:
                    continue
                seen.add(mp)
                _add_volume(out, mp, fstype=fstype, device=device)
        except Exception:
            out["notes"].append("Linux: failed to enumerate volumes from /proc/mounts.")

    if include_disks:
        try:
            _linux_collect_disks(out)
        except Exception:
            out["notes"].append("Linux: failed to collect disks from /sys/block.")


def _collect_darwin_specs(
    out: dict[str, Any], *, include_volumes: bool, include_disks: bool
) -> None:
    # sysctl + getmntinfo
    try:
        import ctypes
        import ctypes.util

        libc_path = ctypes.util.find_library("c")
        if libc_path:
            libc = ctypes.CDLL(libc_path)
            out["cpu"]["model"] = _darwin_sysctl_str(libc, "machdep.cpu.brand_string")
            out["cpu"]["logical_cores"] = _darwin_sysctl(libc, "hw.logicalcpu")
            out["cpu"]["physical_cores"] = _darwin_sysctl(libc, "hw.physicalcpu")
            # Hz -> MHz
            hz = _darwin_sysctl(libc, "hw.cpufrequency_max")
            out["cpu"]["max_mhz"] = int(hz / 1_000_000) if hz else None
            out["memory"]["total_bytes"] = _darwin_sysctl(libc, "hw.memsize")
        else:
            out["notes"].append("macOS: libc not found; sysctl not available.")
    except Exception:
        out["notes"].append("macOS: failed to read cpu/memory via sysctl.")

    if include_volumes:
        try:
            _darwin_collect_volumes(out)
        except Exception:
            out["notes"].append("macOS: failed to enumerate volumes via getmntinfo.")

    if include_disks:
        out["notes"].append(
            "macOS: physical disk model/type detection is not implemented (stdlib-only)."
        )


def get_system_specs(
    *, include_volumes: bool = True, include_disks: bool = True
) -> dict[str, Any]:
    out = _init_system_specs_output()
    system = out["os"]["sys_platform"]

    if _collect_with_psutil(
        out,
        include_volumes=include_volumes,
        include_disks=include_disks,
        system=system,
    ):
        return out

    if system == "Windows":
        _collect_windows_specs(
            out, include_volumes=include_volumes, include_disks=include_disks
        )
    elif system == "Linux":
        _collect_linux_specs(
            out, include_volumes=include_volumes, include_disks=include_disks
        )
    elif system == "Darwin":
        _collect_darwin_specs(
            out, include_volumes=include_volumes, include_disks=include_disks
        )
    else:
        out["notes"].append(f"Unsupported OS: {system}")

    return out


def run_tool(args: dict[str, Any]) -> str:
    include_volumes = bool(args.get("include_volumes", True))
    include_disks = bool(args.get("include_disks", True))

    data = get_system_specs(
        include_volumes=include_volumes, include_disks=include_disks
    )
    return json.dumps(data, ensure_ascii=False)


if __name__ == "__main__":
    print(run_tool({}))
