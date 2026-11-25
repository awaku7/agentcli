"""Tool-loop guards for the LLM round loop (split out of uagent_llm).

Detects repeated management-tool calls, identical tool calls, repeating
round cycles and long runs of one tool, and stops the turn when a
guard trips. Guard state is per conversation (ContextVar).
"""

from __future__ import annotations

from collections import deque
from collections.abc import MutableMapping
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any
import hashlib
import json

from . import core as _core_module
from .env_utils import env_get
from .i18n import _
from .runtime.spinner import stop_quietly as _spinner_stop_quietly
from .runtime.tool_discovery import MANAGEMENT_TOOL_NAMES as _MGMT_TOOLS


@dataclass
class _LoopGuardState:
    fingerprints: dict[str, int] = field(default_factory=dict)
    # Count adjacent rounds using one tool name, including rounds with new args.
    # Exact-argument repeats and short multi-tool cycles have narrower guards.
    consecutive: dict[str, Any] = field(
        default_factory=lambda: {"name": "", "count": 0}
    )


_LOOP_GUARD_STATE: ContextVar[_LoopGuardState | None] = ContextVar(
    "uagent_loop_guard_state", default=None
)


def _loop_guard_state() -> _LoopGuardState:
    """Return the current conversation's loop-guard state, creating it once."""
    state = _LOOP_GUARD_STATE.get()
    if state is None:
        state = _LoopGuardState()
        _LOOP_GUARD_STATE.set(state)
    return state


def begin_loop_guard_turn() -> _LoopGuardState:
    """Start a fresh loop-guard state for a new user turn in this context."""
    state = _LoopGuardState()
    _LOOP_GUARD_STATE.set(state)
    return state


def _owner_loop_guard_state(owner: object) -> _LoopGuardState:
    """Return the loop-guard state carried by ``owner``.

    On first sight the current context's state is adopted and stored
    on the owner, mirroring the auto-unload state's owner pattern.
    """
    state = getattr(owner, "_loop_guard_state", None)
    if state is None:
        state = _loop_guard_state()
        try:
            owner._loop_guard_state = state  # type: ignore[attr-defined]
        except Exception:
            pass
    return state


def _bind_loop_guard_state(owner: object) -> _LoopGuardState:
    """Bind the loop-guard state carried by ``owner`` to this context."""
    state = _owner_loop_guard_state(owner)
    _LOOP_GUARD_STATE.set(state)
    return state


def _store_loop_guard_state(owner: object) -> None:
    """Write this context's loop-guard state back to ``owner``.

    A turn that starts fresh counters (begin_loop_guard_turn) replaces
    the bound state inside its own context; storing it back lets the
    next context that binds from the same owner pick the counters up
    where the turn left them.  The CLI auto-pilot continuation relies
    on this: it runs in a separate worker context and passes
    preserve_tool_loop_state=True precisely so the guard keeps
    counting across the handoff.
    """
    state = _LOOP_GUARD_STATE.get()
    if state is not None:
        try:
            owner._loop_guard_state = state  # type: ignore[attr-defined]
        except Exception:
            pass


class _ContextFingerprints(MutableMapping):
    """Mapping view of the current context's loop-guard fingerprints.

    Kept under the historical ``_TOOL_CALL_FINGERPRINTS`` name so existing
    callers and tests keep working while the storage is context-local.
    """

    def _data(self) -> dict[str, int]:
        return _loop_guard_state().fingerprints

    def __getitem__(self, key: str) -> int:
        return self._data()[key]

    def __setitem__(self, key: str, value: int) -> None:
        self._data()[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data()[key]

    def __iter__(self):
        return iter(list(self._data()))

    def __len__(self) -> int:
        return len(self._data())

    def __repr__(self) -> str:
        return f"_ContextFingerprints({self._data()!r})"


_TOOL_CALL_FINGERPRINTS: MutableMapping = _ContextFingerprints()
_TOOL_ROUND_HISTORY_SIZE = 12
_MGMT_LOOP_THRESHOLD = 4
# Same-args general tool loops (e.g. get_current_location xN) are also blocked.
# Keep this close to the management threshold so runaway tool spam stops early.
_GENERAL_TOOL_LOOP_THRESHOLD = 4


# Tools that may legitimately be called repeatedly with identical args in one
# session (polling/monitors). These stay on the management-only detector.
def _debug_tool_loop(event: str, **fields: Any) -> None:
    """Suppress verbose tool-loop diagnostics."""
    return


def _emit_tool_loop_block(
    *,
    core: Any,
    tool_name: str,
    count: int,
    reason: str,
    round_count: int,
    tool_calls_list: list[dict[str, Any]],
) -> None:
    """Emit a bounded operator line and structured durable loop event."""
    call_id = ""
    for tool_call in tool_calls_list or []:
        if not isinstance(tool_call, dict):
            continue
        function = tool_call.get("function") or {}
        if isinstance(function, dict) and str(function.get("name") or "") == tool_name:
            call_id = str(tool_call.get("id") or "")
            break
    payload = {
        "tool": str(tool_name or "unknown"),
        "count": int(count),
        "reason": str(reason),
        "round": int(round_count),
        "call_id": call_id,
    }
    print(
        "[LOOP-GUARD] "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )
    try:
        from .runtime.logging_setup import log_event

        log_event("tool.loop_blocked", **payload)
    except Exception:
        pass


def _block_tool_loop(
    *,
    core: Any,
    tool_name: str,
    count: int,
    reason: str,
    round_count: int,
    tool_calls_list: list[dict[str, Any]],
    warning: str,
    clear_reason: str = "tool_loop_guard",
) -> None:
    """Common stop sequence shared by every tool-loop guard."""
    core._last_round_reason = "loop_guard"
    _clear_responses_after_tool_loop(core, reason=clear_reason)
    _debug_tool_loop("blocked", name=tool_name, count=count)
    _emit_tool_loop_block(
        core=core,
        tool_name=tool_name,
        count=count,
        reason=reason,
        round_count=round_count,
        tool_calls_list=tool_calls_list,
    )
    _spinner_stop_quietly()
    print(warning)


def _clear_responses_after_tool_loop(
    core: Any, *, reason: str = "tool_loop_guard"
) -> None:
    """Invalidate an incomplete Responses continuation before breaking.

    A loop guard or hard round limit may stop after tool execution but before
    the matching continuation request is sent. Reusing that response id on the
    next user turn makes the provider reject it as a stale ``previous_response_id``.
    """
    try:
        runtime = getattr(core, "responses_runtime", None)
        clear_runtime = getattr(runtime, "clear_continuation", None)
        if callable(clear_runtime):
            clear_runtime(reason)
    except Exception:
        pass
    try:
        clear_fn = getattr(core, "clear_responses_continuation", None)
        if not callable(clear_fn):
            clear_fn = getattr(_core_module, "clear_responses_continuation", None)
        if callable(clear_fn):
            clear_fn()
            return
    except Exception:
        pass
    state = getattr(core, "responses_state", None)
    if isinstance(state, dict):
        state.pop("previous_response_id", None)
        state.pop("active_response_id", None)
        state.pop("_stale_rid_occurred", None)


_GENERAL_LOOP_EXEMPT_TOOLS = frozenset(
    {
        "human_ask",
        "finish_skill",
        "tool_catalog",
        "tool_load",
        "unload_tool",
    }
)


def _parse_mgmt_tool_args(args_raw: Any) -> Any:
    try:
        if isinstance(args_raw, str):
            return json.loads(args_raw) if args_raw.strip() else {}
        return args_raw if args_raw is not None else {}
    except Exception:
        return {"_raw": args_raw}


def _mgmt_tool_targets(name: str, args: Any) -> list[str]:
    """Return target tool names for load/unload (batch-aware)."""
    if name not in ("tool_load", "unload_tool") or not isinstance(args, dict):
        return []
    import re as _re

    def _split(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            out: list[str] = []
            for item in value:
                out.extend(_split(item))
            return out
        text = str(value).strip()
        if not text:
            return []
        return [p for p in _re.split(r"[,\s;]+", text) if p]

    collected: list[str] = []
    collected.extend(_split(args.get("names")))
    collected.extend(_split(args.get("name")))
    collected.extend(_split(args.get("tool")))
    seen: set[str] = set()
    ordered: list[str] = []
    for entry in collected:
        if entry not in seen:
            seen.add(entry)
            ordered.append(entry)
    return ordered


def _mgmt_tool_target(name: str, args: Any) -> str:
    """Return the target tool name for load/unload, else empty."""
    targets = _mgmt_tool_targets(name, args)
    return targets[0] if targets else ""


def _mgmt_tool_fingerprint(name: str, args: Any) -> str:
    """Build a loop-detection key for a management tool call.

    tool_load/unload_tool are keyed by the *target* tool name so that
    parallel loads of different tools do not share a counter.
    """
    if not isinstance(args, dict):
        return f"{name}:{args!r}"
    if name in ("tool_load", "unload_tool"):
        target = _mgmt_tool_target(name, args)
        return f"{name}:{target}"
    if name == "tool_catalog":
        return (
            f"tool_catalog:query={args.get('query', '')}:all={args.get('all', False)}"
        )
    return f"{name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"


def _general_tool_fingerprint(name: str, args: Any) -> str:
    """Build a loop-detection key for a general (non-management) tool call."""
    if not isinstance(args, dict):
        return f"tool:{name}:{args!r}"
    try:
        payload = json.dumps(args, sort_keys=True, ensure_ascii=False)
    except Exception:
        payload = repr(args)
    return f"tool:{name}:{payload}"


def _mgmt_tool_display(name: str, args: Any) -> str:
    if name in ("tool_load", "unload_tool") and isinstance(args, dict):
        targets = _mgmt_tool_targets(name, args)
        if targets:
            if len(targets) == 1:
                return f"{name}({targets[0]})"
            return f"{name}({','.join(targets)})"
    return name


def clear_mgmt_load_streak(target: str) -> None:
    """Clear tool_load loop counters for *target* (auto or explicit unload).

    Auto-unload calls disable_single_tool directly and never emits unload_tool,
    so both paths must clear via this helper or the prior load streak would
    still count toward the loop threshold on the next tool_load.
    """
    name = str(target or "").strip()
    if not name:
        return
    _TOOL_CALL_FINGERPRINTS.pop(f"tool_load:{name}", None)
    # drop any stale unload fingerprint from older builds
    _TOOL_CALL_FINGERPRINTS.pop(f"unload_tool:{name}", None)


def clear_general_tool_loop_streaks() -> None:
    """Clear general-tool loop counters.

    tool_catalog is a re-planning boundary: once the model re-searches tools,
    previous same-args streaks (e.g. get_current_location x3) should not carry over.
    Management fingerprints (tool_load:/tool_catalog:...) are kept.
    """
    for key in list(_TOOL_CALL_FINGERPRINTS.keys()):
        if str(key).startswith("tool:"):
            _TOOL_CALL_FINGERPRINTS.pop(key, None)


def clear_consecutive_tool_call_streak(
    streak: dict[str, Any] | None = None,
) -> None:
    """Clear a same-tool-name streak (default: the current context's streak)."""
    if streak is None:
        streak = _loop_guard_state().consecutive
    streak.clear()
    streak.update({"name": "", "count": 0})


def check_consecutive_tool_calls(
    tool_calls_list: list[dict[str, Any]],
    *,
    record: bool = True,
    threshold: int | None = None,
    streak: dict[str, Any] | None = None,
) -> tuple[bool, str, int]:
    """Guard one tool name repeated across adjacent tool-bearing rounds.

    Parallel calls to the same tool in one round count once. A mixed-tool
    round resets this name-specific streak; repeated multi-tool cycles are
    handled separately by ``check_repeating_tool_round_cycle``.
    """
    if streak is None:
        streak = _loop_guard_state().consecutive
    raw_limit = env_get("UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT", "50")
    try:
        default_limit = max(1, int(raw_limit))
    except (TypeError, ValueError):
        default_limit = 50
    limit = default_limit if threshold is None else max(1, int(threshold))

    round_names: list[str] = []
    for tool_call in tool_calls_list or []:
        if not isinstance(tool_call, dict):
            continue
        function = tool_call.get("function") or {}
        if not isinstance(function, dict):
            continue
        tool_name = str(function.get("name") or "").strip()
        if tool_name and tool_name not in round_names:
            round_names.append(tool_name)

    if len(round_names) != 1:
        if record:
            clear_consecutive_tool_call_streak(streak)
        return False, _("consecutive tool calls"), 0

    current_name = round_names[0]
    previous_name = str(streak.get("name", ""))
    previous_count = int(streak.get("count", 0))
    count = previous_count + 1 if current_name == previous_name else 1
    if record:
        streak.update({"name": current_name, "count": count})
    return count >= limit, current_name, count


def _tool_calls_include_name(tool_calls_list: list[dict[str, Any]], name: str) -> bool:
    target = str(name or "").strip()
    if not target:
        return False
    for tc in tool_calls_list or []:
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function") or {}
        if not isinstance(fn, dict):
            continue
        if str(fn.get("name") or "").strip() == target:
            return True
    return False


def check_mgmt_tool_loop(
    tool_calls_list: list[dict[str, Any]],
    *,
    record: bool = True,
    threshold: int | None = None,
) -> tuple[bool, str, int]:
    """Detect repeated same-target management tool calls.

    Returns (blocked, display_name, count). When record=False, only peeks
    without mutating counters (unused currently; kept for tests/callers).

    unload_tool(target) resets the tool_load counter for that target so a
    deliberate unload→reload cycle does not trip the loop detector.
    """
    if not tool_calls_list:
        return False, "", 0
    limit = _MGMT_LOOP_THRESHOLD if threshold is None else threshold

    round_counts: dict[str, int] = {}
    display: dict[str, str] = {}
    unload_targets: set[str] = set()
    for tc in tool_calls_list:
        fn = tc.get("function", {}) or {}
        name = fn.get("name", "") or ""
        if name not in _MGMT_TOOLS:
            continue
        args = _parse_mgmt_tool_args(fn.get("arguments", "{}"))
        if name == "unload_tool":
            for target in _mgmt_tool_targets(name, args):
                unload_targets.add(target)
            # unload itself is not loop-counted; it only resets load streaks
            continue
        if name == "tool_load":
            # Batch loads fan out per target so reloads of one tool do not
            # inherit the counter of an unrelated batch.
            for target in _mgmt_tool_targets(name, args) or [""]:
                fp = f"tool_load:{target}"
                round_counts[fp] = round_counts.get(fp, 0) + 1
                display.setdefault(fp, f"tool_load({target})" if target else name)
            continue
        fp = _mgmt_tool_fingerprint(name, args)
        round_counts[fp] = round_counts.get(fp, 0) + 1
        display[fp] = _mgmt_tool_display(name, args)

    if record and unload_targets:
        for target in unload_targets:
            clear_mgmt_load_streak(target)

    if not round_counts:
        return False, "", 0

    blocked_name = ""
    blocked_count = 0
    for fp, n in round_counts.items():
        if record:
            total = _TOOL_CALL_FINGERPRINTS.get(fp, 0) + n
            _TOOL_CALL_FINGERPRINTS[fp] = total
        else:
            total = _TOOL_CALL_FINGERPRINTS.get(fp, 0) + n
        if total >= limit and total > blocked_count:
            blocked_name = display.get(fp, fp)
            blocked_count = total

    if blocked_count >= limit:
        return True, blocked_name, blocked_count
    return False, "", 0


def check_general_tool_loop(
    tool_calls_list: list[dict[str, Any]],
    *,
    record: bool = True,
    threshold: int | None = None,
) -> tuple[bool, str, int]:
    """Detect repeated same-args general tool calls across rounds.

    Returns (blocked, display_name, count). Management tools are handled by
    check_mgmt_tool_loop and are ignored here.

    Counters are per fingerprint (tool + args). When a different fingerprint
    appears, other general-tool counters are reset so only the active streak
    is tracked.
    """
    if not tool_calls_list:
        return False, "", 0
    limit = _GENERAL_TOOL_LOOP_THRESHOLD if threshold is None else threshold

    round_counts: dict[str, int] = {}
    display: dict[str, str] = {}
    for tc in tool_calls_list:
        fn = tc.get("function", {}) or {}
        name = str(fn.get("name", "") or "")
        if not name or name in _GENERAL_LOOP_EXEMPT_TOOLS:
            continue
        args = _parse_mgmt_tool_args(fn.get("arguments", "{}"))
        fp = _general_tool_fingerprint(name, args)
        round_counts[fp] = round_counts.get(fp, 0) + 1
        display[fp] = name

    if not round_counts:
        return False, "", 0

    if record:
        # Different fingerprint => previous general-tool streaks are stale.
        for key in list(_TOOL_CALL_FINGERPRINTS.keys()):
            if str(key).startswith("tool:") and key not in round_counts:
                _TOOL_CALL_FINGERPRINTS.pop(key, None)

    blocked_name = ""
    blocked_count = 0
    for fp, n in round_counts.items():
        if record:
            total = _TOOL_CALL_FINGERPRINTS.get(fp, 0) + n
            _TOOL_CALL_FINGERPRINTS[fp] = total
        else:
            total = _TOOL_CALL_FINGERPRINTS.get(fp, 0) + n
        if total >= limit and total > blocked_count:
            blocked_name = display.get(fp, fp)
            blocked_count = total

    if blocked_count >= limit:
        return True, blocked_name, blocked_count
    return False, "", 0


def check_repeating_tool_round_cycle(
    tool_calls_list: list[dict[str, Any]],
    *,
    history: deque[tuple[tuple[str, str], ...]],
    record: bool = True,
    max_cycle_length: int = 4,
    repeats: int = 3,
) -> tuple[bool, tuple[tuple[str, ...], ...], int]:
    """Detect a short, exact cycle of tool-call rounds repeated several times.

    Each round is represented by sorted ``(tool name, args digest)`` pairs.
    Arguments are hashed so raw values are not retained in the loop history or
    emitted in diagnostics. The bounded history detects repeated cycles of 2-4
    rounds after three repetitions; one-round repetition remains the job of the
    exact-argument loop guard.
    """
    signature_items: list[tuple[str, str]] = []
    for tool_call in tool_calls_list or []:
        if not isinstance(tool_call, dict):
            continue
        function = tool_call.get("function") or {}
        if not isinstance(function, dict):
            continue
        name = str(function.get("name") or "").strip()
        if not name:
            continue
        args = _parse_mgmt_tool_args(function.get("arguments", "{}"))
        fingerprint = _general_tool_fingerprint(name, args)
        digest = hashlib.sha256(
            fingerprint.encode("utf-8", errors="replace")
        ).hexdigest()[:16]
        signature_items.append((name, digest))

    if not signature_items:
        if record:
            history.clear()
        return False, (), 0

    signature = tuple(sorted(signature_items))
    history_snapshot = list(history)
    if record:
        history.append(signature)
        history_snapshot = list(history)
    else:
        history_snapshot.append(signature)

    repeat_count = max(2, int(repeats))
    max_period = min(
        max(2, int(max_cycle_length)), len(history_snapshot) // repeat_count
    )
    for period in range(2, max_period + 1):
        repeated = history_snapshot[-period * repeat_count :]
        blocks = [
            tuple(repeated[offset : offset + period])
            for offset in range(0, len(repeated), period)
        ]
        if len(blocks) == repeat_count and all(
            block == blocks[0] for block in blocks[1:]
        ):
            cycle_names = tuple(
                tuple(dict.fromkeys(name for name, _digest in round_signature))
                for round_signature in blocks[0]
            )
            return True, cycle_names, period
    return False, (), 0
