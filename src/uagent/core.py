from __future__ import annotations

# core.py
import os
import sys

from .env_utils import env_get, strip_outer_quotes
from .i18n import _
import json
import time
import glob
import queue
import threading
from typing import Any, Optional

# ==============================
# Configuration
# ==============================

from uagent.utils.paths import get_log_dir

PYTHON_EXEC_TIMEOUT_MS = 2000_000
CMD_EXEC_TIMEOUT_MS = 2000_000
MAX_TOOL_OUTPUT_CHARS = 400_000
READ_FILE_MAX_BYTES = 20_000_000
URL_FETCH_TIMEOUT_MS = 50_000_000
URL_FETCH_MAX_BYTES = 50_000_000

# On Windows default is often cp932; otherwise use UTF-8.
CMD_ENCODING = env_get("UAGENT_CMD_ENCODING") or "utf-8"

# Enable escape sequences on Windows console if possible.
if os.name == "nt":
    try:
        os.system("")
    except Exception:
        pass

# --- Encoding workaround ---
#
# Windows has multiple console modes:
# - Classic cmd.exe/conhost: output code page is often cp932.
# - ConPTY terminals (Windows Terminal / VSCode etc.): typically expect UTF-8.
#
# Policy:
# - Allow explicit UTF-8 forcing via UAGENT_STDIO_UTF8=1 or PYTHONIOENCODING=utf-8*.
# - Otherwise:
#   - If we look like we're running under a UTF-8 terminal (WT/VSCode), keep
#     Python defaults (usually UTF-8 when PYTHONUTF8=1).
#   - Else (classic cmd), match GetConsoleOutputCP() so we don't output UTF-8
#     bytes to a cp932 console.
#
_FORCE_STDIO_UTF8 = bool(
    env_get("UAGENT_STDIO_UTF8", "1") == "1"
    or (str(env_get("PYTHONIOENCODING") or "").lower().startswith("utf-8"))
)


def _get_windows_console_output_encoding() -> str | None:
    if os.name != "nt":
        return None

    try:
        import ctypes

        cp = int(ctypes.windll.kernel32.GetConsoleOutputCP())
        if cp == 65001:
            return "utf-8"
        if cp > 0:
            return f"cp{cp}"
    except Exception:
        pass

    return None


def _looks_like_utf8_terminal() -> bool:
    # Heuristic: ConPTY-based terminals usually set one of these env vars.
    if env_get("WT_SESSION"):
        return True
    if env_get("VSCODE_PID"):
        return True
    term_program = str(env_get("TERM_PROGRAM") or "").lower()
    if term_program in {"vscode", "windows_terminal"}:
        return True
    return False


def _reconfigure_stdio() -> None:
    if os.name != "nt":
        return

    stdout_tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
    stderr_tty = bool(getattr(sys.stderr, "isatty", lambda: False)())
    if not (stdout_tty or stderr_tty):
        return

    if not _FORCE_STDIO_UTF8 and _looks_like_utf8_terminal():
        # Keep Python defaults for ConPTY terminals.
        return

    enc = (
        "utf-8"
        if _FORCE_STDIO_UTF8
        else (_get_windows_console_output_encoding() or "cp932")
    )

    try:
        if stdout_tty and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding=enc, errors="replace")
        if stderr_tty and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding=enc, errors="replace")
    except Exception:
        pass


_reconfigure_stdio()
# Session ID and log/memory file paths
SESSION_ID = time.strftime("%Y%m%d_%H%M%S")

BASE_LOG_DIR = os.path.abspath(env_get("UAGENT_LOG_DIR") or str(get_log_dir()))
LOG_FILE = env_get("UAGENT_LOG_FILE") or os.path.join(
    BASE_LOG_DIR, f"scheck_log_{SESSION_ID}.jsonl"
)

# Whether to guess log topics (disabled if set to 0)
ENABLE_LOG_TOPIC_GUESS = env_get("UAGENT_LOG_TOPICS", "1") != "0"

# Event queue (normal input and timer input share this queue)
event_queue: "queue.Queue[dict[str, Any]]" = queue.Queue()

# GUI mode flag (set by env var or gui.py)
IS_GUI = env_get("UAGENT_GUI_MODE") == "1"

# State for human_ask (shared between stdin_loop and the human_ask tool)
human_ask_lock = threading.RLock()
human_ask_active = False
human_ask_queue = None  # type: ignore[assignment]
human_ask_lines: list[str] = []
human_ask_is_password = False
human_ask_multiline_active = False

# Sentinel token for multiline input (both normal input and human_ask multiline mode)
MULTI_INPUT_SENTINEL = '"""end'

# Prompt/status
status_lock = threading.RLock()
# Shared lock to reduce output races (stdin prompt vs status/log output).
print_lock = threading.RLock()
status_busy = False  # True while LLM/tools are processing
status_label = ""  # e.g. "LLM" or "tool:cmd_exec"

# Remember the last selected reasoning effort so CUI prompt can show it even when
# status lines are not printed (e.g., when stderr is not a TTY).
# Example stored values: "LLM:auto->low", "LLM:medium"
last_reasoning_label = ""


def print_status_line() -> None:
    """
    現在の busy / label 状態を 1 行で描画する。

    方針:
    - デフォルトは ANSI 色を有効（可能な環境では色付きで表示）
    - 色を無効化したい場合は NO_COLOR または UAGENT_NO_COLOR を設定する
    - GUI モード、または stderr が TTY でない場合は色なし
    - Windows で TERM 未設定でも色を出す（TERM に依存しない）
    - Windows の一部コンソールでプロンプトが崩れることがあるため、\r\x1b[2K は使わない
    """
    global status_busy, status_label

    # human_ask がアクティブな間は、プロンプト表示を乱さないようステータス表示を抑制する
    with human_ask_lock:
        if human_ask_active:
            return

    with status_lock:
        busy = status_busy
        label = status_label

    state = "BUSY" if busy else "IDLE"
    label_part = f" [{label}]" if label else ""

    # Color/ANSI control
    # Default: enable ANSI colors unless explicitly disabled.
    no_color = bool(env_get("NO_COLOR") or env_get("UAGENT_NO_COLOR"))
    stderr_is_tty = bool(getattr(sys.stderr, "isatty", lambda: False)())

    if IS_GUI or no_color or (not stderr_is_tty):
        # Fallback: no ANSI
        with print_lock:
            sys.stderr.write(f"[STATE] {state}{label_part}\n")
            sys.stderr.flush()
        return

    # 色分け（BUSY=黄色, IDLE=緑）
    color = "\x1b[33m" if busy else "\x1b[32m"

    # NOTE: Keep output simple: one colored line.
    with print_lock:
        sys.stderr.write(f"{color}[STATE] {state}{label_part}\x1b[0m\n")
        sys.stderr.flush()


def set_status(busy: bool, label: str = "") -> None:
    """
    Busy/Idle 状態を更新し、変化があったときには状態行を描画する。
    """
    global status_busy, status_label, last_reasoning_label

    # Clear on user/command input so toggling reasoning off does not leave stale
    # labels in the next prompt.
    if busy and label in (
        "command_pending",
        "user_pending",
        "user_pending_multi",
        "replying",
        "replying_cancel",
        "replying_multi",
    ):
        last_reasoning_label = ""

    # If a new LLM cycle starts, clear last reasoning label.
    # It will be re-set only when we actually see an effort-bearing label.
    if busy and label in ("LLM", "LLM:auto", "LLM:auto->"):
        last_reasoning_label = ""
    # Record selected effort labels when present.
    # Only keep auto-selected effort in the prompt (LLM:auto->...).
    if busy and isinstance(label, str):
        if label.startswith("LLM:auto->"):
            last_reasoning_label = label
        elif label.startswith("LLM:"):
            # Explicit (non-auto) reasoning effort should not appear in the prompt.
            last_reasoning_label = ""

    with status_lock:
        prev_busy = status_busy
        prev_label = status_label
        status_busy = busy
        status_label = label

    if busy != prev_busy or label != prev_label:
        print_status_line()


def get_prompt() -> str:
    """
    現在のステータスに応じて、標準入力用のプロンプト文字列を返す。
    - アイドル時:  [IDLE] >
    - BUSY時:     [BUSY:LLM] > のような表示
    """
    with status_lock:
        busy = status_busy
        label = status_label

    with human_ask_lock:
        ask_active = human_ask_active

    if ask_active:
        return "[REPLY] > "

    if busy:
        if label:
            return f"[BUSY:{label}] > "
        else:
            return "[BUSY] > "
    else:
        # アイドル時は現在の workdir をプロンプトに表示する
        # 例: /path/to/project>
        try:
            cwd = os.getcwd()
        except Exception:
            cwd = "?"
        base = os.path.basename(cwd.rstrip(os.sep)) or cwd
        with status_lock:
            _lr = last_reasoning_label
        if _lr:
            return f"{base}[{_lr}]> "
        return f"{base}> "


def get_env(name: str) -> str:
    value = env_get(name)
    if not value:
        print(
            _("Environment variable %(name)s is not set.") % {"name": name},
            file=sys.stderr,
        )
        sys.exit(1)
    return value


def normalize_url(url: str) -> str:
    if not url:
        return ""
    # Also accept quoted env values: "https://..." or 'https://...'
    url2 = strip_outer_quotes(str(url))
    return url2.strip().rstrip("/")


def get_env_url(name: str, default: Optional[str] = None) -> str:
    val = env_get(name, default)
    if not val:
        if default is not None:
            return normalize_url(default)
        print(
            _("Environment variable %(name)s is not set.") % {"name": name},
            file=sys.stderr,
        )
        sys.exit(1)
    return normalize_url(val)


def truncate_output(label: str, text: str, limit: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return text[:limit] + f"\n[{label} truncated: {omitted} chars omitted]"


def _mask_message(obj: Any) -> Any:
    """ログ出力用に機密情報を再帰的にマスクする。"""
    if isinstance(obj, dict):
        new_dict = {}
        for k, v in obj.items():
            # human_ask の返り値（JSON文字列）をデコードしてチェック
            if (
                k == "content"
                and isinstance(v, str)
                and v.startswith("{")
                and v.endswith("}")
            ):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, dict) and parsed.get("tool") == "human_ask":
                        if parsed.get("display_reply") == "[SECRET]":
                            parsed["user_reply"] = "********"
                        v = json.dumps(parsed, ensure_ascii=False)
                except Exception:
                    pass
            new_dict[k] = _mask_message(v)
        return new_dict
    elif isinstance(obj, list):
        return [_mask_message(x) for x in obj]
    else:
        return obj


def log_message(message: dict[str, Any]) -> None:
    """
    ChatCompletion に渡している形式の message(dict) を JSONL で追記保存。
    保存前に機密情報（human_ask のパスワード等）をマスクする。
    """
    try:
        # 破壊的な変更を避けるため、マスクしたコピーを作成して書き込む
        masked_msg = _mask_message(message)

        dirpath = os.path.dirname(LOG_FILE)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(masked_msg, ensure_ascii=False) + "\n")
    except Exception:
        # ログで失敗しても黙って無視
        pass


def rewrite_current_log_from_messages(messages: list[dict[str, Any]]) -> str:
    """Rewrite current session log file (core.LOG_FILE) from in-memory messages.

    - Create one-generation backup into <log_dir>/.backup/<basename>.org
    - Write into a temp file and atomically replace
    - Mask secrets (human_ask password input etc.)

    Returns: path to rewritten log file.
    """

    log_path = LOG_FILE
    log_dir = os.path.dirname(log_path) or "."

    # Ensure backup dir
    backup_dir = os.path.join(log_dir, ".backup")
    os.makedirs(backup_dir, exist_ok=True)

    backup_path = os.path.join(backup_dir, os.path.basename(log_path) + ".org")

    # Backup existing log if present
    try:
        if os.path.exists(log_path):
            # Copy bytes to preserve exact original (including any non-utf8 artifacts)
            with open(log_path, "rb") as rf, open(backup_path, "wb") as wf:
                wf.write(rf.read())
    except Exception:
        # Backup failure should not abort rewrite; still attempt to rewrite
        pass

    tmp_path = log_path + ".tmp"

    # Write new JSONL
    with open(tmp_path, "w", encoding="utf-8") as f:
        for m in messages:
            try:
                masked = _mask_message(m)
                f.write(json.dumps(masked, ensure_ascii=False) + "\n")
            except Exception:
                # Skip broken messages
                continue

    os.replace(tmp_path, log_path)
    return log_path


# ==============================
# ログファイル検出／トピック推定／トピック推定
# ==============================


def find_log_files(exclude_current: bool = False) -> list[str]:
    pattern = os.path.join(BASE_LOG_DIR, "scheck_log_*.jsonl")
    files = glob.glob(pattern)
    if exclude_current:
        current_abs = os.path.abspath(LOG_FILE)
        files = [f for f in files if os.path.abspath(f) != current_abs]
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return files


def guess_topics_from_content(content: str) -> set[str]:
    """
    ログ内容から大ざっぱにトピック候補を推定する。
    """
    topics: set[str] = set()
    lower = content.lower()

    # カテゴリ定義
    mapping = {
        "System Development/Design": [
            "design",
            "architecture",
            "requirements",
            "specification",
            "sequence",
            "class diagram",
            "database",
            "db",
            "sql",
            "git",
            "github",
            "docker",
            "k8s",
        ],
        "Programming/Python": [
            "python",
            "pip",
            "pandas",
            "numpy",
            "django",
            "flask",
            "fastapi",
        ],
        "Programming/C#/.NET": [
            "c#",
            "csharp",
            ".net",
            "dotnet",
            "visual studio",
            "wpf",
            "winforms",
        ],
        "Programming/JS/TS": [
            "javascript",
            "typescript",
            "node.js",
            "nodejs",
            "react",
            "vue",
            "next.js",
            "html",
            "css",
        ],
        "Programming/Rust": ["rust", "cargo"],
        "Programming/C/C++": [" c ", "c++", "cpp", "cmake", "gcc", "clang"],
        "Web/Network": [
            "http",
            "api",
            "url",
            "fetch",
            "curl",
            "dns",
            "ip",
            "ssl",
            "certificate",
            "browser",
            "domain",
        ],
        "Infrastructure/OS Settings": [
            "linux",
            "ubuntu",
            "windows",
            "powershell",
            "shell",
            "bash",
            "environment variable",
            "path",
            "service",
            "registry",
        ],
        "Media Processing": [
            "ffmpeg",
            "image",
            "video",
            "audio",
            "video",
            "audio",
            "mp4",
            "wav",
            "mp3",
            "png",
            "jpg",
        ],
        "AI/LLM": [
            "llm",
            "openai",
            "azure",
            "chatgpt",
            "gemini",
            "claude",
            "prompt",
            "reasoning",
            "generative AI",
        ],
        "SNS/Automation": [
            "sns",
            "twitter",
            " x ",
            "discord",
            "slack",
            "bluesky",
            "mastodon",
            "automation",
            "scraping",
        ],
        "Documents/Research": [
            "readme",
            "markdown",
            "materials",
            "research",
            "search",
            "research",
        ],
        "Debugging/Analysis": [
            "traceback",
            "exception",
            "error",
            "exception",
            "error",
            "analysis",
            "logs",
        ],
        "Data Analysis/Excel": [
            "excel",
            "xlsx",
            "csv",
            "analysis",
            "aggregation",
            "statistics",
            "chart",
        ],
        "Security": [
            "security",
            "vulnerability",
            "encryption",
            "authentication",
            "password",
            "token",
            "key",
            "attack",
        ],
    }

    for topic, keywords in mapping.items():
        if any(kw in lower for kw in keywords):
            topics.add(topic)

    return topics


def list_logs(*, limit: int = 10, show_all: bool = False) -> list[str]:
    """ログ一覧を表示する。

    目的:
    - :load で使うための index は維持する。
    - 一覧を見ただけで各ログを区別できるようにする。

    表示内容:
    - index
    - 最終更新日時 (mtime)
    - やりとり件数
    - 先頭の user 発話（短縮）
    - 話題（推定）は上位数件のみ短縮
    """

    files = find_log_files(exclude_current=True)
    if not files:
        print(_("No log files found."))
        return []

    if show_all or limit <= 0:
        view = files
    else:
        view = files[:limit]

    def _shorten(s: str, n: int) -> str:
        s = " ".join((s or "").strip().splitlines())
        return s if len(s) <= n else s[: max(0, n - 1)] + "…"

    def _fmt_ts(ts: float) -> str:
        try:
            import datetime

            return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        except Exception:
            return _("(unknown time)")

    print(
        _("logs: showing %(shown)d/%(total)d (dir=%(dir)s)")
        % {"shown": len(view), "total": len(files), "dir": BASE_LOG_DIR}
    )
    print(_("Log files:"))

    for idx, path in enumerate(view):
        try:
            mtime = os.path.getmtime(path)
            mtime_text = _fmt_ts(mtime)
        except Exception:
            mtime_text = _("(mtime unknown)")
        # 先頭側は最初の user を取るために最大 200 行読む
        head_lines: list[str] = []
        try:
            with open(path, encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= 200:
                        break
                    line = line.strip()
                    if line:
                        head_lines.append(line)
        except Exception:
            head_lines = []

        # 末尾側は「本当の last user」を取るために、末尾から最大 N バイトだけ読む
        # （巨大ログでも遅くしないための上限。ユーザー指定: 16MB）
        tail_max_bytes = 16 * 1024 * 1024
        tail_text = ""
        try:
            size = os.path.getsize(path)
            start = max(0, size - tail_max_bytes)
            with open(path, "rb") as bf:
                bf.seek(start)
                data = bf.read()

            # 行途中から始まる可能性があるので、先頭の不完全な1行は捨てる
            try:
                tail_text = data.decode("utf-8", errors="replace")
            except Exception:
                tail_text = ""

            if start > 0:
                nl = tail_text.find("\\n")
                if nl >= 0:
                    tail_text = tail_text[nl + 1 :]
        except Exception:
            tail_text = ""

        tail_lines: list[str] = []
        if tail_text:
            for ln in tail_text.splitlines():
                ln = (ln or "").strip()
                if ln:
                    tail_lines.append(ln)
        # 正確な件数（user/assistant）は全行を走査してカウントする
        # + フォールバック用に「ログ全体での first/last user content」も拾う
        total_user_count = 0
        total_assistant_count = 0
        first_user_any = ""
        last_user_any = ""
        try:
            with open(path, encoding="utf-8") as f_all:
                for ln in f_all:
                    ln = (ln or "").strip()
                    if not ln:
                        continue
                    try:
                        obj = json.loads(ln)
                    except Exception:
                        continue
                    role = obj.get("role")
                    if role == "user":
                        total_user_count += 1
                        content = str(obj.get("content") or "").strip()
                        if content:
                            if not first_user_any:
                                first_user_any = content
                            last_user_any = content
                    elif role == "assistant":
                        total_assistant_count += 1
        except Exception:
            # 読めない場合は 0 扱い（表示が落ちるよりマシ）
            total_user_count = 0
            total_assistant_count = 0
            first_user_any = ""
            last_user_any = ""

        # first user は先頭側（軽量）から取得
        first_user: str = ""
        for line in head_lines:
            try:
                obj = json.loads(line)
            except Exception:
                continue

            if obj.get("role") != "user":
                continue

            content = str(obj.get("content") or "").strip()
            if content:
                first_user = content
                break

        # last user は末尾側から取得（本当の最後）
        last_user: str = ""
        for line in reversed(tail_lines):
            try:
                obj = json.loads(line)
            except Exception:
                continue

            if obj.get("role") != "user":
                continue

            content = str(obj.get("content") or "").strip()
            if content:
                last_user = content
                break

        # フォールバック: 先頭/末尾が取れない（no user message）場合は、全行走査で拾った値を使う
        if not first_user and first_user_any:
            first_user = first_user_any
        if not last_user and last_user_any:
            last_user = last_user_any

        turns = total_user_count + total_assistant_count

        first_user_text = (
            _shorten(first_user, 60) if first_user else _("(no user message)")
        )
        last_user_text = (
            _shorten(last_user, 80) if last_user else _("(no user message)")
        )

        print(
            _(
                "[%(idx)d] %(mtime_text)s | %(turns)d msgs | first: %(first_user)s | last: %(last_user)s"
            )
            % {
                "idx": idx,
                "mtime_text": mtime_text,
                "turns": turns,
                "first_user": first_user_text,
                "last_user": last_user_text,
            }
        )

    return files


# ==============================
# ログから会話を復元
# ==============================


def normalize_message_from_log(obj: dict[str, Any]) -> Optional[dict[str, Any]]:
    """
    過去ログ1行分の dict から、現在の ChatCompletion API に渡せる
    最小限の message dict に正規化する。
    - 不要なキーは削除
    - 壊れた形式は None を返してスキップ
    """
    role = obj.get("role")
    if role not in ("system", "user", "assistant", "tool"):
        return None

    msg: dict[str, Any] = {"role": role}

    if role == "tool":
        msg["content"] = str(obj.get("content") or "")
        if "tool_call_id" in obj:
            msg["tool_call_id"] = obj["tool_call_id"]
        if "name" in obj:
            msg["name"] = obj["name"]
        for key in ("attachments", "saved_path", "saved_files"):
            if key in obj:
                msg[key] = obj.get(key)
        return msg

    # system / user / assistant 共通
    msg["content"] = obj.get("content") or ""

    # OpenRouter (and compatible stacks) may include assistant.reasoning_details.
    # Preserve it so a loaded conversation can continue the chain.
    if role == "assistant" and "reasoning_details" in obj:
        try:
            msg["reasoning_details"] = obj.get("reasoning_details")
        except Exception:
            pass

    # 画像添付など、将来の構造化フィールドも残す
    for key in ("attachments", "saved_path", "saved_files"):
        if key in obj:
            msg[key] = obj.get(key)

    # 過去ログに tool_calls が入っていた場合は、現在の形式に揃えて残す
    tcs = obj.get("tool_calls")
    if isinstance(tcs, list):
        new_tcs: list[dict[str, Any]] = []
        for tc in tcs:
            if not isinstance(tc, dict):
                continue

            fn = tc.get("function") or {}
            if not isinstance(fn, dict):
                fn = {}

            name = fn.get("name") or tc.get("name")
            arguments = fn.get("arguments") or "{}"

            if not name or not isinstance(arguments, str):
                continue

            new_tcs.append(
                {
                    "id": tc.get("id") or "",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": arguments,
                    },
                }
            )

        if new_tcs:
            msg["tool_calls"] = new_tcs

    return msg


def sanitize_messages_for_tools(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    messages の中から「対応する assistant.tool_calls を持たない孤立した tool メッセージ」を削除する。
    """
    cleaned: list[dict[str, Any]] = []
    seen_tool_call_ids: set[str] = set()

    for m in messages:
        role = m.get("role")

        if role == "assistant" and "tool_calls" in m:
            # この assistant の tool_calls の id を記録しておく
            tcs = m.get("tool_calls") or []
            for tc in tcs:
                if not isinstance(tc, dict):
                    continue
                tcid = tc.get("id")
                if isinstance(tcid, str) and tcid:
                    seen_tool_call_ids.add(tcid)
            cleaned.append(m)

        elif role == "tool":
            tcid = m.get("tool_call_id")
            if isinstance(tcid, str) and tcid in seen_tool_call_ids:
                cleaned.append(m)
            else:
                # 親のない tool → API ではエラーになるので捨てる
                # NOTE: Do not emit blank lines (they look like extra newlines after tool output).
                # If you want diagnostics, enable: UAGENT_DEBUG_ORPHAN_TOOL=1
                if (env_get("UAGENT_DEBUG_ORPHAN_TOOL", "0") or "").strip().lower() in (
                    "1",
                    "true",
                    "yes",
                    "on",
                ):
                    try:
                        print(
                            _(
                                "[WARN] Dropping orphan tool message: tool_call_id=%(tool_call_id)r name=%(name)r"
                            )
                            % {"tool_call_id": tcid, "name": m.get("name")},
                            file=sys.stderr,
                        )
                    except Exception:
                        pass

        else:
            # system / user / 通常 assistant はそのまま
            cleaned.append(m)

    return cleaned


def load_conversation_from_log(
    path: str,
    system_prompt: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    ログファイル（JSONL）から会話履歴を読み込み、
    ・メッセージを正規化
    ・通常の system は捨てるが、skill 注入の system は維持する
    ・先頭に指定された system_prompt を入れ直す
      （指定がない場合は現在の SYSTEM_PROMPT を使う）
    という形で messages を再構成する。
    """
    raw_messages: list[dict[str, Any]] = []

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                # 壊れた行はスキップ
                continue
            if not isinstance(obj, dict) or "role" not in obj:
                continue
            raw_messages.append(obj)

    # まずは正規化
    messages: list[dict[str, Any]] = []
    for obj in raw_messages:
        nm = normalize_message_from_log(obj)
        if nm is not None:
            messages.append(nm)

    # skill 注入の system は残し、それ以外の system は捨てる
    skill_prefix = "[SKILL] "
    skill_messages = [
        m
        for m in messages
        if m.get("role") == "system"
        and isinstance(m.get("content"), str)
        and m.get("content").startswith(skill_prefix)
    ]
    messages = [m for m in messages if m.get("role") != "system"]

    # 引数が None のときは現在の SYSTEM_PROMPT を使う
    if system_prompt is None:
        system_prompt = SYSTEM_PROMPT

    # 先頭に指定された system_prompt を入れ直す
    system_msg = {"role": "system", "content": system_prompt}
    messages.insert(0, system_msg)

    # skill の system メッセージは system_prompt の直後に戻す
    if skill_messages:
        messages[1:1] = skill_messages

    return list(messages)


def shrink_messages(
    messages: list[dict[str, Any]], keep_last: int = 40
) -> list[dict[str, Any]]:
    """
    メモリ上の messages を簡易圧縮する:
    - 先頭の system メッセージ群はそのまま残す
    - それ以外（user/assistant/tool）は末尾の keep_last 件だけ残し、それ以前は捨てる
    """
    # system は先頭にある想定（SYSTEM_PROMPT と長期記憶メモなど）
    system_msgs: list[dict[str, Any]] = []
    others: list[dict[str, Any]] = []

    hit_non_system = False
    for m in messages:
        if m.get("role") == "system" and not hit_non_system:
            system_msgs.append(m)
        else:
            hit_non_system = True
            others.append(m)

    if len(others) <= keep_last:
        print(
            _(
                "[INFO] There were %(count)d messages to compress, so nothing was changed."
            )
            % {"count": len(others)},
            file=sys.stderr,
        )
        return list(messages)

    trimmed_others = others[-keep_last:]
    print(
        _(
            "[INFO] Compressed in-memory conversation history: %(old_n)d -> %(new_n)d messages (keep_last=%(keep_last)d)"
        )
        % {
            "old_n": len(others),
            "new_n": len(trimmed_others),
            "keep_last": keep_last,
        },
        file=sys.stderr,
    )

    new_messages = system_msgs + trimmed_others
    return new_messages


def compress_history_with_llm(
    client: Any,
    depname: str,
    messages: list[dict[str, Any]],
    keep_last: int = 20,
) -> list[dict[str, Any]]:
    """
    別の LLM コンテキストを立ち上げて、古い user/assistant/tool を
    20件前後のチャンクごとに段階要約し、1つの system メッセージに圧縮する。
    コンテキスト長エラーが出た場合は、チャンクを半分にして再試行する。
    """
    try:
        from .profile_manager import run_profiling_async
        import sys as _sys

        _core_mod = _sys.modules[__name__]
        run_profiling_async(messages, _core_mod)
    except Exception:
        pass

    try:
        from .gemini_cache_mgr import GeminiCacheManager

        mgr = GeminiCacheManager(depname)
        mgr.clear_cache(client)
    except Exception:
        pass

    system_msgs: list[dict[str, Any]] = []
    others: list[dict[str, Any]] = []

    hit_non_system = False
    for m in messages:
        if m.get("role") == "system" and not hit_non_system:
            system_msgs.append(m)
        else:
            hit_non_system = True
            others.append(m)

    old_part = others[:-keep_last]
    tail_part = others[-keep_last:]

    chunk_size_raw = (env_get("UAGENT_SHRINK_CHUNK_SIZE", "") or "").strip()
    try:
        initial_chunk_size = int(chunk_size_raw) if chunk_size_raw else 20
    except Exception:
        initial_chunk_size = 20
    if initial_chunk_size <= 0:
        initial_chunk_size = 20

    use_responses_api = env_get("UAGENT_RESPONSES", "").lower() in ("1", "true")
    max_retries_429 = int(env_get("UAGENT_429_MAX_RETRIES", "20"))
    retry_base = float(env_get("UAGENT_429_BACKOFF_BASE", "2"))
    retry_cap = float(env_get("UAGENT_429_BACKOFF_CAP", "300"))

    from .llm_errors import _rate_limit_retry_step

    def _recreate_client() -> Any:
        try:
            from . import util_providers
            import sys as _sys

            _core_mod = _sys.modules[__name__]
            _unused_p, new_client, _unused_m = util_providers.make_client(_core_mod)
            return new_client
        except Exception:
            return None

    from . import util_providers

    provider = util_providers.detect_provider()
    translator = globals().get("_")

    def _t(s: str) -> str:
        try:
            return translator(s) if callable(translator) else s
        except Exception:
            return s

    def _message_to_text(m: dict[str, Any]) -> tuple[str | None, str]:
        role = str(m.get("role") or "")
        content = m.get("content") or ""
        if isinstance(content, (dict, list)):
            content = json.dumps(content, ensure_ascii=False)
        content = str(content).strip()
        if not content:
            return None, role

        if role == "user":
            return f"User: {content}", role
        if role == "assistant":
            return f"Assistant: {content}", role
        if role == "tool":
            tname = m.get("name") or "(unknown_tool)"
            return f"Tool: {tname} {content}", role
        return None, role

    def _is_context_length_exceeded(err: Exception) -> bool:
        s = f"{type(err).__name__}: {err}".lower()
        return (
            "context_length_exceeded" in s
            or "exceeds the context window" in s
            or "input exceeds the context window" in s
        )

    def _summarize_with_llm(
        summary_messages: list[dict[str, Any]],
    ) -> tuple[str | None, Exception | None]:
        nonlocal client
        summary_content = ""
        attempt_429 = 0
        while True:
            try:
                if provider in ("gemini", "vertexai") or "genai.Client" in str(
                    type(client)
                ):
                    from .llm_gemini import gemini_chat_with_tools

                    summary_content, _summary_unused1, _summary_unused2 = (
                        gemini_chat_with_tools(
                            client=client,
                            model_name=depname,
                            messages=summary_messages,
                            core=sys.modules[__name__],
                        )
                    )
                elif provider == "claude":
                    from .llm_claude import claude_chat_with_tools

                    claude_result = claude_chat_with_tools(
                        client=client,
                        model_name=depname,
                        messages=summary_messages,
                    )
                    if isinstance(claude_result, tuple):
                        summary_content = (
                            claude_result[0] if len(claude_result) >= 1 else ""
                        )
                    else:
                        summary_content = str(claude_result)
                elif use_responses_api:
                    resp = client.responses.create(
                        model=depname,
                        instructions=summary_messages[0]["content"],
                        input=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "input_text",
                                        "text": summary_messages[1]["content"],
                                    },
                                ],
                            }
                        ],
                    )
                    if hasattr(resp, "output") and resp.output:
                        for item in resp.output:
                            if item.type == "message":
                                for c in item.content:
                                    if c.type == "output_text":
                                        summary_content += c.text
                elif hasattr(client, "chat") and hasattr(client.chat, "completions"):
                    resp = client.chat.completions.create(
                        model=depname,
                        messages=summary_messages,
                    )
                    summary_content = resp.choices[0].message.content or ""
                else:
                    raise AttributeError(
                        f"Client {type(client)} has no attribute 'chat' and is not recognized as Gemini."
                    )
                return summary_content, None
            except Exception as e:
                if _is_context_length_exceeded(e):
                    return None, e

                attempt_429, new_client, action = _rate_limit_retry_step(
                    exception=e,
                    provider="summarize",
                    model=depname,
                    attempt=attempt_429,
                    max_retries=max_retries_429,
                    base=retry_base,
                    cap=retry_cap,
                    recreate_client_fn=_recreate_client,
                )

                if action == "retry":
                    if new_client is not None:
                        client = new_client
                    continue

                if action == "give_up":
                    print(
                        "[WARN] "
                        + _t(
                            "429 retry limit (%(max_retries)s) reached while history compression."
                        )
                        % {"max_retries": max_retries_429},
                        file=sys.stderr,
                    )
                    print(repr(e), file=sys.stderr)
                    return None, e

                print(
                    "[WARN] "
                    + _t("Error while calling LLM for history compression: %(err)r")
                    % {"err": e},
                    file=sys.stderr,
                )
                return None, e

    def _compress_once(
        current_chunk_size: int,
    ) -> tuple[list[dict[str, Any]] | None, Exception | None]:
        if current_chunk_size <= 0:
            current_chunk_size = 1

        chunks = [
            old_part[i : i + current_chunk_size]
            for i in range(0, len(old_part), current_chunk_size)
        ]

        rolling_summary = ""
        for chunk in chunks:
            lines: list[str] = []
            for m in chunk:
                rendered, _role = _message_to_text(m)
                if rendered is None:
                    continue
                lines.append(rendered)

            if not lines:
                continue

            chunk_text = "\n\n".join(lines)

            if not rolling_summary:
                summary_system_prompt = (
                    _t("- Summarize the conversation chunk in English.\n")
                    + _t(
                        "- Keep the summary concise but include key decisions, constraints, and pending items.\n"
                    )
                    + _t("- Output should be directly usable as a system message.")
                )
                summary_user_content = (
                    _t("Conversation chunk:\n")
                    + f"{chunk_text}\n\n"
                    + _t("Write a concise summary of this chunk.")
                )
            else:
                summary_system_prompt = (
                    _t("- You are updating an existing conversation summary.\n")
                    + _t("- Preserve important facts from the previous summary.\n")
                    + _t(
                        "- Merge in the new chunk without losing constraints, decisions, or pending items.\n"
                    )
                    + _t("- Keep the result concise and suitable for a system message.")
                )
                summary_user_content = (
                    _t("Previous summary:\n")
                    + f"{rolling_summary}\n\n"
                    + _t("New chunk:\n")
                    + f"{chunk_text}\n\n"
                    + _t("Update the summary while keeping the prior context intact.")
                )

            summary_messages = [
                {"role": "system", "content": summary_system_prompt},
                {"role": "user", "content": summary_user_content},
            ]

            summary_content, error = _summarize_with_llm(summary_messages)
            if error is not None:
                return None, error
            if summary_content is None:
                return None, RuntimeError("history compression returned no summary")

            rolling_summary = summary_content.strip()

        if not rolling_summary:
            return list(messages), None

        summary_msg = {
            "role": "system",
            "content": _t("Summary of the conversation so far:\n") + rolling_summary,
        }

        new_messages = system_msgs + [summary_msg] + tail_part

        print(
            _t(
                "[INFO] shrink_llm: {old_n} -> {new_n} messages "
                "(compressed {old_part_n} older messages into 1 summary; kept {tail_n} tail)"
            ).format(
                old_n=len(messages),
                new_n=len(new_messages),
                old_part_n=len(old_part),
                tail_n=len(tail_part),
            ),
            file=sys.stderr,
        )

        log_message(summary_msg)
        return new_messages, None

    current_chunk_size = initial_chunk_size
    while True:
        compressed_messages, error = _compress_once(current_chunk_size)
        if error is None:
            return (
                compressed_messages
                if compressed_messages is not None
                else list(messages)
            )

        if _is_context_length_exceeded(error):
            if current_chunk_size <= 1:
                print(
                    _(
                        "[WARN] history compression hit context length even at chunk_size=1; falling back to shrink_messages()."
                    ),
                    file=sys.stderr,
                )
                return shrink_messages(messages, keep_last=keep_last)

            next_chunk_size = max(1, current_chunk_size // 2)
            if next_chunk_size == current_chunk_size:
                print(
                    _(
                        "[WARN] history compression could not reduce chunk_size further; falling back to shrink_messages()."
                    ),
                    file=sys.stderr,
                )
                return shrink_messages(messages, keep_last=keep_last)

            print(
                _(
                    "[WARN] history compression context length exceeded; retrying with chunk_size=%(chunk_size)d"
                )
                % {"chunk_size": next_chunk_size},
                file=sys.stderr,
            )
            current_chunk_size = next_chunk_size
            continue

        return list(messages)


def print_help() -> None:
    """Print help for the :help command.

    Single source of truth: uagent.util_tools.format_help().
    """

    try:
        from . import util_tools

        text = util_tools.format_help(core=sys.modules[__name__])
        print(text)
    except Exception as e:
        # Fallback: minimal help (avoid breaking interactive use)
        print(
            _(":help  (help unavailable: %(err)s)")
            % {"err": f"{type(e).__name__}: {e}"}
        )


# ==============================
# SYSTEM_PROMPT
# ==============================

# NOTE: Keep system prompt msgids small (avoid giant single msgid).
# Split into section-level msgids and build full/compact prompts by joining.

SYSTEM_PROMPT_FULL_MISSION = _("""## Mission
- You are a capable \"general-purpose tool execution agent\" running on a local environment, and you can actually execute commands and operate on files on the user's machine.
- Ask the user for confirmation before performing any dangerous operation.
- Do not flatter the user. Do not use emojis.
- Do not summarize. Keep information concise.
- When creating files, output the complete final content (do not output diffs or partial summaries).
""")

SYSTEM_PROMPT_FULL_RULES = _("""## Rules
- Always use the provided tools and verify the latest information.
- Be creative, but do not output uncertain information.
- Consult available tools and choose the most appropriate one.
- When executing tools, delegate as little decision-making as possible to the user.
""")

SYSTEM_PROMPT_FULL_NOTES = _("""## Notes
- All user messages come via this script's standard input.
- For tool-specific purpose/arguments/constraints/operational details, prefer each tool's description.
- If you need additional information or confirmation from the user, use the human_ask tool.
- When handling relative date expressions, call get_current_time to reference the current time.
- Do not store secrets (passwords/tokens) in long-term memory (add_long_memory, etc.).
- Files with suffixes like .org / .org1 / .org2 are backup copies and must not be treated as primary editable files.
- If you create Python files, run `python -m py_compile` to validate syntax.
- If expert-level knowledge is required, use prompt templates (Agent Skills) and follow them.
- If the user's input is only a short affirmation and adds no new information, do not repeat the same explanation unless it is a direct answer to the immediately preceding clear question. If needed, ask briefly: "Which point should I continue with?"
""")

SYSTEM_PROMPT_DANGEROUS_DELETE_FILE = _("""## Dangerous operation policy (delete_file)
- For deletion using the delete_file tool, do NOT ask for confirmation before preview.
- Always run delete_file with dry_run=true first to get the list of deletion candidates.
- Show the candidates to the user and ask confirmation via human_ask exactly once.
- Only when the user explicitly replies \"y\" or \"yes\" (or equivalent explicit approval), run delete_file again with the same parameters, dry_run=false, and confirmed=true.
- If there are zero candidates, do not ask; just report that nothing will be deleted.
""")

SYSTEM_PROMPT_COMPACT_MISSION = _("""## Mission
- You are a capable \"general-purpose tool execution agent\" running on a local environment; you can execute commands and operate on the user's machine.
- Ask the user for confirmation before any dangerous operation.
- No flattery. No emojis. No conversation summaries. Keep it concise.
- When creating files, output the complete final content (no diffs/partial summaries).
""")

SYSTEM_PROMPT_COMPACT_RULES = _("""## Rules
- Use the provided tools first and verify results with tools.
- Consult tool descriptions for purpose/arguments/constraints; choose the most appropriate and safest tool.
- Be creative, but do not output uncertain information.
- Delegate as little decision-making as possible to the user.
""")

SYSTEM_PROMPT_COMPACT_NOTES = _("""## Notes
- All user messages come via this script's standard input.
- If required info/parameters are missing, ask via human_ask (do not guess).
- Relative dates: call get_current_time.
- Do not store secrets (passwords/tokens) in long-term memory.
- Files with suffixes like .org / .org1 / .org2 are backup copies and must not be treated as primary editable files.
- If you create Python files, run `python -m py_compile`.
- If expert-level knowledge is required, use Agent Skills prompt templates.
- If the user's input is only a short affirmation and adds no new information, do not repeat the same explanation unless it is a direct answer to the immediately preceding clear question. If needed, ask briefly: "Which point should I continue with?"
""")


SYSTEM_PROMPT_WINDOWS_CMD_PASTE_TIP = _(
    """- If the user is using Windows cmd.exe, prefer multi-line commands using caret (^) line continuation, and keep each line short to avoid copy/paste line breaks.
"""
)


def _build_system_prompt_full() -> str:
    parts = [
        SYSTEM_PROMPT_FULL_MISSION,
        "",
        SYSTEM_PROMPT_FULL_RULES,
        "",
        SYSTEM_PROMPT_FULL_NOTES,
        "",
        SYSTEM_PROMPT_WINDOWS_CMD_PASTE_TIP,
        "",
        SYSTEM_PROMPT_DANGEROUS_DELETE_FILE,
    ]
    return "\
".join(parts).strip() + "\
"


def _build_system_prompt_compact() -> str:
    parts = [
        SYSTEM_PROMPT_COMPACT_MISSION,
        "",
        SYSTEM_PROMPT_COMPACT_RULES,
        "",
        SYSTEM_PROMPT_COMPACT_NOTES,
        "",
        SYSTEM_PROMPT_WINDOWS_CMD_PASTE_TIP,
        "",
        SYSTEM_PROMPT_DANGEROUS_DELETE_FILE,
    ]
    return "\
".join(parts).strip() + "\
"


SYSTEM_PROMPT_MSGID = _build_system_prompt_full()
SYSTEM_PROMPT_COMPACT_MSGID = _build_system_prompt_compact()

# System prompt used by the agent. This is translated via gettext; if translations are missing,
# the msgid (English) is used as-is.


def _select_system_prompt() -> str:
    mode = (env_get("UAGENT_SYSTEM_PROMPT") or "").strip().lower()

    # Default (env unset): compact.
    if mode in ("full",):
        return SYSTEM_PROMPT_MSGID
    if mode in ("", "compact", "short", "lite"):
        return SYSTEM_PROMPT_COMPACT_MSGID

    # Unknown value: fall back to the full prompt (safer/more compatible).
    return SYSTEM_PROMPT_MSGID


SYSTEM_PROMPT = _select_system_prompt()


def build_tools_system_prompt(tool_specs: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    lines.append("[Available Tools]")
    lines.append(
        _(
            "The following tools are currently loaded in this session. Choose the most appropriate tool for the task."
        )
    )
    for spec in tool_specs:
        func = spec.get("function", {})
        name = func.get("name", "(unknown)")
        sp = func.get("system_prompt") or func.get("description") or ""
        lines.append(f"- {name}: {sp}")
    return "\n".join(lines)
