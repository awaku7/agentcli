"""Static and dynamic help formatting (moved from util_tools.py)."""

from __future__ import annotations

from typing import Any

from . import tools
from .i18n import _

# Default translation function used when core.tr is not provided.
tr = _
tr_ = _


def format_help(*, core: Any, topic: str | None = None) -> str:
    """Format help text for interactive :help.

    - No topic: short overview (A)
    - topic set: detailed help for that command (B), including dynamic CMD_SPEC
    """

    tr = getattr(core, "tr", tr_)
    topic_s = (topic or "").strip()
    if topic_s:
        return format_help_detail(topic_s, core=core)

    # --- Overview (short) ---
    static_lines = [
        tr("Available commands:"),
        "  :help [cmd]           " + tr("Show this help, or details for a command"),
        "  :h / :?               " + tr("Alias for :help"),
        "  :cd <path>            " + tr("Change workdir"),
        "  :ls [path]            " + tr("List directory"),
        "  :logs                 " + tr("List conversation logs"),
        "  :load <idx|path>      " + tr("Load a past log into this session"),
        "  :cont                 " + tr("Continue from latest log (:load 0)"),
        "  :clean [N]            " + tr("Delete short logs (default N=5 user turns)"),
        "  :shrink [N]           " + tr("Shrink history (keep last N)"),
        "  :shrink_llm [N]       " + tr("LLM-summarize older history"),
        "  :tokens               " + tr("Show approx. conversation tokens"),
        "  :response ...          " + tr("Manage Responses API lifecycle"),
        "  :env ...              " + tr("Show/set/unset/save UAGENT_* env"),
        "  :skills ...           " + tr("List/apply/install skills"),
        "  :tools ...            " + tr("List/load/on/off tools and genres"),
        "  :plugin ...           " + tr("Manage plugins"),
        "  :tool create ...      " + tr("Scaffold a new tool module"),
        "  :auto <goal>|off      " + tr("Auto-pilot loop / stop"),
        "  :model                " + tr("Show model configuration"),
        "  :r / :v               " + tr("Reasoning / verbosity"),
        "  :mem-list / :mem-del  " + tr("Long-term memory"),
        "  :profile ...          " + tr("User profile show/generate/clear"),
        "  :cp / :mv / :rm       " + tr("Copy, move, delete paths"),
        "  :head / :tail         " + tr("Show file head/tail"),
        "  :reload               " + tr("Reload runtime pieces"),
        "  :exit / :quit         " + tr("Exit"),
    ]

    dyn_block: list[str] = []
    try:
        dyn_help = tools.get_dynamic_commands_help() if tools else []
    except Exception:
        dyn_help = []
    if dyn_help:
        dyn_block.append("")
        dyn_block.append(tr("Dynamic commands (from tools CMD_SPEC):"))
        for line in dyn_help:
            s = str(line).rstrip()
            if not s:
                continue
            stripped = s.lstrip()
            dyn_block.append("  " + stripped if stripped.startswith(":") else s)

    lines = (
        static_lines
        + dyn_block
        + [
            "",
            tr("Hints:"),
            "  "
            + tr("Type :help <command> for details (e.g. :help tools, :help skills)."),
            "  " + tr("Enter a line that is just 'f' to enter multiline input mode."),
            '  """retry  ' + tr("(in multiline) restart input from the beginning"),
        ]
    )

    norm_lines = []
    for ln in lines:
        s = str(ln)
        stripped = s.lstrip()
        if stripped.startswith(":"):
            s = "  " + stripped
        norm_lines.append(s)

    return "\n".join(norm_lines)


def _static_help_catalog(*, tr: Any) -> dict[str, dict[str, Any]]:
    """Detailed help for built-in (non-CMD_SPEC) commands."""

    def e(
        summary: str,
        usage: str = "",
        detail: str = "",
        aliases: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "summary": summary,
            "usage": usage,
            "detail": detail,
            "aliases": aliases or [],
        }

    cat: dict[str, dict[str, Any]] = {
        "help": e(
            tr("Show command help"),
            usage=(":help [command [subcommand]]"),
            detail=tr(
                "Without args: short list of all commands.\n"
                "With a command: detailed usage (static + dynamic CMD_SPEC).\n"
                "Examples: :help tools | :help skills install | :help plugin"
            ),
            aliases=["h", "?"],
        ),
        "cd": e(
            tr("Change workdir without confirmation"),
            usage=(":cd <path>"),
            detail=tr("Examples: :cd .. | :cd ~ | :cd C:\\path | :cd /"),
        ),
        "ls": e(
            tr("List directory entries"),
            usage=(":ls [path]"),
            detail=tr("Examples: :ls | :ls .. | :ls ~ | :ls C:\\path"),
        ),
        "logs": e(tr("Show conversation log file list"), usage=(":logs")),
        "load": e(
            tr("Load a past log (overwrites current conversation history)"),
            usage=(":load <idx|path>"),
            detail=tr(
                "idx is from :logs. After load you may be asked to prepend into the current session log."
            ),
        ),
        "cont": e(
            tr("Load the newest log (:load 0)"),
            usage=(":cont"),
        ),
        "clean": e(
            tr("Delete short conversation logs"),
            usage=(":clean [N]"),
            detail=tr(
                "Deletes scheck_log_*.jsonl where user-turn count (role=user) <= N "
                "(default 5, or UAGENT_CLEAN_THRESHOLD). "
                "On :exit/:quit/Ctrl-C, the current session log is discarded under the same rule. "
                "A silent startup sweep also removes leftover short logs from prior sessions."
            ),
        ),
        "shrink": e(
            tr("Shrink conversation history"),
            usage=(":shrink [N]"),
            detail=tr("Keep last N non-system messages (default 40)."),
        ),
        "shrink_llm": e(
            tr("Shrink history via LLM summarization"),
            usage=(":shrink_llm [N]"),
            detail=tr(
                "Summarize older history into one system message; keep last N raw (default 20)."
            ),
        ),
        "tokens": e(
            tr("Show approximate token count of the conversation"),
            usage=(":tokens"),
        ),
        "response": e(
            tr("Manage Responses API lifecycle"),
            usage=(":response [status|cancel|tokens|compact|items|delete] [response_id]"),
            detail=tr(
                "Manage the current Responses API response. "
                "status retrieves the current response; cancel stops it; "
                "tokens counts input tokens; compact compacts context; "
                "items lists input items; delete removes a response."
            ),
        ),
        "env": e(
            tr("Manage UAGENT_* environment variables"),
            usage=(":env show [KEY] | :env set KEY=VAL | :env unset KEY | :env save"),
            detail=tr(
                "Sensitive KEY names are masked on show. save writes encrypted .env.sec when configured."
            ),
        ),
        "skills": e(
            tr("Manage and apply Agent Skills"),
            usage=(":skills [list|active|clear|install|uninstall|apm|mp_search] ..."),
            detail=tr(
                "Built-in: list/active/clear (see runtime skills handlers).\n"
                ":skills list <keyword>  Filter skills by keyword (name/description).\n"
                ":skills find <keyword>  Same as list with filter.\n"
                "Dynamic subcommands come from tool CMD_SPEC (install, uninstall, apm, mp_search).\n"
                "Use :help skills install for a subcommand."
            ),
        ),
        "tools": e(
            tr("Control tool sending, genres, and loaded tools"),
            usage=(":tools [list|load|on|off|reload|output] ..."),
            detail=tr(
                ":tools on|off           Enable/disable sending tools to the LLM\n"
                ":tools on|off <genre>   Enable/disable a tool genre (and sync global on)\n"
                ":tools list [query]     List loaded tools\n"
                ":tools load <name>      Load one tool by name\n"
                ":tools reload           Reload tool modules from disk\n"
                ":tools output           Toggle showing tool results in UI"
            ),
        ),
        "tool": e(
            tr("Tool authoring helpers"),
            usage=(":tool create <name> [--lang python|rust] [--description '...']"),
            detail=tr("Scaffolds src/uagent/tools/<name>_tool.py (+ json)."),
        ),
        "plugin": e(
            tr("Install and manage plugins"),
            usage=(
                ":plugin <list|install|remove|enable|disable|reload|info|init|validate|marketplace> ..."
            ),
            detail=tr("See :help plugin <subcommand> for each action."),
        ),
        "auto": e(
            tr("Auto-pilot: repeatedly pursue a goal until done or stopped"),
            usage=(":auto <goal> [--max-rounds N] | :auto off"),
            detail=tr("Press x in CLI to request immediate exit from auto-pilot."),
        ),
        "model": e(
            tr("Show detailed model configuration"),
            usage=(":model"),
            detail=tr("Chat, image, audio, translation, embedding as configured."),
        ),
        "r": e(
            tr("Set reasoning effort"),
            usage=(":r [0|1|2|3|auto|minimal|low|medium|high|xhigh]"),
            detail=tr("0=off, 1=low, 2=medium, 3=high. Provider support varies."),
            aliases=["reasoning"],
        ),
        "v": e(
            tr("Set verbosity"),
            usage=(":v [0|1|2|3]"),
            detail=tr("0=off .. 3=high. No arg keeps current."),
            aliases=["verbosity"],
        ),
        "mem-list": e(tr("List long-term memory notes"), usage=(":mem-list")),
        "mem-del": e(
            tr("Delete a long-term memory note by index"),
            usage=(":mem-del <index>"),
            detail=tr("Index from :mem-list."),
        ),
        "profile": e(
            tr("Show or generate the learned user profile"),
            usage=(":profile | :profile fromlog [N]"),
            detail=tr("fromlog N uses the most recent N log files."),
            aliases=["profile-show"],
        ),
        "profile-fromlog": e(
            tr("Generate user profile from past logs"),
            usage=(":profile-fromlog [N]"),
            detail=tr("Default N=100; 0=all."),
        ),
        "profile-clear": e(
            tr("Clear learned user profile data"), usage=(":profile-clear")
        ),
        "cp": e(
            tr("Copy file or directory"),
            usage=(":cp <src> <dst> [-f|--overwrite] [-p|--mkdirs]"),
        ),
        "mv": e(
            tr("Move file or directory"),
            usage=(":mv <src> <dst> [-f|--overwrite] [-p|--mkdirs]"),
        ),
        "rm": e(
            tr("Delete file(s)/directory(ies) with preview + confirm"),
            usage=(":rm <path|glob>"),
        ),
        "head": e(
            tr("Show the first n lines of a file"),
            usage=(":head <path> [n]"),
            detail=tr("Default n=20."),
        ),
        "tail": e(
            tr("Show the last n lines of a file"),
            usage=(":tail <path> [n]"),
            detail=tr("Default n=20."),
        ),
        "reload": e(
            tr("Reload runtime configuration / modules"),
            usage=(":reload [target]"),
        ),
        "exit": e(
            tr("Exit the interactive session"), usage=(":exit"), aliases=["quit"]
        ),
        "quit": e(
            tr("Exit the interactive session"), usage=(":quit"), aliases=["exit"]
        ),
    }
    # alias index
    out = dict(cat)
    for key, info in list(cat.items()):
        for al in info.get("aliases") or []:
            out.setdefault(al, info)
    return out


def format_help_detail(topic: str, *, core: Any) -> str:
    """Detailed help for one command / subcommand."""

    tr = getattr(core, "tr", tr_)
    raw = (topic or "").strip().lstrip(":")
    if not raw:
        return format_help(core=core)

    parts = raw.split()
    cmd = parts[0].lower()
    sub = parts[1].lower() if len(parts) > 1 else ""

    blocks: list[str] = []

    # 1) Static catalog
    catalog = _static_help_catalog(tr=tr)
    info = catalog.get(cmd)
    if info:
        blocks.append(f":{cmd}")
        if info.get("summary"):
            blocks.append(f"  {info['summary']}")
        if info.get("usage"):
            blocks.append(f"  Usage: {info['usage']}")
        if info.get("aliases"):
            als = ", ".join(f":{a}" for a in info["aliases"] if a != cmd)
            if als:
                blocks.append(f"  Aliases: {als}")
        if info.get("detail") and not sub:
            blocks.append("")
            for dl in str(info["detail"]).splitlines():
                blocks.append(f"  {dl}" if dl.strip() else "")

    # 2) Dynamic CMD_SPEC detail
    dyn_text = None
    try:
        getter = getattr(tools, "get_dynamic_command_detail", None)
        if callable(getter):
            dyn_text = getter(cmd, sub or None)
    except Exception as e:
        dyn_text = f"(dynamic help error: {type(e).__name__}: {e})"

    if dyn_text:
        if blocks:
            blocks.append("")
            blocks.append(tr("Dynamic / plugin subcommands:"))
        blocks.append(dyn_text)
    elif not info:
        # unknown
        suggestions: list[str] = []
        for name in sorted(catalog.keys()):
            if name.startswith(cmd) or cmd in name:
                suggestions.append(name)
        try:
            for name in tools.list_dynamic_command_names():
                if name.startswith(cmd) or cmd in name:
                    suggestions.append(name)
        except Exception:
            pass
        msg = tr("Unknown command: :%(cmd)s") % {"cmd": cmd}
        if suggestions:
            msg += (
                "\n"
                + tr("Did you mean: ")
                + ", ".join(f":{s}" for s in suggestions[:12])
            )
        msg += "\n" + tr("Try :help for the full list.")
        return msg

    # If user asked a static-only sub that dynamic didn't cover, note it.
    if sub and info and not dyn_text:
        blocks.append("")
        blocks.append(tr("No dynamic subcommand help for '%(sub)s'.") % {"sub": sub})

    blocks.append("")
    blocks.append(tr("Tip: :help for overview, :help <cmd> <sub> for one subcommand."))
    return "\n".join(blocks).rstrip() + "\n"
