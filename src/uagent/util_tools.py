import argparse
import json
import os
import re
import subprocess
import sys

from .i18n import _ as i18n_
import base64
import glob
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Tuple

from . import tools
from .tools import long_memory as personal_long_memory
from .tools import shared_memory
from .tools.context import ToolCallbacks


def init_tools_callbacks(core: Any) -> None:
    """tools 側へ、ホスト側の依存（core の関数・状態）を注入する。"""

    cb = ToolCallbacks(
        set_status=getattr(core, "set_status", None),
        get_env=getattr(core, "get_env", None),
        get_env_url=getattr(core, "get_env_url", None),
        truncate_output=(
            (
                lambda label, text, limit=200000: core.truncate_output(
                    label, text, limit=limit
                )
            )
            if hasattr(core, "truncate_output")
            else None
        ),
        human_ask_lock=getattr(core, "human_ask_lock", None),
        human_ask_active_ref=(lambda: getattr(core, "human_ask_active", False)),
        human_ask_set_active=(
            (lambda v: setattr(core, "human_ask_active", bool(v)))
            if hasattr(core, "human_ask_active")
            else None
        ),
        human_ask_queue_ref=(lambda: getattr(core, "human_ask_queue", None)),
        human_ask_set_queue=(
            (lambda q: setattr(core, "human_ask_queue", q))
            if hasattr(core, "human_ask_queue")
            else None
        ),
        human_ask_lines_ref=(lambda: getattr(core, "human_ask_lines", [])),
        human_ask_multiline_active_ref=(
            lambda: getattr(core, "human_ask_multiline_active", False)
        ),
        human_ask_set_multiline_active=(
            (lambda v: setattr(core, "human_ask_multiline_active", bool(v)))
            if hasattr(core, "human_ask_multiline_active")
            else None
        ),
        human_ask_set_password=(
            (lambda v: setattr(core, "human_ask_is_password", bool(v)))
            if hasattr(core, "human_ask_is_password")
            else None
        ),
        multi_input_sentinel=getattr(core, "MULTI_INPUT_SENTINEL", '"""end'),
        event_queue=getattr(core, "event_queue", None),
        cmd_encoding=getattr(core, "CMD_ENCODING", "utf-8"),
        cmd_exec_timeout_ms=getattr(core, "CMD_EXEC_TIMEOUT_MS", 60_000),
        python_exec_timeout_ms=getattr(core, "PYTHON_EXEC_TIMEOUT_MS", 60_000),
        url_fetch_timeout_ms=getattr(core, "URL_FETCH_TIMEOUT_MS", 60_000),
        url_fetch_max_bytes=getattr(core, "URL_FETCH_MAX_BYTES", 1_000_000),
        read_file_max_bytes=getattr(core, "READ_FILE_MAX_BYTES", 1_000_000),
        is_gui=False,
    )

    tools.init_callbacks(cb)


_IMAGE_PATH_RE = re.compile(
    r"(?P<path>(?:[A-Za-z]:\\\\|\\\\\\\\|\./|\.\\\\)?[^\s\"']+\.(?:png|jpg|jpeg|gif|webp))",
    re.IGNORECASE,
)


def extract_image_paths(text: str) -> List[str]:
    """テキストから画像ファイルっぽいパスを抽出（ゆるめ）。"""
    if not text:
        return []

    # JSONっぽい出力に備えて先に余計な記号を軽く剥がす
    cleaned = text.replace("\r", "")

    paths: List[str] = []
    for m in _IMAGE_PATH_RE.finditer(cleaned):
        p = m.group("path")
        if not p:
            continue

        # 末尾に句読点などが付くケースの除去（例: "/a.png,")
        p = p.rstrip(',.;:)]}>"')
        p = p.lstrip('"')

        # 重複排除（順序維持）
        if p not in paths:
            paths.append(p)

    return paths


def open_image_with_default_app(path: str) -> bool:
    """Windows の既定アプリでファイルを開く。成功/失敗を返す。"""
    try:
        expanded = os.path.expandvars(os.path.expanduser(path))
        abspath = os.path.abspath(expanded)

        if not os.path.exists(abspath):
            return False

        # Windows: start で既定アプリ起動。
        # shell=True が必要（cmd の内部コマンド）。
        subprocess.Popen(
            f'start "" "{abspath}"',
            shell=True,
        )
        return True
    except Exception:
        return False


def image_file_to_data_url(path: str, *, max_bytes: int = 10_000_000) -> str:
    """Convert a local image file to a data URL (base64).

    Safety:
    - Enforces max_bytes to avoid huge payloads.
    - Requires that the file exists and is a file.

    Returns:
      data:<mime>;base64,<payload>
    """

    p = Path(str(path))
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"image file not found: {path}")

    size = p.stat().st_size
    if size > int(max_bytes):
        raise ValueError(f"image file too large: {size} bytes (limit={max_bytes})")

    mt, _ = mimetypes.guess_type(str(p))
    mime_type = mt or "application/octet-stream"

    data = p.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{b64}"


def try_open_images_from_text(text: str) -> None:
    """アシスタント最終出力に含まれる画像パスがあれば開く（Windows前提）。"""
    if os.name != "nt":
        return

    paths = extract_image_paths(text)
    if not paths:
        return

    opened_any = False
    for p in paths:
        if open_image_with_default_app(p):
            opened_any = True

    if opened_any:
        print("[INFO] " + i18n_("Opened image file with the default app."), file=sys.stderr)


def parse_startup_args() -> Tuple[Dict[str, Any], List[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--workdir",
        "-C",
        dest="workdir",
        help="動作ディレクトリを指定します。指定しない場合は UAGENT_WORKDIR 環境変数、またはカレントディレクトリを使用します。",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="非対話モード。標準入力ループを起動せず、起動時ファイルを処理したら終了します。",
    )
    args, unknown = parser.parse_known_args()
    return vars(args), unknown


def iter_backup_files(root_dir: str) -> List[str]:
    """Find backup files under root_dir.

    Backup pattern:
    - *.org
    - *.org<digits>

    Returns list of file paths.
    """
    root = Path(root_dir)
    results: List[str] = []
    if not root.exists():
        return results

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        name = p.name
        if name.endswith(".org"):
            results.append(str(p))
            continue
        m = re.match(r"^.+\.org\d+$", name)
        if m:
            results.append(str(p))

    return results


def handle_command(
    line: str,
    messages_ref: List[Dict[str, Any]],
    client: Any,
    depname: str,
    *,
    core: Any,
) -> bool:
    """コマンド行(:help, :logs, :load ...)を処理する

    戻り値: False を返すとメインループ終了(:exit / :quit)
    """
    tr = getattr(core, "tr", i18n_)

    line = line.lstrip(":").strip()
    if not line:
        return True

    parts = line.split(maxsplit=1)
    cmd = parts[0]
    arg = parts[1] if len(parts) > 1 else ""

    if cmd in ("help", "h", "?"):
        core.print_help()
        return True

    if cmd in ("cd",):
        a = (arg or "").strip()
        if not a:
            print(tr(":cd <path>"))
            return True

        try:
            expanded = os.path.expandvars(os.path.expanduser(a))
            target = os.path.abspath(expanded)

            if not os.path.isdir(target):
                print(tr("[cd] Directory does not exist: %(src)s -> %(dst)s") % {"src": a, "dst": target})
                return True

            os.chdir(target)
            print(f"[cd] workdir = {os.getcwd()}")
        except Exception as e:
            print(f"[cd error] {type(e).__name__}: {e}")
        return True

    if cmd in ("ls",):
        a = (arg or "").strip()
        target = a or "."

        try:
            expanded = os.path.expandvars(os.path.expanduser(target))

            # Wildcard(glob) support:
            # - If target contains glob meta (* ? [..]) -> list matched paths (files/dirs)
            # - Otherwise, treat as directory and list its entries (previous behavior)
            has_glob = any(ch in expanded for ch in ("*", "?", "["))

            if has_glob:
                matches = glob.glob(expanded)
                if not matches:
                    print(tr("[ls] No matching paths: %(src)s -> %(expanded)s") % {"src": target, "expanded": expanded})
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

                print(f"[ls] {expanded}")
                for _, _, name, p_abs, is_dir, size in items:
                    if is_dir:
                        print(f"  [D] {name} -> {p_abs}")
                    else:
                        print(f"  [F] {name} ({size} bytes) -> {p_abs}")
                return True

            # Directory listing mode (no glob)
            target_abs = os.path.abspath(expanded)

            if not os.path.isdir(target_abs):
                print(tr("[ls] Directory does not exist: %(src)s -> %(dst)s") % {"src": target, "dst": target_abs})
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

            print(f"[ls] {target_abs}")
            for _, _, name, is_dir, size in entries:
                if is_dir:
                    print(f"  [D] {name}")
                else:
                    print(f"  [F] {name} ({size} bytes)")
        except Exception as e:
            print(f"[ls error] {type(e).__name__}: {e}")
        return True

    if cmd in ("logs", "list"):
        show_all = False
        limit = 10

        a = (arg or "").strip()
        if a:
            low = a.lower()
            if low in ("--all", "-a", "all"):
                show_all = True
            else:
                try:
                    limit = int(a)
                except Exception:
                    print(tr("[logs] Invalid argument: %(arg)r (specify all / --all / -a / number)") % {"arg": a})
                    return True

        core.list_logs(limit=limit, show_all=show_all)
        return True

    if cmd == "clean":
        # Dangerous operation: delete conversation log files with <= N non-system messages.
        # Target: core.BASE_LOG_DIR / scheck_log_*.jsonl
        # Count: user/assistant/tool messages only (exclude system), consistent with core.load_conversation_from_log
        # Usage:
        #   :clean            -> threshold=10
        #   :clean 10         -> threshold=10

        threshold = 10
        a = (arg or "").strip()
        if a:
            try:
                threshold = int(a)
            except Exception:
                print(tr("[clean] Invalid argument: %(arg)r (specify number=threshold; default is %(default)d)") % {"arg": a, "default": threshold})
                return True

        try:
            log_files = core.find_log_files(exclude_current=False)
        except Exception as e:
            print(tr("[clean error] Failed to get log list: %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e})
            return True

        targets: List[str] = []
        counts: Dict[str, int] = {}

        for p in log_files:
            try:
                # load_conversation_from_log:
                # - drops system messages from the log
                # - then inserts one system message at head
                # So len(msgs)-1 == non-system message count.
                msgs = core.load_conversation_from_log(p)
                non_system_count = max(0, len(msgs) - 1)
                counts[p] = non_system_count
                if non_system_count <= threshold:
                    targets.append(p)
            except Exception as e:
                print(tr("[clean warn] Skipped (parse failed): %(path)s (%(etype)s: %(err)s)") % {"path": p, "etype": type(e).__name__, "err": e})

        if not targets:
            print(tr("[clean] No logs to delete (threshold=%(threshold)d).\nLog dir: %(dir)s") % {"threshold": threshold, "dir": getattr(core, "BASE_LOG_DIR", "(unknown)")})
            return True

        print(tr("[clean] Logs to delete (<= %(threshold)d msgs): %(n)d") % {"threshold": threshold, "n": len(targets)})
        for p in targets:
            c = counts.get(p, -1)
            print(f" - ({c} msgs) {p}")

        try:
            from uagent.tools.human_ask_tool import run_tool as human_ask

            msg = (
                i18n_(
                    ":clean will delete conversation log files (scheck_log_*.jsonl) from disk.\n"
                    "Log dir: %(dir)s\n"
                    "Rule: total user/assistant/tool messages excluding system <= %(threshold)d\n"
                    "Targets: %(n)d\n\n"
                    "Proceed? Enter y to run, or c to cancel."
                )
                % {
                    "dir": getattr(core, "BASE_LOG_DIR", "(unknown)"),
                    "threshold": threshold,
                    "n": len(targets),
                }
            )
            res_json = human_ask({"message": msg})
            res = json.loads(res_json)
            user_reply = (res.get("user_reply") or "").strip().lower()
            if user_reply not in ("y", "yes"):
                print(tr("[clean] Cancelled."))
                return True
        except Exception as e:
            print(tr("[clean error] Confirmation failed: %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e})
            return True

        deleted = 0
        failed = 0
        for p in targets:
            try:
                os.remove(p)
                deleted += 1
            except Exception as e:
                failed += 1
                print(tr("[clean warn] Delete failed: %(path)s (%(etype)s: %(err)s)") % {"path": p, "etype": type(e).__name__, "err": e})

        print(tr("[clean] Done: deleted=%(deleted)d, failed=%(failed)d") % {"deleted": deleted, "failed": failed})
        return True

    if cmd == "load":
        if not arg:
            print(tr(":load <index|path>"))
            return True

        files = core.find_log_files(exclude_current=True)
        target_path: str

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
            print(f"[load error] {type(e).__name__}: {e}")
            return True

        new_messages = insert_tools_system_message(new_messages, core=core)

        messages_ref.clear()
        messages_ref.extend(new_messages)

        # readline の履歴に過去のユーザー発話を注入し、上キーで辿れるようにする
        try:
            import readline

            for msg in new_messages:
                if msg.get("role") == "user":
                    content = msg.get("content")
                    if isinstance(content, str) and content.strip():
                        # 複数行の場合は1行にまとめて履歴に追加
                        readline.add_history(content.replace("\n", " "))
        except Exception:
            pass

        print(tr("Loaded log: %(path)s") % {"path": target_path})
        print(tr("Conversation message count: %(n)d") % {"n": len(messages_ref)})
        # --- Optional: prepend loaded log contents into CURRENT session log file ---
        # User request: When :load is used, keep a trace in the current log by inserting
        # the loaded conversation at the beginning of the current session log file.
        # NOTE: This rewrites core.LOG_FILE (no backup, per user request). Dangerous.
        try:
            from uagent.tools.human_ask_tool import run_tool as human_ask

            cur_log = getattr(core, "LOG_FILE", None)
            if isinstance(cur_log, str) and cur_log:
                msg2 = (
                    i18n_(
                        ":load will overwrite the current session log file and prepend the loaded log (no backup).\n\n"
                        "Current log: %(cur_log)s\n"
                        "Source log: %(src_log)s\n\n"
                        "Proceed? Enter y to run, or c to cancel."
                    )
                    % {"cur_log": cur_log, "src_log": target_path}
                )
                res_json2 = human_ask({"message": msg2})
                res2 = json.loads(res_json2)
                user_reply2 = (res2.get("user_reply") or "").strip().lower()
                if user_reply2 in ("y", "yes"):
                    # Read loaded raw log lines
                    loaded_lines: list[str] = []
                    try:
                        with open(target_path, encoding="utf-8") as f:
                            loaded_lines = f.read().splitlines(True)  # keepends
                    except Exception as e:
                        print(tr("[load warn] Failed to read source log: %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}, file=sys.stderr)
                        loaded_lines = []

                    # Read current log lines (may not exist yet)
                    cur_lines: list[str] = []
                    try:
                        if os.path.exists(cur_log):
                            with open(cur_log, encoding="utf-8") as f:
                                cur_lines = f.read().splitlines(True)
                    except Exception as e:
                        print(tr("[load warn] Failed to read current log: %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}, file=sys.stderr)
                        cur_lines = []

                    # Build marker line (JSONL entry)
                    marker = {
                        "role": "system",
                        "content": f"[LOG] :load prepend source={os.path.abspath(target_path)}",
                    }
                    marker_line = json.dumps(marker, ensure_ascii=False) + "\n"

                    # Write new file: marker + loaded + old
                    try:
                        os.makedirs(os.path.dirname(cur_log) or ".", exist_ok=True)
                        with open(cur_log, "w", encoding="utf-8") as f:
                            f.write(marker_line)
                            for ln in loaded_lines:
                                f.write(ln)
                            for ln in cur_lines:
                                f.write(ln)
                        print(tr("[load] Prepended to current log: %(path)s") % {"path": cur_log})
                    except Exception as e:
                        print(tr("[load warn] Failed to rewrite current log: %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}, file=sys.stderr)
                else:
                    print(tr("[load] Prepend to current log was cancelled."))
        except Exception as e:
            print(tr("[load warn] Error during prepend to current log: %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}, file=sys.stderr)

        return True

    if cmd == "shrink":
        keep_last = 40
        if arg:
            try:
                keep_last = int(arg)
            except Exception:
                print(
                    i18n_("[shrink error] Failed to parse as int: %(arg)r -> keep last %(keep)d") % {"arg": arg, "keep": keep_last}
                )
        new_messages = core.shrink_messages(messages_ref, keep_last=keep_last)
        messages_ref.clear()
        messages_ref.extend(new_messages)
        return True

    if cmd == "shrink_llm":
        keep_last = 20
        if arg:
            try:
                keep_last = int(arg)
            except Exception:
                print(
                    i18n_("[shrink_llm error] Failed to parse as int: %(arg)r -> keep last %(keep)d") % {"arg": arg, "keep": keep_last}
                )
        new_messages = core.compress_history_with_llm(
            client=client,
            depname=depname,
            messages=messages_ref,
            keep_last=keep_last,
        )
        messages_ref.clear()
        messages_ref.extend(new_messages)
        return True

    if cmd == "mem-list":
        records = personal_long_memory.load_long_memory_records()
        if not records:
            print(tr("No long-term memory entries."))
            return True

        print(tr("Long-term memory entries:"))
        for idx, rec in enumerate(records):
            ts = rec.get("ts")
            if isinstance(ts, (int, float)):
                import time as _time

                dt = _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(ts))
            else:
                dt = "(no-ts)"
            note = str(rec.get("note", ""))
            print(f"[{idx}] {dt}  {note}")
        return True

    if cmd == "mem-del":
        if not arg:
            print(tr(":mem-del <index>"))
            return True
        try:
            idx = int(arg)
        except Exception:
            print(tr("[mem-del error] Failed to parse index as int: %(arg)r") % {"arg": arg})
            return True
        if personal_long_memory.delete_long_memory_entry(idx):
            print(tr("Deleted long-term memory entry [%(idx)d].") % {"idx": idx})
        else:
            print(tr("[mem-del] Failed to delete index=%(idx)d.") % {"idx": idx})
        return True

    if cmd == "shared-mem-list":
        if not shared_memory.is_enabled():
            print(
                i18n_("Shared long-term memory is not enabled (UAGENT_SHARED_MEMORY_FILE is not set).")
            )
            return True

        records = shared_memory.load_shared_memory_records()
        if not records:
            print(tr("No shared long-term memory entries."))
            return True

        import time as _time

        print(tr("Shared long-term memory entries:"))
        for idx, rec in enumerate(records):
            ts = rec.get("ts")
            if isinstance(ts, (int, float)):
                dt = _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(ts))
            else:
                dt = "(no-ts)"
            note = str(rec.get("note", ""))
            print(f"[{idx}] {dt}  {note}")
        return True

    if cmd == "shared-mem-del":
        if not arg:
            print(tr(":shared-mem-del <index>"))
            return True

        if not shared_memory.is_enabled():
            print(
                i18n_("Shared long-term memory is not enabled (UAGENT_SHARED_MEMORY_FILE is not set).")
            )
            return True

        try:
            idx = int(arg)
        except Exception:
            print(tr("[shared-mem-del error] Failed to parse index as int: %(arg)r") % {"arg": arg})
            return True

        records = shared_memory.load_shared_memory_records()
        if idx < 0 or idx >= len(records):
            print(tr("[shared-mem-del] Failed to delete index=%(idx)d.") % {"idx": idx})
            return True

        try:
            records.pop(idx)
            path = shared_memory.get_shared_memory_file()
            if not path:
                print(tr("[shared-mem-del] Failed to delete index=%(idx)d.") % {"idx": idx})
                return True
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                for rec in records:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception as e:
            print(tr("[shared-mem-del error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e})
            return True

        print(tr("Deleted shared long-term memory entry [%(idx)d].") % {"idx": idx})
        return True

    if cmd in ("exit", "quit"):
        print(tr("Exiting."))
        return False

    print(tr("Unknown command: :%(cmd)s") % {"cmd": cmd})
    return True


def load_agents_md() -> str:
    """起動ディレクトリに AGENTS.md があれば内容を返す。"""
    agents_path = os.path.join(os.getcwd(), "AGENTS.md")
    if not os.path.isfile(agents_path):
        return ""
    try:
        from tools.read_file_tool import run_tool as read_file

        content = read_file({"filename": agents_path})
        obj = json.loads(content)
        if obj.get("ok"):
            return str(obj.get("content", ""))
        return ""
    except Exception:
        return ""


def build_initial_messages(*, core: Any) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []

    system_msg = {"role": "system", "content": core.SYSTEM_PROMPT}
    messages.append(system_msg)
    core.log_message(system_msg)

    tool_specs = tools.get_tool_specs()
    tools_prompt = core.build_tools_system_prompt(tool_specs)
    tools_system_msg = {"role": "system", "content": tools_prompt}

    messages.append(tools_system_msg)
    core.log_message(tools_system_msg)

    return messages


def insert_tools_system_message(
    messages: List[Dict[str, Any]],
    *,
    core: Any,
) -> List[Dict[str, Any]]:
    tool_specs = tools.get_tool_specs()
    tools_prompt = core.build_tools_system_prompt(tool_specs)
    tools_system_msg = {"role": "system", "content": tools_prompt}

    if messages and messages[0].get("role") == "system":
        new_messages = [messages[0], tools_system_msg] + messages[1:]
    else:
        new_messages = [tools_system_msg] + messages

    core.log_message(tools_system_msg)
    return new_messages


def build_long_memory_system_message(long_mem_raw: Any) -> Dict[str, Any]:
    if not long_mem_raw:
        return {}

    max_chars = 4000

    header = (
        "ここに記載された箇条書きは、このユーザに関する長期記憶（永続メモ）の抜粋です。"
        "これらをユーザの背景情報として参考にしてください。"
        "ただし、会話の中で新たに与えられた情報の方を常に優先し、古い情報と矛盾する場合は最新の情報を採用してください。\n\n"
    )

    body_lines: List[str] = []

    try:
        if isinstance(long_mem_raw, list):
            for rec in long_mem_raw:
                if isinstance(rec, dict):
                    text = (
                        rec.get("summary")
                        or rec.get("text")
                        or rec.get("content")
                        or rec.get("memory")
                        or json.dumps(rec, ensure_ascii=False)
                    )
                else:
                    text = str(rec)

                text = str(text).replace("\r\n", " ").replace("\n", " ").strip()
                if not text:
                    continue

                body_lines.append(f"- {text}")
                candidate = header + "\n".join(body_lines)
                if len(candidate) > max_chars:
                    body_lines.append(
                        "...（長期記憶が長いため途中までを含めています）..."
                    )
                    break
        else:
            text = str(long_mem_raw).strip()
            if text:
                body_lines.append(text)
    except Exception:
        fallback = header + json.dumps(long_mem_raw, ensure_ascii=False)
        content = fallback[:max_chars]
    else:
        content = header + "\n".join(body_lines)
        if len(content) > max_chars:
            content = (
                content[:max_chars]
                + "\n...（長期記憶が長いため途中までを含めています）..."
            )

    return {"role": "system", "content": content}


def append_result_to_outfile(text: str) -> None:
    """UAGENT_OUTFILE が指定されていれば、アシスタント最終出力を追記する。"""
    out_path = os.environ.get("UAGENT_OUTFILE")
    if not out_path:
        return

    try:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(text)
            if not text.endswith("\n"):
                f.write("\n")
    except Exception:
        return
