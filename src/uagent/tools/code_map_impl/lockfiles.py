"""Lockfile and dependency-edge parsing."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .walk import bounded_rglob


def extract_lock_dependencies(root: Path) -> list[dict[str, Any]]:
    """Read lock/asset manifests without invoking package managers."""
    result: list[dict[str, Any]] = []

    def add(manager: str, name: str, version: str = "", source: str = ""):
        if name:
            result.append(
                {"manager": manager, "name": name, "version": version, "source": source}
            )

    # Composer lock
    for path in bounded_rglob(root, "composer.lock"):
        try:
            obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            for section in ("packages", "packages-dev"):
                for item in obj.get(section, []) or []:
                    add(
                        "Composer",
                        str(item.get("name", "")),
                        str(item.get("version", "")),
                        str(path),
                    )
        except Exception:
            pass
    # NuGet lock/assets files. project.assets.json lives under obj/ by
    # design, so its search keeps generated trees (hidden ones are pruned).
    for path in bounded_rglob(root, "packages.lock.json") + bounded_rglob(
        root, "project.assets.json", skip_generated=False
    ):
        try:
            obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            for target in (obj.get("libraries", {}) or {}).keys():
                name, _, ver = target.partition("/")
                add("NuGet", name, ver, str(path))
            for framework in (obj.get("targets", {}) or {}).values():
                for target in framework.keys():
                    name, _, ver = target.partition("/")
                    add("NuGet", name, ver, str(path))
        except Exception:
            pass
    # Bundler lock: GEM specs and dependencies
    for path in bounded_rglob(root, "Gemfile.lock"):
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                m = re.match(r"\s{4}([A-Za-z0-9_.-]+) \(([^)]+)\)", line)
                if m:
                    add("RubyGems", m.group(1), m.group(2), str(path))
        except OSError:
            pass
    # Swift Package.resolved (v1/v2/v3). Xcode keeps a managed copy under
    # the hidden .swiftpm tree, so that directory is exempt from pruning.
    for path in bounded_rglob(root, "Package.resolved", allow_hidden={".swiftpm"}):
        try:
            obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            pins = obj.get("pins", obj.get("object", {}).get("pins", [])) or []
            for pin in pins:
                state = pin.get("state", {}) or {}
                add(
                    "SwiftPM",
                    str(pin.get("identity", pin.get("package", ""))),
                    str(state.get("version", state.get("revision", ""))),
                    str(path),
                )
        except Exception:
            pass
    # Gradle dependency lock files
    for path in bounded_rglob(root, "gradle.lockfile"):
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    coord, _, configs = line.partition("=")
                    bits = coord.split(":")
                    add(
                        "Gradle",
                        ":".join(bits[:2]),
                        bits[2] if len(bits) > 2 else "",
                        str(path),
                    )
        except OSError:
            pass
    # Lua rockspec dependency declarations
    for path in bounded_rglob(root, "*.rockspec"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"dependencies\\s*=\\s*\\{(.*?)\\}", text, re.S)
            if m:
                for dep in re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)):
                    add("LuaRocks", dep, "", str(path))
        except OSError:
            pass
    # Deduplicate lock entries.
    seen = set()
    out = []
    for item in result:
        key = (item["manager"], item["name"], item["version"], item["source"])
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out
