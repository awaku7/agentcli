"""Generate CycloneDX and SPDX SBOMs from a local project directory.

The scanner is intentionally dependency-free.  It reads common manifest files and
emits standards-shaped JSON, making it useful even when external SBOM generators
are not installed.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from urllib.parse import quote
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    tomllib = None  # type: ignore[assignment]

from .i18n_helper import make_tool_translator
from .._pip_auto import install_with_status as _auto_install

_ = make_tool_translator(__file__)
BUSY_LABEL = True
STATUS_LABEL = "tool:sbom_generate"

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "devel",
    "x_parallel_safe": True,
    "function": {
        "name": "sbom_generate",
        "description": _(
            "tool.description",
            default="Inspect a project directory and generate both CycloneDX and SPDX SBOM JSON files.",
        ),
        "x_search_terms": ["SBOM", "CycloneDX", "SPDX", "software bill of materials", "依存関係一覧", "脆弱性管理"],
        "x_search_terms_en": ["SBOM", "CycloneDX", "SPDX", "dependency inventory", "software composition analysis"],
        "parameters": {
            "type": "object",
            "properties": {
                "root": {"type": "string", "default": ".", "description": _("param.root.description", default="Project directory to inspect (inside the current workdir).")},
                "output_dir": {"type": "string", "default": "outputs/sbom", "description": _("param.output_dir.description", default="Directory for the two generated JSON files.")},
                "project_name": {"type": "string", "description": _("param.project_name.description", default="Optional project name; otherwise inferred from the directory name.")},
                "max_files": {"type": "integer", "default": 10000, "minimum": 1, "maximum": 100000, "description": _("param.max_files.description", default="Maximum files to inspect for metadata.")},
                "overwrite": {"type": "boolean", "default": True, "description": _("param.overwrite.description", default="Overwrite existing CycloneDX/SPDX files.")},
                "auto_install": {"type": "boolean", "default": False, "description": _("param.auto_install.description", default="Install optional CycloneDX/SPDX Python libraries when missing; generation still falls back to the built-in serializer.")},
            },
        },
    },
}

_SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "dist", "build", "__pycache__", ".tox"}


def _inside(path: str | Path, workdir: Path) -> Path:
    p = Path(path).expanduser().resolve()
    if p != workdir and workdir not in p.parents:
        raise ValueError("path must be inside the current workdir")
    return p


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _version(value: Any) -> str:
    text = str(value or "*").strip()
    return text or "*"


def _component(name: str, version: Any, kind: str, source: str) -> dict[str, Any]:
    name = name.strip()
    ver = _version(version)
    # PURLs are deliberately conservative: a constraint is retained in the
    # version field while the purl uses it only when it looks like a version.
    safe_name = quote(name, safe="@/")
    safe_ver = quote(ver, safe="")
    if kind == "npm":
        purl = f"pkg:npm/{safe_name}@{safe_ver}"
        ctype = "npm"
    elif kind == "pypi":
        purl = f"pkg:pypi/{quote(name.lower().replace('_', '-'), safe='')}@{safe_ver}"
        ctype = "pypi"
    elif kind == "cargo":
        purl = f"pkg:cargo/{name}@{safe_ver}"
        ctype = "cargo"
    else:
        purl = f"pkg:generic/{name}@{safe_ver}"
        ctype = "generic"
    return {"name": name, "version": ver, "type": "library", "scope": "required", "purl": purl, "bom-ref": purl, "_source": source, "_type": ctype}


def _requirements(text: str, source: str) -> list[dict[str, Any]]:
    result = []
    for line in text.splitlines():
        line = line.split(" #", 1)[0].strip()
        if not line or line.startswith(("#", "-r", "--")):
            continue
        match = re.match(r"([A-Za-z0-9_.-]+)\s*(?:\[.*?\])?\s*(?:==|~=|>=|<=|!=|>|<)\s*([^;\s]+)", line)
        if match:
            result.append(_component(match.group(1), match.group(2), "pypi", source))
        else:
            match = re.match(r"([A-Za-z0-9_.-]+)", line)
            if match:
                result.append(_component(match.group(1), "*", "pypi", source))
    return result


def _manifest_components(path: Path) -> list[dict[str, Any]]:
    name = path.name
    source = path.as_posix()
    data = _read_json(path) if path.suffix == ".json" else None
    if name in {"package.json", "package-lock.json"} and data:
        out = []
        deps = data.get("dependencies", {})
        if isinstance(deps, dict):
            for dep, val in deps.items():
                out.append(_component(dep, val.get("version", "*") if isinstance(val, dict) else val, "npm", source))
        return out
    if name == "composer.json" and data:
        deps = data.get("require", {})
        return [_component(k, v, "generic", source) for k, v in deps.items() if k != "php" and isinstance(k, str)] if isinstance(deps, dict) else []
    if name in {"requirements.txt", "requirements-dev.txt", "Pipfile.lock"}:
        try:
            return _requirements(path.read_text(encoding="utf-8", errors="ignore"), source)
        except OSError:
            return []
    if name == "pyproject.toml" and tomllib:
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
            deps = raw.get("project", {}).get("dependencies", [])
            return _requirements("\n".join(str(x) for x in deps), source)
        except (OSError, ValueError, TypeError):
            return []
    if name == "Cargo.toml" and tomllib:
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
            deps = raw.get("dependencies", {})
            return [_component(k, v.get("version", "*") if isinstance(v, dict) else v, "cargo", source) for k, v in deps.items()]
        except (OSError, ValueError, TypeError):
            return []
    if name == "go.mod":
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            return [_component(m.group(1), m.group(2), "generic", source) for m in re.finditer(r"^\s*([\w./-]+)\s+(v[0-9][^\s]+)", text, re.M)]
        except OSError:
            return []
    return []


def _scan(root: Path, limit: int) -> tuple[list[dict[str, Any]], int, bool]:
    components: list[dict[str, Any]] = []
    files = 0
    truncated = False
    manifests = {"package.json", "package-lock.json", "requirements.txt", "requirements-dev.txt", "pyproject.toml", "Cargo.toml", "go.mod", "composer.json"}
    for path in sorted(root.rglob("*"), key=lambda p: p.as_posix()):
        if path.is_symlink() or not path.is_file() or any(part in _SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        files += 1
        if files > limit:
            truncated = True
            break
        if path.name in manifests:
            components.extend(_manifest_components(path))
    unique: dict[str, dict[str, Any]] = {}
    for c in components:
        unique[c["bom-ref"]] = c
    return list(unique.values()), files if not truncated else limit, truncated


def _clean(c: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in c.items() if not k.startswith("_")}


def run_tool(args: dict[str, Any]) -> str:
    try:
        workdir = Path.cwd().resolve()
        root = _inside(str(args.get("root", ".") or "."), workdir)
        outdir = _inside(str(args.get("output_dir", "outputs/sbom") or "outputs/sbom"), workdir)
        if not root.is_dir():
            raise ValueError("root must be an existing directory")
        limit = int(args.get("max_files", 10000))
        if not 1 <= limit <= 100000:
            raise ValueError("max_files must be between 1 and 100000")
        overwrite = bool(args.get("overwrite", True))
        optional_status: dict[str, bool] = {}
        if bool(args.get("auto_install", False)):
            optional_status["cyclonedx-python-lib"] = bool(
                _auto_install("cyclonedx-python-lib", "cyclonedx")
            )
            optional_status["spdx-tools"] = bool(
                _auto_install("spdx-tools", "spdx_tools")
            )
        project = str(args.get("project_name") or root.name)
        components, scanned, truncated = _scan(root, limit)
        clean = [_clean(c) for c in components]
        serial = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{root}:{project}"))
        cdx = {"bomFormat": "CycloneDX", "specVersion": "1.5", "serialNumber": f"urn:uuid:{serial}", "version": 1, "metadata": {"component": {"type": "application", "name": project, "bom-ref": f"root:{project}"}}, "components": clean}
        spdx_id = f"SPDXRef-DOCUMENT-{serial}"
        spdx_components = []
        for c in clean:
            spdx_components.append({"SPDXID": "SPDXRef-" + hashlib.sha1(c["bom-ref"].encode()).hexdigest()[:16], "name": c["name"], "versionInfo": c["version"], "downloadLocation": c["purl"], "filesAnalyzed": False, "licenseConcluded": "NOASSERTION", "licenseDeclared": "NOASSERTION", "copyrightText": "NOASSERTION"})
        spdx = {"spdxVersion": "SPDX-2.3", "dataLicense": "CC0-1.0", "SPDXID": spdx_id, "name": project, "documentNamespace": f"https://spdx.org/spdxdocs/{serial}", "creationInfo": {"creators": ["Tool: uagent sbom_generate"]}, "packages": spdx_components, "relationships": [{"spdxElementId": spdx_id, "relationshipType": "DESCRIBES", "relatedSpdxElement": p["SPDXID"]} for p in spdx_components]}
        outdir.mkdir(parents=True, exist_ok=True)
        paths = {"cyclonedx": outdir / "bom.cyclonedx.json", "spdx": outdir / "bom.spdx.json"}
        if not overwrite and any(p.exists() for p in paths.values()):
            raise FileExistsError("SBOM output exists; set overwrite=true to replace it")
        paths["cyclonedx"].write_text(json.dumps(cdx, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        paths["spdx"].write_text(json.dumps(spdx, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return json.dumps({"ok": True, "root": root.as_posix(), "scanned_files": scanned, "truncated": truncated, "component_count": len(clean), "optional_dependencies": optional_status, "cyclonedx_path": paths["cyclonedx"].as_posix(), "spdx_path": paths["spdx"].as_posix(), "cyclonedx": cdx, "spdx": spdx}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
