# tools/skills_mp_search_tool.py
"""skills_mp_search_tool implementation for browsing SkillsMP / ClawHub marketplace."""

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

# ClawHub
CLAWHUB_API_BASE = "https://clawhub.ai"
CLAWHUB_URL = "https://clawhub.ai"

TOOL_SPEC: dict[str, Any] = {
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
                "source": {
                    "type": "string",
                    "enum": ["skillsmp", "clawhub"],
                    "description": _(
                        "param.source.description",
                        default="Marketplace source: 'skillsmp' (skillsmp.com) or 'clawhub' (clawhub.ai). Default: 'skillsmp'.",
                    ),
                    "default": "skillsmp",
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


def _fetch_clawhub(query: str, limit: int, sort_by: str) -> dict[str, Any]:
    """Fetch skills from ClawHub API."""
    if query:
        # vector search
        params = f"?q={urllib.request.quote(query)}&nonSuspiciousOnly=true"
        url = f"{CLAWHUB_API_BASE}/api/v1/search{params}"
        result = _fetch_json(url)
        if "error" in result:
            return result
        results = result.get("results", [])
        # Convert to our internal format
        skills = []
        for r in results:
            skills.append({
                "name": r.get("displayName") or r.get("slug", "?"),
                "slug": r.get("slug", ""),
                "author": r.get("ownerHandle") or (r.get("owner") or {}).get("displayName") or "?",
                "stars": 0,
                "description": r.get("summary", "") or "",
                "githubUrl": f"{CLAWHUB_URL}/{r.get('slug', '')}",
                "updatedAt": _ts_to_iso(r.get("updatedAt")),
                "version": r.get("version", ""),
                "score": r.get("score", 0),
            })
        return {"skills": skills, "pagination": {"totalPages": 1}}
    else:
        # browse list
        sort_map = {"recent": "updated", "stars": "stars", "name": "recommended"}
        sort_param = sort_map.get(sort_by, "updated")
        url = f"{CLAWHUB_API_BASE}/api/v1/skills?limit={limit}&sort={sort_param}&nonSuspiciousOnly=true"
        result = _fetch_json(url)
        if "error" in result:
            return result
        items = result.get("items", [])
        skills = []
        for item in items:
            skills.append({
                "name": item.get("displayName") or item.get("slug", "?"),
                "slug": item.get("slug", ""),
                "author": item.get("ownerHandle") or "?",
                "stars": (item.get("stats") or {}).get("stars", 0),
                "description": item.get("summary", "") or "",
                "githubUrl": f"{CLAWHUB_URL}/{item.get('slug', '')}",
                "updatedAt": _ts_to_iso(item.get("updatedAt")),
                "version": (item.get("latestVersion") or {}).get("version", ""),
            })
        return {"skills": skills, "pagination": {"totalPages": 1}}


def _ts_to_iso(ts: int | None) -> str:
    """Convert Unix timestamp to ISO date string."""
    if not ts:
        return ""
    from datetime import datetime, timezone

    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def _format_skills_table(skills: list[dict[str, Any]], page: int, total_pages: int, source: str = "skillsmp") -> str:
    """Format skills list as readable text."""
    if not skills:
        return _("msg.no_results", default="No skills found.")

    lines: list[str] = []
    if source == "clawhub":
        header_key = "msg.header_clawhub"
        header_default = "ClawHub Marketplace — Page {page}/{total}"
    else:
        header_key = "msg.header"
        header_default = "SkillsMP Marketplace — Page {page}/{total}"
    lines.append(
        _(
            header_key,
            default=header_default,
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

    if source == "clawhub":
        install_hint = _(
            "msg.install_hint_clawhub",
            default="Install a skill with: skills_install source=<url>",
        )
        marketplace_url = CLAWHUB_URL
    else:
        install_hint = _(
            "msg.install_hint",
            default="Install a skill with: skills_install source=<githubUrl>",
        )
        marketplace_url = SKILLSMP_URL
    lines.append(f"[Hint] {install_hint}")
    lines.append(f"       {marketplace_url}")

    return "\n".join(lines)


def run_tool(args: dict[str, Any]) -> str:
    """Execute the skills_mp_search tool."""
    query = (args.get("query") or "").strip()
    page = int(args.get("page") or 1)
    limit = int(args.get("limit") or 10)
    sort_by = (args.get("sort_by") or "recent").strip()
    source = (args.get("source") or "skillsmp").strip().lower()

    if limit < 1:
        limit = 1
    elif limit > 50:
        limit = 50
    if page < 1:
        page = 1

    if source == "clawhub":
        result = _fetch_clawhub(query, limit, sort_by)
    else:
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

    formatted = _format_skills_table(skills, page, total_pages, source=source)

    return json.dumps(
        {
            "ok": True,
            "source": source,
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
    """CLI command handler for :skills mp_search <query> [--page N] [--limit N] [--sort recent|stars|name] [--source skillsmp|clawhub]."""
    from ..util_tools import CommandResult

    parts = arg.strip().split()
    query = ""
    page = 1
    limit = 10
    sort_by = "recent"
    source = "skillsmp"

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
        elif p == "--source" and i + 1 < len(parts):
            source = parts[i + 1].lower()
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
        "source": source,
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
            "  :skills mp_search [query] [--page N] [--limit N] [--sort recent|stars|name] [--source skillsmp|clawhub]\n"
            "    Search and browse SkillsMP (skillsmp.com) or ClawHub (clawhub.ai) marketplace for Agent Skills."
        ),
    ),
}
