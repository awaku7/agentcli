"""scheck/util.py

互換層（薄いラッパ / 再export）。

目的:
- 過去バージョンの `from scheck.util import ...` を壊さない（外部互換）。
- 分割後の実体実装（util_tools / util_providers / scheck_llm）へ委譲する。

設計（Mode A: 互換優先）:
- このモジュールは「外部互換のための再export」を主目的とする。
- 内部コード（cli.py / web.py / gui.py など）は、原則として
  util_tools/util_providers/scheck_llm/runtime_init を直接 import する方向へ寄せる。
  （= util.py の利用は内部では非推奨）

旧名エイリアス（先頭が _）について:
- 旧コードが `_extract_image_paths` のような内部名を import しているケースがあったため、
  互換性のために旧名エイリアスを提供している。
- これらは「外部互換」のために残しており、現行コードでは新API（非アンダースコア名）を推奨する。
- 安易に削除すると外部利用者を壊す可能性があるため、Mode A では削除しない。

分割先:
- util_tools.py      : tools callbacks/コマンド処理/メッセージ構築/UI寄り
- util_providers.py  : provider判定/モデル名/クライアント生成
- scheck_llm.py      : LLMラウンド実行
- llm_gemini.py      : Gemini変換
- llm_errors.py      : エラー処理/429リトライ
"""

import importlib
from typing import Any, Dict, List, Tuple

# scheck_core をインポート（従来通り、このモジュールに core が存在する前提のコードがあるため）
core = importlib.import_module(".core", package="uagent")

from .util_providers import make_client as _make_client  # noqa: E402

from .util_tools import (  # noqa: E402
    append_result_to_outfile,
    build_long_memory_system_message,  # noqa: F401
    build_initial_messages as _build_initial_messages_impl,
    handle_command as _handle_command,
    init_tools_callbacks as _init_tools_callbacks_impl,
    insert_tools_system_message as _insert_tools_system_message_impl,
    iter_backup_files,
    open_image_with_default_app,
    parse_startup_args,
    try_open_images_from_text,
    extract_image_paths,
)


from .uagent_llm import run_llm_rounds as _run_llm_rounds  # noqa: E402

# Public re-exports (explicit)
# NOTE(Mode A): `__all__` is provided mainly to document intended public symbols.
# This project does not use `from scheck.util import *`, but defining __all__ helps
# keep the compatibility surface clear.
__all__ = [
    # Main compatibility wrappers
    "make_client",
    "build_initial_messages",
    "insert_tools_system_message",
    "handle_command",
    "run_llm_rounds",
    "_init_tools_callbacks",
    # Direct re-exports (util_tools)
    "append_result_to_outfile",
    "build_long_memory_system_message",
    "iter_backup_files",
    "open_image_with_default_app",
    "parse_startup_args",
    "try_open_images_from_text",
    "extract_image_paths",
    # Backward-compat private-name aliases
    "_extract_image_paths",
    "_open_image_with_default_app",
    "_try_open_images_from_text",
    "_parse_startup_args",
    "_iter_backup_files",
    "_append_result_to_outfile",
]

# --- 旧名エイリアス（互換用） ---

# 画像パス抽出/オープン
_extract_image_paths = extract_image_paths
_open_image_with_default_app = open_image_with_default_app
_try_open_images_from_text = try_open_images_from_text

# 起動引数
_parse_startup_args = parse_startup_args

# バックアップ列挙
_iter_backup_files = iter_backup_files

# outファイル追記
_append_result_to_outfile = append_result_to_outfile


# --- 旧API互換ラッパ ---


def _init_tools_callbacks(core_obj: Any) -> None:
    """旧シグネチャ互換: tools callbacks 初期化。"""
    return _init_tools_callbacks_impl(core_obj)


def make_client() -> Tuple[str, Any, str]:
    """旧シグネチャ互換: core を内部で捕捉して make_client(core) を呼ぶ。"""
    return _make_client(core)


def build_initial_messages() -> List[Dict[str, Any]]:
    """旧シグネチャ互換: core を暗黙注入して初期 messages を作る。"""
    return _build_initial_messages_impl(core=core)


def insert_tools_system_message(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """旧シグネチャ互換: core を暗黙注入して tools system message を挿入する。"""
    return _insert_tools_system_message_impl(messages, core=core)


def handle_command(
    line: str,
    messages_ref: List[Dict[str, Any]],
    client: Any,
    depname: str,
) -> bool:
    """旧シグネチャ互換: core を内部で捕捉して handle_command(..., core=core) を呼ぶ。"""
    return _handle_command(line, messages_ref, client, depname, core=core)


def run_llm_rounds(
    provider: str,
    client: Any,
    depname: str,
    messages: List[Dict[str, Any]],
) -> None:
    """旧シグネチャ互換: 依存を注入して run_llm_rounds を呼ぶ。"""

    return _run_llm_rounds(
        provider,
        client,
        depname,
        messages,
        core=core,
        make_client_fn=_make_client,
        append_result_to_outfile_fn=append_result_to_outfile,
        try_open_images_from_text_fn=try_open_images_from_text,
    )
