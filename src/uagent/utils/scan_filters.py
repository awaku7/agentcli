"""uagent.utils.scan_filters

ファイル走査の際に除外するパス判定の共通化。

背景:
- 既存コードでは `".scheck" not in f` のような文字列部分一致で除外している箇所があり、
  誤爆（例: my.scheck_notes.txt）や、OS差（区切り文字・大小文字）による漏れが起き得る。

方針:
- パス要素（ディレクトリ名）として一致するかどうかで判定する。
- 状態ディレクトリ（.scheck / .uag）や .git 等をデフォルト除外対象にする。

注意:
- ここは低レイヤ（基盤）として、tools/ や LLM 依存のモジュールへ依存しない。
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

_DEFAULT_IGNORED_DIRNAMES = (
    ".scheck",
    ".uag",
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
)


def path_has_dirname(path: str, dirname: str) -> bool:
    """Return True if the given path contains the directory name as a path element.

    - Case-insensitive compare (Windows friendly)
    - Matches only full path parts, not substring
    """

    if not dirname:
        return False

    try:
        parts = Path(path).parts
    except Exception:
        # If Path parsing fails for some reason, fallback to conservative behavior.
        return False

    dn = dirname.lower()
    for p in parts:
        try:
            if str(p).lower() == dn:
                return True
        except Exception:
            continue
    return False


def is_ignored_path(
    path: str, ignored_dirnames: Iterable[str] = _DEFAULT_IGNORED_DIRNAMES
) -> bool:
    """Return True if path should be ignored during scanning/indexing."""

    for d in ignored_dirnames:
        if path_has_dirname(path, str(d)):
            return True
    return False
