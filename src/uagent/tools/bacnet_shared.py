"""BACnet shared resources: BAC0.lite instance lifecycle management.

Manages a background thread with an asyncio event loop for BAC0.lite,
which is required by COV subscriptions (long-lived connections).
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable

_BAC0_MODULE = None  # cached BAC0 module
_BAC0_INSTANCE: Any = None
_BAC0_LOCK = threading.Lock()
_BAC0_THREAD: threading.Thread | None = None
_BAC0_LOOP: asyncio.AbstractEventLoop | None = None
_COV_SUBSCRIPTIONS: dict[int, dict[str, Any]] = {}
_STOP_EVENT = threading.Event()


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
            loop.close()
        except Exception:
            pass


def ensure_bac0() -> tuple[Any, asyncio.AbstractEventLoop]:
    """Ensure BAC0.lite is running in the background thread.

    Returns (BAC0.lite instance, event loop).
    """
    global _BAC0_INSTANCE, _BAC0_THREAD, _BAC0_LOOP

    with _BAC0_LOCK:
        if _BAC0_INSTANCE is not None and _BAC0_LOOP is not None:
            return _BAC0_INSTANCE, _BAC0_LOOP

        BAC0 = _bac0_import()
        loop = asyncio.new_event_loop()

        # Start background thread
        _STOP_EVENT.clear()
        _BAC0_LOOP = loop
        _BAC0_THREAD = threading.Thread(
            target=_run_loop, args=(loop,), daemon=True, name="bac0-cov"
        )
        _BAC0_THREAD.start()

        # Create BAC0.lite inside the event loop
        future = asyncio.run_coroutine_threadsafe(_async_create_bac0(BAC0), loop)
        try:
            _BAC0_INSTANCE = future.result(timeout=15)
        except Exception as e:
            loop.call_soon_threadsafe(loop.stop)
            _BAC0_THREAD = None
            _BAC0_LOOP = None
            raise RuntimeError(f"BAC0.lite startup failed: {e}") from e

        return _BAC0_INSTANCE, _BAC0_LOOP


async def _async_create_bac0(BAC0: Any) -> Any:
    """Async helper: create BAC0.lite instance."""
    # Use a non-routeable IP to bind locally; BAC0 will auto-detect the subnet
    lite = BAC0.lite(ip="0.0.0.0")
    return lite


def stop_bac0() -> None:
    """Stop the background BAC0.lite instance and thread."""
    global _BAC0_INSTANCE, _BAC0_THREAD, _BAC0_LOOP

    with _BAC0_LOCK:
        if _BAC0_LOOP is not None and _BAC0_LOOP.is_running():
            # Cancel all COV tasks
            for task_id in list(_COV_SUBSCRIPTIONS.keys()):
                _cancel_cov_inner(task_id)

            try:
                _BAC0_LOOP.call_soon_threadsafe(_BAC0_LOOP.stop)
            except Exception:
                pass

        _BAC0_INSTANCE = None
        _BAC0_THREAD = None
        _BAC0_LOOP = None
        _COV_SUBSCRIPTIONS.clear()


def _cancel_cov_inner(task_id: int) -> None:
    """Cancel a COV subscription (must be called with lock held)."""
    global _BAC0_INSTANCE, _BAC0_LOOP
    if _BAC0_INSTANCE is None or _BAC0_LOOP is None:
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

    # Define callback that will be called when a COV notification arrives
    def _cov_callback(property_identifier: str, property_value: Any) -> None:
        """Called from BAC0's async context when a COV notification arrives."""
        # Import scheduler store to queue the event for LLM
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

    # Schedule the COV subscription on the BAC0 event loop
    future = asyncio.run_coroutine_threadsafe(
        _async_cov_subscribe(lite, ip, object_id, lifetime, confirmed, _cov_callback),
        loop,
    )

    try:
        task_id = future.result(timeout=15)
    except Exception as e:
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
    # We capture task_id after subscription by hooking into the internal dict
    before = (
        set(lite._running_cov_tasks.keys())
        if hasattr(lite, "_running_cov_tasks")
        else set()
    )
    lite.cov(
        address=ip,
        objectID=object_id,
        lifetime=lifetime,
        confirmed=confirmed,
        callback=callback,
    )
    after = set(lite._running_cov_tasks.keys())
    new_tasks = after - before
    if new_tasks:
        return list(new_tasks)[0]
    # Fallback: search by process_identifier
    import BAC0.core.devices.COV as cov_mod

    for tid, task in getattr(cov_mod, "_running_cov_tasks", {}).items():
        if str(task.address) == ip:
            return tid
    return -1


def cov_unsubscribe(task_id: int) -> dict[str, Any]:
    """Unsubscribe a COV subscription by task_id."""
    lite, loop = ensure_bac0()
    with _BAC0_LOCK:
        if task_id not in _COV_SUBSCRIPTIONS:
            return {"ok": False, "error": f"task_id {task_id} not found"}
        info = _COV_SUBSCRIPTIONS.get(task_id, {})
        try:
            lite.cancel_cov(task_id)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        _COV_SUBSCRIPTIONS.pop(task_id, None)
    return {"ok": True, "task_id": task_id, "subscription": info}


def cov_list() -> dict[str, Any]:
    """List all active COV subscriptions."""
    with _BAC0_LOCK:
        subs = list(_COV_SUBSCRIPTIONS.values())
    return {"ok": True, "count": len(subs), "subscriptions": subs}
