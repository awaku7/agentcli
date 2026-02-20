# scheck_core.py
import os
import sys

from .i18n import _
import json
import time
import glob
import queue
import threading
from typing import Any, Dict, List, Optional, Set

# ==============================
# 設定
# ==============================

from uagent.utils.paths import get_log_dir

PYTHON_EXEC_TIMEOUT_MS = 2000_000
CMD_EXEC_TIMEOUT_MS = 2000_000
MAX_TOOL_OUTPUT_CHARS = 400_000
READ_FILE_MAX_BYTES = 20_000_000
URL_FETCH_TIMEOUT_MS = 50_000_000
URL_FETCH_MAX_BYTES = 50_000_000

# Windows では cp932、それ以外では UTF-8
CMD_ENCODING = os.environ.get("UAGENT_CMD_ENCODING") or "utf-8"

# Windows コンソールでエスケープシーケンスを有効化（可能なら）
if os.name == "nt":
    try:
        os.system("")
    except Exception:
        pass

# --- 文字化け対策: 標準出力/標準エラーの UTF-8 化（可能な範囲で） ---
#
# tools のロードログや SYSTEM_PROMPT 等の日本語が cp932 コンソールで化けることがあるため、
# 可能なら stdout/stderr を UTF-8 に寄せる。
# - Python 3.7+ の TextIOWrapper.reconfigure を優先
# - 失敗しても無視（環境依存）
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# セッションIDとログ・メモリファイルパス
SESSION_ID = time.strftime("%Y%m%d_%H%M%S")

BASE_LOG_DIR = os.path.abspath(os.environ.get("UAGENT_LOG_DIR") or str(get_log_dir()))
LOG_FILE = os.environ.get("UAGENT_LOG_FILE") or os.path.join(
    BASE_LOG_DIR, f"scheck_log_{SESSION_ID}.jsonl"
)

# ログのトピック推定を行うかどうか（0なら無効）
ENABLE_LOG_TOPIC_GUESS = os.environ.get("UAGENT_LOG_TOPICS", "1") != "0"

# イベントキュー（通常入力・タイマー入力をひとまとめ）
event_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()

# GUIモードかどうか（環境変数または gui.py 側で設定される）
IS_GUI = os.environ.get("UAGENT_GUI_MODE") == "1"

# human_ask 用の状態（stdin_loop と human_ask ツールで共有）
human_ask_lock = threading.RLock()
human_ask_active = False
human_ask_queue = None  # type: ignore[assignment]
human_ask_lines: List[str] = []
human_ask_is_password = False
human_ask_multiline_active = False

# 通常ユーザー入力・human_ask の複数行モードの終端トークン
MULTI_INPUT_SENTINEL = '"""end'

# プロンプト用ステータス
status_lock = threading.RLock()
# 出力競合（stdinプロンプトとstatus/ログ出力の押し流し）を減らすための共有ロック
print_lock = threading.RLock()
status_busy = False  # LLM やツールが処理中なら True
status_label = ""  # "LLM" や "tool:cmd_exec" など


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

    state = 'BUSY' if busy else 'IDLE'
    label_part = f' [{label}]' if label else ''

    # Color/ANSI control
    # Default: enable ANSI colors unless explicitly disabled.
    no_color = bool(os.environ.get('NO_COLOR') or os.environ.get('UAGENT_NO_COLOR'))
    stderr_is_tty = bool(getattr(sys.stderr, 'isatty', lambda: False)())

    if IS_GUI or no_color or (not stderr_is_tty):
        # Fallback: no ANSI
        with print_lock:
            sys.stderr.write(f'[STATE] {state}{label_part}\n')
            sys.stderr.flush()
        return

    # 色分け（BUSY=黄色, IDLE=緑）
    color = '\x1b[33m' if busy else '\x1b[32m'

    # NOTE: Keep output simple: one colored line.
    with print_lock:
        sys.stderr.write(f"{color}[STATE] {state}{label_part}\x1b[0m\n")
        sys.stderr.flush()


def set_status(busy: bool, label: str = "") -> None:
    """
    Busy/Idle 状態を更新し、変化があったときには状態行を描画する。
    """
    global status_busy, status_label
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
        return f"{os.path.basename(cwd.rstrip(os.sep)) or cwd}> "


def get_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(_("Environment variable %(name)s is not set.") % {"name": name}, file=sys.stderr)
        sys.exit(1)
    return value


def normalize_url(url: str) -> str:
    if not url:
        return ""
    return url.strip().rstrip("/")


def get_env_url(name: str, default: Optional[str] = None) -> str:
    val = os.environ.get(name, default)
    if not val:
        if default is not None:
            return normalize_url(default)
        print(_("Environment variable %(name)s is not set.") % {"name": name}, file=sys.stderr)
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


def log_message(message: Dict[str, Any]) -> None:
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


# ==============================
# ログファイル検出／トピック推定
# ==============================


def find_log_files(exclude_current: bool = False) -> List[str]:
    pattern = os.path.join(BASE_LOG_DIR, "scheck_log_*.jsonl")
    files = glob.glob(pattern)
    if exclude_current:
        current_abs = os.path.abspath(LOG_FILE)
        files = [f for f in files if os.path.abspath(f) != current_abs]
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return files


def guess_topics_from_content(content: str) -> Set[str]:
    """
    ログ内容から大ざっぱにトピック候補を推定する。
    """
    topics: Set[str] = set()
    lower = content.lower()

    # カテゴリ定義
    mapping = {
        "システム開発/設計": [
            "設計",
            "アーキテクチャ",
            "要件",
            "仕様",
            "シーケンス",
            "クラス図",
            "database",
            "db",
            "sql",
            "git",
            "github",
            "docker",
            "k8s",
        ],
        "プログラミング/Python": [
            "python",
            "pip",
            "pandas",
            "numpy",
            "django",
            "flask",
            "fastapi",
        ],
        "プログラミング/C#・.NET": [
            "c#",
            "csharp",
            ".net",
            "dotnet",
            "visual studio",
            "wpf",
            "winforms",
        ],
        "プログラミング/JS・TS": [
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
        "プログラミング/Rust": ["rust", "cargo"],
        "プログラミング/C・C++": [" c ", "c++", "cpp", "cmake", "gcc", "clang"],
        "Web・ネットワーク": [
            "http",
            "api",
            "url",
            "fetch",
            "curl",
            "dns",
            "ip",
            "ssl",
            "証明書",
            "ブラウザ",
            "ドメイン",
        ],
        "インフラ・OS設定": [
            "linux",
            "ubuntu",
            "windows",
            "powershell",
            "shell",
            "bash",
            "環境変数",
            "パス",
            "サービス",
            "レジストリ",
        ],
        "メディア処理": [
            "ffmpeg",
            "画像",
            "動画",
            "音声",
            "video",
            "audio",
            "mp4",
            "wav",
            "mp3",
            "png",
            "jpg",
        ],
        "AI・LLM": [
            "llm",
            "openai",
            "azure",
            "chatgpt",
            "gemini",
            "claude",
            "prompt",
            "推論",
            "生成AI",
        ],
        "SNS・自動化": [
            "sns",
            "twitter",
            " x ",
            "discord",
            "slack",
            "bluesky",
            "mastodon",
            "自動化",
            "スクレイピング",
        ],
        "ドキュメント・調査": [
            "readme",
            "markdown",
            "資料",
            "調査",
            "検索",
            "リサーチ",
        ],
        "デバッグ・解析": [
            "traceback",
            "例外",
            "エラー",
            "exception",
            "error",
            "解析",
            "ログ",
        ],
        "データ分析/Excel": ["excel", "xlsx", "csv", "分析", "集計", "統計", "グラフ"],
        "セキュリティ": [
            "security",
            "脆弱性",
            "暗号",
            "認証",
            "パスワード",
            "token",
            "鍵",
            "攻撃",
        ],
    }

    for topic, keywords in mapping.items():
        if any(kw in lower for kw in keywords):
            topics.add(topic)

    return topics


def list_logs(*, limit: int = 10, show_all: bool = False) -> List[str]:
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
            return "(unknown time)"

    print(_("logs: showing %(shown)d/%(total)d (dir=%(dir)s)") % {"shown": len(view), "total": len(files), "dir": BASE_LOG_DIR})
    print(_("Log files:"))

    for idx, path in enumerate(view):
        try:
            mtime = os.path.getmtime(path)
            mtime_text = _fmt_ts(mtime)
        except Exception:
            mtime_text = "(mtime unknown)"
        # 先頭側は最初の user を取るために最大 200 行読む
        head_lines: List[str] = []
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

        tail_lines: List[str] = []
        if tail_text:
            for ln in tail_text.splitlines():
                ln = (ln or "").strip()
                if ln:
                    tail_lines.append(ln)
        # 正確な件数（user/assistant）は全行を走査してカウントする
        total_user_count = 0
        total_assistant_count = 0
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
                    elif role == "assistant":
                        total_assistant_count += 1
        except Exception:
            # 読めない場合は 0 扱い（表示が落ちるよりマシ）
            total_user_count = 0
            total_assistant_count = 0

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

        turns = total_user_count + total_assistant_count

        first_user_text = _shorten(first_user, 60) if first_user else "(no user message)"
        last_user_text = _shorten(last_user, 80) if last_user else "(no user message)"

        # path も末尾だけ出す（同一話題でも区別しやすい）
        try:
            tail = _shorten(os.path.basename(path), 40)
        except Exception:
            tail = "(unknown file)"

        print(f"[{idx}] {mtime_text} | {turns} msgs | {tail} | first: {first_user_text} | last: {last_user_text}")

    return files


# ==============================
# ログから会話を復元
# ==============================


def normalize_message_from_log(obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    過去ログ1行分の dict から、現在の ChatCompletion API に渡せる
    最小限の message dict に正規化する。
    - 不要なキーは削除
    - 壊れた形式は None を返してスキップ
    """
    role = obj.get("role")
    if role not in ("system", "user", "assistant", "tool"):
        return None

    msg: Dict[str, Any] = {"role": role}

    if role == "tool":
        # ツールメッセージ: name / tool_call_id / content のみ残す
        msg["content"] = str(obj.get("content") or "")
        if "tool_call_id" in obj:
            msg["tool_call_id"] = obj["tool_call_id"]
        if "name" in obj:
            msg["name"] = obj["name"]
        return msg

    # system / user / assistant 共通
    msg["content"] = obj.get("content") or ""

    # 過去ログに tool_calls が入っていた場合は、現在の形式に揃えて残す
    tcs = obj.get("tool_calls")
    if isinstance(tcs, list):
        new_tcs: List[Dict[str, Any]] = []
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


def sanitize_messages_for_tools(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    messages の中から「対応する assistant.tool_calls を持たない孤立した tool メッセージ」を削除する。
    """
    cleaned: List[Dict[str, Any]] = []
    seen_tool_call_ids: Set[str] = set()

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
                print(
                    file=sys.stderr,
                )

        else:
            # system / user / 通常 assistant はそのまま
            cleaned.append(m)

    return cleaned


def load_conversation_from_log(
    path: str,
    system_prompt: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    ログファイル（JSONL）から会話履歴を読み込み、
    ・メッセージを正規化
    ・ログ中の system はすべて捨てて、先頭に指定された system_prompt を入れ直す
      （指定がない場合は現在の SYSTEM_PROMPT を使う）
    という形で messages を再構成する。
    """
    raw_messages: List[Dict[str, Any]] = []

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
    messages: List[Dict[str, Any]] = []
    for obj in raw_messages:
        nm = normalize_message_from_log(obj)
        if nm is not None:
            messages.append(nm)

    # ログ中の system は全部捨てる
    messages = [m for m in messages if m.get("role") != "system"]

    # 引数が None のときは現在の SYSTEM_PROMPT を使う
    if system_prompt is None:
        system_prompt = SYSTEM_PROMPT

    # 先頭に指定された system_prompt を入れ直す
    system_msg = {"role": "system", "content": system_prompt}
    messages.insert(0, system_msg)

    return messages


def shrink_messages(
    messages: List[Dict[str, Any]], keep_last: int = 40
) -> List[Dict[str, Any]]:
    """
    メモリ上の messages を簡易圧縮する:
    - 先頭の system メッセージ群はそのまま残す
    - それ以外（user/assistant/tool）は末尾の keep_last 件だけ残し、それ以前は捨てる
    """
    # system は先頭にある想定（SYSTEM_PROMPT と長期記憶メモなど）
    system_msgs: List[Dict[str, Any]] = []
    others: List[Dict[str, Any]] = []

    hit_non_system = False
    for m in messages:
        if m.get("role") == "system" and not hit_non_system:
            system_msgs.append(m)
        else:
            hit_non_system = True
            others.append(m)

    if len(others) <= keep_last:
        print(
            f"[INFO] 圧縮対象メッセージ数が {len(others)} 件なので、そのままにしました。",
            file=sys.stderr,
        )
        return messages

    trimmed_others = others[-keep_last:]
    print(
        f"[INFO] メモリ上の会話履歴を圧縮しました: "
        f"{len(others)} -> {len(trimmed_others)} 件 (keep_last={keep_last})",
        file=sys.stderr,
    )

    new_messages = system_msgs + trimmed_others
    return new_messages


def compress_history_with_llm(
    client: Any,
    depname: str,
    messages: List[Dict[str, Any]],
    keep_last: int = 20,
) -> List[Dict[str, Any]]:
    """
    別の LLM コンテキストを立ち上げて、古い user/assistant を要約し、
    1 つの system メッセージに圧縮する。
    """
    # system とそれ以外を分離
    system_msgs: List[Dict[str, Any]] = []
    others: List[Dict[str, Any]] = []

    hit_non_system = False
    for m in messages:
        if m.get("role") == "system" and not hit_non_system:
            system_msgs.append(m)
        else:
            hit_non_system = True
            others.append(m)

    if not others:
        print("[INFO] 圧縮対象メッセージがありません。", file=sys.stderr)
        return messages

    if len(others) <= keep_last:
        print(
            f"[INFO] 圧縮対象が少ないため、そのままにしました。"
            f"others={len(others)}, keep_last={keep_last}",
            file=sys.stderr,
        )
        return messages

    # 要約対象（old_part）と末尾に残す部分（tail_part）に分割
    old_part = others[:-keep_last]
    tail_part = others[-keep_last:]

    # 要約用に user/assistant/tool をテキスト化する
    # - tool メッセージも要約素材に含める（ユーザー指定仕様）
    lines: List[str] = []
    for m in old_part:
        role = m.get("role")
        content = m.get("content") or ""
        if isinstance(content, (dict, list)):
            content = json.dumps(content, ensure_ascii=False)
        content = str(content).strip()
        if not content:
            continue

        if role == "user":
            lines.append(f"User:{content}")
        elif role == "assistant":
            lines.append(f"Assistant:{content}")
        elif role == "tool":
            # 可能ならツール名も残す
            tname = m.get("name") or "(unknown_tool)"
            lines.append(f"Tool: {tname} {content}")

    if not lines:
        print("[INFO] 要約対象の user/assistant/tool がありません。", file=sys.stderr)
        return messages

    convo_text = "\\n\\n".join(lines)

    # --- 要約用の別コンテキスト ---
    summary_system_prompt = (
        "あなたは対話ログの要約エージェントです。以下のユーザーとアシスタントの過去の対話ログを、"
        "後続の対話に必要な情報を失わない範囲でコンパクトに日本語で要約してください。\n"
        "・重要な前提条件、設定、方針、決定事項は残す\n"
        "・コードのバージョンやファイルパスなど、後から参照しそうなものは必要に応じて残す\n"
        "・挨拶や雑談など、今後のタスクに不要な部分は省略する\n"
        "・出力は「このセッションの過去ログ要約」として、そのまま system メッセージに入れられる形にする\n"
    )

    summary_messages = [
        {"role": "system", "content": summary_system_prompt},
        {"role": "user", "content": convo_text},
    ]

    use_responses_api = os.environ.get("UAGENT_RESPONSES", "").lower() in ("1", "true")

    try:
        if use_responses_api:
            resp = client.responses.create(
                model=depname,
                instructions=summary_messages[0]["content"],
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": convo_text},
                        ],
                    }
                ],
            )
        else:
            resp = client.chat.completions.create(
                model=depname,
                messages=summary_messages,
            )
    except Exception as e:
        print(
            f"[WARN] 履歴圧縮用 LLM 呼び出しでエラーが発生しました: {e!r}",
            file=sys.stderr,
        )
        return messages

    if use_responses_api:
        summary_content = ""
        if hasattr(resp, "output") and resp.output:
            for item in resp.output:
                if item.type == "message":
                    for c in item.content:
                        if c.type == "output_text":
                            summary_content += c.text
    else:
        summary_content = resp.choices[0].message.content or ""
    summary_msg = {
        "role": "system",
        "content": "これまでの対話ログの要約:\n" + summary_content,
    }

    # 新しい messages を構成
    new_messages = system_msgs + [summary_msg] + tail_part

    print(
        f"[INFO] LLM で会話履歴を要約しました: "
        f"old_part={len(old_part)} 件 → 要約 1 件 + tail_part={len(tail_part)} 件",
        file=sys.stderr,
    )

    # ログにも要約を残す
    log_message(summary_msg)

    return new_messages


def print_help() -> None:
    """
    :help コマンドの内容
    """
    lines = [
        "利用可能なコマンド:",
        "  :help                 このヘルプを表示",
        '  (複数行入力中) """retry  入力を最初からやり直す',
        "  :logs / :list         ログファイル一覧を表示",
        "  :cd <path>            確認無しで作業ディレクトリ(workdir)を移動（例: :cd .. / :cd ~ / :cd C:\\path / :cd /）",
        "  :ls [path]            ディレクトリ一覧表示（例: :ls / :ls .. / :ls ~ / :ls C:\\path）",
        "  :load <idx|path>      過去ログを読み込み（会話履歴を上書き）",
        "                       ※実行後に確認が出て、y を選ぶと現在セッションのログファイル先頭へロード元ログ内容を挿入します（バックアップ無しで上書き）",
        "  :clean [N]            会話ログ（scheck_log_*.jsonl）を削除（system を除いた user/assistant/tool が N 件以下のログファイルを削除, 既定=10）",
        "  :shrink [N]           会話履歴を単純圧縮（system 以外を末尾 N 件だけ残す, 既定=40）",
        "  :shrink_llm [N]       LLM による要約圧縮（古い履歴を1件の要約 system にまとめ、末尾 N 件は生のまま残す, 既定=20）",
        "  :mem-list             長期記憶メモの一覧を表示",
        "  :mem-del <index>      指定 index の長期記憶メモを削除（:mem-list で番号を確認）",
        "  :shared-mem-list      共有長期記憶メモの一覧を表示（UAGENT_SHARED_MEMORY_FILE が必要）",
        "  :shared-mem-del <i>   指定 index の共有長期記憶メモを削除",
        "  :exit / :quit         終了",
        "",
        "ヒント:",
        "  - ユーザー入力で 'f' を単独行で入力すると複数行入力モードになります。",
        f"  - 複数行入力モードの終了は行全体が {MULTI_INPUT_SENTINEL} の行です。",
    ]
    print("\n".join(lines))


# ==============================
# SYSTEM_PROMPT
# ==============================
SYSTEM_PROMPT = """
## 命題
- あなたはローカル環境で動作する有能な「万能ツール実行エージェント」で、ユーザーマシン上で実際にコマンド実行やファイル操作ができます。
- 危険な操作はユーザーに確認を取ってから行う事。
- ご機嫌とりは行わない事。絵文字は出さない事。
- あなたは詳細な情報を提供するアシスタントであり、決して要約をしてはいけません。
- ファイルを作成する際はdiffや要約の結果を使わず完全な形で出力するようにしてください。

## 守るべき事
- 必ず用意されたツールを利用し最新の情報を精査してください。
- 発想を最大限に発現させる事。ただし不確かな情報は出さないようにしてください。
- ツールを参照し、最適なツールを選択してください。

## 補足
- すべてのユーザー発話はこのスクリプトの標準入力経由で行われます。
- ツール固有の用途・引数・制約・運用上の詳細は、./tools 以下の各ツールの system_prompt で提供されます。ツール利用に関する追加のルールは各ツール側の説明を優先してください。
- ユーザーへの追加情報や確認を期待する場合は human_ask ツールを利用してください。
- 相対的な日付表現を扱う際は get_current_time ツールを1回呼び出して現在時刻を参照してください。
- 長期記憶（add_long_memory など）にはパスワードやトークン等の秘匿情報を保存しないでください。
- Pythonファイルを作成した場合は python -m py_compile を利用して構文チェックしてください。
- 専門家としての知識が必要な場合はprompt_get ツールを参照し、それを利用してください。
- 未知のプロジェクトや大規模なディレクトリを扱う際は、まず `index_files` で全体をインデックスし、`semantic_search_files` を併用してコードの全体像を把握してください。
- 天気関係はhttps://wttr.inを採用してください。
"""


def build_tools_system_prompt(tool_specs: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    lines.append("【利用可能なツール一覧】")
    lines.append(
        "以下は、このセッションで現在ロードされているツールです。"
        "タスクに応じて適切なツールを選んでください。"
    )
    for spec in tool_specs:
        func = spec.get("function", {})
        name = func.get("name", "(unknown)")
        sp = func.get("system_prompt") or func.get("description") or ""
        lines.append(f"- {name}: {sp}")
    return "\n".join(lines)

