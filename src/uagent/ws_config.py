from __future__ import annotations

"""
WebSocket configuration manager for VSCode extension integration.
Bridges VSCode settings and uag environment variables.
"""

import os
from typing import Any


class WsConfigManager:
    """Configuration manager.

    Priority: VSCode settings > environment variables > .env file defaults.
    VSCode-sent values are session-scoped and do not modify the actual environment.
    """

    def __init__(self):
        self._overrides: dict[str, str] = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value by key.
        Checks: VSCode override -> env var -> default.
        """
        if key in self._overrides:
            return self._overrides[key]

        env_key = self._to_env_key(key)
        env_val = os.environ.get(env_key)
        if env_val is not None:
            return env_val

        return default

    def get_all(self) -> dict[str, Any]:
        """Return all known config values."""
        return {
            "provider": self.get("provider", ""),
            "model": self.get("model", ""),
            "workdir": self.get("workdir", ""),
            "lang": self.get("lang", "en"),
        }

    def set(self, key: str, value: str) -> None:
        """Set a VSCode-scoped override (does NOT modify os.environ)."""
        if value:
            self._overrides[key] = value
        else:
            self._overrides.pop(key, None)

    @staticmethod
    def _to_env_key(key: str) -> str:
        """Convert config key to environment variable name.
        e.g. 'provider' -> 'UAGENT_PROVIDER'
             'model'    -> 'UAGENT_DEPNAME'
        """
        mapping = {
            "provider": "UAGENT_PROVIDER",
            "model": "UAGENT_DEPNAME",
            "lang": "UAGENT_LANG",
            "workdir": "UAGENT_WORKDIR",
        }
        return mapping.get(key, f"UAGENT_{key.upper()}")
