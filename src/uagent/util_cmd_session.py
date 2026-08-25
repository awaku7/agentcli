"""Session / memory / skill related :commands (skills, clean, load, shrink, mem, ...).

Moved from util_tools.py.
"""

from __future__ import annotations

import glob
import json
import os
import sys
import tempfile
import unicodedata
from typing import Any

from . import tools
from .env_utils import env_get
from .i18n import _
from .tools import long_memory as personal_long_memory
from .tools import shared_memory
from .tools.context import get_callbacks
from .util_common import CommandResult
from .util_message import (
    _clear_skill_messages,
    _extract_last_cwd_from_messages,
    _format_cwd_system_content,
    _format_skill_system_content,
    _insert_cwd_system_message,
    _read_raw_log_messages,
    _skills_marker_prefix,
    insert_tools_system_message,
)

# Default translation function used when core.tr is not provided.
tr = _
tr_ = _


def _session_preview(value: Any, limit: int = 100) -> str:
    """Return a compact single-line preview for a stored session message."""
    text = " ".join(str(value or "").split())
    if not text:
        return "-"
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _load_skill_tools() -> None:
    """Make the tools used by Agent Skills visible to the next LLM round.

    Skill tools belong to the ``basic`` genre and are therefore normally
    omitted when genres are disabled at startup.  The ``:skills`` command is
    an explicit request to work with skills, so it should not require the
    user/model to issue a separate ``tool_load`` for every skill operation.
    Only the core read/list/validate tools are preloaded here.  Installation,
    marketplace search, uninstall, and ``finish_skill`` have separate
    lifecycles and should remain opt-in.
    """
    try:
        from .tools._genre_control_util import _find_tool_modules, enable_single_tool

        skill_tool_names = {
            "skills_list",
            "skills_load",
            "skills_validate",
            "skills_read_file",
        }
        discovered_names: set[str] = set()
        for _module_name, module in _find_tool_modules():
            spec = getattr(module, "TOOL_SPEC", None)
            function = spec.get("function", {}) if isinstance(spec, dict) else {}
            name = function.get("name") if isinstance(function, dict) else None
            if isinstance(name, str) and name in skill_tool_names:
                discovered_names.add(name)

        for name in sorted(discovered_names):
            # A failed optional tool (for example, one with a missing
            # dependency) must not make the :skills command unusable.
            try:
                enable_single_tool(name)
            except Exception:
                pass
    except Exception:
        # Skill listing/loading below has its own imports and error reporting.
        # Keep this convenience preload best-effort so it cannot change the
        # existing command behaviour when a tool module is unavailable.
        pass


def _handle_cmd_skills(
    arg: str,
    messages_ref: list[dict[str, Any]],
    client: Any,
    depname: str,
    *,
    core: Any,
    tr: Any,
) -> CommandResult:
    # ``:skills`` is the explicit opt-in point for the skill tool family.
    _load_skill_tools()

    # Try dynamic subcommands (e.g., install, uninstall)
    res = tools.handle_dynamic_command(
        "skills",
        arg,
        messages_ref=messages_ref,
        client=client,
        depname=depname,
        core=core,
        tr=tr,
    )
    if res is not None:
        return res

    a = (arg or "").strip()
    if a.lower() in ("clear", "off", "unset", "reset"):
        removed = _clear_skill_messages(messages_ref)
        if removed <= 0:
            print(_("[skills] No active skill messages to clear."))
            return CommandResult()
        _persist_messages_with_warn(messages_ref, core=core, label="skills")
        print(_("[skills] Cleared %(n)d skill message(s).") % {"n": removed})
        return CommandResult()

    if a.lower() in ("active", "status", "show", "list"):
        prefix = _skills_marker_prefix()
        active = []
        for m in messages_ref or []:
            if not isinstance(m, dict):
                continue
            if m.get("role") != "system":
                continue
            content = m.get("content")
            if not isinstance(content, str):
                continue
            if not content.startswith(prefix):
                continue
            # Show header only (first line)
            line = content.splitlines()[0].strip()
            if line.startswith(prefix):
                line = line[len(prefix) :].strip()
            active.append(line)

        if not active:
            print(_("[skills] No active skills."))
            return CommandResult()

        print(_("[skills] Active skills: %(n)d") % {"n": len(active)})
        for i, line in enumerate(active, start=1):
            print(_("[%(i)d] %(line)s") % {"i": i, "line": line})
        return CommandResult()

    try:
        from uagent.tools.human_ask_tool import run_tool as human_ask
        from uagent.tools.skills_list_tool import run_tool as skills_list_tool
        from uagent.tools.skills_load_tool import run_tool as skills_load_tool

        try:
            from uagent.tools import tools as loaded_tools
        except Exception:
            loaded_tools = None

        res_json = skills_list_tool(
            {
                "root_dir": "",
                "recursive": True,
                "include_invalid": True,
                "strict": False,
            }
        )
        try:
            items = res_json if isinstance(res_json, list) else json.loads(res_json)
        except (TypeError, json.JSONDecodeError) as exc:
            detail = str(res_json).strip()[:300]
            raise ValueError(f"skills_list returned invalid JSON: {detail!r}") from exc
        if not isinstance(items, list):
            items = []

        # Filter by keyword if provided (e.g. :skills list forecast, :skills find forecast)
        search_keyword = ""
        a_lower = a.strip().lower()
        for prefix in ("list ", "find ", "search ", "grep "):
            if a_lower.startswith(prefix):
                search_keyword = a_lower[len(prefix) :].strip()
                break
        if search_keyword:
            filtered = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                name = (it.get("name") or "").lower()
                desc = (it.get("description") or "").lower()
                if search_keyword in name or search_keyword in desc:
                    filtered.append(it)
            if filtered:
                items = filtered
            else:
                print(
                    _("[skills] No skills matching '%(kw)s'.") % {"kw": search_keyword}
                )
                return CommandResult()

        if not items:
            print(_("[skills] No skills found."))
            return CommandResult()

        selected_idx: int | None = None
        a_norm = unicodedata.normalize("NFKC", a).strip()
        # Check if arg is a number for direct selection
        if a_norm.isdigit():
            n = int(a_norm)
            if 1 <= n <= len(items):
                selected_idx = n - 1
            else:
                print(_("[skills] Out of range: %(n)d") % {"n": n})
                return CommandResult()

        # If not direct selection, show list and ask
        if selected_idx is None:
            print(_("[skills] Found %(n)d skills") % {"n": len(items)})
            for i, it in enumerate(items, start=1):
                if not isinstance(it, dict):
                    continue
                name = it.get("name") or "(unknown)"
                desc = it.get("description") or ""
                ok = bool(it.get("ok"))
                ok_mark = "OK" if ok else "WARN"
                print(
                    _("[%(i)d] (%(ok)s) %(name)s: %(desc)s")
                    % {"i": i, "ok": ok_mark, "name": name, "desc": desc}
                )
                # Lifecycle state is a stable machine-readable value; keep it
                # untranslated so it matches the JSON/API representation.
                print(f"    lifecycle_state={it.get('lifecycle_state') or 'draft'}")

            sel_msg = _(
                "Select a skill number to run. Enter c to cancel.\n"
                "Tip: :skills clear  (remove applied skills)\n"
                "Enter number:"
            )

            while selected_idx is None:
                sel_json = human_ask({"message": sel_msg})
                try:
                    sel = (
                        sel_json if isinstance(sel_json, dict) else json.loads(sel_json)
                    )
                except (TypeError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        f"human_ask returned invalid JSON: {str(sel_json).strip()[:300]!r}"
                    ) from exc
                user_reply = unicodedata.normalize(
                    "NFKC", (sel.get("user_reply") or "")
                ).strip()
                low = user_reply.lower()
                if low in ("c", "cancel"):
                    print(_("[skills] Cancelled."))
                    return CommandResult()
                if not user_reply.isdigit():
                    print(_("[skills] Please enter a number or c."))
                    continue
                n = int(user_reply)
                if n < 1 or n > len(items):
                    print(_("[skills] Out of range: %(n)d") % {"n": n})
                    continue
                selected_idx = n - 1

        skill = items[selected_idx]
        if not isinstance(skill, dict):
            print(_("[skills] Invalid selection."))
            return CommandResult()

        name = skill.get("name") or "(unknown)"
        skill_dir = skill.get("path")
        if not isinstance(skill_dir, str) or not skill_dir.strip():
            print(_("[skills] Selected skill has no path."))
            return CommandResult()

        confirm_msg = _(
            "Run this skill as a system-level instruction and keep it active in this session?\n\n"
            "Name: %(name)s\n"
            "Path: %(path)s\n\n"
            "Proceed? Enter y to run, or c to cancel."
        ) % {"name": name, "path": os.path.abspath(skill_dir)}

        conf_json = human_ask({"message": confirm_msg})
        try:
            conf = conf_json if isinstance(conf_json, dict) else json.loads(conf_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"human_ask returned invalid JSON: {str(conf_json).strip()[:300]!r}"
            ) from exc
        conf_reply = (conf.get("user_reply") or "").strip().lower()
        if conf_reply not in ("y", "yes"):
            print(_("[skills] Cancelled."))
            return CommandResult()

        doc_json = skills_load_tool({"skill_dir": skill_dir})
        try:
            doc = doc_json if isinstance(doc_json, dict) else json.loads(doc_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"skills_load returned invalid JSON: {str(doc_json).strip()[:300]!r}"
            ) from exc
        if not isinstance(doc, dict):
            raise ValueError("skills_load returned non-dict")

        # Pin tools declared by the skill so the round-loop auto-unloader
        # cannot remove them while the skill is active.
        try:
            from .tools.skill_history import pin_skill_tools

            frontmatter = doc.get("frontmatter")
            if not isinstance(frontmatter, dict):
                frontmatter = {}
            allowed_tools = frontmatter.get("allowed-tools")
            if allowed_tools is None:
                allowed_tools = skill.get("allowed_tools")
            pin_skill_tools(allowed_tools)
        except Exception:
            # Skill execution should still work if optional pinning fails.
            pass

        try:
            tool_specs = (
                loaded_tools.get_tool_specs() if loaded_tools is not None else []
            )
        except Exception:
            tool_specs = []
        has_finish_skill = any(
            isinstance(spec, dict)
            and isinstance(spec.get("function"), dict)
            and spec["function"].get("name") == "finish_skill"
            for spec in (tool_specs or [])
        )
        content = _format_skill_system_content(
            skill=skill,
            doc=doc,
            include_finish_skill=has_finish_skill,
        )

        skill_system_msg = {"role": "system", "content": content}
        _insert_cwd_system_message(messages_ref, skill_system_msg)

        # A newly applied skill changes the system instructions. If the next
        # Responses API call continued an older previous_response_id, the
        # server would not see this newly inserted system message. Clear only
        # the continuation once; the next successful response stores a fresh
        # previous_response_id for subsequent turns.
        try:
            from .core import clear_responses_continuation

            clear_responses_continuation()
        except Exception:
            pass

        # Gemini/Vertex caches contain the previous system instructions. A
        # newly applied skill must invalidate that cache so the next round
        # recreates it with the skill body included.
        try:
            state = getattr(core, "responses_state", {})
            provider = (
                str(state.get("provider", "")).lower()
                if isinstance(state, dict)
                else ""
            )
            if provider in ("gemini", "vertexai"):
                from .providers.gemini_cache_mgr import GeminiCacheManager

                GeminiCacheManager(depname).clear_cache(client)
        except Exception:
            pass

        _persist_messages_with_warn(messages_ref, core=core, label="skills")
        print(_("[skills] Applied: %(name)s") % {"name": name})
        return CommandResult(run_llm=True)

    except Exception as e:
        print(
            _("[skills error] %(etype)s: %(err)s")
            % {"etype": type(e).__name__, "err": e}
        )

    return CommandResult()


def _default_clean_threshold() -> int:
    """Default max user-turn count for short-log cleanup.

    Override with UAGENT_CLEAN_THRESHOLD (positive int). Falls back to 5.
    """
    raw = (env_get("UAGENT_CLEAN_THRESHOLD", "") or "").strip()
    if raw:
        try:
            n = int(raw)
            if n >= 0:
                return n
        except Exception:
            pass
    return 5


def _count_user_turns(messages: list[Any] | None) -> int:
    """Count user turns (role == user). Commands/system/tool rows are ignored."""
    n = 0
    for m in messages or []:
        if isinstance(m, dict) and m.get("role") == "user":
            n += 1
    return n


def _parse_clean_threshold(arg: str, *, tr: Any) -> int | None:
    threshold = _default_clean_threshold()
    a = (arg or "").strip()
    if not a:
        return threshold

    try:
        return int(a)
    except Exception:
        print(
            tr(
                "[clean] Invalid argument: %(arg)r (specify number=threshold; default is %(default)d)"
            )
            % {"arg": a, "default": threshold}
        )
        return None


def _collect_clean_targets(
    *,
    core: Any,
    threshold: int,
    tr: Any,
) -> tuple[bool, list[str], dict[str, int]]:
    try:
        log_files = core.find_log_files(exclude_current=False)
    except Exception as e:
        print(
            _("[clean error] Failed to get log list: %(etype)s: %(err)s")
            % {"etype": type(e).__name__, "err": e}
        )
        return False, [], {}

    targets: list[str] = []
    counts: dict[str, int] = {}

    for p in log_files:
        try:
            msgs = core.load_conversation_from_log(p)
            user_turns = _count_user_turns(msgs)
            counts[p] = user_turns
            if user_turns <= threshold:
                targets.append(p)
        except Exception as e:
            print(
                _("[clean warn] Skipped (parse failed): %(path)s (%(etype)s: %(err)s)")
                % {"path": p, "etype": type(e).__name__, "err": e}
            )

    return True, targets, counts


def _confirm_clean_delete(
    *, core: Any, threshold: int, targets: list[str], tr: Any
) -> bool:
    try:
        from uagent.tools.human_ask_tool import run_tool as human_ask

        cmd = ":clean"
        body_tpl = _(
            "will delete conversation log files (scheck_log_*.jsonl) from disk.\n"
            "Log dir: %(dir)s\n"
            "Rule: user turns (role=user) <= %(threshold)d\n"
            "Targets: %(n)d\n\n"
            "Proceed? Enter y to run, or c to cancel."
        )
        body = (tr(body_tpl) if callable(tr) else body_tpl) % {
            "dir": getattr(core, "BASE_LOG_DIR", "(unknown)"),
            "threshold": threshold,
            "n": len(targets),
        }
        res_json = human_ask({"message": f"{cmd} {body}"})
        res = json.loads(res_json)
        user_reply = (res.get("user_reply") or "").strip().lower()
        if user_reply not in ("y", "yes"):
            print(_("[clean] Cancelled."))
            return False
        return True
    except Exception as e:
        print(
            _("[clean error] Confirmation failed: %(etype)s: %(err)s")
            % {"etype": type(e).__name__, "err": e}
        )
        return False


def _delete_clean_targets(targets: list[str], *, tr: Any) -> tuple[int, int]:
    deleted = 0
    failed = 0
    for p in targets:
        try:
            os.remove(p)
            deleted += 1
        except Exception as e:
            failed += 1
            print(
                _("[clean warn] Delete failed: %(path)s (%(etype)s: %(err)s)")
                % {"path": p, "etype": type(e).__name__, "err": e}
            )

    return deleted, failed


def _maybe_discard_short_session_log(
    *,
    core: Any,
    messages_ref: list[dict[str, Any]],
    tr: Any,
) -> None:
    """On exit, drop the current session log if it has few user turns.

    Silent no-op when the log is missing or above threshold. No confirmation
    (exit path); threshold matches :clean default / UAGENT_CLEAN_THRESHOLD.
    """
    threshold = _default_clean_threshold()
    user_turns = _count_user_turns(messages_ref)
    if user_turns > threshold:
        return

    log_path = getattr(core, "LOG_FILE", None)
    if not isinstance(log_path, str) or not log_path:
        return
    if not os.path.exists(log_path):
        return

    try:
        os.remove(log_path)
        print(
            tr(
                "[clean] Discarded short session log (user turns=%(n)d <= %(threshold)d): %(path)s"
            )
            % {"n": user_turns, "threshold": threshold, "path": log_path}
        )
    except Exception as e:
        print(
            _(
                "[clean warn] Failed to discard session log: %(path)s (%(etype)s: %(err)s)"
            )
            % {"path": log_path, "etype": type(e).__name__, "err": e},
            file=sys.stderr,
        )


def _sweep_short_session_logs(
    *,
    core: Any,
    tr: Any,
    exclude_current: bool = True,
    quiet: bool = False,
) -> tuple[int, int]:
    """Delete leftover short session logs without confirmation.

    Intended for startup (crashed/killed sessions) and other maintenance paths.
    Current session is excluded by default so a fresh log is never removed.
    Returns (deleted, failed).
    """
    threshold = _default_clean_threshold()
    try:
        log_files = core.find_log_files(exclude_current=exclude_current)
    except Exception as e:
        if not quiet:
            print(
                _(
                    "[clean warn] Startup sweep skipped (list failed): %(etype)s: %(err)s"
                )
                % {"etype": type(e).__name__, "err": e},
                file=sys.stderr,
            )
        return 0, 0

    targets: list[str] = []
    for path in log_files:
        try:
            msgs = core.load_conversation_from_log(path)
            if _count_user_turns(msgs) <= threshold:
                targets.append(path)
        except Exception as e:
            if not quiet:
                print(
                    _(
                        "[clean warn] Startup sweep skipped (parse failed): %(path)s (%(etype)s: %(err)s)"
                    )
                    % {"path": path, "etype": type(e).__name__, "err": e}
                )

    if not targets:
        return 0, 0

    deleted, failed = _delete_clean_targets(targets, tr=tr)
    if not quiet and (deleted or failed):
        print(
            tr(
                "[clean] Startup sweep: deleted=%(deleted)d, failed=%(failed)d "
                "(threshold=%(threshold)d user turns)."
            )
            % {"deleted": deleted, "failed": failed, "threshold": threshold}
        )
    return deleted, failed


def _handle_sqlite_clean(*, core: Any, threshold: int) -> bool:
    """Clean short SQLite sessions while preserving the active session."""
    store = getattr(core, "session_store", None)
    if store is None:
        return False
    current_id = getattr(core, "session_id", None)
    targets: list[tuple[str, int]] = []
    try:
        for row in store.list_sessions():
            session_id = row["session_id"]
            if session_id == current_id:
                continue
            count = sum(
                1
                for msg in store.list_messages(session_id)
                if msg.get("role") == "user"
            )
            if count <= threshold:
                targets.append((session_id, count))
    except Exception as exc:
        print("[clean] SQLite session scan failed: " + str(exc))
        return True
    if not targets:
        print(f"[clean] No SQLite sessions to delete (threshold={threshold}).")
        return True
    print(f"[clean] SQLite sessions to delete: {len(targets)}")
    for session_id, count in targets:
        print(f" - ({count} user turns) {session_id}")
    try:
        from uagent.tools.human_ask_tool import run_tool as human_ask

        response = human_ask(
            {
                "message": (
                    f"Delete {len(targets)} SQLite session(s) with <= {threshold} user turns? "
                    "Enter y to run, or c to cancel."
                )
            }
        )
        parsed = response if isinstance(response, dict) else json.loads(response)
        if str(parsed.get("user_reply") or "").strip().lower() not in {"y", "yes"}:
            print("[clean] Cancelled.")
            return True
    except Exception as exc:
        print("[clean] Confirmation failed: " + str(exc))
        return True
    deleted = 0
    for session_id, _session_summary in targets:
        try:
            store.delete_session(session_id)
            deleted += 1
        except Exception as exc:
            print(f"[clean] Failed to delete {session_id}: {exc}")
    try:
        store.vacuum()
    except Exception as exc:
        print("[clean] SQLite vacuum failed: " + str(exc))
    print(f"[clean] SQLite done: deleted={deleted}, failed={len(targets) - deleted}")
    return True


def _handle_cmd_clean(arg: str, *, core: Any, tr: Any) -> bool:
    threshold = _parse_clean_threshold(arg, tr=tr)
    if threshold is None:
        return True

    if (
        os.environ.get("UAGENT_SESSION_BACKEND", "sqlite").strip().lower() == "sqlite"
        and getattr(core, "session_store", None) is not None
    ):
        return _handle_sqlite_clean(core=core, threshold=threshold)

    ok, targets, counts = _collect_clean_targets(core=core, threshold=threshold, tr=tr)
    if not ok:
        return True

    if not targets:
        print(
            _(
                "[clean] No logs to delete (threshold=%(threshold)d user turns).\nLog dir: %(dir)s"
            )
            % {
                "threshold": threshold,
                "dir": getattr(core, "BASE_LOG_DIR", "(unknown)"),
            }
        )
        return True

    print(
        _("[clean] Logs to delete (<= %(threshold)d user turns): %(n)d")
        % {"threshold": threshold, "n": len(targets)}
    )
    for p in targets:
        c = counts.get(p, -1)
        print(tr(" - (%(count)d user turns) %(path)s") % {"count": c, "path": p})

    if not _confirm_clean_delete(
        core=core, threshold=threshold, targets=targets, tr=tr
    ):
        return True

    deleted, failed = _delete_clean_targets(targets, tr=tr)
    print(
        _("[clean] Done: deleted=%(deleted)d, failed=%(failed)d")
        % {"deleted": deleted, "failed": failed}
    )
    return True


def _prepend_loaded_log_to_current(
    *,
    core: Any,
    source_log_path: str,
    tr: Any,
) -> None:
    try:
        from uagent.tools.human_ask_tool import run_tool as human_ask

        cur_log = getattr(core, "LOG_FILE", None)
        if not isinstance(cur_log, str) or not cur_log:
            return

        cmd = ":load"
        body_tpl = _(
            "will overwrite the current session log file and prepend the loaded log (no backup).\n\n"
            "Current log: %(cur_log)s\n"
            "Source log: %(src_log)s\n\n"
            "Proceed? Enter y to run, or c to cancel."
        )
        body = (tr(body_tpl) if callable(tr) else body_tpl) % {
            "cur_log": cur_log,
            "src_log": source_log_path,
        }
        res_json2 = human_ask({"message": f"{cmd} {body}"})
        res2 = json.loads(res_json2)
        user_reply2 = (res2.get("user_reply") or "").strip().lower()
        if user_reply2 not in ("y", "yes"):
            print(_("[load] Prepend to current log was cancelled."))
            return

        loaded_lines: list[str] = []
        try:
            with open(source_log_path, encoding="utf-8") as f:
                loaded_lines = f.read().splitlines(True)
        except Exception as e:
            print(
                _("[load warn] Failed to read source log: %(etype)s: %(err)s")
                % {"etype": type(e).__name__, "err": e},
                file=sys.stderr,
            )
            loaded_lines = []

        cur_lines: list[str] = []
        try:
            if os.path.exists(cur_log):
                with open(cur_log, encoding="utf-8") as f:
                    cur_lines = f.read().splitlines(True)
        except Exception as e:
            print(
                _("[load warn] Failed to read current log: %(etype)s: %(err)s")
                % {"etype": type(e).__name__, "err": e},
                file=sys.stderr,
            )
            cur_lines = []

        marker = {
            "role": "system",
            "content": f"[LOG] :load prepend source={os.path.abspath(source_log_path)}",
        }
        marker_line = json.dumps(marker, ensure_ascii=False) + "\n"

        try:
            os.makedirs(os.path.dirname(cur_log) or ".", exist_ok=True)
            with open(cur_log, "w", encoding="utf-8") as f:
                f.write(marker_line)
                for ln in loaded_lines:
                    f.write(ln)
                for ln in cur_lines:
                    f.write(ln)
            print(_("[load] Prepended to current log: %(path)s") % {"path": cur_log})
        except Exception as e:
            print(
                _("[load warn] Failed to rewrite current log: %(etype)s: %(err)s")
                % {"etype": type(e).__name__, "err": e},
                file=sys.stderr,
            )
            return
    except Exception as e:
        print(
            _("[load error] Failed: %(etype)s: %(err)s")
            % {"etype": type(e).__name__, "err": e}
        )
        return


def _handle_cmd_sessions(
    arg: str,
    *,
    messages_ref: list[dict[str, Any]] | None = None,
    client: Any = None,
    depname: str = "",
    core: Any,
    tr: Any,
) -> bool:
    """Search opt-in SQLite session history from the CLI."""
    parts = (arg or "").strip().split()
    command = parts[0].lower() if parts else ""
    store = getattr(core, "session_store", None)
    session_id = getattr(core, "session_id", None)
    if command == "prune":
        if store is None:
            print(_("[sessions] Session store is not enabled."))
            return True
        args = parts[1:]
        if "--keep" not in args:
            print(_("[sessions] Usage: :sessions prune --keep <N> [--dry-run|--yes]"))
            return True
        try:
            keep_index = args.index("--keep") + 1
            keep = int(args[keep_index])
            if keep < 0:
                raise ValueError
        except (ValueError, IndexError):
            print(_("[sessions] --keep must be a non-negative integer."))
            return True
        confirmed = "--yes" in args or "-y" in args
        dry_run = "--dry-run" in args or not confirmed
        rows = store.list_sessions()
        candidates = rows[keep:]
        if session_id:
            candidates = [r for r in candidates if r.get("session_id") != session_id]
        print(
            _("[sessions] Prune plan: keep newest %(keep)d, candidates=%(count)d")
            % {"keep": keep, "count": len(candidates)}
        )
        for row in candidates:
            print(
                _("  %(id)s | %(created_at)s | %(count)d messages")
                % {
                    "id": row["session_id"],
                    "created_at": row.get("created_at"),
                    "count": row.get("message_count", 0),
                }
            )
        if not candidates:
            return True
        if dry_run:
            print(
                _(
                    "[sessions] Dry run; nothing deleted. Add --yes to delete these sessions."
                )
            )
            return True
        deleted = 0
        for row in candidates:
            try:
                store.delete_session(str(row["session_id"]))
                deleted += 1
            except Exception as exc:
                print(
                    _("[sessions] Failed to delete %(id)s: %(error)s")
                    % {"id": row["session_id"], "error": exc}
                )
        try:
            store.vacuum()
        except Exception as exc:
            print(_("[sessions] VACUUM failed: %(error)s") % {"error": exc})
        print(
            _("[sessions] Pruned %(deleted)d/%(total)d session(s).")
            % {"deleted": deleted, "total": len(candidates)}
        )
        return True
    if command == "summarize":
        if store is None or client is None or not depname:
            print(_("[sessions] Session store or LLM is not enabled."))
            return True
        force = "--force" in parts[1:]
        target = next((p for p in parts[1:] if not p.startswith("--")), "")
        rows = store.list_sessions()
        if target:
            rows = [r for r in rows if r.get("session_id") == target]
        print(
            _("[sessions] Summarizing %(count)d session(s)...") % {"count": len(rows)}
        )
        done = skipped = failed = 0
        for index, row in enumerate(rows, start=1):
            sid = str(row["session_id"])
            if not force and row.get("summary"):
                print(
                    _("[%(index)d/%(total)d] %(id)s  skipped")
                    % {"index": index, "total": len(rows), "id": sid}
                )
                skipped += 1
                continue
            try:
                stored = store.list_messages(sid)
                if len(stored) < 2:
                    print(
                        _("[%(index)d/%(total)d] %(id)s  skipped (too short)")
                        % {"index": index, "total": len(rows), "id": sid}
                    )
                    skipped += 1
                    continue
                compressed = core.compress_history_with_llm(
                    client=client,
                    depname=depname,
                    messages=stored + [stored[-1]],
                    keep_last=1,
                    emit_log=False,
                )
                from .llm_message_helpers import (
                    _is_history_summary_message,
                    _strip_history_summary_prefix,
                )

                # The summary prefix is translated according to the active
                # locale, so do not search for the English literal here.
                # Use the same helper as history compression/loading.
                summary = next(
                    (
                        _strip_history_summary_prefix(str(m.get("content", "")))
                        for m in compressed
                        if _is_history_summary_message(m)
                    ),
                    "",
                )
                if not summary:
                    raise RuntimeError("LLM returned no summary")
                store.save_session_summary(sid, summary)
                print(
                    _("[%(index)d/%(total)d] %(id)s  saved")
                    % {"index": index, "total": len(rows), "id": sid}
                )
                done += 1
            except Exception as exc:
                print(
                    _("[%(index)d/%(total)d] %(id)s  failed: %(error)s")
                    % {"index": index, "total": len(rows), "id": sid, "error": exc}
                )
                failed += 1
        print(
            _(
                "[sessions] Complete: %(done)d summarized, %(skipped)d skipped, %(failed)d failed"
            )
            % {"done": done, "skipped": skipped, "failed": failed}
        )
        return True
    if command == "candidates":
        if store is None or not session_id:
            print(_("[sessions] Session store is not enabled."))
            return True
        candidates = store.list_memory_candidates(session_id)
        if not candidates:
            print(_("[sessions] No memory candidates."))
            return True
        print(_("[sessions] Memory candidates:"))
        for index, candidate in enumerate(candidates, start=1):
            print(f"[{index}] {candidate}")
        return True
    if command == "approve":
        if store is None or not session_id:
            print(_("[sessions] Session store is not enabled."))
            return True
        try:
            index = int(parts[1]) - 1
            candidate = store.list_memory_candidates(session_id)[index]
        except (ValueError, IndexError):
            print(_("[sessions] Usage: :sessions approve <number>"))
            return True
        personal_long_memory.append_long_memory(candidate)
        print(_("[sessions] Memory candidate approved."))
        return True
    if command == "import":
        if store is None:
            print(_("[sessions] Session store is not enabled."))
            return True
        # This command runs inside the CLI, not through a shell, so ``~`` is
        # not expanded automatically.
        source = os.path.expanduser(parts[1]) if len(parts) > 1 else ""
        project = parts[2] if len(parts) > 2 else None
        if not source:
            print(_("[sessions] Usage: :sessions import <jsonl_path> [project]"))
            return True
        sources = (
            sorted(glob.glob(os.path.join(source, "scheck_log_*.jsonl")))
            if os.path.isdir(source)
            else [source]
        )
        if not sources:
            print(_("[sessions] No JSONL logs found."))
            return True
        imported_count = 0
        try:
            for source_path in sources:
                store.import_jsonl(source_path, project=project)
                imported_count += 1
            print(_("[sessions] JSONL imported: %(count)d") % {"count": imported_count})
        except Exception as exc:
            print(_("[sessions] Import failed: " + str(exc)))
        return True
    if command == "load":
        if store is None:
            print(_("[sessions] Session store is not enabled."))
            return True
        target = parts[1] if len(parts) > 1 else ""
        if not target or messages_ref is None:
            print(_("[sessions] Usage: :sessions load <session_id>"))
            return True
        if target == session_id:
            print(_("[sessions] Session is already active."))
            return True
        try:
            loaded = store.list_messages(target)
            if not loaded:
                print(_("[sessions] Session has no messages."))
                return True
            messages_ref.clear()
            messages_ref.extend(loaded)
            print(_("[sessions] Session loaded: " + target))
        except Exception as exc:
            print(_("[sessions] Load failed: " + str(exc)))
        return True
    if command == "pdf":
        if store is None:
            print(_("[sessions] Session store is not enabled."))
            return True
        target = parts[1] if len(parts) > 1 else ""
        output_path = parts[2] if len(parts) > 2 else f"session-{target}.pdf"
        if not target:
            print(_("[sessions] Usage: :sessions pdf <session_id> [output.pdf]"))
            return True
        temp_path = ""
        try:
            messages = store.list_messages(target)
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".jsonl", encoding="utf-8", delete=False
            ) as temp:
                temp_path = temp.name
                for message in messages:
                    temp.write(json.dumps(message, ensure_ascii=False) + "\n")
            from uagent.tools.pdf_export_tool import run_tool as pdf_export_run

            result = pdf_export_run({"log_path": temp_path, "output_path": output_path})
            print(result)
        except Exception as exc:
            print(_("[sessions] PDF export failed: " + str(exc)))
        finally:
            if temp_path:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
        return True
    if command == "list":
        if store is None:
            print(_("[sessions] Session store is not enabled."))
            return True
        for index, row in enumerate(store.list_sessions()):
            first = _session_preview(row.get("first_message"))
            last = _session_preview(row.get("last_message"))
            summary = _session_preview(row.get("summary"))
            print(
                f"[{index}] {row['created_at']}  {row.get('message_count', 0)} messages"
            )
            print(f"    first: {first}")
            print(f"    last:  {last}")
            if summary and summary not in {first, last}:
                print(f"    summary: {summary}")
            print(
                f"    id: {row['session_id']} | {row.get('project') or '-'} | "
                f"{row['entry_point']}"
            )
        return True
    if command == "delete":
        if store is None or not session_id:
            print(_("[sessions] Session store is not enabled."))
            return True
        target = parts[1] if len(parts) > 1 else ""
        confirmed = "--yes" in parts[2:] or "-y" in parts[2:]
        if not target or not confirmed:
            print(_("[sessions] Usage: :sessions delete <session_id> --yes"))
            return True
        if target == session_id:
            print(_("[sessions] Cannot delete the active session."))
            return True
        try:
            store.delete_session(target)
            print(_("[sessions] Session deleted."))
        except Exception as exc:
            print(_("[sessions] Delete failed: " + str(exc)))
        return True
    if command == "vacuum":
        if store is None:
            print(_("[sessions] Session store is not enabled."))
            return True
        try:
            store.vacuum()
            print(_("[sessions] Database vacuum completed."))
        except Exception as exc:
            print(_("[sessions] Vacuum failed: " + str(exc)))
        return True
    if command != "search":
        print(
            ":sessions list | load <session_id> | search <query> | candidates | approve <number> | delete <session_id> --yes | vacuum | pdf <session_id> [output.pdf] | import <jsonl_path>"
        )
        return True
    query_parts = parts[1:]
    project = None
    if "--project" in query_parts:
        index = query_parts.index("--project")
        if index + 1 < len(query_parts):
            project = query_parts[index + 1]
            del query_parts[index : index + 2]
    query = " ".join(query_parts).strip()
    store = getattr(core, "session_store", None)
    if store is None:
        print(_("[sessions] Session store is not enabled."))
        return True
    if not query:
        print(":sessions search <query>")
        return True
    try:
        results = store.search(query, project=project)
    except Exception as exc:
        print(_("[sessions] Search failed: " + str(exc)))
        return True
    if not results:
        print(_("[sessions] No matching sessions."))
        return True
    print(_("[sessions] Matches: " + str(len(results))))
    for row in results:
        print(
            f"{row['session_id']} | {row.get('project') or '-'} | "
            f"{row['role']}: {row['content']}"
        )
    return True


def _handle_cmd_load(
    arg: str,
    messages_ref: list[dict[str, Any]],
    *,
    core: Any,
    tr: Any,
) -> bool:
    if (
        os.environ.get("UAGENT_SESSION_BACKEND", "sqlite").strip().lower() == "sqlite"
        and getattr(core, "session_store", None) is not None
    ):
        store = core.session_store
        try:
            sessions = [
                row
                for row in store.list_sessions()
                if row["session_id"] != getattr(core, "session_id", None)
            ]
        except Exception as exc:
            print(
                _("[load error] SQLite session listing failed: %(error)s")
                % {"error": exc}
            )
            return True
        target = (arg or "").strip()
        # The web UI quotes session IDs when sending :load. Remove only a
        # matching outer quote pair; SQLite session IDs themselves are bare.
        if len(target) >= 2 and target[0] == target[-1] and target[0] in {'"', "'"}:
            target = target[1:-1]
        if not target:
            if not sessions:
                print(_("[load] No SQLite sessions available."))
                return True
            print(_("[load] Select a session (newest first):"))
            for index, row in enumerate(sessions):
                summary = _session_preview(row.get("summary"))
                preview = summary
                if preview == "-":
                    preview = _session_preview(row.get("first_message"))
                print(
                    f"  [{index}] {row.get('created_at') or '-'} | "
                    f"{row.get('message_count', 0)} messages | "
                    f"{row.get('project') or '-'}"
                )
                print(f"      {preview}")
                print(f"      id: {row['session_id']}")
            print(_("[load] Usage: :load <index|session_id>"))
            return True
        if target.isdigit():
            index = int(target)
            if index < 0 or index >= len(sessions):
                print("[load] Session index out of range.")
                return True
            target = sessions[index]["session_id"]
        session_row = next(
            (row for row in sessions if row.get("session_id") == target), None
        )
        try:
            loaded = store.list_messages(target)
            if not loaded:
                print("[load] Session has no messages.")
                return True
            messages_ref.clear()
            messages_ref.extend(loaded)
            # Keep subsequent messages and tool results in the loaded session,
            # rather than silently appending them to the session created at
            # startup.
            core.session_id = target
            core._session_store_active_id = target
            state = store.latest_response_state(target)
            if state is not None:
                response_state = getattr(core, "responses_state", None)
                if isinstance(response_state, dict):
                    response_state.update(
                        {
                            "provider": state["provider"],
                            "model": state["model"],
                            "previous_response_id": state["response_id"],
                            "last_response_status": state["status"],
                        }
                    )
            print(_("[load] SQLite session loaded"))
            print(f"  id: {target}")
            if session_row is not None:
                print(f"  created: {session_row.get('created_at') or '-'}")
                print(f"  project: {session_row.get('project') or '-'}")
                print(f"  messages: {len(loaded)}")
                summary = _session_preview(session_row.get("summary"))
                if summary != "-":
                    print(f"  summary: {summary}")
                print(f"  first: {_session_preview(session_row.get('first_message'))}")
                print(f"  last:  {_session_preview(session_row.get('last_message'))}")
            print(
                _(
                    "[load] Conversation loaded into the current context; "
                    "you can continue by entering a message."
                )
            )
        except Exception as exc:
            print("[load error] Failed: " + str(exc))
        return True

    if not arg:
        print(_(":load <index|path>"))
        return True

    files = core.find_log_files(exclude_current=True)
    if arg.isdigit():
        idx = int(arg)
        if idx < 0 or idx >= len(files):
            print(tr("Specified index %(idx)d is out of range.") % {"idx": idx})
            return True
        target_path = files[idx]
    else:
        target_path = arg

    try:
        new_messages = core.load_conversation_from_log(target_path)
    except FileNotFoundError:
        print(tr("Log file not found: %(path)s") % {"path": target_path})
        return True
    except Exception as e:
        print(
            _("[load error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )
        return True

    new_messages = insert_tools_system_message(new_messages, core=core)
    messages_ref.clear()
    messages_ref.extend(new_messages)

    try:
        cb = get_callbacks()
        append_history = getattr(cb, "prompt_history_append", None)
        if callable(append_history):
            for msg in new_messages:
                if msg.get("role") != "user":
                    continue
                content = msg.get("content")
                if isinstance(content, str) and content.strip():
                    append_history(content)
    except Exception:
        pass

    # Auto-restore cwd from the loaded log (no confirmation).
    # Note: extract from the RAW log lines because load_conversation_from_log
    # strips non-[SKILL]/[HOOK] system messages (including [CWD] markers).
    try:
        target_cwd = _extract_last_cwd_from_messages(
            _read_raw_log_messages(target_path)
        )
        if (
            isinstance(target_cwd, str)
            and target_cwd.strip()
            and os.path.isdir(target_cwd)
        ):
            prev = os.getcwd()
            os.chdir(target_cwd)
            now = os.getcwd()

            # Record the cwd change triggered by :load.
            try:
                msg = {
                    "role": "system",
                    "content": _format_cwd_system_content(
                        event="load",
                        path=now,
                        extra={"prev": prev, "log": os.path.abspath(target_path)},
                    ),
                }
                _insert_cwd_system_message(messages_ref, msg)
                core.log_message(msg)
            except Exception:
                pass

            print(_("[load] workdir = %(path)s") % {"path": now})
    except Exception as e:
        print(
            _("[load warn] Failed to chdir from loaded log: %(etype)s: %(err)s")
            % {"etype": type(e).__name__, "err": e},
            file=sys.stderr,
        )

    print(_("Loaded log: %(path)s") % {"path": target_path})
    print(_("Conversation message count: %(n)d") % {"n": len(messages_ref)})

    # Restore the newest Responses state from the loaded log only when it is
    # structurally valid and matches the active provider/model.  The source
    # log remains intact; the current session continues in the current log.
    try:
        old_state = dict(getattr(core, "responses_state", {}) or {})
        loaded_state = None
        read_state = getattr(core, "latest_responses_state", None)
        if callable(read_state):
            loaded_state = read_state(target_path)

        current_provider = (
            str(
                old_state.get("provider")
                or getattr(core, "provider", "")
                or getattr(core, "_responses_provider", "")
                or ""
            )
            .strip()
            .lower()
        )
        current_model = str(
            old_state.get("model")
            or getattr(core, "depname", "")
            or getattr(core, "model", "")
            or ""
        ).strip()

        if hasattr(core, "responses_state"):
            core.responses_state.clear()

        if isinstance(loaded_state, dict):
            rid = str(loaded_state.get("response_id") or "").strip()
            loaded_provider = str(loaded_state.get("provider") or "").strip().lower()
            loaded_model = str(loaded_state.get("model") or "").strip()
            status = str(loaded_state.get("status") or "").strip().lower()
            supported = loaded_provider in {"openai", "azure"}
            same_provider = not current_provider or loaded_provider == current_provider
            same_model = not current_model or loaded_model == current_model
            validated = True
            if (
                supported
                and rid
                and getattr(core, "_responses_client", None) is not None
            ):
                try:
                    from .providers.responses_manager import ResponsesManager

                    ResponsesManager(
                        getattr(core, "_responses_client"),
                        provider=loaded_provider,
                        model=loaded_model,
                    ).retrieve(rid)
                except Exception:
                    validated = False
            if (
                rid.startswith("resp_")
                and status == "completed"
                and supported
                and same_provider
                and same_model
                and validated
            ):
                core.responses_state.update(
                    {
                        "provider": loaded_provider,
                        "model": loaded_model,
                        "previous_response_id": rid,
                        "last_response_status": "completed",
                    }
                )

        if hasattr(core, "_save_responses_state"):
            core._save_responses_state()
    except Exception:
        # Loading the conversation must still succeed if state inspection fails.
        try:
            if hasattr(core, "responses_state"):
                core.responses_state.clear()
            if hasattr(core, "_save_responses_state"):
                core._save_responses_state()
        except Exception:
            pass

    _prepend_loaded_log_to_current(core=core, source_log_path=target_path, tr=tr)
    return True


def _persist_messages_with_warn(
    messages: list[dict[str, Any]], *, core: Any, label: str
) -> None:
    try:
        cb = get_callbacks()
        rewrite_current_log = getattr(cb, "rewrite_current_log_from_messages", None)
        if rewrite_current_log is not None:
            rewrite_current_log(messages)
        else:
            core.rewrite_current_log_from_messages(messages)
    except Exception as e:
        print(
            _("[%(label)s warn] Failed to rewrite current log: %(etype)s: %(err)s")
            % {"label": label, "etype": type(e).__name__, "err": e},
            file=sys.stderr,
        )


def _handle_cmd_shrink(
    arg: str, messages_ref: list[dict[str, Any]], *, core: Any
) -> bool:
    keep_last = 40
    if arg:
        try:
            keep_last = int(arg)
        except Exception:
            print(
                _(
                    _(
                        "[shrink error] Failed to parse as int: %(arg)r -> keep last %(keep)d"
                    )
                )
                % {"arg": arg, "keep": keep_last}
            )

    new_messages = core.shrink_messages(messages_ref, keep_last=keep_last)
    messages_ref.clear()
    messages_ref.extend(new_messages)
    _persist_messages_with_warn(messages_ref, core=core, label="shrink")
    return True


def _handle_cmd_shrink_llm(
    arg: str,
    messages_ref: list[dict[str, Any]],
    client: Any,
    depname: str,
    *,
    core: Any,
) -> bool:
    keep_last = 20
    if arg:
        try:
            keep_last = int(arg)
        except Exception:
            print(
                _(
                    "[shrink_llm error] Failed to parse as int: %(arg)r -> keep last %(keep)d"
                )
                % {"arg": arg, "keep": keep_last}
            )

    _use_responses = (env_get("UAGENT_RESPONSES", "") or "").strip().lower() in (
        "1",
        "true",
    )
    # Mirror the main-flow guard: only providers in RESPONSES_PROVIDERS
    # can actually use the Responses API.  Gemini/Claude/DeepSeek etc.
    # are routed to their own branches inside compress_history_with_llm
    # regardless, so we just need to prevent a 404 on unsupported providers.
    if _use_responses:
        from .providers.provider_caps import RESPONSES_PROVIDERS

        _provider = (env_get("UAGENT_PROVIDER", "") or "").strip().lower()
        if _provider not in RESPONSES_PROVIDERS:
            _use_responses = False

    try:
        new_messages = core.compress_history_with_llm(
            client=client,
            depname=depname,
            messages=messages_ref,
            keep_last=keep_last,
            use_responses_api=_use_responses,
        )
    except Exception as e:
        print(
            _("[shrink_llm error] %(etype)s: %(err)s")
            % {"etype": type(e).__name__, "err": e}
        )
        return True
    messages_ref.clear()
    messages_ref.extend(new_messages)
    _persist_messages_with_warn(messages_ref, core=core, label="shrink_llm")
    return True


def _handle_cmd_tokens(
    messages_ref: list[dict[str, Any]],
    *,
    core: Any,
    depname: str = "",
) -> bool:
    try:
        from .llm_message_helpers import (
            _count_messages_tokens,
            _count_request_extras_tokens,
        )

        total_tokens = _count_messages_tokens(messages_ref, depname or None)
        # Tool schemas are sent beside the conversation and are not part of
        # messages_ref. Count them locally so :tokens does not under-report
        # requests when the tool surface is large.
        tool_specs = []
        if getattr(core, "tools_enabled", True):
            try:
                state = getattr(core, "responses_state", {})
                provider = (
                    str(
                        (state.get("provider") if isinstance(state, dict) else "")
                        or getattr(core, "provider", "")
                        or ""
                    )
                    .strip()
                    .lower()
                )
                responses_env = (env_get("UAGENT_RESPONSES") or "").strip().lower()
                use_responses = responses_env in ("1", "true", "yes", "on")
                if isinstance(state, dict) and state.get("previous_response_id"):
                    use_responses = True

                # Native GPT-5.4 tool_search keeps tool schemas server-side;
                # they are not part of the client input and must not be added
                # to this local estimate. Legacy/non-Responses paths still
                # count the schemas sent by the client.
                native_tool_search = False
                if use_responses:
                    from .tools.llm_tool_narrowing import should_emit_catalog_steering

                    native_tool_search = not should_emit_catalog_steering(
                        provider=provider,
                        depname=depname,
                        use_responses_api=True,
                    )
                if not native_tool_search:
                    tool_specs = tools.get_tool_specs() or []
            except Exception:
                tool_specs = []
        total_tokens += _count_request_extras_tokens(
            messages_ref,
            tool_specs=tool_specs,
            depname=depname or None,
        )
    except Exception as e:
        print(
            _("[tokens error] %(etype)s: %(err)s")
            % {"etype": type(e).__name__, "err": e}
        )
        return True

    print(_("Current token count (approx): %(n)s") % {"n": total_tokens})
    return True


def _handle_cmd_mem_list(*, tr: Any) -> bool:
    records = personal_long_memory.load_long_memory_records()
    if not records:
        print(_("No long-term memory entries."))
        return True

    print(_("Long-term memory entries:"))
    for idx, rec in enumerate(records):
        ts = rec.get("ts")
        if isinstance(ts, (int, float)):
            import time as _time

            dt = _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(ts))
        else:
            dt = "(no-ts)"
        note = str(rec.get("note", ""))
        print(_("[%(idx)s] %(dt)s  %(note)s") % {"idx": idx, "dt": dt, "note": note})
    return True


def _handle_cmd_mem_del(arg: str, *, tr: Any) -> bool:
    if not arg:
        print(_(":mem-del <index>"))
        return True

    try:
        idx = int(arg)
    except Exception:
        print(_("[mem-del error] Failed to parse index as int: %(arg)r") % {"arg": arg})
        return True

    if personal_long_memory.delete_long_memory_entry(idx):
        print(_("Deleted long-term memory entry [%(idx)d].") % {"idx": idx})
    else:
        print(_("[mem-del] Failed to delete index=%(idx)d.") % {"idx": idx})
    return True


def _handle_cmd_shared_mem_list(*, tr: Any) -> bool:
    if not shared_memory.is_enabled():
        print(
            _(
                "Shared long-term memory is not enabled (UAGENT_SHARED_MEMORY_FILE is not set)."
            )
        )
        return True

    records = shared_memory.load_shared_memory_records()
    if not records:
        print(_("No shared long-term memory entries."))
        return True

    import time as _time

    print(_("Shared long-term memory entries:"))
    for idx, rec in enumerate(records):
        ts = rec.get("ts")
        if isinstance(ts, (int, float)):
            dt = _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(ts))
        else:
            dt = "(no-ts)"
        note = str(rec.get("note", ""))
        print(_("[%(idx)s] %(dt)s  %(note)s") % {"idx": idx, "dt": dt, "note": note})

    return True


def _handle_cmd_profile_show(arg: str = "", *, core: Any, tr: Any) -> bool:
    from .profile_manager import load_profile, profile_from_logs
    from .runtime.runtime_memory import _format_profile

    arg = (arg or "").strip().lower()
    if arg.startswith("fromlog"):
        # Parse optional max_log_files from ":profile fromlog 50"
        parts = arg.split()
        max_log_files: int | None = None
        if len(parts) > 1:
            try:
                max_log_files = max(1, int(parts[1]))
            except (ValueError, TypeError):
                pass
        if max_log_files is not None:
            print(
                tr("Analyzing the most recent %d log files to generate user profile...")
                % max_log_files
            )
        else:
            print(tr("Analyzing past logs to generate user profile..."))
        try:
            profile = profile_from_logs(core, max_log_files=max_log_files)
            if not profile:
                print(tr("No past logs found or failed to generate profile."))
                return True
            print(tr("User profile generated successfully from past logs!"))
        except Exception as e:
            print(
                _("[profile fromlog error] %(etype)s: %(err)s")
                % {"etype": type(e).__name__, "err": e}
            )
            return True
    else:
        profile = load_profile()

    if (
        not profile.get("environment")
        and not profile.get("preferences")
        and not profile.get("constraints")
    ):
        print(tr("No user profile data found."))
        return True

    print(tr("User Profile:"))
    print(_format_profile(profile))
    return True


def _handle_cmd_profile_clear(*, tr: Any) -> bool:
    from .profile_manager import get_profile_file_path

    path = get_profile_file_path()
    if os.path.exists(path):
        try:
            os.remove(path)
            print(tr("User profile cleared successfully."))
        except Exception as e:
            print(
                _("[profile-clear error] %(etype)s: %(err)s")
                % {"etype": type(e).__name__, "err": e}
            )
    else:
        print(tr("No user profile file found to clear."))
    return True


def _handle_cmd_shared_mem_del(arg: str, *, tr: Any) -> bool:
    if not arg:
        print(_(":shared-mem-del <index>"))
        return True

    if not shared_memory.is_enabled():
        print(
            _(
                "Shared long-term memory is not enabled (UAGENT_SHARED_MEMORY_FILE is not set)."
            )
        )
        return True

    try:
        idx = int(arg)
    except Exception:
        print(
            _("[shared-mem-del error] Failed to parse index as int: %(arg)r")
            % {"arg": arg}
        )
        return True

    records = shared_memory.load_shared_memory_records()
    if idx < 0 or idx >= len(records):
        print(_("[shared-mem-del] Failed to delete index=%(idx)d.") % {"idx": idx})
        return True

    try:
        records.pop(idx)
        path = shared_memory.get_shared_memory_file()
        if not path:
            print(_("[shared-mem-del] Failed to delete index=%(idx)d.") % {"idx": idx})
            return True

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:
        print(
            _("[shared-mem-del error] %(etype)s: %(err)s")
            % {"etype": type(e).__name__, "err": e}
        )
        return True

    print(_("Deleted shared long-term memory entry [%(idx)d].") % {"idx": idx})
    return True
