from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


from .i18n import _

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
        description=_("Web Inspector (playwright_inspector) guide"),
    ),
    DocItem(
        name="develop",
        filename="DEVELOP.md",
        description=_("Developer information"),
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
    raise KeyError(_("unknown doc name: %(name)r") % {"name": name})


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
        raise FileNotFoundError(_("doc file not found: %(filename)s") % {"filename": d.filename})
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
        raise FileNotFoundError(_("doc path resolution failed: %(filename)s: %(err)s") % {"filename": d.filename, "err": e})


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
    lines = [_("[docs] Available documents:")]
    for d in items:
        lines.append(f"- {d.name}: {d.description} ({d.filename})")
    lines.append("")
    lines.append(_("Usage:"))
    lines.append(_("  uag docs                 # list"))
    lines.append(_("  uag docs <name>          # show"))
    lines.append(_("  uag docs --path <name>   # show path"))
    lines.append(_("  uag docs --open <name>   # open with OS"))
    return "\n".join(lines)
