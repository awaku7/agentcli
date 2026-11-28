"""Bounded directory traversal shared by code_map discovery.

Project discovery must not descend into hidden directories (``.git`` and
friends) or known generated / dependency trees: manifests found there do
not describe this repository, and on Windows an unbounded ``Path.rglob``
also matches names case-insensitively, so ``.git/description`` is picked
up as an R ``DESCRIPTION`` manifest. ``bounded_rglob`` is the common
replacement: it prunes those directories and matches file names
case-sensitively on every platform.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path

SKIP_DIRS = {
    ".git",
    ".svn",
    "__pycache__",
    "node_modules",
    "bin",
    "obj",
    "build",
    "dist",
    ".gradle",
    "target",
    ".next",
    ".nuxt",
    ".output",
    "venv",
    ".venv",
    ".tox",
}


def bounded_rglob(
    root: Path, pattern: str, *, skip_generated: bool = True
) -> list[Path]:
    """Find files under ``root`` matching ``pattern`` without entering
    hidden or (unless ``skip_generated`` is false) generated trees.

    ``pattern`` is a file-name pattern as accepted by ``Path.rglob``
    (an exact name or a glob such as ``*.rockspec``), matched
    case-sensitively. Results are sorted for deterministic output.

    ``skip_generated=False`` still prunes hidden directories but keeps
    generated ones; it exists for files that live in a generated tree by
    design, such as NuGet's ``obj/project.assets.json``.
    """
    matches: list[Path] = []
    if not root.is_dir():
        return matches
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [
            name
            for name in dirnames
            if not name.startswith(".") and not (skip_generated and name in SKIP_DIRS)
        ]
        for filename in filenames:
            if fnmatch.fnmatchcase(filename, pattern):
                matches.append(Path(dirpath) / filename)
    return sorted(matches, key=lambda value: os.path.normcase(str(value)))


__all__ = ["SKIP_DIRS", "bounded_rglob"]
