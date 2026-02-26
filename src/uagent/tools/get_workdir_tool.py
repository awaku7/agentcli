from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from typing import Dict, Any

# Tool metadata definition (loaded by tools/__init__.py)
TOOL_SPEC: Dict[str, Any] = {
    "type": "function",  # Mandatory for OpenAI / Azure
    "function": {
        "name": "get_workdir",
        "description": _("tool.description", default="Get the current working directory."),
        "system_prompt": _(
            "tool.system_prompt",
            default="This tool is used for the following purpose: get the current working directory.",
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
    # Metadata indicating this tool does not generate content shown directly to users (optional)
    "is_agent_content": False,
}

# Whether to show a Busy status (False because this tool is fast)
BUSY_LABEL = False


def run_tool(args: Dict[str, Any]) -> str:
    """Get the current working directory and return it."""
    import os

    return os.getcwd()


# Entry point for direct execution (for testing, not called from the toolchain)
if __name__ == "__main__":
    print(run_tool({}))
