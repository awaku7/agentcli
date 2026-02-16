from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class DocItem:
    """A bundled documentation item."""

    name: str
    filename: str
    description: str


_DOCS: List[DocItem] = [
    DocItem(
        name="webinspect",
        filename="WEBINSPECTER.md",
        description="Web Inspector（playwright_inspector）の説明",
    ),
    DocItem(
        name="develop",
        filename="DEVELOP.md",
        description="開発者向け情報",
    ),
]


def _package_doc_path(filename: str) -> Tuple[Optional[Path], str]:
    """Return (path, mode).

    mode:
      - 'resources': resolved via importlib.resources
      - 'filesystem': resolved via fallback filesystem path
    """

    # Prefer importlib.resources for wheel installs
    try:
        import importlib.resources as r

        p = r.files("uagent").joinpath("docs", filename)
        # In some environments, this may not be a pathlib.Path, but it implements
        # read_text. For --path/--open we try to materialize it.
        try:
            fs_path = Path(str(p))
            return fs_path, "resources"
        except Exception:
            return None, "resources"
    except Exception:
        pass

    # Fallback: source tree / editable installs
    base = Path(__file__).resolve().parent
    fs_path = base.joinpath("docs", filename)
    if fs_path.exists():
        return fs_path, "filesystem"
    return None, "filesystem"


def list_docs() -> List[DocItem]:
    return list(_DOCS)


def resolve_doc(name: str) -> DocItem:
    key = (name or "").strip().lower()
    for d in _DOCS:
        if d.name == key:
            return d
    raise KeyError(f"unknown doc name: {name!r}")


def _read_via_resources(filename: str) -> str:
    import importlib.resources as r

    return r.files("uagent").joinpath("docs", filename).read_text(encoding="utf-8")


def read_doc_text(name: str) -> str:
    d = resolve_doc(name)

    # Prefer resources read
    try:
        return _read_via_resources(d.filename)
    except Exception:
        pass

    # Fallback to filesystem
    p, _ = _package_doc_path(d.filename)
    if p is None:
        raise FileNotFoundError(f"doc file not found: {d.filename}")
    return p.read_text(encoding="utf-8")


def get_doc_path(name: str) -> Path:
    d = resolve_doc(name)
    p, mode = _package_doc_path(d.filename)
    if p is not None and p.exists():
        return p

    # If resources can't be represented as a stable filesystem path, materialize.
    try:
        import importlib.resources as r

        ref = r.files("uagent").joinpath("docs", d.filename)
        # as_file provides a temporary file location
        from importlib.resources import as_file

        with as_file(ref) as tmp_path:
            # Copy to a persistent temp location for opening
            from uagent.utils.paths import get_docs_cache_dir

            tmp_dir = get_docs_cache_dir()
            tmp_dir.mkdir(parents=True, exist_ok=True)
            dst = tmp_dir / d.filename
            dst.write_text(tmp_path.read_text(encoding="utf-8"), encoding="utf-8")
            return dst
    except Exception as e:
        raise FileNotFoundError(f"doc path resolution failed: {d.filename}: {e}")


def open_path_with_os(path: Path) -> None:
    """Open a file using OS default handler."""

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))

    if os.name == "nt":
        os.startfile(str(p))  # type: ignore[attr-defined]
        return

    if sys.platform == "darwin":
        subprocess.Popen(["open", str(p)])
        return

    subprocess.Popen(["xdg-open", str(p)])


def format_docs_list(items: Iterable[DocItem]) -> str:
    lines = ["[docs] 利用可能なドキュメント:"]
    for d in items:
        lines.append(f"- {d.name}: {d.description} ({d.filename})")
    lines.append("")
    lines.append("使い方:")
    lines.append("  uag docs                 # 一覧")
    lines.append("  uag docs <name>          # 内容表示")
    lines.append("  uag docs --path <name>   # パス表示")
    lines.append("  uag docs --open <name>   # OS既定で開く")
    return "\n".join(lines)
