from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime, timezone

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


Location = tuple[float, float, float | None, str | None, str | None]


def get_location() -> Location:
    """Get a location from the native provider for the current platform."""
    if sys.platform == "win32":
        return _windows()
    if sys.platform == "darwin":
        return _macos()
    if sys.platform.startswith("linux"):
        return _linux()
    raise RuntimeError(
        _(
            "location.unsupported_platform", default="Unsupported platform: {platform}"
        ).format(platform=sys.platform)
    )


def _windows() -> Location:
    from .._pip_auto import install_with_status

    if not install_with_status(
        "winrt-Windows.Devices.Geolocation",
        "winrt.windows.devices.geolocation",
    ):
        raise RuntimeError(
            _(
                "location.windows_unavailable",
                default="Windows Location API backend is unavailable; install winrt-Windows.Devices.Geolocation",
            )
        )
    from winrt.windows.devices.geolocation import Geolocator

    pos = asyncio.run(Geolocator().get_geoposition_async())
    coord = pos.coordinate
    return (
        coord.point.position.latitude,
        coord.point.position.longitude,
        coord.accuracy,
        coord.position_source.name if coord.position_source else None,
        coord.timestamp.isoformat() if coord.timestamp else None,
    )


def _macos() -> Location:
    """Get a one-shot location through Core Location."""
    from .._pip_auto import install_with_status

    if not install_with_status(
        "pyobjc-framework-CoreLocation", "CoreLocation", version_spec=">=11.1"
    ):
        raise RuntimeError(
            _(
                "location.macos_unavailable",
                default="macOS Core Location backend is unavailable; install pyobjc-framework-CoreLocation",
            )
        )
    try:
        import CoreLocation
        from Foundation import NSDate, NSRunLoop, NSObject
    except ImportError as exc:
        raise RuntimeError(
            _(
                "location.macos_unavailable",
                default="macOS Core Location backend is unavailable; install pyobjc-framework-CoreLocation",
            )
        ) from exc

    class Delegate(NSObject):
        def __init__(self):
            self.location = None
            self.error = None

        def locationManager_didUpdateLocations_(self, manager, locations):
            if locations:
                self.location = locations[-1]

        def locationManager_didFailWithError_(self, manager, error):
            self.error = error

    delegate = Delegate.alloc().init()
    manager = CoreLocation.CLLocationManager.alloc().init()
    manager.setDelegate_(delegate)
    if (
        CoreLocation.CLLocationManager.authorizationStatus()
        == CoreLocation.kCLAuthorizationStatusNotDetermined
    ):
        manager.requestWhenInUseAuthorization()
    manager.startUpdatingLocation()

    deadline = time.monotonic() + 20
    run_loop = NSRunLoop.currentRunLoop()
    while (
        delegate.location is None
        and delegate.error is None
        and time.monotonic() < deadline
    ):
        run_loop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))
    manager.stopUpdatingLocation()

    if delegate.error is not None:
        raise RuntimeError(str(delegate.error))
    if delegate.location is None:
        raise RuntimeError(
            _("location.error", default="Timed out waiting for macOS location")
        )

    coord = delegate.location.coordinate
    timestamp = delegate.location.timestamp
    timestamp_text = None
    if timestamp is not None:
        timestamp_text = datetime.fromtimestamp(
            timestamp.timeIntervalSince1970(), tz=timezone.utc
        ).isoformat()
    accuracy = delegate.location.horizontalAccuracy
    return (
        coord.latitude,
        coord.longitude,
        accuracy if accuracy >= 0 else None,
        "CORE_LOCATION",
        timestamp_text,
    )


def _linux() -> Location:
    """Get a one-shot location through GeoClue2 over the system D-Bus."""
    from .._pip_auto import install_with_status

    if not install_with_status("dbus-next", "dbus_next", version_spec=">=0.2.3"):
        raise RuntimeError(
            _(
                "location.linux_unavailable",
                default="Linux GeoClue2 backend is unavailable; install dbus-next",
            )
        )
    from dbus_next import BusType, Variant
    from dbus_next.aio import MessageBus

    async def request() -> Location:
        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        manager_intro = await bus.introspect(
            "org.freedesktop.GeoClue2", "/org/freedesktop/GeoClue2"
        )
        manager_obj = bus.get_proxy_object(
            "org.freedesktop.GeoClue2", "/org/freedesktop/GeoClue2", manager_intro
        )
        manager = manager_obj.get_interface("org.freedesktop.GeoClue2.Manager")
        client_path = await manager.call_get_client()

        client_intro = await bus.introspect("org.freedesktop.GeoClue2", client_path)
        client_obj = bus.get_proxy_object(
            "org.freedesktop.GeoClue2", client_path, client_intro
        )
        client = client_obj.get_interface("org.freedesktop.GeoClue2.Client")
        props = client_obj.get_interface("org.freedesktop.DBus.Properties")
        await props.call_set(
            "org.freedesktop.GeoClue2.Client", "DesktopId", Variant("s", "uagent")
        )
        await props.call_set(
            "org.freedesktop.GeoClue2.Client", "RequestedAccuracyLevel", Variant("u", 4)
        )
        await client.call_start()

        location_variant = await props.call_get(
            "org.freedesktop.GeoClue2.Client", "Location"
        )
        location_path = location_variant.value
        location_intro = await bus.introspect("org.freedesktop.GeoClue2", location_path)
        location_obj = bus.get_proxy_object(
            "org.freedesktop.GeoClue2", location_path, location_intro
        )
        location_props = location_obj.get_interface("org.freedesktop.DBus.Properties")
        values = {}
        for name in ("Latitude", "Longitude", "Accuracy", "Timestamp"):
            values[name] = (
                await location_props.call_get("org.freedesktop.GeoClue2.Location", name)
            ).value
        await client.call_stop()
        bus.disconnect()
        return (
            values["Latitude"],
            values["Longitude"],
            values["Accuracy"],
            "GEOCLUE2",
            str(values["Timestamp"]),
        )

    return asyncio.run(request())
