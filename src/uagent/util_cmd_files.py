"""File-system related :commands (cd, ls, cp, mv, rm, head, tail, ...).

Moved from util_tools.py.
"""

from __future__ import annotations

import datetime as dt
import glob
import json
import os
import shlex
import shutil
from pathlib import Path
from typing import Any

from . import tools
from .i18n import _
from .util_message import _format_cwd_system_content, _insert_cwd_system_message

# Default translation function used when core.tr is not provided.
tr = _
tr_ = _


def _handle_cmd_cd(
    arg: str,
    messages_ref: list[dict[str, Any]],
    *,
    core: Any,
    tr: Any,
) -> bool:
    a = (arg or "").strip()
    if not a:
        print(_(":cd <path>"))
        return True

    try:
        prev = os.getcwd()
        expanded = os.path.expandvars(os.path.expanduser(a))
        target = os.path.abspath(expanded)

        if not os.path.isdir(target):
            print(
                _("[cd] Directory does not exist: %(src)s -> %(dst)s")
                % {"src": a, "dst": target}
            )
            return True

        os.chdir(target)
        now = os.getcwd()

        # Record cwd change into message history + log.
        try:
            msg = {
                "role": "system",
                "content": _format_cwd_system_content(
                    event="cd",
                    path=now,
                    extra={"prev": prev, "src": a, "resolved": target},
                ),
            }
            _insert_cwd_system_message(messages_ref, msg)
            core.log_message(msg)
        except Exception:
            pass

        print(_("[cd] workdir = %(path)s") % {"path": now})
    except Exception as e:
        print(
            _("[cd error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )

    return True


def _handle_cmd_reload(
    arg: str,
    messages_ref: list[dict[str, Any]],
    *,
    core: Any,
    tr: Any,
) -> bool:
    """Reload project instruction files (CLAUDE.md / AGENTS.md) for current workdir.

    Only loads files that haven't been loaded before in this session.
    Skips the interactive prompt; new files are auto-loaded.
    """
    try:
        from .runtime.runtime_instructions import reload_instruction_files

        instructions = reload_instruction_files(workdir=os.getcwd())
        if not instructions:
            print(tr("[reload] No new instruction files found."))
            return True

        for instr in instructions:
            msg = {"role": "system", "content": instr}
            messages_ref.append(msg)
            core.log_message(msg)

        print(
            tr("[reload] Loaded %(count)d new instruction file(s).")
            % {"count": len(instructions)}
        )
    except Exception as e:
        print(
            tr("[reload error] %(etype)s: %(err)s")
            % {"etype": type(e).__name__, "err": e}
        )

    return True


def _handle_cmd_ls(arg: str, *, tr: Any) -> bool:
    target = (arg or "").strip() or "."

    try:
        expanded = os.path.expandvars(os.path.expanduser(target))
        has_glob = any(ch in expanded for ch in ("*", "?", "["))

        if has_glob:
            matches = glob.glob(expanded, recursive=True)
            if not matches:
                print(
                    tr("[ls] No matching paths: %(src)s -> %(expanded)s")
                    % {"src": target, "expanded": expanded}
                )
                return True

            items = []
            for p in matches:
                try:
                    p_exp = os.path.expandvars(os.path.expanduser(p))
                    p_abs = os.path.abspath(p_exp)
                    is_dir = os.path.isdir(p_abs)
                    size = os.path.getsize(p_abs) if os.path.isfile(p_abs) else 0
                except Exception:
                    p_abs = os.path.abspath(p)
                    is_dir = os.path.isdir(p_abs)
                    size = 0

                base = os.path.basename(p_abs.rstrip(os.sep)) or p_abs
                items.append(
                    (0 if is_dir else 1, base.lower(), base, p_abs, is_dir, size)
                )

            items.sort(key=lambda x: (x[0], x[1]))

            print(tr("[ls] %(path)s") % {"path": expanded})
            for _ord, _key, name, p_abs, is_dir, size in items:
                if is_dir:
                    print(
                        tr("  [D] %(name)s -> %(path)s") % {"name": name, "path": p_abs}
                    )
                else:
                    print(
                        tr("  [F] %(name)s (%(size)d bytes) -> %(path)s")
                        % {"name": name, "size": size, "path": p_abs}
                    )
            return True

        target_abs = os.path.abspath(expanded)
        if os.path.isfile(target_abs):
            try:
                size = os.path.getsize(target_abs)
            except OSError:
                size = 0
            print(
                tr("[ls] [F] %(path)s (%(size)d bytes)")
                % {
                    "path": target_abs,
                    "size": size,
                }
            )
            return True
        if not os.path.isdir(target_abs):
            print(
                tr("[ls] Directory does not exist: %(src)s -> %(dst)s")
                % {"src": target, "dst": target_abs}
            )
            return True

        entries = []
        for name in os.listdir(target_abs):
            p = os.path.join(target_abs, name)
            try:
                st = os.stat(p)
                is_dir = os.path.isdir(p)
                size = st.st_size
            except Exception:
                is_dir = os.path.isdir(p)
                size = 0

            entries.append((0 if is_dir else 1, name.lower(), name, is_dir, size))

        entries.sort(key=lambda x: (x[0], x[1]))

        print(tr("[ls] %(path)s") % {"path": target_abs})
        for _ord, _key, name, is_dir, size in entries:
            if is_dir:
                print(tr("  [D] %(name)s") % {"name": name})
            else:
                print(
                    tr("  [F] %(name)s (%(size)d bytes)") % {"name": name, "size": size}
                )
    except Exception as e:
        print(
            tr("[ls error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )

    return True


def _session_preview(value: Any, limit: int = 100) -> str:
    """Return a compact single-line preview for a stored session message."""
    text = " ".join(str(value or "").split())
    if not text:
        return "-"
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _session_display_time(value: Any) -> str:
    """Format the UTC timestamp stored by SQLite in local time."""
    raw = str(value or "").strip()
    if not raw:
        return "-"
    try:
        timestamp = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=dt.timezone.utc)
        return timestamp.astimezone().strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OverflowError):
        return raw


def _handle_cmd_logs(arg: str, *, core: Any, tr: Any) -> bool:
    # In sqlite-only mode, :logs is backed by the session store. The legacy
    # JSONL path remains available in dual/jsonl mode.
    if (
        os.environ.get("UAGENT_SESSION_BACKEND", "sqlite").strip().lower() == "sqlite"
        and getattr(core, "session_store", None) is not None
    ):
        store = core.session_store
        a = (arg or "").strip()
        if a.lower().startswith("pdf"):
            print("[logs] Use :sessions pdf <session_id> [output.pdf] in sqlite mode.")
            return True
        try:
            limit = 10
            if a and a.lower() not in {"all", "-a", "--all"}:
                limit = max(1, int(a))
            rows = store.list_sessions(
                limit=None if a.lower() in {"all", "-a", "--all"} else limit,
                exclude_session_id=getattr(core, "session_id", None),
            )
            for index, row in enumerate(rows):
                first = _session_preview(row.get("first_message"))
                last = _session_preview(row.get("last_message"))
                summary = _session_preview(row.get("summary"))
                print(f"[{index}] {_session_display_time(row.get('created_at'))}  {row.get('message_count', 0)} messages")
                if summary:
                    print(f"    summary: {summary}")
                else:
                    print(f"    first: {first}")
                    print(f"    last:  {last}")
                print(
                    f"    id: {row['session_id']} | {row.get('project') or '-'} | "
                    f"{row['entry_point']}"
                )
            return True
        except Exception as exc:
            print("[logs] SQLite session listing failed: " + str(exc))
            return True

    show_all = False
    limit = 10
    export_pdf_index = None

    a = (arg or "").strip()
    if a:
        parts = a.split()
        cmd = parts[0].lower()

        if cmd == "pdf":
            if len(parts) >= 2:
                try:
                    export_pdf_index = int(parts[1])
                except ValueError:
                    print(_("[logs] Invalid PDF index: '%(idx)s'") % {"idx": parts[1]})
                    return True
            else:
                print(_("[logs] Usage: :logs pdf <index> [output_path]"))
                return True
        elif cmd in ("--all", "-a", "all"):
            show_all = True
        else:
            try:
                limit = int(cmd)
            except Exception:
                print(
                    tr(
                        "[logs] Invalid argument: %(arg)r (specify all / --all / -a / number / pdf <index>)"
                    )
                    % {"arg": a}
                )
                return True

    if export_pdf_index is not None:
        files = core.find_log_files(exclude_current=True)
        if not files:
            print(_("[logs] No log files found."))
            return True
        if export_pdf_index < 0 or export_pdf_index >= len(files):
            print(
                _("[logs] Index %(idx)s is out of range (0-%(max)s).")
                % {"idx": export_pdf_index, "max": len(files) - 1}
            )
            return True

        log_path = files[export_pdf_index]
        # If output path is provided as third argument, use it; else default to cwd
        if len(parts) >= 3:
            output_path = parts[2]
        else:
            # Strip "scheck_log_" prefix from filename for the default PDF name
            basename = os.path.basename(log_path)
            if basename.startswith("scheck_log_"):
                basename = basename[len("scheck_log_") :]
            output_path = os.path.join(os.getcwd(), basename + ".pdf")

        # Call the pdf_export tool
        from uagent.tools.pdf_export_tool import run_tool as pdf_export_run

        result = pdf_export_run({"log_path": log_path, "output_path": output_path})
        print(result)
        return True

    core.list_logs(limit=limit, show_all=show_all)
    return True


def _handle_cmd_tools(*, tr: Any) -> bool:
    try:
        tool_specs = tools.get_tool_specs() or []
        if not tool_specs:
            print(_("[tools] No tools loaded."))
            return True

        print(_("[tools] Loaded %(n)d tools") % {"n": len(tool_specs)})
        for spec in tool_specs:
            fn = (spec or {}).get("function") or {}
            name = fn.get("name") or "(unknown)"
            desc = (fn.get("description") or "").strip()
            if desc:
                print(_("- %(name)s: %(desc)s") % {"name": name, "desc": desc})
            else:
                print(_("- %(name)s") % {"name": name})
    except Exception as e:
        print(
            _("[tools error] %(etype)s: %(err)s")
            % {"etype": type(e).__name__, "err": e}
        )

    return True


def _strip_outer_quotes(s: str) -> str:
    """Strip matching outer quotes (single/double) from a string."""
    s = s.strip()
    if len(s) >= 2 and s[0] in ('"', "'") and s[0] == s[-1]:
        return s[1:-1]
    return s


def _normalize_cp_mv_args(raw: str) -> tuple[list[str], bool, bool]:
    try:
        items = shlex.split(raw, posix=False)
    except Exception as e:
        raise ValueError(tr("failed to parse arguments: %(err)s") % {"err": e}) from e

    if not items:
        raise ValueError(tr("missing arguments"))

    overwrite = False
    mkdirs = False
    paths: list[str] = []
    for item in items:
        clean = _strip_outer_quotes(item)
        low = clean.lower()
        if low in ("-f", "--overwrite", "--force"):
            overwrite = True
            continue
        if low in ("-p", "--mkdirs", "--parents"):
            mkdirs = True
            continue
        paths.append(clean)

    if len(paths) < 2:
        raise ValueError(tr("src and dst are required"))

    return paths, overwrite, mkdirs


def _resolve_copy_move_target(src: Path, dst_raw: str) -> Path:
    dst_expanded = os.path.expandvars(os.path.expanduser(dst_raw))
    dst = Path(dst_expanded)
    if dst.exists() and dst.is_dir():
        return dst / src.name
    if dst_raw.endswith((os.sep, "/", os.altsep or "")):
        return dst / src.name
    return dst


def _remove_existing_path(target: Path) -> None:
    if target.is_dir() and not target.is_symlink():
        shutil.rmtree(target)
    else:
        target.unlink()


def _handle_cmd_cp(arg: str, *, tr: Any) -> bool:
    raw = (arg or "").strip()
    if not raw:
        print(tr(":cp <src> <dst> [-f|--overwrite] [-p|--mkdirs]"))
        return True

    try:
        items, overwrite, mkdirs = _normalize_cp_mv_args(raw)
    except Exception as e:
        print(
            tr("[cp error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )
        return True

    src_raw, dst_raw = items[0], items[1]
    try:
        src = Path(src_raw).expanduser().resolve()
        target = _resolve_copy_move_target(src, dst_raw)
        if target == src:
            print(
                tr("[cp] Source and destination are the same: %(path)s")
                % {"path": str(src)}
            )
            return True

        if not src.exists():
            print(tr("[cp] Source does not exist: %(path)s") % {"path": str(src)})
            return True

        if src.is_dir():
            if target.exists():
                if not overwrite:
                    print(
                        tr("[cp] Destination already exists: %(path)s")
                        % {"path": str(target)}
                    )
                    return True
                _remove_existing_path(target)
            if mkdirs:
                target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, target)
        else:
            if target.exists():
                if not overwrite:
                    print(
                        tr("[cp] Destination already exists: %(path)s")
                        % {"path": str(target)}
                    )
                    return True
                _remove_existing_path(target)
            if mkdirs:
                target.parent.mkdir(parents=True, exist_ok=True)
            elif not target.parent.exists():
                print(
                    tr("[cp] Destination parent does not exist: %(path)s")
                    % {"path": str(target.parent)}
                )
                return True
            shutil.copy2(src, target)

        print(
            tr("[cp] Copied: %(src)s -> %(dst)s")
            % {"src": str(src), "dst": str(target)}
        )
        return True
    except Exception as e:
        print(
            tr("[cp error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )
        return True


def _handle_cmd_mv(arg: str, *, tr: Any) -> bool:
    raw = (arg or "").strip()
    if not raw:
        print(tr(":mv <src> <dst> [-f|--overwrite] [-p|--mkdirs]"))
        return True

    try:
        items, overwrite, mkdirs = _normalize_cp_mv_args(raw)
    except Exception as e:
        print(
            tr("[mv error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )
        return True

    src_raw, dst_raw = items[0], items[1]
    try:
        src = Path(src_raw).expanduser().resolve()
        target = _resolve_copy_move_target(src, dst_raw)
        if target == src:
            print(
                tr("[mv] Source and destination are the same: %(path)s")
                % {"path": str(src)}
            )
            return True

        if not src.exists():
            print(tr("[mv] Source does not exist: %(path)s") % {"path": str(src)})
            return True

        if target.exists():
            if not overwrite:
                print(
                    tr("[mv] Destination already exists: %(path)s")
                    % {"path": str(target)}
                )
                return True
            _remove_existing_path(target)

        if mkdirs:
            target.parent.mkdir(parents=True, exist_ok=True)
        elif not target.parent.exists():
            print(
                tr("[mv] Destination parent does not exist: %(path)s")
                % {"path": str(target.parent)}
            )
            return True

        os.replace(src, target)
        print(
            tr("[mv] Moved: %(src)s -> %(dst)s") % {"src": str(src), "dst": str(target)}
        )
        return True
    except Exception as e:
        print(
            tr("[mv error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )
        return True


def _handle_cmd_head(arg: str, *, tr: Any) -> bool:
    raw = (arg or "").strip()
    if not raw:
        print(_(":head <path> [n]"))
        return True

    try:
        items = shlex.split(raw, posix=False)
    except Exception as e:
        print(
            _("[head error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )
        return True

    if not items:
        print(_(":head <path> [n]"))
        return True

    lines = 20
    path_tokens: list[str] = []
    i = 0
    while i < len(items):
        tok = items[i]
        low = tok.lower()
        if low in ("-n", "--lines"):
            i += 1
            if i >= len(items):
                print(_(":head <path> [n]"))
                return True
            try:
                lines = int(items[i])
            except Exception:
                print(_("[head] Invalid line count: %(n)r") % {"n": items[i]})
                return True
        elif not tok.startswith("-") and not path_tokens:
            path_tokens.append(tok)
        elif not tok.startswith("-") and path_tokens:
            try:
                lines = int(tok)
            except Exception:
                path_tokens.append(tok)
        else:
            path_tokens.append(tok)
        i += 1

    if not path_tokens:
        print(_(":head <path> [n]"))
        return True

    path = " ".join(path_tokens)
    try:
        from .tools.read_file_tool import run_tool as read_file_tool

        content = read_file_tool({"filename": path, "head_lines": lines})
        if content.startswith("{"):
            try:
                res = json.loads(content)
            except Exception:
                res = None
            if isinstance(res, dict) and not res.get("ok", False):
                print(str(res.get("error") or res.get("stderr") or "[head] Failed."))
                return True
            if isinstance(res, dict):
                content = str(res.get("content") or "")
        if content:
            print(content, end="" if content.endswith("\n") else "\n")
        else:
            print(_("[head] Empty."))
        return True
    except Exception as e:
        print(
            _("[head error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )
        return True


def _handle_cmd_tail(arg: str, *, tr: Any) -> bool:
    raw = (arg or "").strip()
    if not raw:
        print(_(":tail <path> [n]"))
        return True

    try:
        items = shlex.split(raw, posix=False)
    except Exception as e:
        print(
            _("[tail error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )
        return True

    if not items:
        print(_(":tail <path> [n]"))
        return True

    lines = 20
    path_tokens: list[str] = []
    i = 0
    while i < len(items):
        tok = items[i]
        low = tok.lower()
        if low in ("-n", "--lines"):
            i += 1
            if i >= len(items):
                print(_(":tail <path> [n]"))
                return True
            try:
                lines = int(items[i])
            except Exception:
                print(_("[tail] Invalid line count: %(n)r") % {"n": items[i]})
                return True
        elif not tok.startswith("-") and not path_tokens:
            path_tokens.append(tok)
        elif not tok.startswith("-") and path_tokens:
            try:
                lines = int(tok)
            except Exception:
                path_tokens.append(tok)
        else:
            path_tokens.append(tok)
        i += 1

    if not path_tokens:
        print(_(":tail <path> [n]"))
        return True

    path = " ".join(path_tokens)
    try:
        from .tools.read_file_tool import run_tool as read_file_tool

        content = read_file_tool({"filename": path, "tail_lines": lines})
        if content.startswith("{"):
            try:
                res = json.loads(content)
            except Exception:
                res = None
            if isinstance(res, dict) and not res.get("ok", False):
                print(str(res.get("error") or res.get("stderr") or "[tail] Failed."))
                return True
            if isinstance(res, dict):
                content = str(res.get("content") or "")
        if content:
            print(content, end="" if content.endswith("\n") else "\n")
        else:
            print(_("[tail] Empty."))
        return True
    except Exception as e:
        print(
            _("[tail error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )
        return True


def _handle_cmd_rm(arg: str, *, tr: Any) -> bool:
    raw = (arg or "").strip()
    if not raw:
        print(_(":rm <path|glob> [path|glob]"))
        return True

    try:
        items = shlex.split(raw, posix=False)
    except Exception as e:
        print(_("[rm error] Failed to parse arguments: %(err)s") % {"err": e})
        return True

    if not items:
        print(_(":rm <path|glob> [path|glob]"))
        return True

    try:
        from uagent.tools.delete_file_tool import run_tool as delete_file_tool
        from uagent.tools.human_ask_tool import run_tool as human_ask

        preview_json = delete_file_tool(
            {
                "filename": items,
                "missing_ok": True,
                "dry_run": True,
                "allow_dir": True,
            }
        )
        preview = json.loads(preview_json)
        if not isinstance(preview, dict):
            print(_("[rm] Unexpected delete_file preview response."))
            return True

        if not preview.get("ok", False):
            print(_("[rm] Preview failed."))
            stderr = preview.get("stderr")
            if stderr:
                print(str(stderr))
            return True

        missing = [str(p) for p in (preview.get("missing") or []) if str(p).strip()]
        matches = [str(p) for p in (preview.get("matches") or []) if str(p).strip()]

        if not matches:
            print(_("[rm] No matching paths."))
            if missing:
                print(_("[rm] Missing:"))
                for p in missing:
                    print(p)
            return True

        print(_("[rm] Candidates:"))
        for p in matches:
            print(p)
        if missing:
            print(_("[rm] Missing:"))
            for p in missing:
                print(p)

        confirm_msg = _(
            "Delete {count} path(s)?\n\n{paths}\n\nEnter y to proceed, or c to cancel."
        ).format(count=len(matches), paths="\n".join(matches))
        res_json = human_ask({"message": confirm_msg})
        res = json.loads(res_json)
        user_reply = (res.get("user_reply") or "").strip().lower()
        cancelled = bool(res.get("cancelled", False))
        if cancelled or user_reply not in ("y", "yes"):
            print(_("[rm] Cancelled."))
            return True

        delete_json = delete_file_tool(
            {
                "filename": items,
                "missing_ok": True,
                "dry_run": False,
                "allow_dir": True,
                "confirmed": True,
            }
        )
        delete = json.loads(delete_json)
        if not isinstance(delete, dict):
            print(_("[rm] Unexpected delete_file response."))
            return True

        if delete.get("ok", False) and delete.get("deleted"):
            print(
                _("[rm] Deleted %(count)d path(s).")
                % {"count": int(delete.get("count") or 0)}
            )
        else:
            print(_("[rm] Failed."))
            stderr = delete.get("stderr")
            if stderr:
                print(str(stderr))
        return True
    except Exception as e:
        print(
            _("[rm error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )
        return True
