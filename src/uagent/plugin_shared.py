"""Plugin system shared utilities.

Provides parsing, validation, discovery, and enablement management
for the uagent plugin system (Claude Code .claude-plugin/plugin.json compatible).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from .env_utils import env_get

# ---------------------------------------------------------------------------
# Source type detection helpers
# ---------------------------------------------------------------------------


def is_git_url(source: str) -> bool:
    """Check if the source looks like a Git URL."""
    s = source.lower().strip()
    if s.startswith(("git@", "git://")):
        return True
    if (s.startswith(("http://", "https://"))) and (
        s.endswith(".git") or "github.com/" in s or "gitlab.com/" in s
    ):
        # Exclude URLs that look like archive downloads (ZIPs, tarballs, etc.)
        if s.endswith((".zip", ".tar.gz", ".tgz", ".tar.bz2")):
            return False
        if "/archive/" in s or "/releases/download/" in s:
            return False
        return True
    return False


def is_remote_zip(source: str) -> bool:
    """Check if the source looks like a remote ZIP URL."""
    s = source.lower().strip()
    if s.startswith(("http://", "https://")):
        if s.endswith(".zip") or "/archive/" in s or "/zip/" in s:
            return True
    return False


def _infer_name_from_source(source: str) -> str:
    """Infer a safe folder name from the source string."""
    s = source.rstrip("/\\")
    base = os.path.basename(s)
    if not base:
        return "plugin"

    if base.lower().endswith(".git"):
        base = base[:-4]
    elif base.lower().endswith(".zip"):
        base = base[:-4]

    sanitized = re.sub(r"[^a-zA-Z0-9-_]", "-", base)
    sanitized = sanitized.strip("-").lower()
    return sanitized or "plugin"


def infer_plugin_name_from_source(source: str) -> str:
    """Public wrapper to infer plugin name from source."""
    return _infer_name_from_source(source)


def _normalize_source(source: str) -> str:
    """Normalize shorthand sources such as owner/repo to a GitHub URL."""
    s = source.strip()
    if not s:
        return s

    if is_git_url(s) or is_remote_zip(s) or os.path.exists(s):
        return s

    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?", s):
        return f"https://github.com/{s}"

    return s


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MANIFEST_FILENAME = "plugin.json"
MANIFEST_DIRNAME = ".claude-plugin"

# Known top-level manifest fields (for validation / warning on unknown fields)
KNOWN_MANIFEST_FIELDS: set[str] = {
    "$schema",
    "name",
    "displayName",
    "version",
    "description",
    "defaultEnabled",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "skills",
    "commands",
    "agents",
    "hooks",
    "mcpServers",
    "lspServers",
    "outputStyles",
    "experimental",
    "userConfig",
    "dependencies",
    "channels",
    "settings",
}

# Component fields that replace defaults (vs. add to defaults)
REPLACE_FIELDS: set[str] = {
    "commands",
    "agents",
    "outputStyles",
}

# Component fields that merge (add to defaults)
MERGE_FIELDS: set[str] = {
    "skills",
    "hooks",
    "mcpServers",
    "lspServers",
}

_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


# ---------------------------------------------------------------------------
# Manifest parsing
# ---------------------------------------------------------------------------


def parse_plugin_manifest(plugin_dir: str) -> dict[str, Any] | None:
    """Parse and return the plugin manifest for a given plugin directory.

    Reads .claude-plugin/plugin.json. If the file is missing, returns a
    default manifest with the directory basename as 'name'.

    Returns None only if the directory does not exist.
    """
    path = Path(plugin_dir)
    if not path.is_dir():
        return None

    manifest_path = path / MANIFEST_DIRNAME / MANIFEST_FILENAME
    if manifest_path.is_file():
        try:
            raw = manifest_path.read_text(encoding="utf-8")
            manifest: dict[str, Any] = json.loads(raw)
            if not isinstance(manifest, dict):
                return None
            manifest.setdefault("version", "0.0.0")
            manifest["_path"] = plugin_dir
            # Fallback name: directory basename if manifest has no name
            if not manifest.get("name"):
                manifest["name"] = path.name
            return manifest
        except (json.JSONDecodeError, OSError):
            return None

    # No manifest file -> default with dirname as name
    return {
        "name": path.name,
        "version": "0.0.0",
        "_path": plugin_dir,
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_plugin_manifest(
    plugin_dir: str,
    manifest: dict[str, Any],
    *,
    strict: bool = False,
) -> tuple[bool, list[str], list[str]]:
    """Validate a plugin manifest.

    Returns (ok, errors, warnings).
    """
    errors: list[str] = []
    warnings: list[str] = []

    name = manifest.get("name", "")
    if not name or not isinstance(name, str):
        errors.append("Manifest 'name' is missing or not a string.")

    # Validate paths (no traversal)
    for field in (
        "skills",
        "commands",
        "agents",
        "hooks",
        "mcpServers",
        "lspServers",
        "outputStyles",
    ):
        value = manifest.get(field)
        if value is None:
            continue
        if isinstance(value, str):
            _check_path_safe(field, value, plugin_dir, errors)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    _check_path_safe(field, item, plugin_dir, errors)
                elif isinstance(item, dict):
                    pass  # inline object, not a path

    # Check experimental subfields
    experimental = manifest.get("experimental")
    if isinstance(experimental, dict):
        for subfield in ("themes", "monitors"):
            val = experimental.get(subfield)
            if isinstance(val, str):
                _check_path_safe(f"experimental.{subfield}", val, plugin_dir, errors)

    # defaultEnabled must be bool if present
    de = manifest.get("defaultEnabled")
    if de is not None and not isinstance(de, bool):
        errors.append("'defaultEnabled' must be a boolean.")

    # version must be semver-like string if present
    ver = manifest.get("version")
    if ver is not None and not isinstance(ver, str):
        errors.append("'version' must be a string.")

    # Warn on unknown top-level fields
    for key in manifest:
        if key.startswith("_"):
            continue  # internal keys (_path, etc.)
        if key not in KNOWN_MANIFEST_FIELDS:
            warnings.append(f"Unknown manifest field '{key}'.")

    if strict and warnings:
        errors.extend(warnings)
        warnings = []

    ok = len(errors) == 0
    return ok, errors, warnings


def _check_path_safe(
    field: str,
    path_val: str,
    plugin_dir: str,
    errors: list[str],
) -> None:
    """Check that a path field does not traverse outside the plugin directory."""
    if ".." in path_val.split("/") or ".." in path_val.split("\\"):
        errors.append(f"Path traversal detected in '{field}': {path_val}")


# ---------------------------------------------------------------------------
# Plugin discovery
# ---------------------------------------------------------------------------


def get_plugin_roots(*, cwd: str | None = None) -> list[str]:
    """Return search roots for plugins, in priority order.

    Policy:
      0. UAGENT_PLUGIN_DIRS (env var, highest priority)
      1. .uag/plugins/ (project, relative to cwd)
      2. .claude/plugins/ (project, Claude Code compat)
      3. ~/.uag/plugins/ (user, uagent native)
      4. ~/.claude/plugins/ (user, Claude Code compat)
    """
    base = cwd or os.getcwd()

    roots: list[str] = []
    seen: set[str] = set()

    def _add(p: str) -> None:
        resolved = str(Path(p).resolve())
        key = os.path.normcase(resolved)
        if key not in seen:
            seen.add(key)
            roots.append(p)

    # project roots
    _add(os.path.join(base, ".uag", "plugins"))
    _add(os.path.join(base, ".claude", "plugins"))

    # user roots
    _add(os.path.join(os.path.expanduser("~"), ".uag", "plugins"))
    _add(os.path.join(os.path.expanduser("~"), ".claude", "plugins"))

    # UAGENT_PLUGIN_DIRS env var (highest priority — prepend in reverse
    # so the first entry ends up at index 0)
    env = env_get("UAGENT_PLUGIN_DIRS")
    if env:
        extra = [p.strip() for p in env.split(os.pathsep) if p.strip()]
        for p in reversed(extra):
            resolved = str(Path(p).resolve())
            key = os.path.normcase(resolved)
            if key not in seen:
                seen.add(key)
                roots.insert(0, p)

    return roots


def scan_plugins(scan_dirs: list[str]) -> list[dict[str, Any]]:
    """Scan plugin directories and return sorted deduplicated plugin list.

    For each directory in scan_dirs (in order), checks each subdirectory
    as a potential plugin. First-found wins on name duplicates.
    """
    seen_names: set[str] = set()
    results: list[dict[str, Any]] = []

    for scan_dir in scan_dirs:
        sp = Path(scan_dir)
        if not sp.is_dir():
            continue
        for child in sorted(sp.iterdir()):
            if not child.is_dir():
                continue
            manifest = parse_plugin_manifest(str(child))
            if manifest is None:
                continue
            name = manifest.get("name", child.name)
            if name in seen_names:
                continue
            seen_names.add(name)
            manifest["name"] = name
            manifest["_path"] = str(child)
            results.append(manifest)

    return results


# ---------------------------------------------------------------------------
# Enablement management
# ---------------------------------------------------------------------------


def get_enabled_plugins(
    *,
    state_dir: str | None = None,
) -> dict[str, bool]:
    """Read enabledPlugins from settings.json.

    Returns a dict mapping plugin name -> bool.
    """
    settings = _read_settings(state_dir=state_dir)
    ep = settings.get("enabledPlugins", {})
    if not isinstance(ep, dict):
        return {}
    return {str(k): bool(v) for k, v in ep.items()}


def is_plugin_enabled(
    name: str,
    *,
    state_dir: str | None = None,
    default_enabled: bool = True,
) -> bool:
    """Check whether a plugin is enabled.

    Uses enabledPlugins from settings.json if present.
    Falls back to default_enabled if not listed.
    """
    ep = get_enabled_plugins(state_dir=state_dir)
    if name in ep:
        return ep[name]
    return default_enabled


def set_plugin_enabled(
    name: str,
    enabled: bool,
    *,
    state_dir: str | None = None,
) -> None:
    """Set a plugin's enabled state in settings.json."""
    from uagent.utils.paths import get_state_dir

    sd = Path(state_dir) if state_dir else get_state_dir()
    sd.mkdir(parents=True, exist_ok=True)
    sf = sd / "settings.json"

    settings = _read_settings(state_dir=str(sd))
    ep = settings.get("enabledPlugins", {})
    if not isinstance(ep, dict):
        ep = {}
    ep[name] = enabled
    settings["enabledPlugins"] = ep

    sf.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _read_settings(*, state_dir: str | None = None) -> dict[str, Any]:
    """Read settings.json from the state directory."""
    from uagent.utils.paths import get_state_dir

    sd = Path(state_dir) if state_dir else get_state_dir()
    sf = sd / "settings.json"
    if not sf.is_file():
        return {}
    try:
        data = json.loads(sf.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {}


# ---------------------------------------------------------------------------
# Component discovery
# ---------------------------------------------------------------------------


def discover_plugin_components(
    plugin_dir: str,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Discover components (skills, commands, agents, etc.) in a plugin.

    Returns a dict with component types as keys.
    """
    components: dict[str, Any] = {}
    pd = Path(plugin_dir)

    # Skills (default: skills/ dir + any manifest 'skills' paths)
    skills: list[str] = []
    skills_field = manifest.get("skills")
    if skills_field:
        if isinstance(skills_field, str):
            _collect_skills(pd, skills_field, skills)
        elif isinstance(skills_field, list):
            for item in skills_field:
                if isinstance(item, str):
                    _collect_skills(pd, item, skills)
    else:
        _collect_skills(pd, "skills", skills)

    # Also check for single SKILL.md at root (fallback)
    root_skill = pd / "SKILL.md"
    if not skills and root_skill.is_file():
        skills.append("__root__")

    if skills:
        components["skills"] = skills

    # Commands (default: commands/ dir)
    commands: list[str] = []
    cmds_field = manifest.get("commands")
    if cmds_field:
        if isinstance(cmds_field, str):
            _collect_dir_entries(pd, cmds_field, commands)
        elif isinstance(cmds_field, list):
            for item in cmds_field:
                if isinstance(item, str):
                    _collect_dir_entries(pd, item, commands)
    else:
        _collect_dir_entries(pd, "commands", commands)
    if commands:
        components["commands"] = commands

    # Agents
    agents: list[str] = []
    agents_field = manifest.get("agents")
    if agents_field:
        if isinstance(agents_field, str):
            _collect_dir_entries(pd, agents_field, agents)
        elif isinstance(agents_field, list):
            for item in agents_field:
                if isinstance(item, str):
                    _collect_dir_entries(pd, item, agents)
    else:
        _collect_dir_entries(pd, "agents", agents)
    if agents:
        components["agents"] = agents

    # MCP servers (.mcp.json or inline)
    if manifest.get("mcpServers") or (pd / ".mcp.json").is_file():
        components["mcpServers"] = True

    # Hooks (hooks/hooks.json or inline)
    if manifest.get("hooks") or (pd / "hooks" / "hooks.json").is_file():
        components["hooks"] = True

    return components


def _collect_skills(base: Path, subpath: str, out: list[str]) -> None:
    """Collect skill names from a skills directory."""
    target = base / subpath
    if not target.is_dir():
        return
    for child in sorted(target.iterdir()):
        if child.is_dir() and (child / "SKILL.md").is_file():
            out.append(child.name)


def _collect_dir_entries(base: Path, subpath: str, out: list[str]) -> None:
    """Collect file/directory names from a given subpath."""
    target = base / subpath
    if not target.is_dir():
        return
    for child in sorted(target.iterdir()):
        if child.is_file() and child.suffix.lower() in (".md",):
            out.append(child.stem)
        elif child.is_dir():
            out.append(child.name)


# ---------------------------------------------------------------------------
# MCP integration
# ---------------------------------------------------------------------------


def _read_plugin_mcp_servers(
    plugin_dir: str, manifest: dict[str, Any]
) -> dict[str, Any] | None:
    """Read MCP server definitions from a plugin.

    Returns the mcpServers dict, or None if no MCP config is found.
    Checks .mcp.json first, then inline mcpServers in manifest.
    """

    pd = Path(plugin_dir)

    # Check .mcp.json
    mcp_file = pd / ".mcp.json"
    if mcp_file.is_file():
        try:
            data = json.loads(mcp_file.read_text(encoding="utf-8"))
            servers = data.get("mcpServers", data)
            if isinstance(servers, dict):
                return servers
        except (json.JSONDecodeError, OSError):
            return None

    # Check inline in manifest
    inline = manifest.get("mcpServers")
    if isinstance(inline, dict):
        return inline

    return None


def merge_plugin_mcp_servers(
    plugin_dir: str,
    plugin_name: str,
    *,
    mcp_config_path: str | None = None,
) -> dict[str, Any]:
    """Merge a plugin's MCP servers into the main mcp_servers.json.

    Returns dict with ok, merged_count.
    """
    from uagent.tools.mcp_servers_shared import (
        get_default_mcp_config_path as _get_mcp_path,
    )

    # Read plugin MCP servers
    manifest = parse_plugin_manifest(plugin_dir) or {}
    servers = _read_plugin_mcp_servers(plugin_dir, manifest)
    if not servers:
        return {
            "ok": False,
            "merged_count": 0,
            "error": "No MCP servers found in plugin.",
        }

    # Read main config
    config_path = mcp_config_path or _get_mcp_path()
    cp = Path(config_path)
    cp.parent.mkdir(parents=True, exist_ok=True)

    config: dict[str, Any] = {"mcp_servers": []}
    if cp.is_file():
        try:
            config = json.loads(cp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            config = {"mcp_servers": []}

    existing = config.get("mcp_servers", [])
    if not isinstance(existing, list):
        existing = []

    # Track existing names for idempotency
    existing_names = {s.get("name") for s in existing if isinstance(s, dict)}

    merged_count = 0
    for srv_name, srv_config in servers.items():
        if not isinstance(srv_config, dict):
            continue
        # Namespace the server name
        scoped_name = f"{plugin_name}:{srv_name}"
        if scoped_name in existing_names:
            continue  # idempotent
        entry = dict(srv_config)
        entry["name"] = scoped_name
        entry["_plugin_source"] = plugin_name
        existing.append(entry)
        existing_names.add(scoped_name)
        merged_count += 1

    config["mcp_servers"] = existing
    cp.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    return {"ok": True, "merged_count": merged_count}


def remove_plugin_mcp_servers(
    plugin_name: str,
    *,
    mcp_config_path: str | None = None,
) -> dict[str, Any]:
    """Remove all MCP servers from a plugin from the main config.

    Returns dict with ok, removed_count.
    """
    from uagent.tools.mcp_servers_shared import (
        get_default_mcp_config_path as _get_mcp_path,
    )

    config_path = mcp_config_path or _get_mcp_path()
    cp = Path(config_path)
    if not cp.is_file():
        return {"ok": True, "removed_count": 0}

    try:
        config = json.loads(cp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"ok": True, "removed_count": 0}

    existing = config.get("mcp_servers", [])
    if not isinstance(existing, list):
        return {"ok": True, "removed_count": 0}

    before = len(existing)
    existing = [
        s
        for s in existing
        if not (isinstance(s, dict) and s.get("_plugin_source") == plugin_name)
    ]
    removed_count = before - len(existing)

    config["mcp_servers"] = existing
    cp.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    return {"ok": True, "removed_count": removed_count}


# ---------------------------------------------------------------------------
# Agent integration
# ---------------------------------------------------------------------------


def parse_agent_md(file_path: str) -> dict[str, Any] | None:
    """Parse an agent .md file with YAML frontmatter.

    Returns dict with name, description, system_prompt, or None on failure.
    """
    p = Path(file_path)
    if not p.is_file():
        return None

    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return None

    name = p.stem
    description = ""
    system_prompt = text
    frontmatter: dict[str, Any] = {}

    # Parse YAML frontmatter (--- ... ---)
    if text.startswith("---"):
        end_idx = text.find("---", 3)
        if end_idx != -1:
            fm_text = text[3:end_idx].strip()
            body = text[end_idx + 3 :].strip()
            if body:
                system_prompt = body

            # Simple YAML-like parsing for common fields
            for line in fm_text.split(chr(10)):
                line = line.strip()
                if ":" in line:
                    key, _, val = line.partition(":")
                    key = key.strip()
                    val = val.strip()
                    frontmatter[key] = val
                    if key == "name":
                        name = val
                    elif key == "description":
                        description = val

    return {
        "name": name,
        "description": description,
        "system_prompt": system_prompt,
        "frontmatter": frontmatter,
    }


def _agent_role_filename(plugin_name: str, agent_name: str) -> str:
    """Create a filesystem-safe role filename from plugin:agent pair.

    Uses '@' instead of ':' on Windows where ':' is illegal in filenames.
    """
    if os.name == "nt":
        return f"{plugin_name}@{agent_name}.json"
    return f"{plugin_name}:{agent_name}.json"


def _agent_role_name_from_filename(filename: str) -> str | None:
    """Extract the display name (plugin:agent) from a role filename.

    Returns None if the filename doesn't match expected patterns.
    """
    stem = Path(filename).stem
    # Try Windows format (plugin@agent)
    if "@" in stem:
        return stem.replace("@", ":", 1)
    # Try Unix format (plugin:agent)
    if ":" in stem:
        return stem
    return None


def install_plugin_agents(
    plugin_dir: str,
    plugin_name: str,
    *,
    roles_dir: str | None = None,
) -> dict[str, Any]:
    """Install plugin agent .md files as sub-agent JSON role files.

    Returns dict with ok, installed_count.
    """
    if roles_dir is None:
        roles_dir = str(Path.home() / ".uag" / "subagent_roles")

    rd = Path(roles_dir)
    rd.mkdir(parents=True, exist_ok=True)

    agents_dir = Path(plugin_dir) / "agents"
    if not agents_dir.is_dir():
        return {"ok": True, "installed_count": 0}

    installed_count = 0
    for agent_file in sorted(agents_dir.glob("*.md")):
        parsed = parse_agent_md(str(agent_file))
        if parsed is None:
            continue

        agent_name = parsed.get("name", agent_file.stem)
        scoped_name = f"{plugin_name}:{agent_name}"
        role_filename = _agent_role_filename(plugin_name, agent_name)

        # Check existing (idempotent)
        role_path = rd / role_filename
        if role_path.exists():
            continue

        role_data = {
            "name": scoped_name,
            "description": parsed.get("description", ""),
            "system_prompt": parsed.get("system_prompt", ""),
            "allowed_tools": [],
            "default_required_fields": ["task"],
            "default_response_mode": "json",
        }

        try:
            role_path.write_text(
                json.dumps(role_data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            installed_count += 1
        except OSError:
            continue

    return {"ok": True, "installed_count": installed_count}


def remove_plugin_agents(
    plugin_name: str,
    *,
    roles_dir: str | None = None,
) -> dict[str, Any]:
    """Remove all agent role files belonging to a plugin.

    Returns dict with ok, removed_count.
    """
    if roles_dir is None:
        roles_dir = str(Path.home() / ".uag" / "subagent_roles")

    rd = Path(roles_dir)
    if not rd.is_dir():
        return {"ok": True, "removed_count": 0}

    # Match files with both : and @ separators (cross-platform compat)
    colon_prefix = f"{plugin_name}:"
    at_prefix = f"{plugin_name}@"
    removed_count = 0

    for role_file in list(rd.glob("*.json")):
        stem = role_file.stem
        if stem.startswith(colon_prefix) or stem.startswith(at_prefix):
            try:
                role_file.unlink()
                removed_count += 1
            except OSError:
                continue

    return {"ok": True, "removed_count": removed_count}


# ---------------------------------------------------------------------------
# Hooks integration
# ---------------------------------------------------------------------------


def parse_plugin_hooks_file(hooks_path: str) -> dict[str, Any] | None:
    """Parse a hooks.json file from a plugin.

    Returns the hooks dict (event_name -> list of hook groups), or None on failure.
    """
    p = Path(hooks_path)
    if not p.is_file():
        return None

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    hooks = data.get("hooks", data)
    if not isinstance(hooks, dict):
        return None

    return hooks


def _read_hooks_registry(registry_path: str) -> dict[str, Any]:
    """Read the hooks registry file."""
    p = Path(registry_path)
    if not p.is_file():
        return {"plugins": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "plugins" in data:
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {"plugins": {}}


def install_plugin_hooks(
    plugin_dir: str,
    plugin_name: str,
    *,
    registry_path: str | None = None,
) -> dict[str, Any]:
    """Install a plugin's hooks into the hooks registry.

    Returns dict with ok, event_count.
    """
    if registry_path is None:
        registry_path = str(Path.home() / ".uag" / "hooks" / "plugin_hooks.json")

    pd = Path(plugin_dir)

    # Try hooks/hooks.json first, then inline from manifest
    hooks_data: dict[str, Any] | None = None
    hooks_file = pd / "hooks" / "hooks.json"
    if hooks_file.is_file():
        hooks_data = parse_plugin_hooks_file(str(hooks_file))
    else:
        manifest = parse_plugin_manifest(plugin_dir)
        if manifest:
            inline = manifest.get("hooks")
            if isinstance(inline, dict):
                hooks_data = inline

    if not hooks_data:
        return {"ok": True, "event_count": 0}

    registry = _read_hooks_registry(registry_path)

    # Idempotent: skip if already registered
    if plugin_name in registry.get("plugins", {}):
        return {"ok": True, "event_count": 0}

    registry.setdefault("plugins", {})[plugin_name] = hooks_data

    rp = Path(registry_path)
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")

    event_count = len(hooks_data)
    return {"ok": True, "event_count": event_count}


def remove_plugin_hooks(
    plugin_name: str,
    *,
    registry_path: str | None = None,
) -> dict[str, Any]:
    """Remove a plugin's hooks from the hooks registry.

    Returns dict with ok, removed (bool).
    """
    if registry_path is None:
        registry_path = str(Path.home() / ".uag" / "hooks" / "plugin_hooks.json")

    rp = Path(registry_path)
    if not rp.is_file():
        return {"ok": True, "removed": False}

    registry = _read_hooks_registry(registry_path)
    plugins = registry.get("plugins", {})

    if plugin_name not in plugins:
        return {"ok": True, "removed": False}

    del plugins[plugin_name]

    rp.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "removed": True}


# ---------------------------------------------------------------------------
# Skills-directory plugin detection (@skills-dir)
# ---------------------------------------------------------------------------


def scan_skills_dirs_for_plugins(skills_roots: list[str]) -> list[dict[str, Any]]:
    """Scan skills directories for nested plugins (with .claude-plugin/plugin.json).

    Skills-directory plugins are discovered in-place (no install step needed).
    They are marked with _skills_dir_plugin=True.
    """
    results: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    for root in skills_roots:
        rp = Path(root)
        if not rp.is_dir():
            continue
        for child in sorted(rp.iterdir()):
            if not child.is_dir():
                continue
            manifest_dir = child / MANIFEST_DIRNAME
            manifest_file = manifest_dir / MANIFEST_FILENAME
            if not manifest_file.is_file():
                continue
            manifest = parse_plugin_manifest(str(child))
            if manifest is None:
                continue
            name = manifest.get("name", child.name)
            if name in seen_names:
                continue
            seen_names.add(name)
            manifest["name"] = name
            manifest["_path"] = str(child)
            manifest["_skills_dir_plugin"] = True
            results.append(manifest)

    return results


# ---------------------------------------------------------------------------
# userConfig support
# ---------------------------------------------------------------------------


def store_user_config_values(
    plugin_name: str,
    values: dict[str, Any],
    *,
    settings_path: str | None = None,
) -> dict[str, Any]:
    """Store user config values for a plugin in settings.json.

    Values are stored under pluginConfigs[].options.
    Sensitive values (marked sensitive=True) are NOT stored here
    (they should go to a secure store).
    """
    from uagent.utils.paths import get_state_dir

    sp = Path(settings_path) if settings_path else get_state_dir() / "settings.json"

    settings: dict[str, Any] = {"pluginConfigs": []}
    if sp.is_file():
        try:
            settings = json.loads(sp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            settings = {"pluginConfigs": []}

    configs = settings.get("pluginConfigs", [])
    if not isinstance(configs, list):
        configs = []

    # Find existing entry or create new
    existing = None
    for entry in configs:
        if isinstance(entry, dict) and entry.get("name") == plugin_name:
            existing = entry
            break

    if existing is None:
        existing = {"name": plugin_name, "options": {}}
        configs.append(existing)

    existing["options"].update(values)
    settings["pluginConfigs"] = configs

    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")

    return {"ok": True, "plugin": plugin_name}


def get_user_config_values(
    plugin_name: str,
    *,
    manifest: dict[str, Any] | None = None,
    settings_path: str | None = None,
) -> dict[str, Any]:
    """Get user config values for a plugin, merged with defaults.

    Returns dict with all config keys resolved (stored values + defaults).
    """
    from uagent.utils.paths import get_state_dir

    sp = Path(settings_path) if settings_path else get_state_dir() / "settings.json"

    # Start with defaults from manifest
    result: dict[str, Any] = {}
    if manifest:
        uc = manifest.get("userConfig", {})
        if isinstance(uc, dict):
            for key, field in uc.items():
                if isinstance(field, dict) and "default" in field:
                    result[key] = field["default"]

    # Override with stored values
    if sp.is_file():
        try:
            settings = json.loads(sp.read_text(encoding="utf-8"))
            configs = settings.get("pluginConfigs", [])
            if isinstance(configs, list):
                for entry in configs:
                    if isinstance(entry, dict) and entry.get("name") == plugin_name:
                        options = entry.get("options", {})
                        if isinstance(options, dict):
                            result.update(options)
        except (json.JSONDecodeError, OSError):
            pass

    return result


# Simple variable pattern for ${user_config.KEY}
_USER_CONFIG_RE = re.compile(r"\$\{user_config\.([^}]+)\}")


def resolve_user_config_string(
    text: str,
    values: dict[str, Any],
) -> str:
    """Resolve ${user_config.KEY} placeholders in a string.

    Unknown keys are left as-is.
    """

    def _replacer(m: re.Match) -> str:
        key = m.group(1)
        if key in values:
            val = values[key]
            return str(val)
        return m.group(0)  # leave unresolved

    return _USER_CONFIG_RE.sub(_replacer, text)


# ---------------------------------------------------------------------------
# Marketplace support
# ---------------------------------------------------------------------------


def parse_marketplace(marketplace_path: str) -> dict[str, Any] | None:
    """Parse a marketplace.json file.

    Returns the marketplace dict, or None on failure.
    """
    p = Path(marketplace_path)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "name" in data and "plugins" in data:
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return None


# ---------------------------------------------------------------------------
# Default built-in marketplaces
# ---------------------------------------------------------------------------

DEFAULT_MARKETPLACES: list[dict[str, Any]] = [
    {
        "name": "claude-plugins-official",
        "url": "https://github.com/anthropics/claude-plugins-official",
        "description": "Anthropic official plugin marketplace",
        "builtin": True,
    },
]


# ---------------------------------------------------------------------------
# Marketplace registry
# ---------------------------------------------------------------------------


def _get_marketplace_registry_path() -> str:
    """Return default marketplace registry path."""
    from uagent.utils.paths import get_state_dir

    return str(get_state_dir() / "marketplaces.json")


def _get_marketplace_cache_dir() -> Path:
    """Return the cache directory where remote marketplaces are cloned."""
    from uagent.utils.paths import get_state_dir

    return get_state_dir() / "marketplace_cache"


def _marketplace_cache_path(marketplace_name: str) -> Path:
    """Return the expected cache path for a marketplace by name."""
    return _get_marketplace_cache_dir() / marketplace_name


def _ensure_marketplace_local(
    mp_entry: dict[str, Any],
) -> Path | None:
    """Ensure a marketplace is available locally, cloning if needed.

    If the entry points to a local directory, returns it directly.
    If it points to a remote Git URL, clones it into the cache directory.

    Returns the local path, or None on failure.
    """
    mp_url = mp_entry.get("url", "")
    if not mp_url:
        return None

    name = mp_entry.get("name", "")
    if not name:
        return None

    local_path = Path(mp_url)

    # Already a local directory
    if local_path.is_dir():
        return local_path

    # Try cache
    cached = _marketplace_cache_path(name)
    if cached.is_dir() and (cached / ".claude-plugin" / "marketplace.json").is_file():
        return cached

    # Remote URL -- clone into cache
    normalized = _normalize_source(mp_url)
    if not is_git_url(normalized):
        return None

    try:
        import subprocess

        subprocess.run(["git", "--version"], capture_output=True, check=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        return None

    try:
        import subprocess
        import shutil

        parent = cached.parent
        parent.mkdir(parents=True, exist_ok=True)

        # If cache dir already exists from a previous failed attempt, clean it
        if cached.exists():
            shutil.rmtree(str(cached))

        result = subprocess.run(
            ["git", "clone", "--depth", "1", normalized, str(cached)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None

        if (
            cached.is_dir()
            and (cached / ".claude-plugin" / "marketplace.json").is_file()
        ):
            return cached
    except Exception:
        return None

    return None


def list_marketplaces(
    *,
    registry_path: str | None = None,
    include_defaults: bool = True,
) -> list[dict[str, Any]]:
    """List registered marketplaces.

    Always includes built-in default marketplaces unless
    include_defaults=False or a user-registered marketplace
    with the same name exists.
    """
    rp = (
        Path(registry_path) if registry_path else Path(_get_marketplace_registry_path())
    )
    mps: list[dict[str, Any]] = []
    if rp.is_file():
        try:
            data = json.loads(rp.read_text(encoding="utf-8"))
            user_mps = data.get("marketplaces", [])
            if isinstance(user_mps, list):
                mps = user_mps
        except (json.JSONDecodeError, OSError):
            pass

    # Merge with defaults (user entries override builtins with same name)
    if include_defaults:
        user_names: set[str] = set()
        for mp in mps:
            if isinstance(mp, dict) and mp.get("name"):
                user_names.add(mp["name"])
        for default in DEFAULT_MARKETPLACES:
            if default["name"] not in user_names:
                mps.append(dict(default))

    return mps


def seed_default_marketplaces(
    *,
    registry_path: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Seed registry with default marketplaces if empty.

    Returns dict with 'added' list of marketplace names.
    """
    rp = (
        Path(registry_path) if registry_path else Path(_get_marketplace_registry_path())
    )
    data: dict[str, Any] = {"marketplaces": []}
    if rp.is_file():
        try:
            data = json.loads(rp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {"marketplaces": []}

    mps = data.get("marketplaces", [])
    if not isinstance(mps, list):
        mps = []

    existing_names = {m["name"] for m in mps if isinstance(m, dict) and m.get("name")}

    added: list[str] = []
    for default in DEFAULT_MARKETPLACES:
        if default["name"] not in existing_names:
            mps.append(
                {
                    "name": default["name"],
                    "url": default["url"],
                }
            )
            added.append(default["name"])
        elif overwrite:
            for i, mp in enumerate(mps):
                if isinstance(mp, dict) and mp.get("name") == default["name"]:
                    mps[i] = {"name": default["name"], "url": default["url"]}
                    if default["name"] not in added:
                        added.append(default["name"])
                    break

    if added:
        data["marketplaces"] = mps
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    return {"ok": True, "added": added}


def add_marketplace(
    name: str,
    url: str,
    *,
    registry_path: str | None = None,
) -> dict[str, Any]:
    """Register a marketplace.

    If the name matches a built-in default marketplace, the built-in
    entry is overridden with the new URL.
    """
    rp = (
        Path(registry_path) if registry_path else Path(_get_marketplace_registry_path())
    )
    data: dict[str, Any] = {"marketplaces": []}
    if rp.is_file():
        try:
            data = json.loads(rp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {"marketplaces": []}
    mps = data.get("marketplaces", [])
    if not isinstance(mps, list):
        mps = []
    # Replace if exists
    for i, mp in enumerate(mps):
        if isinstance(mp, dict) and mp.get("name") == name:
            mps[i] = {"name": name, "url": url}
            data["marketplaces"] = mps
            rp.parent.mkdir(parents=True, exist_ok=True)
            rp.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            return {"ok": True, "name": name}
    mps.append({"name": name, "url": url})
    data["marketplaces"] = mps
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "name": name}


def remove_marketplace(
    name: str,
    *,
    registry_path: str | None = None,
) -> dict[str, Any]:
    """Remove a marketplace from registry.

    Built-in default marketplaces are only hidden from the user
    registry but will still appear via include_defaults=True in
    list_marketplaces(). To fully hide them, pass include_defaults=False
    or add them with a different name.
    """
    rp = (
        Path(registry_path) if registry_path else Path(_get_marketplace_registry_path())
    )
    if not rp.is_file():
        return {"ok": True, "removed": False}
    try:
        data = json.loads(rp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"ok": True, "removed": False}
    mps = data.get("marketplaces", [])
    if not isinstance(mps, list):
        return {"ok": True, "removed": False}
    before = len(mps)
    mps = [mp for mp in mps if not (isinstance(mp, dict) and mp.get("name") == name)]
    removed = len(mps) < before
    data["marketplaces"] = mps
    rp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "removed": removed}


def resolve_marketplace_plugin(
    plugin_name: str,
    marketplace_name: str,
    *,
    marketplace_dir: str | None = None,
    registry_path: str | None = None,
) -> str | None:
    """Resolve a plugin source path from a marketplace.

    Handles both local directories and remote Git URLs
    (auto-clones remote repos into cache).

    Returns the resolved source path, or None if not found.
    """
    # If marketplace_dir is provided, use it directly (for testing)
    if marketplace_dir:
        mp_path = Path(marketplace_dir)
    else:
        # Look up in registry (includes defaults)
        mps = list_marketplaces(registry_path=registry_path)
        mp_entry = next(
            (
                m
                for m in mps
                if isinstance(m, dict) and m.get("name") == marketplace_name
            ),
            None,
        )
        if not mp_entry:
            return None

        # Ensure marketplace is available locally
        mp_path_or_none = _ensure_marketplace_local(mp_entry)
        if mp_path_or_none is None:
            return None
        mp_path = mp_path_or_none

    # Parse marketplace.json
    mp_json = mp_path / ".claude-plugin" / "marketplace.json"
    mp_data = parse_marketplace(str(mp_json))
    if not mp_data:
        return None

    # Handle plugin entries with 'source' field
    plugins = mp_data.get("plugins", [])
    for entry in plugins:
        if isinstance(entry, dict) and entry.get("name") == plugin_name:
            raw_source = entry.get("source", "")
            if not raw_source:
                continue

            # 'source' can be a str (path) or a dict with {source, url, path, ref}
            if isinstance(raw_source, str):
                # Relative path, resolve to absolute
                resolved = mp_path / raw_source
                return str(resolved)
            elif isinstance(raw_source, dict):
                # Complex source: git-subdir, url, etc.
                src_type = raw_source.get("source", "")
                # Handle inline URL
                if src_type == "url":
                    return raw_source.get("url", "")
                # Handle git-subdir
                elif src_type == "git-subdir":
                    sub_url = raw_source.get("url", "")
                    sub_path = raw_source.get("path", "")
                    if sub_url and sub_path:
                        # Return the clone URL + subdirectory -- the caller handles cloning
                        return f"{sub_url}#subdir={sub_path}"
                # Fallback: relative path
                sub_path = raw_source.get("path", "")
                if sub_path:
                    resolved = mp_path / sub_path
                    return str(resolved)

    return None


# ---------------------------------------------------------------------------
# Dependencies support
# ---------------------------------------------------------------------------


def parse_plugin_dependencies(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse dependencies from a plugin manifest.

    Dependencies can be strings ("plugin-name") or objects
    ({"name": "plugin-name", "version": "~1.0"}).

    Returns list of dicts with at least "name" key.
    """
    deps_raw = manifest.get("dependencies", [])
    if not isinstance(deps_raw, list):
        return []

    result: list[dict[str, Any]] = []
    for dep in deps_raw:
        if isinstance(dep, str):
            result.append({"name": dep})
        elif isinstance(dep, dict):
            name = dep.get("name", "")
            if name:
                result.append(dict(dep))
    return result


def resolve_dependencies(
    plugin_name: str,
    registry: dict[str, dict[str, Any]],
    *,
    _visited: set[str] | None = None,
) -> list[str]:
    """Resolve dependencies in dependency order (dependencies first).

    Uses DFS topological sort.
    Returns list of plugin names in dependency order.
    Raises ValueError on circular dependency.
    """
    if _visited is None:
        _visited = set()

    if plugin_name in _visited:
        raise ValueError(f"Circular dependency detected: {plugin_name}")

    manifest = registry.get(plugin_name)
    if not manifest:
        return []

    _visited.add(plugin_name)
    result: list[str] = []

    deps = parse_plugin_dependencies(manifest)
    for dep in deps:
        dep_name = dep.get("name", "")
        if dep_name:
            sub_deps = resolve_dependencies(dep_name, registry, _visited=_visited)
            for sd in sub_deps:
                if sd not in result:
                    result.append(sd)
            if dep_name not in result:
                result.append(dep_name)

    _visited.discard(plugin_name)
    return result


# ---------------------------------------------------------------------------
# Channels support
# ---------------------------------------------------------------------------

_CHANNEL_CONFIG_PATH = None


def _get_channel_store_path() -> str:
    """Return default channel config store path."""
    from uagent.utils.paths import get_state_dir

    return str(get_state_dir() / "channels.json")


def parse_plugin_channels(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse channel definitions from a plugin manifest.

    Channels list entries with 'server' and optional 'userConfig'.
    Returns empty list if no channels.
    """
    raw = manifest.get("channels", [])
    if not isinstance(raw, list):
        return []
    result: list[dict[str, Any]] = []
    for entry in raw:
        if isinstance(entry, dict) and entry.get("server"):
            result.append(entry)
    return result


def _read_channel_store(store_path: str) -> dict[str, Any]:
    """Read the channel config store."""
    sp = Path(store_path)
    if not sp.is_file():
        return {"channels": []}
    try:
        data = json.loads(sp.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "channels" in data:
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {"channels": []}


def store_channel_config(
    plugin_name: str,
    channel_name: str,
    config: dict[str, Any],
    *,
    store_path: str | None = None,
) -> dict[str, Any]:
    """Store channel configuration."""
    sp = store_path or _get_channel_store_path()
    data = _read_channel_store(sp)
    channels = data.get("channels", [])
    if not isinstance(channels, list):
        channels = []

    # Find existing or create
    existing = None
    for entry in channels:
        if (
            isinstance(entry, dict)
            and entry.get("plugin") == plugin_name
            and entry.get("channel") == channel_name
        ):
            existing = entry
            break

    if existing:
        existing["config"].update(config)
    else:
        channels.append(
            {
                "plugin": plugin_name,
                "channel": channel_name,
                "config": dict(config),
            }
        )

    data["channels"] = channels
    sp_obj = Path(sp)
    sp_obj.parent.mkdir(parents=True, exist_ok=True)
    sp_obj.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True}


def get_channel_config(
    plugin_name: str,
    channel_name: str,
    *,
    store_path: str | None = None,
) -> dict[str, Any] | None:
    """Get channel configuration."""
    sp = store_path or _get_channel_store_path()
    data = _read_channel_store(sp)
    for entry in data.get("channels", []):
        if (
            isinstance(entry, dict)
            and entry.get("plugin") == plugin_name
            and entry.get("channel") == channel_name
        ):
            return dict(entry.get("config", {}))
    return None


def list_channel_configs(
    *,
    store_path: str | None = None,
) -> list[dict[str, Any]]:
    """List all channel configurations."""
    sp = store_path or _get_channel_store_path()
    data = _read_channel_store(sp)
    channels = data.get("channels", [])
    if not isinstance(channels, list):
        return []
    return [dict(c) for c in channels if isinstance(c, dict)]


def remove_channel_config(
    plugin_name: str,
    channel_name: str,
    *,
    store_path: str | None = None,
) -> dict[str, Any]:
    """Remove a specific channel configuration."""
    sp = store_path or _get_channel_store_path()
    data = _read_channel_store(sp)
    channels = data.get("channels", [])
    if not isinstance(channels, list):
        return {"ok": True, "removed": False}

    before = len(channels)
    channels = [
        c
        for c in channels
        if not (
            isinstance(c, dict)
            and c.get("plugin") == plugin_name
            and c.get("channel") == channel_name
        )
    ]
    removed = len(channels) < before
    data["channels"] = channels
    Path(sp).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {"ok": True, "removed": removed}


def remove_plugin_channels(
    plugin_name: str,
    *,
    store_path: str | None = None,
) -> dict[str, Any]:
    """Remove all channel configurations for a plugin."""
    sp = store_path or _get_channel_store_path()
    data = _read_channel_store(sp)
    channels = data.get("channels", [])
    if not isinstance(channels, list):
        return {"ok": True, "removed": 0}

    before = len(channels)
    channels = [
        c
        for c in channels
        if not (isinstance(c, dict) and c.get("plugin") == plugin_name)
    ]
    removed = before - len(channels)
    data["channels"] = channels
    Path(sp).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {"ok": True, "removed": removed}


# ---------------------------------------------------------------------------
# Output style support
# ---------------------------------------------------------------------------


def list_output_styles(style_dir: str) -> list[str]:
    """List available output style names from a directory."""
    sd = Path(style_dir)
    if not sd.is_dir():
        return []
    styles: list[str] = []
    for f in sorted(sd.glob("*.md")):
        styles.append(f.stem)
    return styles


def read_output_style(plugin_dir_or_style_dir: str, style_name: str) -> str | None:
    """Read an output style file.

    Tries plugin_dir/output-styles/<name>.md first,
    then <plugin_dir_or_style_dir>/<name>.md directly.
    """
    # Try output-styles/<name>.md
    candidate = Path(plugin_dir_or_style_dir) / "output-styles" / f"{style_name}.md"
    if candidate.is_file():
        try:
            return candidate.read_text(encoding="utf-8")
        except OSError:
            pass

    # Try <name>.md directly
    candidate2 = Path(plugin_dir_or_style_dir) / f"{style_name}.md"
    if candidate2.is_file():
        try:
            return candidate2.read_text(encoding="utf-8")
        except OSError:
            pass

    return None
