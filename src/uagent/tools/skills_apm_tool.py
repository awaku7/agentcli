# tools/skills_apm_tool.py
"""skills_apm_tool for browsing and using APM-installed skills.

APM (Agent Package Manager) by Microsoft installs skills to:
  <project-root>/apm_modules/<package>/.apm/skills/<skill-name>/SKILL.md

This tool discovers and activates those skills.
"""

from __future__ import annotations

import json
import os
from typing import Any

from .i18n_helper import make_tool_translator
from .agent_skills_shared import load_skill_doc, load_skill_frontmatter_only

_ = make_tool_translator(__file__)

STATUS_LABEL = "tool:skills_apm"

# APM project root directory (persistent across calls)
_apm_dir: str | None = None


def _get_apm_dir() -> str:
    """Return the current APM project root directory."""
    global _apm_dir
    if _apm_dir:
        return _apm_dir
    return os.getcwd()


def _scan_apm_skills(apm_root: str) -> list[dict[str, Any]]:
    """Scan apm_modules/ for SKILL.md files and return info dicts."""
    results: list[dict[str, Any]] = []
    apm_modules = os.path.join(apm_root, "apm_modules")
    if not os.path.isdir(apm_modules):
        return results

    try:
        pkg_entries = sorted(os.listdir(apm_modules))
    except PermissionError:
        return results

    for pkg_name in pkg_entries:
        skills_dir = os.path.join(apm_modules, pkg_name, ".apm", "skills")
        if not os.path.isdir(skills_dir):
            continue
        try:
            skill_names = sorted(os.listdir(skills_dir))
        except PermissionError:
            continue
        for skill_name in skill_names:
            skill_path = os.path.join(skills_dir, skill_name)
            skill_md = os.path.join(skill_path, "SKILL.md")
            if not os.path.isfile(skill_md):
                continue
            fm = {}
            try:
                fm = load_skill_frontmatter_only(skill_path)
            except Exception:
                pass
            results.append({
                "name": fm.get("name") or skill_name,
                "package": pkg_name,
                "path": skill_path,
                "skill_md": skill_md,
                "description": fm.get("description") or "",
                "metadata": fm.get("metadata"),
                "allowed_tools": fm.get("allowed-tools"),
            })

    return results


def handle_cmd_apm(arg: str, **kwargs: Any) -> Any:
    """CLI command handler for :skills apm <subcommand> [args]."""
    from ..util_tools import CommandResult

    parts = arg.strip().split(maxsplit=1)
    subcmd = parts[0].lower() if parts else ""
    subarg = parts[1].strip() if len(parts) > 1 else ""

    if not subcmd or subcmd in ("help", "--help"):
        print(_(
            "help_text",
            default=(
                "  :skills apm list                    List skills from APM apm_modules/\n"
                "  :skills apm use <name|#>            Load and activate an APM skill\n"
                "  :skills apm dir [path]              Show or set APM project root"
            ),
        ))
        return CommandResult()

    if subcmd == "list":
        return _handle_apm_list(subarg, **kwargs)
    elif subcmd == "use":
        return _handle_apm_use(subarg, **kwargs)
    elif subcmd in ("dir", "path"):
        return _handle_apm_dir(subarg, **kwargs)
    else:
        print(_(
            "err.unknown_subcommand",
            default="[apm] Unknown subcommand: {cmd}",
        ).format(cmd=subcmd))
        return CommandResult()


def _handle_apm_list(arg: str, **kwargs: Any) -> Any:
    from ..util_tools import CommandResult

    apm_root = _get_apm_dir()
    skills = _scan_apm_skills(apm_root)

    if not skills:
        print(_(
            "msg.no_skills",
            default="[apm] No skills found in {path}/apm_modules/",
        ).format(path=apm_root))
        return CommandResult()

    print(_(
        "msg.found_skills",
        default="[apm] Found {n} skill(s) in {path}/apm_modules/:",
    ).format(n=len(skills), path=apm_root))
    print("")

    for i, s in enumerate(skills, start=1):
        name = s.get("name") or "(unknown)"
        pkg = s.get("package") or "?"
        desc = s.get("description") or ""
        print(f"  [{i}] {name}  (package: {pkg})")
        if desc:
            desc_display = desc[:100] + "..." if len(desc) > 100 else desc
            print(f"       {desc_display}")
        print()

    print(_(
        "msg.use_hint",
        default="[apm] Use ':skills apm use <number>' to activate a skill.",
    ))
    return CommandResult()


def _handle_apm_use(arg: str, **kwargs: Any) -> Any:
    from ..util_tools import CommandResult

    if not arg.strip():
        print(_("err.name_required", default="[apm] Specify a skill name or number."))
        return CommandResult()

    apm_root = _get_apm_dir()
    skills = _scan_apm_skills(apm_root)

    if not skills:
        print(_(
            "msg.no_skills",
            default="[apm] No skills found in {path}/apm_modules/",
        ).format(path=apm_root))
        return CommandResult()

    selected = None
    if arg.isdigit():
        n = int(arg)
        if 1 <= n <= len(skills):
            selected = skills[n - 1]
        else:
            print(_(
                "err.out_of_range",
                default="[apm] Number out of range (1-{max}).",
            ).format(max=len(skills)))
            return CommandResult()
    else:
        arg_lower = arg.strip().lower()
        matches = [s for s in skills if s.get("name", "").lower() == arg_lower]
        if not matches:
            matches = [s for s in skills
                       if s.get("name", "").lower().startswith(arg_lower)]
        if not matches:
            for s in skills:
                full = f"{s.get('package', '')}/{s.get('name', '')}".lower()
                if arg_lower in full:
                    matches.append(s)
        if len(matches) == 1:
            selected = matches[0]
        elif len(matches) > 1:
            print(_(
                "msg.multiple_matches",
                default="[apm] Multiple matches. Please use a number:\n",
            ))
            for i, m in enumerate(matches, start=1):
                print(f"  [{i}] {m.get('name')} (package: {m.get('package')})")
            return CommandResult()
        else:
            print(_(
                "err.not_found",
                default="[apm] No skill matching '{name}' found.",
            ).format(name=arg))
            return CommandResult()

    skill_dir = selected["path"]
    try:
        doc = load_skill_doc(skill_dir)
    except Exception as e:
        print(_(
            "err.load_failed",
            default="[apm] Failed to load skill: {err}",
        ).format(err=repr(e)))
        return CommandResult()

    name = selected["name"]
    prefix = "[SKILL] "
    header_parts = [f"{prefix}name={name}"]
    header_parts.append(f"path={skill_dir}")
    header_parts.append(f"skill_md={selected['skill_md']}")

    allowed_tools = selected.get("allowed_tools")
    if allowed_tools is not None:
        header_parts.append(f"allowed-tools={allowed_tools}")

    header = " ".join(header_parts)
    body = (doc.body_markdown or "").strip()
    exec_instructions = (
        "\n\n"
        "[Skill execution]\n"
        "This skill is intended to be run. Read the skill body carefully "
        "and follow the instructions.\n"
        "If the skill contains tasks, continue until they are complete.\n"
        "Use tools as needed.\n"
        "When finished, always call `finish_skill` if available.\n"
    )
    if body:
        content = header + "\n\n" + body + exec_instructions + "\n"
    else:
        content = header + exec_instructions + "\n"

    skill_msg = {"role": "system", "content": content}

    messages_ref = kwargs.get("messages_ref")
    core = kwargs.get("core")
    if messages_ref is not None:
        idx = 0
        while idx < len(messages_ref) and messages_ref[idx].get("role") == "system":
            idx += 1
        messages_ref.insert(idx, skill_msg)

        try:
            cb = __import__(
                "uagent.tools.context", fromlist=["get_callbacks"]
            ).get_callbacks()
            rewrite = getattr(cb, "rewrite_current_log_from_messages", None)
            if rewrite is not None:
                rewrite(messages_ref)
            elif core is not None:
                core.rewrite_current_log_from_messages(messages_ref)
        except Exception:
            pass

        print(_(
            "msg.applied",
            default="[apm] Applied APM skill: {name}",
        ).format(name=name))
        return CommandResult(run_llm=True)
    else:
        print("[apm] Skill content (messages_ref not available):")
        print(content)
        return CommandResult()


def _handle_apm_dir(arg: str, **kwargs: Any) -> Any:
    from ..util_tools import CommandResult

    global _apm_dir

    if arg.strip():
        new_dir = os.path.abspath(arg.strip())
        if not os.path.isdir(new_dir):
            print(_(
                "err.dir_not_found",
                default="[apm] Directory not found: {path}",
            ).format(path=new_dir))
            return CommandResult()
        _apm_dir = new_dir
        print(_(
            "msg.dir_set",
            default="[apm] APM project root set to: {path}",
        ).format(path=new_dir))
    else:
        current = _get_apm_dir()
        print(_(
            "msg.dir_current",
            default="[apm] APM project root: {path}",
        ).format(path=current))

    return CommandResult()


CMD_SPEC = {
    "command": "skills",
    "subcommand": "apm",
    "handler": handle_cmd_apm,
    "help_text": _(
        "help_text",
        default=(
            "  :skills apm list                    List skills from APM apm_modules/\n"
            "  :skills apm use <name|#>            Load and activate an APM skill\n"
            "  :skills apm dir [path]              Show or set APM project root"
        ),
    ),
}
