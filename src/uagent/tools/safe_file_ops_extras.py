# tools/safe_file_ops_extras.py
"""safe_file_ops_extras

既存 tools.safe_file_ops の設計に合わせ、追加ツールが使いやすい公開APIを提供する。

背景:
- safe_file_ops.py は safe_create_file/safe_delete_file/safe_rename_path 等の「実行」を提供している。
- 追加ツール（replace_in_file 等）は、
  - 危険パス判定
  - workdir 配下への制限
  - 上書き前バックアップ(.org/.orgN)
  などの「ユーティリティ」が必要。

このファイルは safe_file_ops.py を壊さずに機能追加するための補助モジュール。
（既存モジュールに直接追記してもよいが、変更範囲を限定するため分離）

提供関数:
- is_path_dangerous(path) -> bool
- ensure_within_workdir(path) -> str  (絶対パス化して返す)
- make_backup_before_overwrite(path) -> str  (.org/.orgN を作成して返す)

注意:
- workdir は os.getcwd() の実体（resolve）を基準とする。
- ensure_within_workdir は workdir 外なら例外を投げる。
"""

from __future__ import annotations

import os
from pathlib import Path


def _resolve_path(p: str) -> str:
    return str(Path(p).expanduser().resolve())


def _workdir_root() -> str:
    return str(Path(os.getcwd()).resolve())


def _is_under(root: str, target: str) -> bool:
    try:
        Path(target).relative_to(Path(root))
        return True
    except Exception:
        return False


def is_path_dangerous(p: str) -> bool:
    """危険パス判定。

    true となる条件:
    - '..' を含む（簡易）
    - 絶対パス
    - workdir(cwd) 配下ではない（resolve後）

    safe_file_ops の trigger 条件と同等。
    """
    if not p:
        return True

    try:
        path_obj = Path(p)
    except Exception:
        return True

    if ".." in str(p).replace("\\", "/"):
        return True

    if path_obj.is_absolute():
        return True

    resolved = _resolve_path(p)
    if not _is_under(_workdir_root(), resolved):
        return True

    return False


def ensure_within_workdir(p: str) -> str:
    """p を resolve し、workdir 配下であることを保証して絶対パスを返す。"""
    if not p:
        raise ValueError("path is empty")

    resolved = _resolve_path(p)
    root = _workdir_root()
    if not _is_under(root, resolved):
        raise PermissionError(f"path is outside workdir: root={root} path={resolved}")

    return resolved


def _next_backup_name(filename: str) -> str:
    base = filename + ".org"
    if not os.path.exists(base):
        return base

    i = 1
    while True:
        cand = f"{base}{i}"
        if not os.path.exists(cand):
            return cand
        i += 1


def make_backup_before_overwrite(filename: str) -> str:
    """filename のバックアップ(.org/.orgN)を作成して、そのパスを返す。

    - filename が存在しない場合は例外
    - バイトコピーで保存
    """
    if not os.path.exists(filename):
        raise FileNotFoundError(f"file not found: {filename}")

    backup_path = _next_backup_name(filename)
    Path(backup_path).parent.mkdir(parents=True, exist_ok=True)

    with open(filename, "rb") as rf, open(backup_path, "wb") as wf:
        wf.write(rf.read())

    return backup_path
