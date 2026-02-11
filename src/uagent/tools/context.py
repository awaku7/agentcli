# tools/context.py
"""tools.context

ツール実装からホスト（scheck_core / scheck.py）への依存を薄くするための
「コールバック注入式」コンテキスト。

- tools/__init__.py は scheck_core を import しない。
- 代わりにホスト側（scheck.py）が起動時に init_callbacks(...) を呼び、
  必要な関数や共有状態へのアクセサを注入する。

このモジュールは tools/ 配下の各ツールが参照する共通窓口。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class ToolCallbacks:
    # Busy/Idle 表示
    set_status: Optional[Callable[[bool, str], None]] = None

    # 環境変数取得（必須扱い）
    get_env: Optional[Callable[[str], str]] = None
    get_env_url: Optional[Callable[[str, Optional[str]], str]] = None

    # 出力トリミング
    truncate_output: Optional[Callable[[str, str, int], str]] = None

    # human_ask の共有状態（stdin_loop と同期するため）
    human_ask_lock: Any = None
    human_ask_active_ref: Optional[Callable[[], bool]] = None
    human_ask_set_active: Optional[Callable[[bool], None]] = None
    human_ask_queue_ref: Optional[Callable[[], Any]] = None
    human_ask_set_queue: Optional[Callable[[Any], None]] = None
    human_ask_lines_ref: Optional[Callable[[], Any]] = None
    human_ask_multiline_active_ref: Optional[Callable[[], bool]] = None
    human_ask_set_multiline_active: Optional[Callable[[bool], None]] = None
    human_ask_set_password: Optional[Callable[[bool], None]] = None
    multi_input_sentinel: str = '"""end'

    # タイマー等のイベント注入
    event_queue: Any = None

    # 表示環境
    is_gui: bool = False

    # 設定値
    cmd_encoding: str = "utf-8"
    cmd_exec_timeout_ms: int = 60_000
    python_exec_timeout_ms: int = 60_000
    url_fetch_timeout_ms: int = 60_000
    url_fetch_max_bytes: int = 1_000_000
    read_file_max_bytes: int = 1_000_000


_CALLBACKS: ToolCallbacks = ToolCallbacks()


def init_callbacks(cb: ToolCallbacks) -> None:
    global _CALLBACKS
    _CALLBACKS = cb


def get_callbacks() -> ToolCallbacks:
    return _CALLBACKS
