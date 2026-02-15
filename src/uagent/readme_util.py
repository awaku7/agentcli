# -*- coding: utf-8 -*-
"""readme_util.py

Wheelインストール後に README.md をユーザーへ読ませるためのユーティリティ。

pip/wheel には post-install フックが無いので、起動時（scheck / scheckweb / scheckgui）に
「初回だけ」README を開く方式を採用する。

要件（ユーザー指定）:
- モードA: バージョンが上がるたびに1回表示（同一バージョンでは1回だけ）
- 可能なら OS 既定アプリ（ビューワ）で開く
  - 失敗した場合は標準出力へテキスト表示にフォールバック

実装:
- フラグ: <state>/first_run_readme_shown.json（既定: ~/.uag/first_run_readme_shown.json。旧: ~/.scheck/first_run_readme_shown.json を読み取り参照）
  - JSON: {"shown_versions": ["0.2.8", ...]}
- README の取得: importlib.resources (wheel/zip 環境でも動作)
  - package-data により scheck/README.md が同梱されている前提

注意:
- 例外は握りつぶし、起動を止めない。
"""

from __future__ import annotations

import os
import sys
from typing import Optional

_FLAG_FILENAME = "first_run_readme_shown.json"
_QUICKSTART_FLAG_FILENAME = "first_run_quickstart_shown.json"


def _get_flag_paths() -> list[str]:
    """Return flag file paths in priority order (new -> legacy).

    This keeps backward compatibility when switching state dir from
    ~/.scheck to ~/.uag without migrating files.
    """

    from uagent.utils.paths import get_state_dir, get_legacy_state_dir

    p_new = str(get_state_dir() / _FLAG_FILENAME)
    p_old = str(get_legacy_state_dir() / _FLAG_FILENAME)
    if p_new == p_old:
        return [p_new]
    return [p_new, p_old]


def _get_flag_path() -> str:
    from uagent.utils.paths import get_state_dir

    return str(get_state_dir() / _FLAG_FILENAME)


def _get_installed_version() -> str:
    """Return installed package version if possible."""
    try:
        from importlib.metadata import version as _v

        return _v("uag")
    except Exception:
        return "(unknown)"


def _already_shown(*, current_version: str) -> bool:
    try:
        for p in _get_flag_paths():
            if not os.path.exists(p):
                continue

            import json

            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            shown = data.get("shown_versions") or []
            if str(current_version) in set(map(str, shown)):
                return True
        return False
    except Exception:
        return False


def _mark_shown(*, current_version: str) -> None:
    try:
        p = _get_flag_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)

        import json

        data = {"shown_versions": []}
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f) or data
            except Exception:
                data = {"shown_versions": []}

        shown = data.get("shown_versions") or []
        shown_set = set(map(str, shown))
        shown_set.add(str(current_version))
        data["shown_versions"] = sorted(shown_set)

        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except Exception:
        # 失敗しても起動は続行
        pass


def _read_readme_text() -> Optional[str]:
    """同梱された README.md を読み出す。読めなければ None。"""

    try:
        import importlib.resources as ir

        data = ir.files("uagent").joinpath("README.md")
        if not data.is_file():
            return None
        return data.read_text(encoding="utf-8")
    except Exception:
        return None


def _open_text_with_os_default_app(
    text: str, *, filename_hint: str = "README.md"
) -> bool:
    """Write text to a temp file and open it with OS default app."""

    try:
        import tempfile
        import subprocess

        fd, p = tempfile.mkstemp(prefix="scheck_", suffix="_" + filename_hint)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", errors="replace") as f:
                f.write(text)
        except Exception:
            try:
                os.close(fd)
            except Exception:
                pass
            raise

        if sys.platform == "win32":
            os.startfile(p)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", p])
        else:
            subprocess.Popen(["xdg-open", p])
        return True
    except Exception:
        return False


def maybe_print_readme_on_first_run(
    *, force: bool = False, stream=None, open_with_os: bool = True
) -> bool:
    """初回だけ README を表示する（モードA: バージョンが上がるたびに1回）。

    Returns:
        表示/オープンした場合 True、何もしなかった場合 False
    """

    if stream is None:
        stream = sys.stdout

    current_version = _get_installed_version()

    if (not force) and _already_shown(current_version=current_version):
        return False

    text = _read_readme_text()
    if not text:
        # README が同梱されていない/読めない場合は静かにスキップ
        _mark_shown(current_version=current_version)  # ループ防止
        return False

    opened = False
    if open_with_os:
        opened = _open_text_with_os_default_app(text, filename_hint="README.md")

    if not opened:
        try:
            stream.write("\n" + "=" * 80 + "\n")
            stream.write(f"[scheck] README (first run, version={current_version})\n")
            stream.write("=" * 80 + "\n")
            stream.write(text)
            if not text.endswith("\n"):
                stream.write("\n")
            stream.write("=" * 80 + "\n")
            stream.write("[scheck] End of README\n")
            stream.write("=" * 80 + "\n\n")
            try:
                stream.flush()
            except Exception:
                pass
        except Exception:
            # 出力失敗は無視
            pass

    _mark_shown(current_version=current_version)
    return True


# --- QUICKSTART.md (first run) ---


def _get_quickstart_flag_paths() -> list[str]:
    """Return quickstart flag paths in priority order (new -> legacy)."""

    from uagent.utils.paths import get_state_dir, get_legacy_state_dir

    p_new = str(get_state_dir() / _QUICKSTART_FLAG_FILENAME)
    p_old = str(get_legacy_state_dir() / _QUICKSTART_FLAG_FILENAME)
    if p_new == p_old:
        return [p_new]
    return [p_new, p_old]


def _get_quickstart_flag_path() -> str:
    from uagent.utils.paths import get_state_dir

    return str(get_state_dir() / _QUICKSTART_FLAG_FILENAME)


def _already_shown_quickstart(*, current_version: str) -> bool:
    try:
        for p in _get_quickstart_flag_paths():
            if not os.path.exists(p):
                continue

            import json

            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            shown = data.get("shown_versions") or []
            if str(current_version) in set(map(str, shown)):
                return True
        return False
    except Exception:
        return False


def _mark_shown_quickstart(*, current_version: str) -> None:
    try:
        p = _get_quickstart_flag_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)

        import json

        data = {"shown_versions": []}
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f) or data
            except Exception:
                data = {"shown_versions": []}

        shown = data.get("shown_versions") or []
        shown_set = set(map(str, shown))
        shown_set.add(str(current_version))
        data["shown_versions"] = sorted(shown_set)

        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except Exception:
        # 失敗しても起動は続行
        pass


def _read_quickstart_text() -> Optional[str]:
    """同梱された QUICKSTART.md を読み出す。読めなければ None。"""

    try:
        import importlib.resources as ir

        data = ir.files("uagent").joinpath("QUICKSTART.md")
        if not data.is_file():
            return None
        return data.read_text(encoding="utf-8")
    except Exception:
        return None


def maybe_print_quickstart_on_first_run(
    *, force: bool = False, stream=None, open_with_os: bool = True
) -> bool:
    """初回だけ QUICKSTART を表示する（モードA: バージョンが上がるたびに1回）。

    Returns:
        表示/オープンした場合 True、何もしなかった場合 False
    """

    if stream is None:
        stream = sys.stdout

    current_version = _get_installed_version()

    if (not force) and _already_shown_quickstart(current_version=current_version):
        return False

    text = _read_quickstart_text()
    if not text:
        # QUICKSTART が同梱されていない/読めない場合は静かにスキップ
        _mark_shown_quickstart(current_version=current_version)  # ループ防止
        return False

    opened = False
    if open_with_os:
        opened = _open_text_with_os_default_app(text, filename_hint="QUICKSTART.md")

    if not opened:
        try:
            stream.write("\n" + "=" * 80 + "\n")
            stream.write(
                f"[scheck] QUICKSTART (first run, version={current_version})\n"
            )
            stream.write("=" * 80 + "\n")
            stream.write(text)
            if not text.endswith("\n"):
                stream.write("\n")
            stream.write("=" * 80 + "\n")
            stream.write("[scheck] End of QUICKSTART\n")
            stream.write("=" * 80 + "\n\n")
            try:
                stream.flush()
            except Exception:
                pass
        except Exception:
            # 出力失敗は無視
            pass

    _mark_shown_quickstart(current_version=current_version)
    return True
