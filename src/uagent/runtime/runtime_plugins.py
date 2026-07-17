"""Runtime plugin loader for uagent.

Scans plugin directories at startup and loads enabled plugins.
Integrates with the existing skills, MCP, and command systems.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..plugin_shared import (
    discover_plugin_components,
    get_plugin_roots,
    is_plugin_enabled,
    parse_plugin_manifest,
    scan_plugins,
)
from ..utils.paths import get_state_dir


def load_plugins_at_startup(
    *,
    cwd: str | None = None,
    plugin_dirs: list[str] | None = None,
    extra_plugin_dirs: list[str] | None = None,
    state_dir: str | None = None,
) -> list[dict[str, Any]]:
    """Scan and load plugins at startup.

    Args:
        cwd: Current working directory (for resolving project roots).
        plugin_dirs: Override plugin scan directories (if None, uses get_plugin_roots()).
        extra_plugin_dirs: Additional plugin directories (from --plugin-dir).
        state_dir: State directory for enablement checks.

    Returns:
        List of loaded plugin info dicts.
    """
    _cwd = cwd or os.getcwd()
    _state_dir = state_dir or str(get_state_dir())

    # Determine scan roots
    if plugin_dirs is not None:
        scan_roots = plugin_dirs
    else:
        scan_roots = get_plugin_roots(cwd=_cwd)

    # Add extra dirs (--plugin-dir) at the front (highest priority)
    if extra_plugin_dirs:
        scan_roots = list(extra_plugin_dirs) + scan_roots

    # Discover all plugins
    all_plugins = scan_plugins(scan_roots)

    # Load each plugin
    loaded: list[dict[str, Any]] = []
    for manifest in all_plugins:
        name = manifest.get("name", "?")
        plugin_path = manifest.get("_path", "")

        # Check if enabled
        de = manifest.get("defaultEnabled", True)
        if not isinstance(de, bool):
            de = True
        enabled = is_plugin_enabled(
            name, state_dir=_state_dir, default_enabled=de
        )

        # Discover components
        components = discover_plugin_components(plugin_path, manifest)

        plugin_info = {
            "name": name,
            "version": manifest.get("version", "0.0.0"),
            "path": plugin_path,
            "enabled": enabled,
            "components": components,
        }

        if enabled:
            # TODO Phase 2: actual integration with skills/MCP/command systems
            pass

        loaded.append(plugin_info)

    return loaded
