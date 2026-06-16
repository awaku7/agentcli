# tools/skills_mp_search_tool.py
"""skills_mp_search_tool implementation for browsing SkillsMP marketplace."""

from __future__ import annotations

import json
import os
import ssl
import urllib.request
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

STATUS_LABEL = "tool:skills_mp_search"

MARKETPLACE_API = "https://skillsmp.com/api/skills"
SKILLSMP_URL = "https://skillsmp.com"

TOOL_SPEC: dict[str, Any] = {
    "tool_level": 0,
    "type": "function",
    "tool_genre": "basic",
    "function": {
        "name": "skills_mp_search",
        "description": _(
            "tool.description",
            default="Search and browse the SkillsMP marketplace (skillsmp.com) for Agent Skills. Returns a list of skills with name, author, description, stars, and GitHub URL.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "skills_mp_search",
                "skillsmp",
                "marketplace",
                "search skill",
                "browse skill",
                "find skill",
                "skill directory",
            ],
        ),
        "x_search_terms_en": [
            "skills_mp_search",
            "skillsmp",
            "marketplace",
            "search skill",
            "browse skill",
            "find skill",
            "skill directory",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": _(
                        "param.query.description",
                        default="Search query to filter skills by name or description.",
                    ),
                },
                "page": {
                    "type": "integer",
                    "description": _(
                        "param.page.description",
                        default="Page number for pagination (default: 1).",
                    ),
                    "default": 1,
                },
                "limit": {
                    "type": "integer",
                    "description": _(
                        "param.limit.description",
                        default="Number of results per page (default: 10, max: 50).",
                    ),
                    "default": 10,
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["recent", "stars", "name"],
                    "description": _(
                        "param.sort_by.description",
                        default="Sort order: 'recent' (newest first), 'stars' (most starred), 'name' (alphabetical). Default: 'recent'.",
                    ),
                    "default": "recent",
                },
            },
        },
    },
}


def _fetch_json(url: str) -> dict[str, Any]:
    """Fetch JSON from URL with SSL verification disabled."""
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "uag/1.0", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if isinstance(data, dict):
            return data
        return {}
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"error": f"Connection failed: {e.reason}"}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON response: {e}"}
    except Exception as e:
        return {"error": str(e)}


def _format_skills_table(skills: list[dict[str, Any]], page: int, total_pages: int) -> str:
    """Format skills list as readable text."""
    if not skills:
        return _("msg.no_results", default="No skills found.")

    lines: list[str] = []
    lines.append(
        _(
            "msg.header",
            default="SkillsMP Marketplace — Page {page}/{total}",
        ).format(page=page, total=total_pages if total_pages else "?")
    )
    lines.append("")

    for i, skill in enumerate(skills, 1):
        name = skill.get("name", "?")
        author = skill.get("author", "?")
        stars = skill.get("stars", 0)
        desc = skill.get("description", "")
        gh_url = skill.get("githubUrl", "")
        updated = skill.get("updatedAt", "")

        # Truncate long descriptions
        if len(desc) > 120:
            desc = desc[:117] + "..."

        lines.append(f"{i}. {name}")
        lines.append(f"   Author: {author}  |  Stars: {stars}")
        if desc:
            lines.append(f"   {desc}")
        lines.append(f"   GitHub: {gh_url}")
        lines.append("")

    if total_pages and page < total_pages:
        lines.append(
            _(
                "msg.next_page_hint",
                default="Use page={next} to see more results.",
            ).format(next=page + 1)
        )

    install_hint = _(
        "msg.install_hint",
        default="Install a skill with: skills_install source=<githubUrl>",
    )
    lines.append(f"[Hint] {install_hint}")
    lines.append(f"       {SKILLSMP_URL}")

    return "\n".join(lines)


def run_tool(args: dict[str, Any]) -> str:
    """Execute the skills_mp_search tool."""
    query = (args.get("query") or "").strip()
    page = int(args.get("page") or 1)
    limit = int(args.get("limit") or 10)
    sort_by = (args.get("sort_by") or "recent").strip()

    if limit < 1:
        limit = 1
    elif limit > 50:
        limit = 50
    if page < 1:
        page = 1

    params = f"?limit={limit}&page={page}&sortBy={sort_by}"
    if query:
        params += f"&search={urllib.request.quote(query)}"

    url = MARKETPLACE_API + params
    result = _fetch_json(url)

    if "error" in result:
        return json.dumps({
            "ok": False,
            "message": result["error"],
        })

    skills = result.get("skills", [])
    pagination = result.get("pagination", {})
    total_pages = pagination.get("totalPages", 0) or 0
    total_all = pagination.get("totalAll", 0) or 0

    if not skills:
        return json.dumps({
            "ok": True,
            "skills": [],
            "total_results": 0,
            "message": _("msg.no_results", default="No skills found."),
        })

    formatted = _format_skills_table(skills, page, total_pages)

    return json.dumps(
        {
            "ok": True,
            "skills": [
                {
                    "name": s.get("name"),
                    "author": s.get("author"),
                    "description": s.get("description", ""),
                    "stars": s.get("stars", 0),
                    "forks": s.get("forks", 0),
                    "githubUrl": s.get("githubUrl"),
                    "updatedAt": s.get("updatedAt"),
                }
                for s in skills
            ],
            "page": page,
            "total_pages": total_pages,
            "total_marketplace": total_all,
            "message": formatted,
        },
        ensure_ascii=False,
    )


def handle_cmd_mp_search(arg: str, **kwargs: Any) -> Any:
    """CLI command handler for :skills mp_search <query> [--page N] [--limit N] [--sort recent|stars|name]."""
    from ..util_tools import CommandResult

    parts = arg.strip().split()
    query = ""
    page = 1
    limit = 10
    sort_by = "recent"

    i = 0
    while i < len(parts):
        p = parts[i]
        if p == "--page" and i + 1 < len(parts):
            try:
                page = int(parts[i + 1])
            except ValueError:
                pass
            i += 2
        elif p == "--limit" and i + 1 < len(parts):
            try:
                limit = int(parts[i + 1])
            except ValueError:
                pass
            i += 2
        elif p == "--sort" and i + 1 < len(parts):
            sort_by = parts[i + 1]
            i += 2
        else:
            if query:
                query += " "
            query += p
            i += 1

    args_dict = {
        "query": query.strip(),
        "page": page,
        "limit": limit,
        "sort_by": sort_by,
    }
    res_json = run_tool(args_dict)
    res = json.loads(res_json)

    if res.get("ok"):
        print(res.get("message", ""))
    else:
        print(
            f"{_('prefix.error', default='[error]')} {res.get('message', 'Unknown error')}"
        )

    return CommandResult()


CMD_SPEC = {
    "command": "skills",
    "subcommand": "mp_search",
    "handler": handle_cmd_mp_search,
    "help_text": _(
        "help_text.mp_search",
        default=(
            "  :skills mp_search [query] [--page N] [--limit N] [--sort recent|stars|name]\n"
            "    Search and browse the SkillsMP marketplace for Agent Skills."
        ),
    ),
}
