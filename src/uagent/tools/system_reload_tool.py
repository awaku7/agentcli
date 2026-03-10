from typing import Any, Dict

from . import reload_plugins
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "system_reload",
        "description": _(
            "tool.description",
            default=(
                "Reload the system and reflect the latest code for all tools under tools/ (Python .py files) into memory. Run this after modifying code."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "This tool is used for the following purpose: reload the system and reflect the latest code for all tools under tools/ (Python .py files) into memory. Run this after modifying code."
            ),
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    try:
        reload_plugins()
        return "System reload successful. All plugins have been reloaded with the latest code."
    except Exception as e:
        return f"Error during system reload: {str(e)}"
