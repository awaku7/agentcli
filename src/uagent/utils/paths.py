"""uagent.utils.paths

uagent/scheck が使用する状態ディレクトリ（ログ、キャッシュ、DB、tmp、outputs 等）の
パス決定を一元化する。

目的:
- コードベース全体に散らばった ~/.scheck/... 直書きを排除し、設定/移行を容易にする。
- 環境変数による上書きを可能にしつつ、既定値は ~/.uag とする（旧: ~/.scheck を読み取りフォールバック可能）。
- 将来的に ~/.uag へ移行する場合でも、このモジュールの既定値を差し替えるだけで済む形にする。

重要な方針:
- 既定では ~/.uag を使用する。旧 ~/.scheck は移行期間の読み取りフォールバックとして扱う（リネームは行わない）。
- 明示的に変更したい場合は UAGENT_STATE_DIR / UAGENT_LOG_DIR / UAGENT_CACHE_DIR 等を利用する。

環境変数（現状互換 + 将来拡張）:
- UAGENT_STATE_DIR: 状態ディレクトリ基底（logs/cache/dbs/tmp/outputs/... の基底）
- UAGENT_LOG_DIR: ログディレクトリ（優先）
- UAGENT_CACHE_DIR: キャッシュディレクトリ（優先）
- UAGENT_DB_DIR: DB ディレクトリ（優先）
- UAGENT_TMP_DIR: tmp ディレクトリ（優先）
- UAGENT_OUTPUTS_DIR: outputs ディレクトリ（優先）
- UAGENT_MCP_CONFIG: MCP設定ファイルのパス（mcp_servers.json を直接指す）

注意:
- ここは低レイヤ（基盤）として、tools/ や LLM 依存のモジュールへ依存しない。
"""

from __future__ import annotations

import os
from pathlib import Path

# 既定の状態ディレクトリ名（将来ここを ".uag" に変更して移行できる）
_DEFAULT_STATE_DIRNAME = ".uag"


def _expand(p: str) -> Path:
    """Expand and resolve a path string to an absolute Path.

    - expands '~'
    - returns absolute path

    resolve() は存在しないパスで例外になり得るため使わない（.absolute() 相当で十分）。
    """

    return Path(os.path.expanduser(p)).absolute()


def get_state_dir() -> Path:
    """Return base state directory.

    Default: ~/.uag (legacy: ~/.scheck)
    Override: UAGENT_STATE_DIR
    """

    env = os.environ.get("UAGENT_STATE_DIR")
    if env:
        return _expand(env)
    return Path.home() / _DEFAULT_STATE_DIRNAME


def get_log_dir() -> Path:
    """Return log directory.

    Default: <state>/logs
    Override: UAGENT_LOG_DIR
    """

    env = os.environ.get("UAGENT_LOG_DIR")
    if env:
        return _expand(env)
    return get_state_dir() / "logs"


def get_cache_dir() -> Path:
    """Return cache directory.

    Default: <state>/cache
    Override: UAGENT_CACHE_DIR

    Note:
      既存コードには「UAGENT_LOG_DIR を cache に流用する」挙動が存在する場合があるが、
      ここでは採用しない（log と cache は概念的に別）。
      互換が必要なら、呼び出し側で明示的に UAGENT_CACHE_DIR を設定する。
    """

    env = os.environ.get("UAGENT_CACHE_DIR")
    if env:
        return _expand(env)
    return get_state_dir() / "cache"


def get_dbs_dir() -> Path:
    """Return DB directory.

    Priority (compatibility-aware):
      1) UAGENT_DB_DIR (explicit)
      2) dirname(UAGENT_CACHE_DIR)/dbs (legacy behavior)
      3) dirname(UAGENT_LOG_DIR)/dbs (legacy behavior)
      4) <state>/dbs (default)

    NOTE:
      semantic_search_files_tool.py historically derived dbs_dir from
      UAGENT_CACHE_DIR/UAGENT_LOG_DIR by taking dirname(). We keep that
      behavior here to avoid breaking existing deployments.
    """

    env = os.environ.get("UAGENT_DB_DIR")
    if env:
        return _expand(env)

    env_cache = os.environ.get("UAGENT_CACHE_DIR")
    if env_cache:
        try:
            return _expand(env_cache).parent / "dbs"
        except Exception:
            pass

    env_log = os.environ.get("UAGENT_LOG_DIR")
    if env_log:
        try:
            return _expand(env_log).parent / "dbs"
        except Exception:
            pass

    return get_state_dir() / "dbs"


def get_tmp_dir() -> Path:
    """Return tmp directory.

    Default: <state>/tmp
    Override: UAGENT_TMP_DIR
    """

    env = os.environ.get("UAGENT_TMP_DIR")
    if env:
        return _expand(env)
    return get_state_dir() / "tmp"


def get_tmp_patch_dir() -> Path:
    """Return tmp dir for git patch files.

    This path is security-sensitive:
    - git_ops_tool.py allows paths outside workdir only under this directory.
    - apply_patch_tool.py writes patch files here.

    Therefore, both tools must reference the same function.
    """

    return get_tmp_dir() / "patch"


def get_outputs_dir() -> Path:
    """Return outputs directory.

    Default: <state>/outputs
    Override: UAGENT_OUTPUTS_DIR
    """

    env = os.environ.get("UAGENT_OUTPUTS_DIR")
    if env:
        return _expand(env)
    return get_state_dir() / "outputs"


def get_image_generations_dir() -> Path:
    """Return image generations output directory."""

    return get_outputs_dir() / "image_generations"


def get_docs_cache_dir() -> Path:
    """Return docs cache directory (used to materialize packaged docs for opening)."""

    return get_state_dir() / "docs_cache"


def get_files_dir() -> Path:
    """Return files directory (used by generate_prompt tool)."""

    return get_state_dir() / "files"


def get_mcps_dir() -> Path:
    """Return MCP config directory."""

    return get_state_dir() / "mcps"


def get_mcp_servers_json_path() -> Path:
    """Return MCP servers config JSON path.

    Override:
      - UAGENT_MCP_CONFIG: points directly to the mcp_servers.json

    Default (compatibility mode, no migration):
      - <state>/mcps/mcp_servers.json (default state: ~/.uag)
      - if missing, fallback to legacy ~/.scheck/mcps/mcp_servers.json
    """

    env = os.environ.get("UAGENT_MCP_CONFIG")
    if env:
        return _expand(env)

    # Prefer new location
    p_new = get_mcps_dir() / "mcp_servers.json"
    if p_new.exists():
        return p_new

    # Fallback to legacy (read-only)
    p_old = get_legacy_state_dir() / "mcps" / "mcp_servers.json"
    return p_old

def get_history_file_path() -> Path:
    """Return CLI history file path.

    NOTE:
      This is a legacy path (not under state_dir) for backward compatibility.
      Default: ~/.scheck_history

    Override:
      - UAGENT_HISTORY_FILE
    """

    env = os.environ.get("UAGENT_HISTORY_FILE")
    if env:
        return _expand(env)
    return Path.home() / ".scheck_history"

def get_legacy_state_dir() -> Path:
    """Return legacy state directory (read-only fallback).

    Default: ~/.scheck
    Override: UAGENT_LEGACY_STATE_DIR

    NOTE: This does not perform any migration/rename.
    """

    env = os.environ.get("UAGENT_LEGACY_STATE_DIR")
    if env:
        return _expand(env)
    return Path.home() / ".scheck"


def get_compat_state_dirs() -> list[Path]:
    """Return state directories in priority order (new -> legacy)."""

    sd = get_state_dir()
    ld = get_legacy_state_dir()
    if sd == ld:
        return [sd]
    return [sd, ld]

