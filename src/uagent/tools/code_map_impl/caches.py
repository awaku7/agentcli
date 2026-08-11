"""Read-only local dependency cache and classpath discovery."""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

def resolve_dependency_cache(dep: dict[str, Any], root: Path) -> list[str]:
    """Resolve declared dependencies against local, read-only caches."""
    name = str(dep.get("name", "")); manager = str(dep.get("manager", "")); version = str(dep.get("version", ""))
    candidates: list[Path] = []
    home = Path.home()
    if manager in ("Maven", "Gradle") and ":" in name:
        group, artifact = name.split(":", 1)[:2]
        versions = [version] if version and not version.startswith(("$", "[", "(", "+")) else []
        bases = [home/".m2"/"repository", home/".gradle"/"caches"/"modules-2"/"files-2.1", home/".cache"/"coursier"/"v1"]
        for base in bases:
            for ver in versions or ["*"]:
                candidates.extend(base.joinpath(*group.split("."), artifact, ver).glob("**/*"))
    elif manager == "NuGet":
        package_root=Path(os.environ.get("NUGET_PACKAGES", str(home/".nuget"/"packages")))
        candidates.extend(package_root.joinpath(name.lower(), version.lower() if version else "*").glob("**/*"))
    elif manager == "Composer":
        vendor=root/"vendor"/name
        candidates.extend([vendor, root/"vendor"/"autoload.php"])
    elif manager == "RubyGems":
        candidates.extend((root/"vendor"/"bundle").glob("**/*"))
        candidates.extend((home/".local"/"share"/"gem").glob("**/*"))
    elif manager == "SwiftPM":
        candidates.extend([(root/".build"/"checkouts")/Path(name).stem, home/".swiftpm"])
    elif manager == "DartPub":
        cfg=root/".dart_tool"/"package_config.json"
        if cfg.is_file(): candidates.append(cfg)
    elif manager == "SBT":
        candidates.extend((home/".ivy2"/"cache").glob("**/*"))
        candidates.extend((home/".cache"/"coursier").glob("**/*"))
    elif manager == "LuaRocks":
        candidates.extend((root/"lua_modules").glob("**/*"))
        candidates.extend((home/".luarocks").glob("**/*"))
    elif manager == "R":
        for env_name in ("R_LIBS_USER", "R_LIBS_SITE"):
            for part in os.environ.get(env_name, "").split(os.pathsep):
                if part: candidates.append(Path(part)/name)
    results=[]
    for candidate in candidates:
        try:
            if candidate.exists(): results.append(str(candidate.resolve()))
        except OSError: pass
    return list(dict.fromkeys(results))[:50]


def project_target_frameworks(root: Path) -> list[str]:
    frameworks=[]
    for csproj in root.rglob("*.csproj"):
        try:
            xml=ET.parse(csproj).getroot()
            for node in xml.iter():
                if node.tag.rsplit("}",1)[-1] in ("TargetFramework","TargetFrameworks") and node.text:
                    frameworks.extend(x.strip().lower() for x in node.text.split(";") if x.strip())
        except (ET.ParseError,OSError): pass
    return sorted(set(frameworks))


def dependency_classpath_paths(dep: dict[str, Any], paths: list[str], root: Path) -> list[str]:
    """Convert resolved cache entries into useful source/classpath paths."""
    manager = str(dep.get("manager", ""))
    target_frameworks = project_target_frameworks(root)
    result: list[str] = []
    suffixes = {
        "Maven": {".jar", ".aar"}, "Gradle": {".jar", ".aar"}, "SBT": {".jar"},
        "NuGet": {".dll", ".xml", ".winmd"}, "SwiftPM": {".swiftmodule", ".swiftinterface"},
        "RubyGems": {".rb"}, "Composer": {".php"}, "DartPub": {".dart"},
        "LuaRocks": {".lua", ".so", ".dll"}, "R": {".r", ".R", ".so", ".dll"},
    }.get(manager, set())
    for value in paths:
        path = Path(value)
        if path.is_file():
            if not suffixes or path.suffix in suffixes: result.append(str(path))
        elif path.is_dir():
            if manager in ("RubyGems", "Composer", "DartPub", "LuaRocks", "R"):
                for sub in (path / "lib", path / "src", path):
                    if sub.is_dir(): result.append(str(sub.resolve()))
            if manager == "NuGet" and target_frameworks:
                for family in ("lib", "ref", "runtimes"):
                    base=path / family
                    if base.is_dir():
                        for tfm in target_frameworks:
                            for sub in base.glob(tfm):
                                if sub.is_dir(): result.append(str(sub.resolve()))
            for suffix in suffixes:
                result.extend(str(x.resolve()) for x in path.rglob(f"*{suffix}") if x.is_file())
    return list(dict.fromkeys(result))[:200]


