"""plugin_manage_tool implementation for managing uagent plugins.

Provides TOOL_SPEC (LLM-facing), run_tool(), and CMD_SPECS (CLI commands).
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from ..plugin_shared import (
    activate_plugin,
    clear_plugin_settings,
    deactivate_plugin,
    discover_plugin_components,
    get_plugin_roots,
    is_plugin_enabled,
    parse_plugin_manifest,
    scan_plugins,
    set_plugin_enabled,
    validate_plugin_manifest,
)
from ..utils.paths import get_state_dir
from ..runtime.skill_lifecycle import SkillLifecycleError, SkillLifecycleManager
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

STATUS_LABEL = "tool:plugin_manage"

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "basic",
    "function": {
        "name": "plugin_manage",
        "description": _(
            "tool.description",
            default=(
                "Manage uagent plugins: list, install, remove, enable, disable, "
                "validate, or get info about a plugin."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "plugin_manage",
                "manage plugin",
                "install plugin",
                "remove plugin",
                "enable plugin",
                "disable plugin",
                "list plugins",
            ],
        ),
        "x_search_terms_en": [
            "plugin_manage",
            "manage plugin",
            "install plugin",
            "remove plugin",
            "enable plugin",
            "disable plugin",
            "list plugins",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": _(
                        "param.action.description",
                        default=(
                            "Operation to perform. One of: "
                            "list/install/remove/review/enable/disable/validate/info."
                        ),
                    ),
                    "enum": [
                        "list",
                        "install",
                        "remove",
                        "review",
                        "enable",
                        "disable",
                        "validate",
                        "info",
                    ],
                },
                "source": {
                    "type": "string",
                    "description": _(
                        "param.source.description",
                        default=(
                            "Source URL or path for install action "
                            "(Git URL, HTTP ZIP, local directory)."
                        ),
                    ),
                },
                "name": {
                    "type": "string",
                    "description": _(
                        "param.name.description",
                        default="Plugin name (target for info/remove/enable/disable/validate).",
                    ),
                },
                "confirmed": {
                    "type": "boolean",
                    "description": _(
                        "param.confirmed.description",
                        default="Explicit user confirmation required for enable/deprecate actions.",
                    ),
                    "default": False,
                },
                "scope": {
                    "type": "string",
                    "description": _(
                        "param.scope.description",
                        default=(
                            "Installation scope: 'user' (~/.uag/plugins/), "
                            "'project' (.uag/plugins/), "
                            "'local' (.uag/plugins.local/). Default: 'user'."
                        ),
                    ),
                    "enum": ["user", "project", "local"],
                },
            },
            "required": ["action"],
        },
    },
}


def _get_install_root(scope: str, *, cwd: str | None = None) -> str:
    """Return the install root directory for the given scope."""
    base = cwd or os.getcwd()
    if scope == "user":
        return str(get_state_dir() / "plugins")
    elif scope == "project":
        return str(Path(base) / ".uag" / "plugins")
    elif scope == "local":
        return str(Path(base) / ".uag" / "plugins.local")
    else:
        return str(get_state_dir() / "plugins")


def _find_scanned_plugin(name: str, scan_dirs: list[str]) -> dict[str, Any] | None:
    """Return scanned plugin manifest for name, or None."""
    if not name:
        return None
    for plugin in scan_plugins(scan_dirs):
        if plugin.get("name") == name:
            return plugin
    return None


def run_tool(args: dict[str, Any]) -> str:
    """Run the plugin_manage tool with the given arguments."""
    action = args.get("action", "list")
    name = args.get("name", "")
    source = args.get("source", "")
    scope = args.get("scope", "user")

    # Allow test injection via _test_* keys
    test_roots: list[str] | None = args.get("_test_roots")
    test_install_root: str | None = args.get("_test_install_root")
    test_state_dir: str | None = args.get("_test_state_dir")

    # Determine plugin scan roots
    if test_roots is not None:
        scan_dirs = test_roots
    else:
        scan_dirs = get_plugin_roots()

    # State dir
    state_dir = test_state_dir or str(get_state_dir())

    # Install root
    if test_install_root:
        install_root = test_install_root
    else:
        install_root = _get_install_root(scope)

    act_kwargs = {
        "mcp_config_path": args.get("_test_mcp_config_path"),
        "roles_dir": args.get("_test_roles_dir"),
        "hooks_registry_path": args.get("_test_hooks_registry_path"),
    }

    # Actions
    if action == "list":
        return _action_list(scan_dirs, state_dir)
    elif action == "info":
        return _action_info(name, scan_dirs)
    elif action == "install":
        return _action_install(
            source,
            name,
            install_root,
            state_dir=state_dir,
            scan_dirs=scan_dirs,
            _test_marketplace_dir=args.get("_test_marketplace_dir"),
            **act_kwargs,
        )
    elif action == "remove":
        return _action_remove(name, install_root, state_dir=state_dir, **act_kwargs)
    elif action == "review":
        return _action_review(name, state_dir, scan_dirs)
    elif action == "enable":
        return _action_enable(
            name,
            state_dir,
            scan_dirs=scan_dirs,
            confirmed=bool(args.get("confirmed", False)),
            allow_unreviewed=bool(test_state_dir),
            **act_kwargs,
        )
    elif action == "disable":
        return _action_disable(name, state_dir, **act_kwargs)
    elif action == "validate":
        return _action_validate(name, scan_dirs)
    else:
        return json.dumps({"ok": False, "error": f"Unknown action: {action}"})


# ---------------------------------------------------------------------------
# Action implementations
# ---------------------------------------------------------------------------


def _action_list(scan_dirs: list[str], state_dir: str) -> str:
    """List all discovered plugins with their status."""
    plugins = scan_plugins(scan_dirs)
    ep = {}
    try:
        from ..plugin_shared import get_enabled_plugins

        ep = get_enabled_plugins(state_dir=state_dir)
    except Exception:
        pass

    results: list[dict[str, Any]] = []
    for p in plugins:
        name = p.get("name", "?")
        enabled = ep.get(name, True)
        results.append(
            {
                "name": name,
                "version": p.get("version", "0.0.0"),
                "description": p.get("description", ""),
                "enabled": enabled,
                "path": p.get("_path", ""),
            }
        )

    return json.dumps(
        {"ok": True, "plugins": results},
        ensure_ascii=False,
        indent=2,
    )


def _action_info(name: str, scan_dirs: list[str]) -> str:
    """Get detailed info about a specific plugin."""
    if not name:
        return json.dumps({"ok": False, "error": "Plugin name is required."})

    plugins = scan_plugins(scan_dirs)
    for p in plugins:
        if p.get("name") == name:
            # Discover components
            comps = discover_plugin_components(p.get("_path", ""), p)
            # Validate
            ok, errors, warnings = validate_plugin_manifest(p.get("_path", ""), p)
            return json.dumps(
                {
                    "ok": True,
                    "name": name,
                    "version": p.get("version", "0.0.0"),
                    "description": p.get("description", ""),
                    "path": p.get("_path", ""),
                    "valid": ok,
                    "errors": errors,
                    "warnings": warnings,
                    "components": comps,
                },
                ensure_ascii=False,
                indent=2,
            )

    return json.dumps({"ok": False, "error": f"Plugin '{name}' not found."})


def _action_install(
    source: str,
    name: str,
    install_root: str,
    *,
    state_dir: str | None = None,
    scan_dirs: list[str] | None = None,
    mcp_config_path: str | None = None,
    roles_dir: str | None = None,
    hooks_registry_path: str | None = None,
    _test_marketplace_dir: str | None = None,
) -> str:
    """Install a plugin from various source types."""
    if not source:
        return json.dumps({"ok": False, "error": "Source is required for install."})

    from ..plugin_shared import (
        _infer_name_from_source,
        _normalize_source,
        is_git_url,
        is_remote_zip,
        parse_plugin_manifest,
    )

    normalized = _normalize_source(source)

    # Handle name@marketplace syntax
    if "@" in normalized and not normalized.startswith(("git@", "http")):
        parts = normalized.split("@", 1)
        mp_plugin_name = parts[0]
        mp_name = parts[1]
        from ..plugin_shared import resolve_marketplace_plugin

        resolved = resolve_marketplace_plugin(
            mp_plugin_name,
            mp_name,
            marketplace_dir=_test_marketplace_dir,
        )
        if resolved:
            normalized = resolved
            if not name:
                name = mp_plugin_name
        else:
            return json.dumps(
                {
                    "ok": False,
                    "error": f"Plugin '{mp_plugin_name}' not found in marketplace '{mp_name}'.",
                }
            )
    else:
        # Bare plugin name (Claude Code style: /plugin install genshijin)
        # Auto-resolve from registered marketplaces when not a path/URL.
        from ..plugin_shared import (
            looks_like_bare_plugin_name,
            resolve_plugin_name_from_marketplaces,
        )
        from pathlib import Path as _Path

        if looks_like_bare_plugin_name(normalized) and not _Path(normalized).exists():
            resolved, mp_found = resolve_plugin_name_from_marketplaces(
                normalized,
                marketplace_dir=_test_marketplace_dir,
            )
            if resolved:
                if not name:
                    name = normalized
                normalized = resolved
            else:
                return json.dumps(
                    {
                        "ok": False,
                        "error": (
                            f"Plugin '{normalized}' not found as a local path/URL "
                            "and not found in any registered marketplace. "
                            "Try ':plugin install name@marketplace' or a git/zip URL."
                        ),
                    }
                )

    # Determine destination name
    dest_name = name or _infer_name_from_source(normalized)
    dest = Path(install_root) / dest_name

    # Prevent overwriting existing
    if dest.exists():
        return json.dumps(
            {
                "ok": False,
                "error": f"Plugin '{dest_name}' already exists at {dest}.",
            }
        )

    # Create temporary workspace for non-directory sources
    import subprocess
    import urllib.request
    import tempfile

    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        if is_git_url(normalized):
            # Git clone
            try:
                subprocess.run(["git", "--version"], capture_output=True, check=True)
            except (subprocess.SubprocessError, FileNotFoundError):
                return json.dumps(
                    {
                        "ok": False,
                        "error": "Git command not found. Please install Git or use a ZIP URL instead.",
                    }
                )

            res = subprocess.run(
                ["git", "clone", normalized, str(dest)],
                capture_output=True,
                text=True,
            )
            if res.returncode != 0:
                return json.dumps(
                    {
                        "ok": False,
                        "error": f"Git clone failed: {res.stderr.strip()}",
                    }
                )

        elif is_remote_zip(normalized):
            # Download and extract remote ZIP
            with tempfile.TemporaryDirectory() as tmpdir:
                zip_path = os.path.join(tmpdir, "download.zip")
                try:
                    urllib.request.urlretrieve(normalized, zip_path)
                except Exception as e:
                    return json.dumps(
                        {
                            "ok": False,
                            "error": f"Failed to download ZIP: {e}",
                        }
                    )

                _extract_plugin_zip(zip_path, str(dest))

        elif normalized.lower().endswith(".zip") and os.path.isfile(normalized):
            # Local ZIP file
            _extract_plugin_zip(normalized, str(dest))

        elif os.path.isdir(normalized):
            # Local directory
            shutil.copytree(normalized, str(dest))

        else:
            return json.dumps(
                {
                    "ok": False,
                    "error": f"Source not recognized or not found: {source}",
                }
            )

    except Exception as e:
        # Cleanup on failure
        if dest.exists():
            shutil.rmtree(str(dest))
        return json.dumps(
            {
                "ok": False,
                "error": f"Install failed: {e}",
            }
        )

    # Update manifest name if destination name differs from source
    installed_manifest = parse_plugin_manifest(str(dest))
    if installed_manifest and installed_manifest.get("name") != dest_name:
        manifest_path = dest / ".claude-plugin" / "plugin.json"
        if manifest_path.exists():
            try:
                mdata = json.loads(manifest_path.read_text(encoding="utf-8"))
                mdata["name"] = dest_name
                manifest_path.write_text(json.dumps(mdata, indent=2), encoding="utf-8")
            except (json.JSONDecodeError, OSError):
                pass

    result: dict[str, Any] = {
        "ok": True,
        "name": dest_name,
        "path": str(dest),
        "message": f"Plugin '{dest_name}' installed to {dest}.",
    }

    # Activate immediately when the plugin is enabled (default True).
    _state = state_dir or str(get_state_dir())
    if is_plugin_enabled(dest_name, state_dir=_state, default_enabled=True):
        try:
            result["activation"] = activate_plugin(
                str(dest),
                dest_name,
                mcp_config_path=mcp_config_path,
                roles_dir=roles_dir,
                hooks_registry_path=hooks_registry_path,
            )
        except Exception as exc:  # noqa: BLE001 - install itself succeeded
            result["activation"] = {"ok": False, "error": str(exc)}

    return json.dumps(result)


def _extract_plugin_zip(zip_path: str, dest_dir: str) -> None:
    """Extract a plugin ZIP, unwrapping single top-level directory."""
    import zipfile
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        extract_root = os.path.join(tmpdir, "extracted")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_root)

        items = os.listdir(extract_root)
        src = extract_root
        if len(items) == 1 and os.path.isdir(os.path.join(extract_root, items[0])):
            src = os.path.join(extract_root, items[0])

        shutil.copytree(src, dest_dir)


def _action_remove(
    name: str,
    install_root: str,
    *,
    state_dir: str | None = None,
    mcp_config_path: str | None = None,
    roles_dir: str | None = None,
    hooks_registry_path: str | None = None,
) -> str:
    """Remove (uninstall) a plugin.

    Order: disable-equivalent cleanup (deactivate + settings wipe) then rmtree.
    Unlike disable, enabledPlugins/pluginConfigs keys are deleted, not set false.
    """
    if not name:
        return json.dumps({"ok": False, "error": "Plugin name is required."})

    target = Path(install_root) / name
    if not target.exists():
        return json.dumps(
            {"ok": False, "error": f"Plugin '{name}' not found at {install_root}."}
        )

    # 1) disable-equivalent component teardown (MCP / agents / hooks)
    deactivation = deactivate_plugin(
        name,
        mcp_config_path=mcp_config_path,
        roles_dir=roles_dir,
        hooks_registry_path=hooks_registry_path,
    )

    # 2) wipe settings residue (stronger than disable's false flag)
    sd = state_dir if state_dir is not None else str(get_state_dir())
    settings_cleanup = clear_plugin_settings(name, state_dir=sd)

    # 3) delete install directory (skills live in-place under the plugin)
    shutil.rmtree(str(target))

    return json.dumps(
        {
            "ok": True,
            "message": f"Plugin '{name}' removed.",
            "deactivation": deactivation,
            "settings_cleanup": settings_cleanup,
        }
    )


def _action_review(name: str, state_dir: str, scan_dirs: list[str]) -> str:
    """Validate a plugin and record a reviewed lifecycle state."""
    if not name:
        return json.dumps({"ok": False, "error": _("err.name_required", default="Plugin name is required.")})
    validation = _action_validate(name, scan_dirs)
    try:
        result = json.loads(validation)
    except Exception:
        result = {"ok": False, "error": validation}
    if not result.get("ok"):
        return json.dumps({"ok": False, "error": _("err.review_validation_failed", default="Plugin validation failed."), "validation": result})
    manager = SkillLifecycleManager(Path(state_dir) / "skill_lifecycle.json")
    try:
        manager.register(name, version=str(result.get("version") or ""))
        record = manager.review(name, validation_ok=True, security_review_ok=True)
    except SkillLifecycleError as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    return json.dumps({"ok": True, "name": name, "lifecycle": record.as_dict()})


def _action_enable(
    name: str,
    state_dir: str,
    *,
    scan_dirs: list[str] | None = None,
    confirmed: bool = False,
    allow_unreviewed: bool = False,
    mcp_config_path: str | None = None,
    roles_dir: str | None = None,
    hooks_registry_path: str | None = None,
) -> str:
    """Enable a plugin and activate its components."""
    if not name:
        return json.dumps({"ok": False, "error": "Plugin name is required."})

    if not allow_unreviewed:
        lifecycle = SkillLifecycleManager(Path(state_dir) / "skill_lifecycle.json")
        try:
            record = lifecycle.get(name)
            if record.state != "reviewed":
                return json.dumps({"ok": False, "error": _("err.lifecycle_review_required", default="Skill review is required before enabling.")})
            lifecycle.enable(name, confirmed=confirmed)
        except SkillLifecycleError as exc:
            return json.dumps({"ok": False, "error": str(exc)})

    set_plugin_enabled(name, True, state_dir=state_dir)
    result: dict[str, Any] = {
        "ok": True,
        "message": f"Plugin '{name}' enabled.",
    }

    roots = scan_dirs if scan_dirs is not None else get_plugin_roots()
    plugin = _find_scanned_plugin(name, roots)
    if plugin and plugin.get("_path"):
        try:
            result["activation"] = activate_plugin(
                str(plugin["_path"]),
                name,
                mcp_config_path=mcp_config_path,
                roles_dir=roles_dir,
                hooks_registry_path=hooks_registry_path,
            )
        except Exception as exc:  # noqa: BLE001 - enable flag already saved
            result["activation"] = {"ok": False, "error": str(exc)}

    return json.dumps(result)


def _action_disable(
    name: str,
    state_dir: str,
    *,
    mcp_config_path: str | None = None,
    roles_dir: str | None = None,
    hooks_registry_path: str | None = None,
) -> str:
    """Disable a plugin and deactivate its components."""
    if not name:
        return json.dumps({"ok": False, "error": "Plugin name is required."})

    set_plugin_enabled(name, False, state_dir=state_dir)
    deactivation = deactivate_plugin(
        name,
        mcp_config_path=mcp_config_path,
        roles_dir=roles_dir,
        hooks_registry_path=hooks_registry_path,
    )
    return json.dumps(
        {
            "ok": True,
            "message": f"Plugin '{name}' disabled.",
            "deactivation": deactivation,
        }
    )


def _action_validate(name: str, scan_dirs: list[str]) -> str:
    """Validate a plugin's manifest."""
    if not name:
        return json.dumps({"ok": False, "error": "Plugin name is required."})

    plugins = scan_plugins(scan_dirs)
    for p in plugins:
        if p.get("name") == name:
            ok, errors, warnings = validate_plugin_manifest(p.get("_path", ""), p)
            return json.dumps(
                {
                    "ok": ok,
                    "name": name,
                    "errors": errors,
                    "warnings": warnings,
                },
                ensure_ascii=False,
                indent=2,
            )

    return json.dumps({"ok": False, "error": f"Plugin '{name}' not found."})


# ---------------------------------------------------------------------------
# CLI command handlers
# ---------------------------------------------------------------------------

# Lazy-built CMD_SPECS
CMD_SPECS: list[dict[str, Any]] = []


def _register_cmd_specs() -> None:
    """Register plugin subcommands."""
    global CMD_SPECS
    if CMD_SPECS:
        return

    CMD_SPECS = [
        {
            "command": "plugin",
            "subcommand": "list",
            "handler": _handle_cmd_plugin_list,
            "help_text": _(
                "cmd.help.plugin_list",
                default=(
                    "  :plugin list [--enabled] [--verbose]  List installed plugins."
                ),
            ),
        },
        {
            "command": "plugin",
            "subcommand": "install",
            "handler": _handle_cmd_plugin_install,
            "help_text": _(
                "cmd.help.plugin_install",
                default=(
                    "  :plugin install <source|name|name@marketplace> [name] "
                    "[--scope user|project|local]  Install a plugin. "
                    "Bare names resolve via registered marketplaces."
                ),
            ),
        },
        {
            "command": "plugin",
            "subcommand": "remove",
            "handler": _handle_cmd_plugin_remove,
            "help_text": _(
                "cmd.help.plugin_remove",
                default="  :plugin remove <name>  Remove (uninstall) a plugin.",
            ),
        },
        {
            "command": "plugin",
            "subcommand": "uninstall",
            "handler": _handle_cmd_plugin_remove,
            "help_text": _(
                "cmd.help.plugin_uninstall",
                default="  :plugin uninstall <name>  Alias for remove.",
            ),
        },
        {
            "command": "plugin",
            "subcommand": "enable",
            "handler": _handle_cmd_plugin_enable,
            "help_text": _(
                "cmd.help.plugin_enable",
                default="  :plugin enable <name>  Enable a plugin.",
            ),
        },
        {
            "command": "plugin",
            "subcommand": "disable",
            "handler": _handle_cmd_plugin_disable,
            "help_text": _(
                "cmd.help.plugin_disable",
                default="  :plugin disable <name>  Disable a plugin.",
            ),
        },
        {
            "command": "plugin",
            "subcommand": "reload",
            "handler": _handle_cmd_plugin_reload,
            "help_text": _(
                "cmd.help.plugin_reload",
                default="  :plugin reload  Re-scan all plugin directories.",
            ),
        },
        {
            "command": "plugin",
            "subcommand": "info",
            "handler": _handle_cmd_plugin_info,
            "help_text": _(
                "cmd.help.plugin_info",
                default="  :plugin info <name>  Show plugin details.",
            ),
        },
        {
            "command": "plugin",
            "subcommand": "init",
            "handler": _handle_cmd_plugin_init,
            "help_text": _(
                "cmd.help.plugin_init",
                default="  :plugin init <name>  Scaffold a new plugin directory.",
            ),
        },
        {
            "command": "plugin",
            "subcommand": "validate",
            "handler": _handle_cmd_plugin_validate,
            "help_text": _(
                "cmd.help.plugin_validate",
                default=("  :plugin validate <name>  Validate a plugin's manifest."),
            ),
        },
    ]


def _handle_cmd_plugin_list(arg: str, **kwargs: Any) -> Any:
    """CLI handler for :plugin list."""
    from ..util_tools import CommandResult

    parts = arg.strip().split()
    _enabled_only = "--enabled" in parts
    _verbose = "--verbose" in parts

    scan_dirs = get_plugin_roots()
    result = json.loads(_action_list(scan_dirs, str(get_state_dir())))

    if not result.get("ok"):
        print(f"Error: {result.get('error', 'Unknown error')}")
        return CommandResult()

    plugins = result.get("plugins", [])
    if not plugins:
        print("No plugins found.")
        return CommandResult()

    # Filter
    if _enabled_only:
        plugins = [p for p in plugins if p.get("enabled")]

    # Display
    name_width = max((len(p.get("name", "")) for p in plugins), default=8)
    ver_width = max((len(p.get("version", "")) for p in plugins), default=7)

    print(
        f"{'Name':<{name_width}}  {'Version':<{ver_width}}  {'Enabled':<8}  Description"
    )
    print("-" * (name_width + ver_width + 30))
    for p in plugins:
        en = "yes" if p.get("enabled") else "no"
        print(
            f"{p.get('name', ''):<{name_width}}  "
            f"{p.get('version', ''):<{ver_width}}  "
            f"{en:<8}  "
            f"{p.get('description', '')}"
        )

    if _verbose:
        print()
        for p in plugins:
            path = p.get("path", "")
            if path:
                print(f"  Path: {path}")

    return CommandResult()


def _handle_cmd_plugin_install(arg: str, **kwargs: Any) -> Any:
    """CLI handler for :plugin install <source> [name] [--scope ...]."""
    from ..util_tools import CommandResult

    parts = arg.strip().split()
    if not parts:
        print("Source is required.")
        return CommandResult()

    source = parts[0]
    name = ""
    scope = "user"

    rest = parts[1:]
    i = 0
    while i < len(rest):
        if rest[i] == "--scope" and i + 1 < len(rest):
            scope = rest[i + 1]
            i += 2
        elif not rest[i].startswith("--"):
            name = rest[i]
            i += 1
        else:
            i += 1

    test_install_root = kwargs.get("_test_install_root")
    result = json.loads(
        _action_install(source, name, test_install_root or _get_install_root(scope))
    )

    if result.get("ok"):
        print(f"Installed: {result.get('message')}")
    else:
        print(f"Error: {result.get('error')}")

    return CommandResult()


def _handle_cmd_plugin_remove(arg: str, **kwargs: Any) -> Any:
    """CLI handler for :plugin remove <name>."""
    from ..util_tools import CommandResult

    name = arg.strip()
    if not name:
        print("Plugin name is required.")
        return CommandResult()

    test_install_root = kwargs.get("_test_install_root")
    test_state_dir = kwargs.get("_test_state_dir")
    result = json.loads(
        _action_remove(
            name,
            test_install_root or _get_install_root("user"),
            state_dir=test_state_dir or str(get_state_dir()),
        )
    )

    if result.get("ok"):
        print(f"Removed: {result.get('message')}")
    else:
        print(f"Error: {result.get('error')}")

    return CommandResult()


def _handle_cmd_plugin_enable(arg: str, **kwargs: Any) -> Any:
    """CLI handler for :plugin enable <name>."""
    from ..util_tools import CommandResult

    name = arg.strip()
    if not name:
        print("Plugin name is required.")
        return CommandResult()

    test_state_dir = kwargs.get("_test_state_dir")
    result = json.loads(_action_enable(name, test_state_dir or str(get_state_dir())))

    if result.get("ok"):
        print(f"Enabled: {result.get('message')}")
    else:
        print(f"Error: {result.get('error')}")

    return CommandResult()


def _handle_cmd_plugin_disable(arg: str, **kwargs: Any) -> Any:
    """CLI handler for :plugin disable <name>."""
    from ..util_tools import CommandResult

    name = arg.strip()
    if not name:
        print("Plugin name is required.")
        return CommandResult()

    test_state_dir = kwargs.get("_test_state_dir")
    result = json.loads(_action_disable(name, test_state_dir or str(get_state_dir())))

    if result.get("ok"):
        print(f"Disabled: {result.get('message')}")
    else:
        print(f"Error: {result.get('error')}")

    return CommandResult()


def _handle_cmd_plugin_reload(arg: str, **kwargs: Any) -> Any:
    """CLI handler for :plugin reload."""
    from ..runtime.runtime_plugins import load_plugins_at_startup
    from ..util_tools import CommandResult

    plugins = load_plugins_at_startup(activate=True)
    enabled = [p for p in plugins if p.get("enabled")]
    print(
        f"Plugin reload: {len(plugins)} plugin(s) found, "
        f"{len(enabled)} enabled/activated."
    )
    for p in plugins:
        flag = "on" if p.get("enabled") else "off"
        print(f"  - {p.get('name', '?')} ({p.get('version', '0.0.0')}) [{flag}]")

    return CommandResult()


def _handle_cmd_plugin_info(arg: str, **kwargs: Any) -> Any:
    """CLI handler for :plugin info <name>."""
    from ..util_tools import CommandResult

    name = arg.strip()
    if not name:
        print("Plugin name is required.")
        return CommandResult()

    scan_dirs = get_plugin_roots()
    result = json.loads(_action_info(name, scan_dirs))

    if not result.get("ok"):
        print(f"Error: {result.get('error')}")
        return CommandResult()

    print(f"Name:        {result.get('name', '')}")
    print(f"Version:     {result.get('version', '')}")
    print(f"Description: {result.get('description', '')}")
    print(f"Path:        {result.get('path', '')}")
    print(f"Valid:       {result.get('valid', False)}")

    comps = result.get("components", {})
    if comps:
        print("Components:")
        for ctype, items in comps.items():
            if isinstance(items, list):
                print(f"  {ctype}: {', '.join(items)}")
            else:
                print(f"  {ctype}: yes")

    errors = result.get("errors", [])
    if errors:
        print("Errors:")
        for e in errors:
            print(f"  - {e}")

    warnings = result.get("warnings", [])
    if warnings:
        print("Warnings:")
        for w in warnings:
            print(f"  - {w}")

    return CommandResult()


def _handle_cmd_plugin_init(arg: str, **kwargs: Any) -> Any:
    """CLI handler for :plugin init <name>.

    Scaffolds a minimal plugin directory structure with a manifest.
    """
    from ..util_tools import CommandResult

    name = arg.strip()
    if not name:
        print("Plugin name is required.")
        return CommandResult()

    # Determine target: current dir by default
    target = Path.cwd() / name
    if target.exists():
        print(f"Directory '{name}' already exists.")
        return CommandResult()

    # Create structure
    manifest_dir = target / ".claude-plugin"
    manifest_dir.mkdir(parents=True)

    manifest = {
        "name": name,
        "version": "0.1.0",
        "description": f"Plugin: {name}",
    }
    (manifest_dir / "plugin.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    # Create skills directory
    skill_dir = target / "skills" / "hello"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: hello\n"
        "description: A sample skill\n"
        "---\n\n"
        "Hello from the plugin!\n",
        encoding="utf-8",
    )

    print(f"Plugin '{name}' scaffolded at {target}.")
    return CommandResult()


def _handle_cmd_plugin_validate(arg: str, **kwargs: Any) -> Any:
    """CLI handler for :plugin validate <name>."""
    from ..util_tools import CommandResult

    name = arg.strip()
    if not name:
        print("Plugin name is required.")
        return CommandResult()

    scan_dirs = get_plugin_roots()
    result = json.loads(_action_validate(name, scan_dirs))

    if not result.get("ok"):
        if "not found" in result.get("error", ""):
            # Try as path directly
            manifest = parse_plugin_manifest(name)
            if manifest is None:
                print(f"Plugin not found: {name}")
                return CommandResult()
            ok, errors, warnings = validate_plugin_manifest(name, manifest)
            result = {
                "ok": ok,
                "name": manifest.get("name", name),
                "errors": errors,
                "warnings": warnings,
            }

    if result.get("ok"):
        print(f"Plugin '{result.get('name')}' is valid.")
    else:
        print(f"Plugin '{result.get('name')}' has issues:")

    for e in result.get("errors", []):
        print(f"  ERROR: {e}")
    for w in result.get("warnings", []):
        print(f"  WARNING: {w}")

    return CommandResult()


# ---------------------------------------------------------------------------
# Marketplace CLI handlers
# ---------------------------------------------------------------------------


def _handle_cmd_plugin_marketplace(arg: str, **kwargs: Any) -> Any:
    """CLI handler for :plugin marketplace <subcommand> [args]."""
    from ..util_tools import CommandResult

    parts = arg.strip().split()
    if not parts:
        print("Marketplace subcommand required: add, remove, list, update")
        return CommandResult()

    subcmd = parts[0]
    rest = parts[1:]

    if subcmd == "list":
        from ..plugin_shared import list_marketplaces

        mps = list_marketplaces()
        if not mps:
            print("No marketplaces registered.")
        else:
            for mp in mps:
                name = mp.get("name", "?")
                url = mp.get("url", "?")
                builtin = mp.get("builtin", False)
                tag = " (builtin)" if builtin else ""
                print(f"  {name}{tag}: {url}")
        return CommandResult()

    elif subcmd == "add":
        if not rest:
            print("Usage: :plugin marketplace add <url>")
            return CommandResult()
        url = rest[0]
        # Infer name from URL
        import re

        name_match = re.search(r"([^/]+)/([^/]+?)(?:\.git)?$", url)
        name = name_match.group(0).replace("/", "-") if name_match else url
        from ..plugin_shared import add_marketplace

        result = add_marketplace(name, url)
        if result.get("ok"):
            print(f"Marketplace '{name}' added.")
        else:
            print(f"Error adding marketplace: {result.get('error')}")
        return CommandResult()

    elif subcmd == "remove":
        if not rest:
            print("Usage: :plugin marketplace remove <name>")
            return CommandResult()
        name = rest[0]
        from ..plugin_shared import remove_marketplace

        result = remove_marketplace(name)
        if result.get("removed"):
            print(f"Marketplace '{name}' removed.")
        else:
            print(f"Marketplace '{name}' not found.")
        return CommandResult()

    elif subcmd == "update":
        if not rest:
            print("Usage: :plugin marketplace update <name>")
            return CommandResult()
        name = rest[0]
        from ..plugin_shared import list_marketplaces, add_marketplace

        mps = list_marketplaces()
        mp = next((m for m in mps if m.get("name") == name), None)
        if mp:
            # Re-add with same URL to refresh
            add_marketplace(name, mp.get("url", ""))
            print(f"Marketplace '{name}' updated.")
        else:
            print(f"Marketplace '{name}' not found.")
        return CommandResult()

    else:
        print(f"Unknown marketplace subcommand: {subcmd}")
        print("Available: add, remove, list, update")
        return CommandResult()


# Ensure CMD_SPECS is populated at import time
_register_cmd_specs()


# Add marketplace to CMD_SPECS after registration
def _register_marketplace_cmd() -> None:
    """Add marketplace subcommand to the plugin command."""
    global CMD_SPECS
    mp_entry = {
        "command": "plugin",
        "subcommand": "marketplace",
        "handler": _handle_cmd_plugin_marketplace,
        "help_text": _(
            "cmd.help.plugin_marketplace",
            default=(
                "  :plugin marketplace add <url>      Register a marketplace\n"
                "  :plugin marketplace remove <name>  Remove a marketplace\n"
                "  :plugin marketplace list           List registered marketplaces\n"
                "  :plugin marketplace update <name>  Update a marketplace catalog"
            ),
        ),
    }
    # Avoid duplicates
    for spec in CMD_SPECS:
        if spec.get("command") == "plugin" and spec.get("subcommand") == "marketplace":
            return
    CMD_SPECS.append(mp_entry)


_register_marketplace_cmd()
