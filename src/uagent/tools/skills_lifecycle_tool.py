from __future__ import annotations

import json
from typing import Any

from ..runtime.skill_lifecycle import SkillLifecycleError, SkillLifecycleManager
from .i18n_helper import make_tool_translator
from .skills_list_tool import run_tool as list_skills
from ..util_tools import CommandResult

_ = make_tool_translator(__file__)


def _find(name: str) -> dict[str, Any] | None:
    try:
        rows = json.loads(list_skills({"include_invalid": True}))
    except Exception:
        return None
    for row in rows if isinstance(rows, list) else []:
        if str(row.get("name") or "") == name or str(row.get("path") or "") == name:
            return row
    return None


def handle_cmd_review(arg: str, **kwargs: Any) -> CommandResult:
    name = arg.strip()
    if not name:
        print(_("err.name_required", default="Skill name is required."))
        return CommandResult()
    item = _find(name)
    if not item or not item.get("ok"):
        print(_("err.review_validation_failed", default="Skill validation failed."))
        return CommandResult()
    target = str(item.get("name") or name)
    manager = SkillLifecycleManager()
    try:
        manager.register(target)
        record = manager.review(target, validation_ok=True, security_review_ok=True)
        print(_("out.reviewed", default="Skill '{name}' is reviewed.").format(name=target))
        print(json.dumps(record.as_dict(), ensure_ascii=False, indent=2))
    except SkillLifecycleError as exc:
        print(str(exc))
    return CommandResult()


def handle_cmd_enable(arg: str, **kwargs: Any) -> CommandResult:
    parts = arg.strip().split()
    name = parts[0] if parts else ""
    confirmed = "--yes" in parts[1:] or "-y" in parts[1:]
    if not name:
        print(_("err.name_required", default="Skill name is required."))
        return CommandResult()
    if not confirmed:
        print(_("err.confirmation_required", default="Explicit confirmation is required. Use --yes to enable the Skill."))
        return CommandResult()
    try:
        record = SkillLifecycleManager().enable(name, confirmed=True)
        print(_("out.enabled", default="Skill '{name}' is enabled.").format(name=name))
        print(json.dumps(record.as_dict(), ensure_ascii=False, indent=2))
    except SkillLifecycleError as exc:
        print(str(exc))
    return CommandResult()


CMD_SPECS = [
    {"command": "skills", "subcommand": "review", "handler": handle_cmd_review,
     "help_text": _("help.review", default="  :skills review <name>  Validate and review a Skill."),
     "usage": ":skills review <name>"},
    {"command": "skills", "subcommand": "enable", "handler": handle_cmd_enable,
     "help_text": _("help.enable", default="  :skills enable <name> --yes  Enable a reviewed Skill."),
     "usage": ":skills enable <name> --yes"},
]
