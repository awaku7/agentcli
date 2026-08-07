"""Lockfile and dependency-edge parsing."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

def extract_lock_dependencies(root: Path) -> list[dict[str, Any]]:
    """Read lock/asset manifests without invoking package managers."""
    result: list[dict[str, Any]] = []
    def add(manager: str, name: str, version: str = "", source: str = ""):
        if name:
            result.append({"manager": manager, "name": name, "version": version, "source": source})
    # Composer lock
    for path in root.rglob("composer.lock"):
        try:
            obj=json.loads(path.read_text(encoding="utf-8", errors="replace"))
            for section in ("packages","packages-dev"):
                for item in obj.get(section,[]) or []: add("Composer",str(item.get("name","")),str(item.get("version","")),str(path))
        except Exception: pass
    # NuGet lock/assets files
    for path in list(root.rglob("packages.lock.json"))+list(root.rglob("project.assets.json")):
        try:
            obj=json.loads(path.read_text(encoding="utf-8", errors="replace"))
            for target in (obj.get("libraries",{}) or {}).keys():
                name,_,ver=target.partition("/"); add("NuGet",name,ver,str(path))
            for framework in (obj.get("targets",{}) or {}).values():
                for target in framework.keys():
                    name,_,ver=target.partition("/"); add("NuGet",name,ver,str(path))
        except Exception: pass
    # Bundler lock: GEM specs and dependencies
    for path in root.rglob("Gemfile.lock"):
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                m=re.match(r"\s{4}([A-Za-z0-9_.-]+) \(([^)]+)\)",line)
                if m: add("RubyGems",m.group(1),m.group(2),str(path))
        except OSError: pass
    # Swift Package.resolved (v1/v2/v3)
    for path in root.rglob("Package.resolved"):
        try:
            obj=json.loads(path.read_text(encoding="utf-8", errors="replace"))
            pins=obj.get("pins",obj.get("object",{}).get("pins",[])) or []
            for pin in pins:
                state=pin.get("state",{}) or {}; add("SwiftPM",str(pin.get("identity",pin.get("package",""))),str(state.get("version",state.get("revision",""))),str(path))
        except Exception: pass
    # Gradle dependency lock files
    for path in root.rglob("gradle.lockfile"):
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    coord,_,configs=line.partition("="); bits=coord.split(":")
                    add("Gradle",":".join(bits[:2]),bits[2] if len(bits)>2 else "",str(path))
        except OSError: pass
    # Lua rockspec dependency declarations
    for path in root.rglob("*.rockspec"):
        try:
            text=path.read_text(encoding="utf-8", errors="replace")
            m=re.search(r"dependencies\\s*=\\s*\\{(.*?)\\}",text,re.S)
            if m:
                for dep in re.findall(r"['\"]([^'\"]+)['\"]",m.group(1)): add("LuaRocks",dep,"",str(path))
        except OSError: pass
    # Deduplicate lock entries.
    seen=set(); out=[]
    for item in result:
        key=(item["manager"],item["name"],item["version"],item["source"])
        if key not in seen: seen.add(key); out.append(item)
    return out


