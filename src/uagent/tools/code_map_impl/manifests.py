"""Project manifest and declared dependency parsing."""

from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .cmake import cmake_active_source


def extract_project_dependencies(
    root: Path, project_files: list[Path]
) -> list[dict[str, Any]]:
    """Extract declared dependencies from common project/manifest files.

    This is metadata extraction; it does not execute package managers or resolve
    remote artifacts. Local project references are represented as paths/names.
    """
    deps: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(project: Path, manager: str, name: str, version: str = ""):
        name = name.strip()
        if not name:
            return
        key = (str(project.resolve()), name)
        if key not in seen:
            seen.add(key)
            deps.append(
                {
                    "project": str(project.resolve()),
                    "manager": manager,
                    "name": name,
                    "version": version.strip(),
                }
            )

    for project in project_files:
        suffix = project.name.lower()
        try:
            text = project.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if suffix.endswith(".csproj"):
            try:
                root_xml = ET.parse(project).getroot()
                for node in root_xml.iter():
                    tag = node.tag.rsplit("}", 1)[-1]
                    if tag in ("PackageReference", "ProjectReference") and node.get(
                        "Include"
                    ):
                        add(
                            project,
                            (
                                "NuGet"
                                if tag == "PackageReference"
                                else "ProjectReference"
                            ),
                            node.get("Include", ""),
                            node.get("Version", ""),
                        )
            except (ET.ParseError, OSError):
                pass
        elif suffix == "pom.xml":
            try:
                root_xml = ET.fromstring(text)
                for node in root_xml.iter():
                    tag = node.tag.rsplit("}", 1)[-1]
                    if tag in ("parent", "dependencyManagement"):
                        vals = {c.tag.rsplit("}", 1)[-1]: (c.text or "") for c in node}
                        if vals.get("groupId") and vals.get("artifactId"):
                            add(
                                project,
                                "MavenParent" if tag == "parent" else "MavenBOM",
                                vals.get("groupId", "")
                                + ":"
                                + vals.get("artifactId", ""),
                                vals.get("version", ""),
                            )
                for node in root_xml.iter():
                    if node.tag.rsplit("}", 1)[-1] == "dependency":
                        vals = {c.tag.rsplit("}", 1)[-1]: (c.text or "") for c in node}
                        add(
                            project,
                            "Maven",
                            ":".join(
                                x
                                for x in (
                                    vals.get("groupId", ""),
                                    vals.get("artifactId", ""),
                                )
                                if x
                            ),
                            vals.get("version", ""),
                        )
            except ET.ParseError:
                pass
        elif suffix in ("build.gradle", "build.gradle.kts"):
            for m in re.finditer(
                r"\b(?:implementation|api|compileOnly|runtimeOnly|testImplementation|kapt|classpath)\s*[( ]\s*[\"']([^\"']+)",
                text,
            ):
                add(project, "Gradle", m.group(1))
            for m in re.finditer(r"\bproject\s*\(\s*[\"']([^\"']+)[\"']\s*\)", text):
                add(project, "GradleProject", m.group(1))
        elif suffix == "cargo.toml":
            in_deps = False
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("["):
                    in_deps = stripped in (
                        "[dependencies]",
                        "[dev-dependencies]",
                        "[build-dependencies]",
                    )
                elif in_deps and "=" in stripped and not stripped.startswith("#"):
                    name, val = stripped.split("=", 1)
                    add(project, "Cargo", name.strip(), val.strip().strip('"'))
        elif suffix == "cmakelists.txt":
            text = cmake_active_source(text)
            for m in re.finditer(
                r"\b(?:set|list)\s*\(\s*(CMAKE_TOOLCHAIN_FILE|CMAKE_MODULE_PATH)\s+([^)]*)\)",
                text,
                re.IGNORECASE,
            ):
                for value in re.findall(r"[A-Za-z0-9_./\\-]+", m.group(2)):
                    add(project, "CMakeToolchain", value)
            for m in re.finditer(
                r"\bfind_package\s*\(\s*([A-Za-z0-9_+.-]+)", text, re.IGNORECASE
            ):
                add(project, "CMake", m.group(1))
            for m in re.finditer(
                r"\btarget_link_libraries\s*\(\s*[^\s)]+\s+([^)]*)\)",
                text,
                re.IGNORECASE | re.DOTALL,
            ):
                for lib in re.findall(r"[A-Za-z0-9_+.-]+", m.group(1)):
                    add(project, "CMakeLink", lib)
        elif suffix == "libs.versions.toml":
            section = ""
            versions = {}
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("["):
                    section = stripped.strip("[]")
                elif "=" in stripped and not stripped.startswith("#"):
                    key, val = stripped.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"')
                    if section == "versions":
                        versions[key] = val
                    elif section in ("libraries", "plugins"):
                        add(project, "GradleCatalog", key, val)
        elif suffix == "package.json":
            try:
                obj = json.loads(text)
                for section in (
                    "dependencies",
                    "devDependencies",
                    "peerDependencies",
                    "optionalDependencies",
                ):
                    for name, ver in (obj.get(section, {}) or {}).items():
                        add(project, "npm", name, str(ver))
            except Exception:
                pass
        elif suffix == "composer.json":
            try:
                obj = json.loads(text)
                for section in ("require", "require-dev"):
                    for name, ver in (obj.get(section, {}) or {}).items():
                        add(project, "Composer", name, str(ver))
            except Exception:
                pass
        elif suffix == "gemfile":
            for m in re.finditer(r"\bgem\s+['\"]([^'\"]+)", text):
                add(project, "RubyGems", m.group(1))
        elif suffix in ("package.swift",):
            for m in re.finditer(
                r'\.package\s*\([^\n]*?(?:url|path)\s*:\s*"([^"]+)', text
            ):
                add(project, "SwiftPM", m.group(1))
        elif suffix == "pubspec.yaml":
            in_deps = False
            for line in text.splitlines():
                if line.strip() in ("dependencies:", "dev_dependencies:"):
                    in_deps = True
                    continue
                if in_deps and line and not line.startswith((" ", "\t")):
                    in_deps = False
                if in_deps:
                    m = re.match(r"\s{2}([A-Za-z0-9_-]+)\s*:\s*(.*)", line)
                    if m:
                        add(project, "DartPub", m.group(1), m.group(2).strip())
        elif suffix == "build.sbt":
            for m in re.finditer(
                r"[\"']([^\"']+)[\"']\s*(%%?|%)\s*[\"']([^\"']+)[\"']\s*%\s*[\"']([^\"']+)[\"']",
                text,
            ):
                org, op, artifact, ver = m.groups()
                add(project, "SBT", org + ":" + artifact, ver)
        elif suffix == "cmakecache.txt":
            for line in text.splitlines():
                m = re.match(r"([^:#]+):[^=]*=(.*)", line)
                if m and m.group(1) in (
                    "CMAKE_TOOLCHAIN_FILE",
                    "CMAKE_MODULE_PATH",
                    "CMAKE_PREFIX_PATH",
                    "CMAKE_CXX_COMPILER",
                    "CMAKE_C_COMPILER",
                ):
                    add(project, "CMakeCache", m.group(1), m.group(2).strip())
        elif suffix == "description":
            for line in text.splitlines():
                if re.match(r"^(Imports|Depends):", line):
                    for name in line.split(":", 1)[1].split(","):
                        add(project, "R", name)
        elif suffix.endswith(".rockspec"):
            m = re.search(r"dependencies\s*=\s*\{(.*?)\}", text, re.S)
            if m:
                for name in re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)):
                    add(project, "LuaRocks", name)
    return deps


def extract_local_artifact_edges(
    dependencies: list[dict[str, Any]], root: Path
) -> list[dict[str, str]]:
    """Walk local POM/module/nuspec metadata for additional dependency edges."""
    edges = []

    def add(manager, source, target):
        if source and target:
            edges.append({"manager": manager, "source": source, "target": target})

    home = Path.home()
    for dep in dependencies:
        manager = str(dep.get("manager", ""))
        name = str(dep.get("name", ""))
        version = str(dep.get("version", ""))
        candidates = []
        if manager in ("Maven", "Gradle", "SBT") and ":" in name:
            group, artifact = name.split(":", 1)[:2]
            for base in (
                home / ".m2" / "repository",
                home / ".gradle" / "caches" / "modules-2" / "files-2.1",
                home / ".ivy2" / "cache",
            ):
                if version and not version.startswith(("$", "[", "(", "+")):
                    candidates.extend(
                        base.joinpath(*group.split("."), artifact, version).glob(
                            "*.pom"
                        )
                    )
                    candidates.extend(
                        base.joinpath(*group.split("."), artifact, version).glob(
                            "*.module"
                        )
                    )
                else:
                    candidates.extend(base.glob(f"**/{artifact}/*.pom"))
                    candidates.extend(base.glob(f"**/{artifact}/*.module"))
            for meta in candidates[:100]:
                try:
                    text = meta.read_text(encoding="utf-8", errors="replace")
                    if meta.suffix == ".pom":
                        xml = ET.fromstring(text)
                        for node in xml.iter():
                            if node.tag.rsplit("}", 1)[-1] == "dependency":
                                vals = {
                                    c.tag.rsplit("}", 1)[-1]: (c.text or "")
                                    for c in node
                                }
                                target = ":".join(
                                    x
                                    for x in (
                                        vals.get("groupId", ""),
                                        vals.get("artifactId", ""),
                                    )
                                    if x
                                )
                                add(manager, name, target)
                                if edges:
                                    edges[-1]["scope"] = vals.get("scope", "compile")
                                    edges[-1]["optional"] = (
                                        vals.get("optional", "false").lower() == "true"
                                    )
                                    excluded = [
                                        child.text or ""
                                        for group in node
                                        if group.tag.rsplit("}", 1)[-1] == "exclusions"
                                        for child in group
                                        if child.tag.rsplit("}", 1)[-1] == "exclusion"
                                    ]
                                    if excluded:
                                        edges[-1]["exclusions"] = excluded
                    else:
                        obj = json.loads(text)
                        for variant in obj.get("variants", []) or []:
                            for item in variant.get("dependencies", []) or []:
                                target = (
                                    item.get("group", "")
                                    + ":"
                                    + item.get("module", item.get("name", ""))
                                )
                                add(manager, name, target.strip(":"))
                except Exception:
                    pass
        elif manager == "NuGet":
            roots = [
                Path(
                    os.environ.get("NUGET_PACKAGES", str(home / ".nuget" / "packages"))
                )
                / name.lower()
            ]
            for base in roots:
                for nuspec in base.glob("**/*.nuspec"):
                    try:
                        xml = ET.parse(nuspec).getroot()
                        for node in xml.iter():
                            if node.tag.rsplit("}", 1)[-1] == "dependency" and node.get(
                                "id"
                            ):
                                add("NuGet", name, node.get("id", ""))
                    except Exception:
                        pass
        elif manager == "Composer":
            vendor = root / "vendor" / name
            if vendor.is_dir():
                for php in vendor.rglob("*.php"):
                    add("ComposerAutoload", name, str(php))
    seen = set()
    out = []
    for e in edges:
        key = tuple(e.values())
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


def extract_recursive_artifact_edges(
    initial: list[dict[str, Any]], root: Path, max_depth: int = 8
) -> list[dict[str, str]]:
    """Breadth-first expansion of local artifact metadata without downloads."""
    edges = []
    queue = [(dict(x), 0) for x in initial]
    seen = set()
    while queue:
        dep, depth = queue.pop(0)
        key = (dep.get("manager", ""), dep.get("name", ""), dep.get("version", ""))
        if key in seen or depth >= max_depth:
            continue
        seen.add(key)
        local = extract_local_artifact_edges([dep], root)
        for edge in local:
            edges.append(edge)
            manager = edge["manager"]
            if manager in ("Maven", "Gradle", "SBT", "NuGet"):
                queue.append(
                    (
                        {"manager": manager, "name": edge["target"], "version": ""},
                        depth + 1,
                    )
                )
    unique = []
    keys = set()
    for edge in edges:
        key = tuple(edge.values())
        if key not in keys:
            keys.add(key)
            unique.append(edge)
    return unique


def extract_manifest_graph(root: Path) -> list[dict[str, str]]:
    """Extract additional local dependency edges from manifests and caches."""
    edges = []

    def add(manager, source, target):
        if source and target:
            edges.append({"manager": manager, "source": source, "target": target})

    # Composer PSR-4/classmap declarations
    for path in root.rglob("composer.json"):
        try:
            obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            autoload = obj.get("autoload", {}) or {}
            for section in ("psr-4", "psr-0", "classmap", "files"):
                val = autoload.get(section, {})
                if isinstance(val, dict):
                    for namespace, target in val.items():
                        add("ComposerAutoload", str(path), f"{namespace}->{target}")
                elif isinstance(val, list):
                    for target in val:
                        add("ComposerAutoload", str(path), str(target))
        except Exception:
            pass
    # Composer generated classmap: map fully-qualified classes to concrete files.
    for path in root.rglob("autoload_classmap.php"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r'"([^"]+)"\s*=>\s*"([^"]+\.php)"', text):
                target = (
                    str((path.parent.parent / m.group(2)).resolve())
                    if not Path(m.group(2)).is_absolute()
                    else m.group(2)
                )
                add("ComposerClassmap", m.group(1), target)
        except OSError:
            pass

    # Composer generated PSR-4/PSR-0 maps.
    for path in list(root.rglob("autoload_psr4.php")) + list(
        root.rglob("autoload_psr0.php")
    ):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r'"([^"]+)"\s*=>\s*array\s*\(\s*"([^"]+)"', text):
                add(
                    "ComposerAutoload",
                    m.group(1),
                    str((path.parent.parent / m.group(2)).resolve()),
                )
        except OSError:
            pass

    # Swift Package.swift local/URL package declarations and Package.resolved pins
    for path in root.rglob("Package.swift"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(
                r'\.package\s*\([^\n]*?(?:url|path)\s*:\s*"([^"]+)', text
            ):
                add("SwiftPM", str(path), m.group(1))
        except OSError:
            pass
    # NuGet target-framework and dependency groups from assets files
    for path in list(root.rglob("project.assets.json")) + list(
        root.rglob("packages.lock.json")
    ):
        try:
            obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            for framework, libs in (obj.get("targets", {}) or {}).items():
                for source, meta in (libs or {}).items():
                    source_name = source.split("/", 1)[0]
                    for target in meta.get("dependencies", {}) or {}:
                        add(f"NuGet:{framework}", source_name, str(target))
        except Exception:
            pass
    # Swift Package.resolved pins are linked to the package manifest when present.
    for path in root.rglob("Package.resolved"):
        try:
            obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            pins = obj.get("pins", obj.get("object", {}).get("pins", [])) or []
            manifest = path.parent / "Package.swift"
            source = str(manifest if manifest.is_file() else path)
            for pin in pins:
                identity = str(pin.get("identity", pin.get("package", "")))
                state = pin.get("state", {}) or {}
                target = (
                    identity
                    + "@"
                    + str(state.get("version", state.get("revision", "")))
                )
                add("SwiftPMResolved", source, target)
        except Exception:
            pass

    # R installed DESCRIPTION dependency edges (local libraries only)
    r_roots = []
    for env_name in ("R_LIBS_USER", "R_LIBS_SITE"):
        r_roots.extend(
            Path(x) for x in os.environ.get(env_name, "").split(os.pathsep) if x
        )
    r_roots.extend([root / "R_libs", root / "library"])
    for base in r_roots:
        if not base.is_dir():
            continue
        for desc in base.glob("*/DESCRIPTION"):
            try:
                for line in desc.read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines():
                    if re.match(r"^(Imports|Depends|Suggests):", line):
                        for target in line.split(":", 1)[1].split(","):
                            token = target.strip()
                            match = re.match(r"([^ (]+)\s*(?:\(([^)]+)\))?", token)
                            if match:
                                version = match.group(2)
                                add(
                                    "R",
                                    desc.parent.name,
                                    match.group(1)
                                    + ((" " + version) if version else ""),
                                )
            except OSError:
                pass
    # Local rockspec dependency edges
    for path in root.rglob("*.rockspec"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"dependencies\\s*=\\s*\\{(.*?)\\}", text, re.S)
            if m:
                for target in re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)):
                    add("LuaRocks", path.stem, target)
        except OSError:
            pass
    seen = set()
    result = []
    for edge in edges:
        key = tuple(edge.values())
        if key not in seen:
            seen.add(key)
            result.append(edge)
    return result


def extract_dependency_edges(root: Path) -> list[dict[str, str]]:
    """Extract dependency-to-dependency edges from lock manifests."""
    edges = []

    def add(manager, source, target):
        if source and target:
            edges.append({"manager": manager, "source": source, "target": target})

    for path in root.rglob("composer.lock"):
        try:
            obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            for section in ("packages", "packages-dev"):
                for item in obj.get(section, []) or []:
                    source = str(item.get("name", ""))
                    for target in item.get("require", {}) or {}:
                        add("Composer", source, str(target))
        except Exception:
            pass
    for path in list(root.rglob("packages.lock.json")) + list(
        root.rglob("project.assets.json")
    ):
        try:
            obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            for framework in (obj.get("targets", {}) or {}).values():
                for source, meta in framework.items():
                    source_name = source.split("/", 1)[0]
                    for target in meta.get("dependencies", {}) or {}:
                        add("NuGet", source_name, str(target))
        except Exception:
            pass
    for path in root.rglob("Gemfile.lock"):
        try:
            source = ""
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                m = re.match(r"\s{4}([A-Za-z0-9_.-]+) \(([^)]+)\)", line)
                if m:
                    source = m.group(1)
                elif source and re.match(r"\s{6,}[A-Za-z0-9_.-]+", line):
                    add("RubyGems", source, line.strip().split()[0])
                elif not line.startswith(" "):
                    source = ""
        except OSError:
            pass
    seen = set()
    out = []
    for edge in edges:
        key = (edge["manager"], edge["source"], edge["target"])
        if key not in seen:
            seen.add(key)
            out.append(edge)
    return out
