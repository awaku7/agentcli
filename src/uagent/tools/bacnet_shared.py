"""BACnet shared resources: BAC0.lite instance lifecycle management.

Manages a background thread with an asyncio event loop for BAC0.lite.
Required because BAC0 2025+ APIs (who_is/read/write/disconnect) are async
and need a running event loop.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable, TypeVar

_BAC0_MODULE = None  # cached BAC0 module
_BAC0_INSTANCE: Any = None
_BAC0_LOCK = threading.Lock()
_BAC0_THREAD: threading.Thread | None = None
_BAC0_LOOP: asyncio.AbstractEventLoop | None = None
_BAC0_IP: str | None = None
_COV_SUBSCRIPTIONS: dict[int, dict[str, Any]] = {}
_STOP_EVENT = threading.Event()
_REFCOUNT = 0

T = TypeVar("T")


def _bac0_import():
    """Dynamically import BAC0 with auto-install."""
    global _BAC0_MODULE
    if _BAC0_MODULE is not None:
        return _BAC0_MODULE
    try:
        import BAC0  # type: ignore[import-untyped]
    except ImportError:
        from .._pip_auto import install_with_status as _install_bac0

        if not _install_bac0("BAC0"):
            raise ImportError("BAC0 library could not be installed.")
        import BAC0  # type: ignore[import-untyped]
    _BAC0_MODULE = BAC0
    return BAC0


def _run_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Target for the background thread: run the event loop until stopped."""
    asyncio.set_event_loop(loop)
    try:
        loop.run_forever()
    except RuntimeError:
        pass
    finally:
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        try:
            loop.close()
        except Exception:
            pass


def _ensure_loop_locked() -> asyncio.AbstractEventLoop:
    """Ensure background event loop thread is running. Caller holds lock."""
    global _BAC0_THREAD, _BAC0_LOOP

    if _BAC0_LOOP is not None and _BAC0_LOOP.is_running():
        return _BAC0_LOOP

    loop = asyncio.new_event_loop()
    _STOP_EVENT.clear()
    _BAC0_LOOP = loop
    _BAC0_THREAD = threading.Thread(
        target=_run_loop, args=(loop,), daemon=True, name="bac0-loop"
    )
    _BAC0_THREAD.start()

    # Wait briefly for loop to start
    for _ in range(50):
        if loop.is_running():
            break
        threading.Event().wait(0.02)
    if not loop.is_running():
        _BAC0_LOOP = None
        _BAC0_THREAD = None
        raise RuntimeError("BAC0 event loop failed to start")
    return loop


async def _async_create_bac0(BAC0: Any, ip: str | None) -> Any:
    """Async helper: create BAC0.lite instance."""
    kwargs: dict[str, Any] = {"ping": False}
    if ip:
        kwargs["ip"] = ip
    lite = BAC0.lite(**kwargs)
    # Give the stack a moment to finish registration
    await asyncio.sleep(0.2)
    return lite


async def _async_disconnect_bac0(lite: Any) -> None:
    """Async helper: disconnect BAC0.lite."""
    try:
        result = lite.disconnect()
        if asyncio.iscoroutine(result) or asyncio.isfuture(result):
            await result
        elif hasattr(result, "__await__"):
            await result
    except Exception:
        pass


def ensure_bac0(ip: str | None = None) -> tuple[Any, asyncio.AbstractEventLoop]:
    """Ensure BAC0.lite is running in the background thread.

    Returns (BAC0.lite instance, event loop).
    """
    global _BAC0_INSTANCE, _BAC0_THREAD, _BAC0_LOOP, _BAC0_IP, _REFCOUNT

    with _BAC0_LOCK:
        loop = _ensure_loop_locked()

        # Reuse existing instance when IP matches (or both auto)
        if _BAC0_INSTANCE is not None:
            if ip is None or _BAC0_IP is None or ip == _BAC0_IP:
                _REFCOUNT += 1
                return _BAC0_INSTANCE, loop
            # Different IP requested: tear down and recreate
            try:
                future = asyncio.run_coroutine_threadsafe(
                    _async_disconnect_bac0(_BAC0_INSTANCE), loop
                )
                future.result(timeout=10)
            except Exception:
                pass
            _BAC0_INSTANCE = None
            _BAC0_IP = None

        BAC0 = _bac0_import()
        future = asyncio.run_coroutine_threadsafe(
            _async_create_bac0(BAC0, ip), loop
        )
        try:
            _BAC0_INSTANCE = future.result(timeout=20)
            _BAC0_IP = ip
            _REFCOUNT = 1
        except Exception as e:
            # Leave loop running for subsequent retries; clear instance only
            _BAC0_INSTANCE = None
            _BAC0_IP = None
            raise RuntimeError(f"BAC0.lite startup failed: {e}") from e

        return _BAC0_INSTANCE, loop


def release_bac0(force: bool = False) -> None:
    """Release a reference to the shared BAC0 instance.

    Disconnects when refcount hits 0 (or force=True).
    """
    global _BAC0_INSTANCE, _BAC0_IP, _REFCOUNT

    with _BAC0_LOCK:
        if _BAC0_INSTANCE is None:
            _REFCOUNT = 0
            return
        if not force:
            _REFCOUNT = max(0, _REFCOUNT - 1)
            if _REFCOUNT > 0:
                return

        loop = _BAC0_LOOP
        lite = _BAC0_INSTANCE
        _BAC0_INSTANCE = None
        _BAC0_IP = None
        _REFCOUNT = 0

        if loop is not None and loop.is_running() and lite is not None:
            try:
                future = asyncio.run_coroutine_threadsafe(
                    _async_disconnect_bac0(lite), loop
                )
                future.result(timeout=10)
            except Exception:
                pass


def stop_bac0() -> None:
    """Stop the background BAC0.lite instance and thread."""
    global _BAC0_INSTANCE, _BAC0_THREAD, _BAC0_LOOP, _BAC0_IP, _REFCOUNT

    with _BAC0_LOCK:
        loop = _BAC0_LOOP
        lite = _BAC0_INSTANCE

        # Cancel all COV tasks first
        for task_id in list(_COV_SUBSCRIPTIONS.keys()):
            _cancel_cov_inner(task_id)

        if loop is not None and loop.is_running() and lite is not None:
            try:
                future = asyncio.run_coroutine_threadsafe(
                    _async_disconnect_bac0(lite), loop
                )
                future.result(timeout=10)
            except Exception:
                pass

        if loop is not None and loop.is_running():
            try:
                loop.call_soon_threadsafe(loop.stop)
            except Exception:
                pass

        thread = _BAC0_THREAD
        _BAC0_INSTANCE = None
        _BAC0_THREAD = None
        _BAC0_LOOP = None
        _BAC0_IP = None
        _REFCOUNT = 0
        _COV_SUBSCRIPTIONS.clear()

    if thread is not None and thread.is_alive():
        thread.join(timeout=3)


def run_on_bac0_loop(
    coro_factory: Callable[[Any], Any],
    *,
    ip: str | None = None,
    timeout: float = 30.0,
    keep_alive: bool = False,
) -> Any:
    """Run an async callable with the shared BAC0.lite instance.

    coro_factory(lite) -> awaitable
    """
    lite, loop = ensure_bac0(ip=ip)
    try:
        coro = coro_factory(lite)
        if not asyncio.iscoroutine(coro) and not asyncio.isfuture(coro):
            return coro
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=timeout)
    finally:
        if not keep_alive:
            release_bac0()


async def who_is(
    lite: Any,
    *,
    address: str | None = None,
    timeout: float = 5.0,
    low_limit: int = 0,
    high_limit: int = 4194303,
) -> list[Any]:
    """Send Who-Is and return I-Am responses."""
    result = lite.who_is(
        address=address,
        low_limit=low_limit,
        high_limit=high_limit,
        timeout=timeout,
    )
    if asyncio.iscoroutine(result) or asyncio.isfuture(result):
        result = await result
    if result is None:
        return []
    return list(result)


async def read_property(
    lite: Any,
    args: str,
    *,
    timeout: int = 10,
) -> Any:
    """Read a BACnet property via BAC0 args string."""
    result = lite.read(args, timeout=timeout)
    if asyncio.iscoroutine(result) or asyncio.isfuture(result):
        return await result
    return result


async def write_property(
    lite: Any,
    args: str,
) -> Any:
    """Write a BACnet property via BAC0 args string."""
    result = lite.write(args)
    if asyncio.iscoroutine(result) or asyncio.isfuture(result):
        return await result
    return result


def parse_iam(iam: Any) -> dict[str, Any]:
    """Normalize a BAC0/bacpypes3 I-Am response into a plain dict."""
    info: dict[str, Any] = {
        "instance": None,
        "ip": None,
        "vendor_id": None,
        "max_apdu": None,
        "segmentation": None,
        "raw_type": type(iam).__name__,
    }

    # bacpypes3 IAmRequest style
    device_id = getattr(iam, "iAmDeviceIdentifier", None)
    if device_id is not None:
        try:
            # often (objectType, instance) or object with value
            if isinstance(device_id, (list, tuple)) and len(device_id) >= 2:
                info["instance"] = int(device_id[1])
            elif hasattr(device_id, "instance"):
                info["instance"] = int(device_id.instance)
            elif hasattr(device_id, "value"):
                val = device_id.value
                if isinstance(val, (list, tuple)) and len(val) >= 2:
                    info["instance"] = int(val[1])
                else:
                    info["instance"] = int(val)
            else:
                info["instance"] = int(device_id)
        except Exception:
            pass

    vendor = getattr(iam, "vendorID", None)
    if vendor is None:
        vendor = getattr(iam, "vendorIdentifier", None)
    if vendor is not None:
        try:
            info["vendor_id"] = int(getattr(vendor, "value", vendor))
        except Exception:
            pass

    max_apdu = getattr(iam, "maxAPDULengthAccepted", None)
    if max_apdu is not None:
        try:
            info["max_apdu"] = int(getattr(max_apdu, "value", max_apdu))
        except Exception:
            pass

    seg = getattr(iam, "segmentationSupported", None)
    if seg is not None:
        info["segmentation"] = str(getattr(seg, "value", seg))

    # Address / source
    pdu_source = getattr(iam, "pduSource", None)
    if pdu_source is None:
        pdu_source = getattr(iam, "source", None)
    if pdu_source is not None:
        info["ip"] = str(pdu_source)

    # tuple/list fallback: (address, instance) or similar
    if info["instance"] is None and isinstance(iam, (list, tuple)):
        if len(iam) >= 2:
            info["ip"] = str(iam[0])
            try:
                info["instance"] = int(iam[1])
            except Exception:
                pass
        elif len(iam) == 1:
            info["ip"] = str(iam[0])

    if info["instance"] is None and isinstance(iam, dict):
        info["ip"] = str(iam.get("ip") or iam.get("address") or "") or None
        try:
            info["instance"] = int(iam.get("instance") or iam.get("device_id") or 0) or None
        except Exception:
            pass
        if iam.get("vendor_id") is not None:
            try:
                info["vendor_id"] = int(iam["vendor_id"])
            except Exception:
                pass

    return info


def _cancel_cov_inner(task_id: int) -> None:
    """Cancel a COV subscription (must be called with lock held)."""
    if _BAC0_INSTANCE is None:
        return
    try:
        _BAC0_INSTANCE.cancel_cov(task_id)
    except Exception:
        pass
    _COV_SUBSCRIPTIONS.pop(task_id, None)


def cov_subscribe(
    ip: str,
    object_type: str,
    object_instance: int,
    lifetime: int = 900,
    confirmed: bool = False,
    label: str = "",
    on_change_prompt: str = "",
) -> dict[str, Any]:
    """Subscribe to COV notifications for a BACnet object.

    Returns dict with task_id and status.
    """
    lite, loop = ensure_bac0()

    object_id = (object_type, object_instance)

    def _cov_callback(property_identifier: str, property_value: Any) -> None:
        from ..scheduler import (
            SchedulerStore,
            ScheduleItem,
            format_iso_datetime,
            utc_now,
        )
        from uuid import uuid4
        from datetime import timedelta

        prompt_text = (
            on_change_prompt or f"{label}: {property_identifier} = {property_value}"
        )
        item = ScheduleItem(
            id=str(uuid4()),
            type="once",
            at=format_iso_datetime(utc_now() + timedelta(seconds=1)),
            message=f"[COV] {label}: {property_identifier} changed to {property_value}",
            llm_prompt=prompt_text,
            interval_sec=0,
            enabled=True,
        )
        SchedulerStore().add_item(item)

    future = asyncio.run_coroutine_threadsafe(
        _async_cov_subscribe(lite, ip, object_id, lifetime, confirmed, _cov_callback),
        loop,
    )

    try:
        task_id = future.result(timeout=15)
    except Exception as e:
        release_bac0()
        return {"ok": False, "error": str(e)}

    info = {
        "task_id": task_id,
        "ip": ip,
        "object_type": object_type,
        "object_instance": object_instance,
        "lifetime": lifetime,
        "confirmed": confirmed,
        "label": label,
        "on_change_prompt": on_change_prompt,
        "status": "active",
    }
    with _BAC0_LOCK:
        _COV_SUBSCRIPTIONS[task_id] = info
        # COV keeps instance alive
        global _REFCOUNT
        _REFCOUNT = max(_REFCOUNT, 1)

    return {"ok": True, "task_id": task_id, "subscription": info}


async def _async_cov_subscribe(
    lite: Any,
    ip: str,
    object_id: tuple[str, int],
    lifetime: int,
    confirmed: bool,
    callback: Callable[[str, Any], None],
) -> int:
    """Async helper: call BAC0.lite.cov() and return the task_id."""
    before = (
        set(lite._running_cov_tasks.keys())
        if hasattr(lite, "_running_cov_tasks")
        else set()
    )
    result = lite.cov(
        address=ip,
        objectID=object_id,
        lifetime=lifetime,
        confirmed=confirmed,
        callback=callback,
    )
    if asyncio.iscoroutine(result) or asyncio.isfuture(result):
        await result
    after = set(lite._running_cov_tasks.keys()) if hasattr(lite, "_running_cov_tasks") else set()
    new_tasks = after - before
    if new_tasks:
        return list(new_tasks)[0]
    try:
        import BAC0.core.devices.COV as cov_mod

        for tid, task in getattr(cov_mod, "_running_cov_tasks", {}).items():
            if str(getattr(task, "address", "")) == ip:
                return tid
    except Exception:
        pass
    return -1


def cov_unsubscribe(task_id: int) -> dict[str, Any]:
    """Unsubscribe a COV subscription by task_id."""
    lite, _loop = ensure_bac0()
    with _BAC0_LOCK:
        if task_id not in _COV_SUBSCRIPTIONS:
            return {"ok": False, "error": f"task_id {task_id} not found"}
        info = _COV_SUBSCRIPTIONS.get(task_id, {})
        try:
            lite.cancel_cov(task_id)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        _COV_SUBSCRIPTIONS.pop(task_id, None)
    release_bac0()
    return {"ok": True, "task_id": task_id, "subscription": info}


def cov_list() -> dict[str, Any]:
    """List all active COV subscriptions."""
    with _BAC0_LOCK:
        subs = list(_COV_SUBSCRIPTIONS.values())
    return {"ok": True, "count": len(subs), "subscriptions": subs}
