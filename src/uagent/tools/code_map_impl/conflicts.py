"""Dependency version conflict helpers."""
from __future__ import annotations
import re
from typing import Any

def _version_key(value: str) -> tuple:
    parts=re.findall(r"\d+|[A-Za-z]+",value or "")
    return tuple((0,int(x)) if x.isdigit() else (1,x.lower()) for x in parts)


def normalize_dependency_versions(dependencies: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Choose a deterministic highest local version and report conflicts."""
    groups={}
    for dep in dependencies:
        key=(dep.get("manager",""),dep.get("name","")); groups.setdefault(key,[]).append(dep)
    normalized=[]; conflicts=[]
    for key,items in groups.items():
        versions={str(x.get("version","")) for x in items if x.get("version")}
        if len(versions)>1:
            chosen=max(versions,key=_version_key); conflicts.append({"manager":key[0],"name":key[1],"versions":sorted(versions),"selected":chosen})
        else: chosen=next(iter(versions),"")
        selected=next((x for x in items if str(x.get("version",""))==chosen),items[0])
        normalized.append(selected)
    return normalized,conflicts


