"""Modbus shared resources: pymodbus client management."""

from __future__ import annotations

import threading
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

_MODBUS_MODULE = None
_CLIENT_LOCK = threading.Lock()


def _modbus_import():
    """Dynamically import pymodbus with auto-install."""
    global _MODBUS_MODULE
    if _MODBUS_MODULE is not None:
        return _MODBUS_MODULE
    try:
        from pymodbus.client import ModbusTcpClient  # type: ignore[import-untyped]
        import pymodbus  # type: ignore[import-untyped]
    except ImportError:
        from .._pip_auto import install_with_status as _install_mb

        if not _install_mb("pymodbus"):
            raise ImportError(
                _(
                    "modbus.install_failed",
                    default="pymodbus library could not be installed.",
                )
            )
        from pymodbus.client import ModbusTcpClient  # type: ignore[import-untyped]
        import pymodbus  # type: ignore[import-untyped]
    _MODBUS_MODULE = (ModbusTcpClient, pymodbus)
    return _MODBUS_MODULE


def create_client(ip: str, port: int = 502, timeout: int = 5) -> Any:
    """Create a Modbus TCP client and connect."""
    ModbusTcpClient, _ = _modbus_import()
    client = ModbusTcpClient(ip, port=port, timeout=timeout)
    client.connect()
    return client


def close_client(client: Any) -> None:
    """Close a Modbus TCP client."""
    try:
        client.close()
    except Exception:
        pass
