# MCP configuration shared utilities
from __future__ import annotations

import json
import os
from typing import Any


def get_default_mcp_config_path() -> str:
    """Return the default path to the MCP server configuration file.

    Priority:
    1. Environment variable UAGENT_MCP_CONFIG
    2. <state>/mcps/mcp_servers.json (Default: ~/.uag/mcps/mcp_servers.json)
    """
    from uagent.utils.paths import get_mcp_servers_json_path

    return str(get_mcp_servers_json_path())


def is_trusted_mcp_trace_propagation_enabled(server: Any) -> bool:
    """Return whether a managed HTTP MCP server explicitly opts into tracing.

    Only the exact JSON boolean ``true`` combined with a managed ``http://`` or
    ``https://`` URL crosses this trust boundary. String/integer truthy values and
    non-HTTP transports remain untrusted.
    """

    if not isinstance(server, dict) or server.get("trusted_trace_propagation") is not True:
        return False
    url = server.get("url")
    return isinstance(url, str) and url.strip().lower().startswith(
        ("http://", "https://")
    )


def ensure_mcp_config_template() -> str:
    """Create a default template file only if the standard configuration file does not exist.

    Returns the path to the created (or already existing) file.
    """
    from uagent.utils.paths import get_mcps_dir

    path = str(get_mcps_dir() / "mcp_servers.json")

    if os.path.exists(path):
        return path

    os.makedirs(os.path.dirname(path), exist_ok=True)

    data = {"mcp_servers": []}

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return path
