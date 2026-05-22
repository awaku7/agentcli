from __future__ import annotations

import os
import subprocess


def open_image_with_default_app(path: str) -> bool:
    """Windows の既定アプリでファイルを開く。成功/失敗を返す。"""
    try:
        expanded = os.path.expandvars(os.path.expanduser(path))
        abspath = os.path.abspath(expanded)

        if not os.path.exists(abspath):
            return False

        if os.name == "nt" and hasattr(os, "startfile"):
            os.startfile(abspath)  # type: ignore[attr-defined]
            return True

        subprocess.Popen(
            ["xdg-open", abspath],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False
