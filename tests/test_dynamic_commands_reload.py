"""`:tools reload` (importlib.reload of uagent.tools) resets the command registry.

The registry lives in ``tools/_dynamic_commands.py``, which stays cached when
only the package is reloaded. Commands of removed plugins must not survive.
Runs in a subprocess so reloading the package does not affect other tests.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"

_SCRIPT = r"""
import importlib, json, sys
sys.path.insert(0, sys.argv[1])
import uagent.tools as tools
from uagent.tools import _dynamic_commands

tools._ensure_loaded()
plugin_commands = set(tools._DYNAMIC_COMMANDS)
tools.register_dynamic_command(
    "zz_removed_probe", lambda arg: "stale", subcommand="run", help_text="x"
)
before = "zz_removed_probe" in tools._DYNAMIC_COMMANDS

importlib.reload(tools)

out = {
    "before": before,
    "after_reload": "zz_removed_probe" in tools._DYNAMIC_COMMANDS,
    "same_registry": tools._DYNAMIC_COMMANDS is _dynamic_commands._DYNAMIC_COMMANDS,
}
tools._ensure_loaded()
out["plugin_commands_back"] = bool(plugin_commands) and plugin_commands <= set(
    tools._DYNAMIC_COMMANDS
)
print("RESULT=" + json.dumps(out))
"""


def test_package_reload_drops_commands_of_removed_plugins(tmp_path: Path) -> None:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.update(
        {
            "UAGENT_STATE_DIR": str(tmp_path / "state"),
            "UAGENT_AUTO_INSTALL": "off",
            "UAGENT_TOOLS_WARMUP": "0",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(SRC_DIR)],
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT=")]
    assert lines, proc.stderr[-3000:]
    result = json.loads(lines[-1][len("RESULT=") :])
    assert result == {
        "before": True,
        "after_reload": False,
        "same_registry": True,
        "plugin_commands_back": True,
    }
