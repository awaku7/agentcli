from __future__ import annotations

from typing import Any

import importlib
import sys

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
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "reload system",
                "refresh tools",
                "reload code",
                "システムリロード",
                "recargar sistema",
                "recharger le système",
                "시스템 재로드",
                "перезагрузить систему",
            ],
        ),
        "x_search_terms_en": [
            "reload system",
            "refresh tools",
            "reload code",
            "システムリロード",
            "recargar sistema",
            "recharger le système",
            "시스템 재로드",
            "перезагрузить систему",
        ],
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}


def run_tool(args: dict[str, Any]) -> str:
    try:
        pkg_name = __package__ or "src.uagent.tools"
        mod = sys.modules.get(pkg_name)
        if mod is None:
            mod = importlib.import_module(pkg_name)
        importlib.reload(mod)
        return "System reload successful. All tools were reloaded with the latest code."
    except Exception as e:
        return f"Error during system reload: {str(e)}"
