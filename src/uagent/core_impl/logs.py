"""Log file helpers (split from core.py)."""

from __future__ import annotations

import glob
import json
import os
from typing import Any

from ..i18n import _
from ..utils.secret_mask import mask_message as _mask_message
from .. import core as _core


def log_message(message: dict[str, Any]) -> None:
    """Compatibility shim for runtime.logging_setup."""
    from ..runtime.logging_setup import append_masked_message

    append_masked_message(_core.LOG_FILE, message, _mask_message)


def rewrite_current_log_from_messages(messages: list[dict[str, Any]]) -> str:
    """Rewrite the active JSONL log or SQLite session history."""
    session_store = globals().get("session_store")
    session_id = globals().get("session_id")
    if (
        os.environ.get("UAGENT_SESSION_BACKEND", "sqlite").strip().lower() == "sqlite"
        and session_store is not None
        and session_id
    ):
        session_store.replace_messages(session_id, messages)
        return str(session_id)
    from ..runtime.history import rewrite_jsonl_log

    return rewrite_jsonl_log(
        _core.LOG_FILE,
        messages,
        read_responses_state_records(_core.LOG_FILE),
        _mask_message,
    )


def find_log_files(exclude_current: bool = False) -> list[str]:
    pattern = os.path.join(_core.BASE_LOG_DIR, "scheck_log_*.jsonl")
    files = glob.glob(pattern)
    if exclude_current:
        current_abs = os.path.abspath(_core.LOG_FILE)
        files = [f for f in files if os.path.abspath(f) != current_abs]
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return files


def read_responses_state_records(path: str) -> list[dict[str, Any]]:
    """Read Responses API metadata records from a JSONL conversation log."""
    records: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if not isinstance(obj, dict) or obj.get("type") != "responses_state":
                    continue
                if obj.get("schema_version", 1) != 1:
                    continue
                records.append(obj)
    except (OSError, TypeError):
        return []
    return records


def latest_responses_state(path: str) -> dict[str, Any] | None:
    """Return the newest Responses API metadata record in a JSONL log."""
    records = read_responses_state_records(path)
    return records[-1] if records else None


def guess_topics_from_content(content: str) -> set[str]:
    """
    Roughly estimate topic candidates from the log content.
    """
    topics: set[str] = set()
    lower = content.lower()

    # Category definitions
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

    topics = {
        topic
        for topic, keywords in mapping.items()
        if any(kw in lower for kw in keywords)
    }

    return topics


def list_logs(*, limit: int = 10, show_all: bool = False) -> list[str]:
    """Display a list of logs.

    Purpose:
    - Maintain the index for use with :load.
    - Make each log distinguishable at a glance.

    Display contents:
    - index
    - Last modified time (mtime)
    - Number of messages :load would load (matches "Conversation message count")
    - First user utterance (shortened)
    - Topics (estimated) shortened to top few items
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
        return s if len(s) <= n else s[: max(0, n - 1)] + "\u2026"

    def _fmt_ts(ts: float) -> str:
        try:
            import datetime

            return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        except Exception:
            return _("(unknown time)")

    print(
        _("logs: showing %(shown)d/%(total)d (dir=%(dir)s)")
        % {"shown": len(view), "total": len(files), "dir": _core.BASE_LOG_DIR}
    )
    print(_("Log files:"))

    for idx, path in enumerate(view):
        try:
            mtime = os.path.getmtime(path)
            mtime_text = _fmt_ts(mtime)
        except Exception:
            mtime_text = _("(mtime unknown)")

        response_state = latest_responses_state(path)
        response_count = len(read_responses_state_records(path))
        response_marker = "[R]" if response_count else "[ ]"
        response_summary = ""
        if response_state:
            rid = str(response_state.get("response_id") or "")
            rid_short = rid if len(rid) <= 18 else rid[:18] + "..."
            response_summary = f" | {response_marker} {response_count} · {rid_short}"
        else:
            response_summary = f" | {response_marker}"
        # Read up to 200 lines from the beginning to get the first user message
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

        # Read up to N bytes from the end to get the "actual last user" message
        # (Upper limit to prevent slowdowns even with huge logs. User specified: 16MB)
        tail_max_bytes = 16 * 1024 * 1024
        tail_text = ""
        try:
            size = os.path.getsize(path)
            start = max(0, size - tail_max_bytes)
            with open(path, "rb") as bf:
                bf.seek(start)
                data = bf.read()

            # Discard the first incomplete line as it may start in the middle of a line
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
        # Scan all lines to count exactly what :load would load
        # (load_conversation_from_log): user/assistant/tool messages,
        # preserved [SKILL]/[HOOK] system messages, and the last [CWD] marker.
        # + Also pick up "first/last user content in the entire log" for fallback
        total_user_count = 0
        total_assistant_count = 0
        total_tool_count = 0
        preserved_system_count = 0
        last_cwd_path: str | None = None
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
                    elif role == "tool":
                        total_tool_count += 1
                    elif role == "system":
                        content = obj.get("content")
                        if isinstance(content, str):
                            if content.startswith("[SKILL] ") or content.startswith(
                                "[HOOK] "
                            ):
                                preserved_system_count += 1
                            if content.startswith("[CWD] "):
                                tail = content[len("[CWD] ") :].strip()
                                try:
                                    cobj = json.loads(tail)
                                except Exception:
                                    cobj = None
                                if isinstance(cobj, dict):
                                    p = cobj.get("path")
                                    if isinstance(p, str) and p.strip():
                                        last_cwd_path = p
        except Exception:
            # Treat as 0 if unreadable (better than crashing the display)
            total_user_count = 0
            total_assistant_count = 0
            total_tool_count = 0
            preserved_system_count = 0
            last_cwd_path = None
            first_user_any = ""
            last_user_any = ""

        # Get the first user message from the beginning (lightweight)
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

        # Get the last user message from the end (the actual last one)
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

        # Fallback: If first/last user cannot be retrieved (no user message), use the values picked up during the full scan
        if not first_user and first_user_any:
            first_user = first_user_any
        if not last_user and last_user_any:
            last_user = last_user_any

        # "msgs" must match what :load reports ("Conversation message count"):
        # 1 (re-inserted SYSTEM_PROMPT) + preserved [SKILL]/[HOOK] system messages
        # + user/assistant/tool messages + a [CWD] marker when the last recorded
        # workdir still exists on disk (auto-restored by :load).
        cwd_bonus = 1 if (last_cwd_path and os.path.isdir(last_cwd_path)) else 0
        turns = (
            1
            + preserved_system_count
            + total_user_count
            + total_assistant_count
            + total_tool_count
            + cwd_bonus
        )

        first_user_text = (
            _shorten(first_user, 60) if first_user else _("(no user message)")
        )
        last_user_text = (
            _shorten(last_user, 80) if last_user else _("(no user message)")
        )

        print(
            _(
                "[%(idx)d] %(mtime_text)s | %(turns)d msgs | first: %(first_user)s | last: %(last_user)s%(response_summary)s"
            )
            % {
                "idx": idx,
                "mtime_text": mtime_text,
                "turns": turns,
                "first_user": first_user_text,
                "last_user": last_user_text,
                "response_summary": response_summary,
            }
        )

    return files
