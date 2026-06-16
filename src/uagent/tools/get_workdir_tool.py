from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from typing import Any

# Tool metadata definition (loaded by tools/__init__.py)
TOOL_SPEC: dict[str, Any] = {
    "type": "function",  # Mandatory for OpenAI / Azure
    "tool_genre": "basic",
    "function": {
        "name": "get_workdir",
        "description": _(
            "tool.description", default="Get the current working directory."
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "working directory",
                "cwd",
                "current dir",
                "作業ディレクトリ",
                "directorio de trabajo",
                "répertoire de travail",
                "작업 디렉터리",
                "рабочая директория",
            ],
        ),
        "x_search_terms_en": [
            "working directory",
            "cwd",
            "current dir",
            "作業ディレクトリ",
            "directorio de trabajo",
            "répertoire de travail",
            "작업 디렉터리",
            "рабочая директория",
        ],
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


def run_tool(args: dict[str, Any]) -> str:
    """Get the current working directory and return it."""
    import os

    return os.getcwd()


# Entry point for direct execution (for testing, not called from the toolchain)
if __name__ == "__main__":
    print(run_tool({}))
