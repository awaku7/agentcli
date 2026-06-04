# tools/skills_uninstall_tool.py
"""skills_uninstall_tool implementation for removing Agent Skills."""

from __future__ import annotations

import json
import os
import shutil
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

STATUS_LABEL = "tool:skills_uninstall"

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "skills_uninstall",
        "description": _(
            "tool.description",
            default="Uninstall an Agent Skill from ~/.uag/skills.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "skills_uninstall",
                "uninstall skill",
                "remove skill",
                "delete skill",
            ],
        ),
        "x_search_terms_en": [
            "skills_uninstall",
            "uninstall skill",
            "remove skill",
            "delete skill",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": _(
                        "param.name.description",
                        default="The folder name of the skill to uninstall.",
                    ),
                },
            },
            "required": ["name"],
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    """Execute the skills_uninstall tool."""
    name = (args.get("name") or "").strip()

    if not name:
        return json.dumps({"ok": False, "message": _("err.name_required", default="Skill name is required.")})

    # Directory traversal check on name
    if "/" in name or "\\" in name or ".." in name or name in (".", ""):
        return json.dumps(
            {
                "ok": False,
                "message": _("err.invalid_name", default="Invalid skill folder name: {name}").format(name=name),
            }
        )

    # Centralized skills directory
    skills_root = os.path.join(os.path.expanduser("~"), ".uag", "skills")
    dest_dir = os.path.join(skills_root, name)

    if not os.path.exists(dest_dir):
        return json.dumps(
            {
                "ok": False,
                "message": _("err.not_found", default="Skill '{name}' is not installed in {root}").format(
                    name=name, root=skills_root
                ),
            }
        )

    try:
        shutil.rmtree(dest_dir)
        return json.dumps(
            {
                "ok": True,
                "path": dest_dir,
                "message": _(
                    "success.uninstalled",
                    default="Successfully uninstalled skill '{name}' from {path}",
                ).format(name=name, path=dest_dir),
            }
        )
    except Exception as e:
        return json.dumps(
            {
                "ok": False,
                "message": _("err.unexpected", default="An unexpected error occurred: {error}").format(error=str(e)),
            }
        )


def handle_cmd_uninstall(arg: str, **kwargs: Any) -> Any:
    """CLI command handler for :skills uninstall <name>."""
    from ..util_tools import CommandResult

    name = arg.strip()
    if not name:
        print(_("err.name_required", default="Skill name is required."))
        return CommandResult()

    res_json = run_tool({"name": name})
    res = json.loads(res_json)

    if res.get("ok"):
        print(f"[skills] {res.get('message')}")
    else:
        print(f"[skills error] {res.get('message')}")

    return CommandResult()


CMD_SPEC = {
    "command": "skills",
    "subcommand": "uninstall",
    "handler": handle_cmd_uninstall,
}
