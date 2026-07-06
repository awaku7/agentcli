"""DALI shared resources."""

from __future__ import annotations

from typing import Any


def _dali_import():
    try:
        import dali.gear.general as gg
        import dali.address as addr
        import dali.driver as drv
    except ImportError:
        from .._pip_auto import install_with_status as _install_dali

        if not _install_dali("python-dali"):
            raise ImportError("python-dali library could not be installed.")
        import dali.gear.general as gg
        import dali.address as addr
        import dali.driver as drv
    return gg, addr, drv


def create_driver(driver_type: str = "auto", **kwargs) -> Any:
    """Create a DALI driver instance.

    Supported driver types:
      - "auto": try Tridonic USB first, fallback to daliserver
      - "tridonic": Tridonic DALI USB (USB vendor=0x17b5, product=0x0020)
      - "hasseb": Hasseb DALI Master
      - "daliserver": TCP connection to daliserver (host, port)
      - "lunatone": Lunatone LUBA RS232 (port)
      - "atxled": ATX LED SERIAL DALI HAT
    """
    gg, addr, drv = _dali_import()

    if driver_type == "tridonic":
        from dali.driver.tridonic import TridonicDALIUSBDriver

        return TridonicDALIUSBDriver()
    elif driver_type == "hasseb":
        from dali.driver.hasseb import HassebDALIUSBDriver

        return HassebDALIUSBDriver()
    elif driver_type == "daliserver":
        host = kwargs.get("host", "localhost")
        port = int(kwargs.get("port", 55825))
        from dali.driver.daliserver import DaliServer

        return DaliServer(host=host, port=port)
    elif driver_type == "lunatone":
        port_name = kwargs.get("port", "")
        from dali.driver.serial import LunatoneSerial

        return LunatoneSerial(port=port_name)
    elif driver_type == "atxled":
        from dali.driver.atxled import ATXLEDDALIDriver

        return ATXLEDDALIDriver()
    else:
        # auto: try Tridonic, fallback to daliserver
        try:
            from dali.driver.tridonic import TridonicDALIUSBDriver

            return TridonicDALIUSBDriver()
        except Exception:
            from dali.driver.daliserver import DaliServer

            return DaliServer(
                host=kwargs.get("host", "localhost"),
                port=int(kwargs.get("port", 55825)),
            )


def send_command(driver: Any, command: Any) -> Any:
    """Send a DALI command and return the response."""
    if hasattr(driver, "send"):
        return driver.send(command)
    raise RuntimeError("Driver does not support send()")
