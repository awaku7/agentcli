from __future__ import annotations

# tools/ble_ops_tool.py
import asyncio
import importlib.util
import sys
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:ble_ops"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "function": {
        "name": "ble_ops",
        "description": _(
            "tool.description",
            default="Perform Bluetooth Low Energy (BLE) operations: scan for devices, read, or write GATT characteristics. Use MAC addresses on Windows/Linux, and UUIDs...",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["scan", "read", "write"],
                    "description": _(
                        "param.action.description",
                        default="The operation to perform. scan: discover nearby devices, read: read characteristic, write: write characteristic.",
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "default": 5,
                    "description": _(
                        "param.timeout.description",
                        default="Timeout (seconds).",
                    ),
                },
                "scan_mode": {
                    "type": "string",
                    "enum": ["ble", "all"],
                    "default": "ble",
                    "description": _(
                        "param.scan_mode.description",
                        default="Scan mode: ble (BLE only) or all (BLE + Classic).",
                    ),
                },
                "address": {
                    "type": "string",
                    "description": _(
                        "param.address.description",
                        default="Target device MAC address (Windows/Linux) or UUID (macOS)",
                    ),
                },
                "uuid": {
                    "type": "string",
                    "description": _(
                        "param.uuid.description",
                        default="Char UUID.",
                    ),
                },
                "data_hex": {
                    "type": "string",
                    "description": _(
                        "param.data_hex.description",
                        default="Hexadecimal string of data to write (e.g., '010203'). Required only when action='write'",
                    ),
                },
            },
            "required": ["action"],
        },
    },
}


async def _scan(timeout: int) -> list[dict[str, Any]]:
    from bleak import BleakScanner

    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    result = []
    for d, a in devices.values():
        result.append(
            {"name": d.name or "Unknown", "address": d.address, "rssi": a.rssi}
        )
    return result


def _scan_all_pyside6(timeout: int) -> list[dict[str, Any]]:
    import sys
    from PySide6.QtCore import QCoreApplication, QTimer
    from PySide6.QtBluetooth import QBluetoothDeviceDiscoveryAgent, QBluetoothDeviceInfo

    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    agent = QBluetoothDeviceDiscoveryAgent()
    devices_list = []

    def device_discovered(info: QBluetoothDeviceInfo):
        name = info.name()
        address = info.address().toString()
        rssi = info.rssi()

        dev_type = "Unknown"
        t = info.coreConfigurations()
        is_classic = bool(
            t & QBluetoothDeviceInfo.CoreConfiguration.BaseRateCoreConfiguration
        )
        is_ble = bool(
            t & QBluetoothDeviceInfo.CoreConfiguration.LowEnergyCoreConfiguration
        )

        if is_classic and is_ble:
            dev_type = "Dual"
        elif is_classic:
            dev_type = "Classic"
        elif is_ble:
            dev_type = "BLE"

        devices_list.append(
            {
                "name": name or "Unknown",
                "address": address,
                "type": dev_type,
                "rssi": rssi,
            }
        )

    agent.deviceDiscovered.connect(device_discovered)
    agent.finished.connect(app.quit)
    agent.errorOccurred.connect(lambda err: app.quit())

    methods = (
        QBluetoothDeviceDiscoveryAgent.DiscoveryMethod.ClassicMethod
        | QBluetoothDeviceDiscoveryAgent.DiscoveryMethod.LowEnergyMethod
    )
    agent.start(methods)

    QTimer.singleShot(timeout * 1000, app.quit)
    app.exec()
    return devices_list


async def _read(address: str, char_uuid: str, timeout: int) -> dict[str, Any]:
    from bleak import BleakClient

    async with BleakClient(address, timeout=timeout) as client:
        data = await client.read_gatt_char(char_uuid)
        return {"hex": data.hex(), "text": data.decode("utf-8", errors="replace")}


async def _write(address: str, char_uuid: str, data_hex: str, timeout: int) -> str:
    from bleak import BleakClient

    data = bytes.fromhex(data_hex)
    async with BleakClient(address, timeout=timeout) as client:
        await client.write_gatt_char(char_uuid, data)
        return "Success"


def run_tool(args: dict[str, Any]) -> str:
    action = args.get("action")
    timeout = args.get("timeout", 5)
    scan_mode = args.get("scan_mode", "ble")
    address = args.get("address")
    char_uuid = args.get("uuid")
    data_hex = args.get("data_hex")

    # 1. Check dependency
    if action == "scan" and scan_mode == "all":
        if importlib.util.find_spec("PySide6") is None:
            return _(
                "err.pyside6_missing",
                default="Error: 'PySide6' library is not installed. Please install it using:\npip install PySide6",
            )
    else:
        if importlib.util.find_spec("bleak") is None:
            return _(
                "err.bleak_missing",
                default="Error: 'bleak' library is not installed. Please install it using:\npip install bleak",
            )

    # 2. Set event loop policy for Windows
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass

    try:
        if action == "scan":
            if scan_mode == "all":
                res = _scan_all_pyside6(timeout)
            else:
                res = asyncio.run(_scan(timeout))
            return str(res)

        elif action == "read":
            if not address or not char_uuid:
                return _(
                    "err.missing_read_params",
                    default="Error: 'address' and 'char_uuid' are required.",
                )
            res = asyncio.run(_read(address, char_uuid, timeout))
            return str(res)

        elif action == "write":
            if not address or not char_uuid or not data_hex:
                return _(
                    "err.missing_write_params",
                    default="Error: 'address', 'char_uuid', and 'data_hex' are required.",
                )
            res = asyncio.run(_write(address, char_uuid, data_hex, timeout))
            return str(res)

        else:
            return _(
                "err.unknown_action",
                default="Error: Unknown action '{action}'.",
                action=action,
            )

    except Exception as e:
        err_msg = str(e)
        # Linux permission error handling
        if sys.platform.startswith("linux"):
            if (
                "Permission" in err_msg
                or "AccessDenied" in err_msg
                or "dbus" in err_msg.lower()
                or "notready" in err_msg.lower()
            ):
                return _(
                    "err.linux_permission",
                    default="Error during BLE operation: {err_msg}\n\n[Linux/Raspberry Pi Permission Guide]\nYou might lack permissions to access the Bluetooth socket. Try one of the following:\n1. Add your user to the bluetooth group (recommended):\n   sudo usermod -aG bluetooth $USER\n   (Requires restart or re-login)\n2. Grant permissions directly to the Python binary:\n   sudo setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f $(which python))",
                    err_msg=err_msg,
                )
        # macOS permission error handling
        elif sys.platform == "darwin":
            if (
                "CoreBluetooth" in err_msg
                or "permission" in err_msg.lower()
                or "auth" in err_msg.lower()
            ):
                return _(
                    "err.macos_permission",
                    default="Error during BLE operation: {err_msg}\n\n[macOS Permission Guide]\nBluetooth access might have been denied by macOS security restrictions.\nPlease open 'System Settings > Privacy & Security > Bluetooth' and ensure your terminal, VS Code, or Python process is allowed to access Bluetooth.",
                    err_msg=err_msg,
                )

        return _(
            "err.operation_failed",
            default="Error during BLE operation: {err_msg}",
            err_msg=err_msg,
        )
