"""skills_install_tool implementation for installing Agent Skills."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from typing import Any

from .i18n_helper import make_tool_translator
from .agent_skills_shared import load_skill_frontmatter_only

_ = make_tool_translator(__file__)

STATUS_LABEL = "tool:skills_install"

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "basic",
    "function": {
        "name": "skills_install",
        "description": _(
            "tool.description",
            default="Install or update an Agent Skill (Git repo, remote/local ZIP, local dir).",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "skills_install",
                "install skill",
                "add skill",
                "download skill",
                "git clone skill",
                "marketplace skill",
                "all@source",
            ],
        ),
        "x_search_terms_en": [
            "skills_install",
            "install skill",
            "add skill",
            "download skill",
            "git clone skill",
            "marketplace skill",
            "all@source",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": _(
                        "param.source.description",
                        default="The source URL or path (Git URL, HTTP ZIP URL, local directory, or local ZIP). You can also prefix a selector as skil...",
                    ),
                },
                "name": {
                    "type": "string",
                    "description": _(
                        "param.name.description",
                        default="Optional destination folder name. If not specified, it will be inferred from the source.",
                    ),
                },
                "overwrite": {
                    "type": "boolean",
                    "description": _(
                        "param.overwrite.description",
                        default="Whether to overwrite or update the destination if it already exists. Defaults to true.",
                    ),
                    "default": True,
                },
            },
            "required": ["source"],
        },
    },
}


def _infer_name_from_source(source: str) -> str:
    """Infer a safe folder name from the source string."""
    s = source.rstrip("/\\")
    base = os.path.basename(s)
    if not base:
        return "downloaded-skill"

    if base.lower().endswith(".git"):
        base = base[:-4]
    elif base.lower().endswith(".zip"):
        base = base[:-4]

    sanitized = re.sub(r"[^a-zA-Z0-9-_]", "-", base)
    sanitized = sanitized.strip("-").lower()
    return sanitized or "downloaded-skill"


def _normalize_source(source: str) -> str:
    """Normalize shorthand sources such as owner/repo to a GitHub URL."""
    s = source.strip()
    if not s:
        return s

    if _is_git_url(s) or _is_remote_zip(s) or os.path.exists(s):
        return s

    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?", s):
        return f"https://github.com/{s}"

    return s


def _split_selector_source(source: str) -> tuple[str | None, str]:
    """Split `selector@source` syntax.

    We intentionally avoid treating git@host:path as selector syntax.
    """
    s = source.strip()
    if not s:
        return None, s

    if s.startswith("git@"):
        return None, s

    if s.startswith(("http://", "https://", "git://", "file://")):
        return None, s

    if "@" not in s:
        return None, s

    selector, base = s.split("@", 1)
    selector = selector.strip()
    base = base.strip()
    if not selector or not base:
        return None, s

    if any(ch in selector for ch in "/\\:"):
        return None, s

    return selector, base


def _is_git_url(source: str) -> bool:
    """Check if the source looks like a Git URL."""
    s = source.lower()
    if s.startswith(("git@", "git://")):
        return True
    if (s.startswith(("http://", "https://"))) and (
        s.endswith(".git") or "github.com/" in s or "gitlab.com/" in s
    ):
        return True
    return False


def _is_remote_zip(source: str) -> bool:
    """Check if the source looks like a remote ZIP URL."""
    s = source.lower()
    if s.startswith(("http://", "https://")):
        if s.endswith(".zip") or "/archive/" in s or "/zip/" in s:
            return True
    return False


def _safe_extract_zip(
    zip_path: str,
    dest_dir: str,
    max_size_bytes: int = 50_000_000,
    max_files: int = 1000,
) -> None:
    """Extract a ZIP file safely with size and file count limits (Zip Bomb protection)."""
    total_size = 0
    file_count = 0

    with zipfile.ZipFile(zip_path, "r") as z:
        for info in z.infolist():
            file_count += 1
            if file_count > max_files:
                raise ValueError(
                    _(
                        "err.zip_too_many_files",
                        default="ZIP archive contains too many files (limit: {max_files})",
                    ).format(max_files=max_files)
                )
            total_size += info.file_size
            if total_size > max_size_bytes:
                raise ValueError(
                    _(
                        "err.zip_too_large",
                        default="ZIP archive uncompressed size exceeds limit (limit: {max_size}MB)",
                    ).format(max_size=max_size_bytes // 1_000_000)
                )

            norm_path = os.path.normpath(info.filename)
            if (
                norm_path.startswith(("/", "\\")) or ".." in norm_path.split(os.sep)
            ):
                raise ValueError(
                    _(
                        "err.zip_traversal",
                        default="ZIP archive contains invalid path: {filename}",
                    ).format(filename=info.filename)
                )

        os.makedirs(dest_dir, exist_ok=True)
        z.extractall(dest_dir)


def _copy_source_tree(source: str, dest_dir: str) -> None:
    """Copy/clone/extract source contents into dest_dir."""
    if _is_git_url(source):
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            raise RuntimeError(
                _(
                    "err.git_not_found",
                    default="Git command not found. Please install Git or use a ZIP URL instead.",
                )
            )

        if os.path.exists(dest_dir):
            if os.path.exists(os.path.join(dest_dir, ".git")):
                res = subprocess.run(
                    ["git", "pull"],
                    cwd=dest_dir,
                    capture_output=True,
                    text=True,
                )
                if res.returncode != 0:
                    raise RuntimeError(
                        _(
                            "err.git_pull_failed",
                            default="Failed to update Git repository: {error}",
                        ).format(error=res.stderr.strip())
                    )
                return
            shutil.rmtree(dest_dir)

        res = subprocess.run(
            ["git", "clone", source, dest_dir],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            raise RuntimeError(
                _(
                    "err.git_clone_failed",
                    default="Failed to clone Git repository: {error}",
                ).format(error=res.stderr.strip())
            )
        return

    if _is_remote_zip(source):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_temp_path = os.path.join(tmpdir, "downloaded.zip")
            try:
                urllib.request.urlretrieve(source, zip_temp_path)
            except Exception as e:
                raise RuntimeError(
                    _(
                        "err.download_failed",
                        default="Failed to download ZIP from {url}: {error}",
                    ).format(url=source, error=str(e))
                ) from e

            extract_tmp = os.path.join(tmpdir, "extracted")
            _safe_extract_zip(zip_temp_path, extract_tmp)

            items = os.listdir(extract_tmp)
            src_to_copy = extract_tmp
            if len(items) == 1 and os.path.isdir(os.path.join(extract_tmp, items[0])):
                src_to_copy = os.path.join(extract_tmp, items[0])

            if os.path.exists(dest_dir):
                shutil.rmtree(dest_dir)
            shutil.copytree(src_to_copy, dest_dir)
        return

    if os.path.isfile(source) and source.lower().endswith(".zip"):
        with tempfile.TemporaryDirectory() as tmpdir:
            extract_tmp = os.path.join(tmpdir, "extracted")
            _safe_extract_zip(source, extract_tmp)

            items = os.listdir(extract_tmp)
            src_to_copy = extract_tmp
            if len(items) == 1 and os.path.isdir(os.path.join(extract_tmp, items[0])):
                src_to_copy = os.path.join(extract_tmp, items[0])

            if os.path.exists(dest_dir):
                shutil.rmtree(dest_dir)
            shutil.copytree(src_to_copy, dest_dir)
        return

    if os.path.isdir(source):
        if os.path.exists(dest_dir):
            shutil.rmtree(dest_dir)
        shutil.copytree(source, dest_dir)
        return

    raise RuntimeError(
        _(
            "err.unsupported_source",
            default="Unsupported source format or path not found: {source}",
        ).format(source=source)
    )


def _iter_candidate_skill_dirs(root_dir: str, recursive: bool = True) -> list[str]:
    out: list[str] = []
    root_dir = os.path.abspath(root_dir)

    if not os.path.isdir(root_dir):
        return out

    if recursive:
        for dirpath, dirnames, filenames in os.walk(root_dir):
            base = os.path.basename(dirpath)
            if base in (".git", "node_modules", "__pycache__", ".venv", "venv"):
                dirnames[:] = []
                continue

            if "SKILL.md" in filenames:
                out.append(dirpath)
    else:
        for entry in os.scandir(root_dir):
            if not entry.is_dir():
                continue
            if os.path.isfile(os.path.join(entry.path, "SKILL.md")):
                out.append(entry.path)

    return out


def _skill_display_name(skill_dir: str) -> str:
    try:
        fm = load_skill_frontmatter_only(skill_dir)
        name = fm.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    except Exception:
        pass
    return os.path.basename(os.path.normpath(skill_dir)) or skill_dir


def _find_skill_dir(root_dir: str, selector: str) -> str | None:
    selector_norm = selector.strip().lower()
    if not selector_norm:
        return None

    candidates = _iter_candidate_skill_dirs(root_dir, recursive=True)
    if not candidates:
        return None

    exact_name_matches: list[str] = []
    exact_basename_matches: list[str] = []

    for skill_dir in candidates:
        basename = os.path.basename(os.path.normpath(skill_dir)).lower()
        if basename == selector_norm:
            exact_basename_matches.append(skill_dir)

        try:
            fm = load_skill_frontmatter_only(skill_dir)
            fm_name = fm.get("name")
            if isinstance(fm_name, str) and fm_name.strip().lower() == selector_norm:
                exact_name_matches.append(skill_dir)
        except Exception:
            continue

    if exact_name_matches:
        return exact_name_matches[0]
    if exact_basename_matches:
        return exact_basename_matches[0]
    return None


def _copy_skill_dir_contents(src_skill_dir: str, dest_dir: str) -> None:
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    shutil.copytree(src_skill_dir, dest_dir)


def _is_all_selector(selector: str) -> bool:
    return selector.strip().lower() in {"all", "*"}


# Dangerous patterns to scan for in SKILL.md content
_DANGEROUS_PATTERNS: list[tuple[str, str, str]] = [
    (
        "rm_destructive",
        r"\brm\s+[-][rf]\s+[/~]",
        "Destructive recursive delete (rm -rf /, rm -rf ~)",
    ),
    ("del_force", r"\bdel\s+[/][f]\s+", "Force delete file (del /f)"),
    (
        "rd_destructive",
        r"\brd\s+[/][s]\s+[/][q]?\s+",
        "Destructive directory removal (rd /s)",
    ),
    (
        "sudo_exec",
        r"\bsudo\s+(rm|del|dd|mkfs|format|shutdown|reboot)",
        "Privileged destructive command",
    ),
    (
        "pipe_to_shell",
        r"(curl|wget|iwr|Invoke-WebRequest)\s+.*[|]\s*(sh|bash|pwsh|powershell|iex)",
        "Pipe download to shell execution",
    ),
    (
        "download_exec",
        r"(curl|wget)\s+.*[-]O[-]\s*[|]\s*(sh|bash)",
        "Download and execute pattern",
    ),
    (
        "base64_decode_exec",
        r"(base64\s+-d|frombase64|\[\s*System\.Text\.Encoding)",
        "Potentially obfuscated code execution",
    ),
    (
        "chmod_recursive",
        r"\bchmod\s+[-]?R?\s*777\s+",
        "Recursive permission change to world-writable",
    ),
    ("format_disk", r"\bformat\s+\w+:|mkfs\.", "Disk format operation"),
    ("shutdown", r"\bshutdown\s+[/]?[sfr]", "System shutdown/restart command"),
    (
        "net_user_admin",
        r"\bnet\s+user\s+\w+\s+.*/add|net\s+localgroup\s+.*/add",
        "User account / privilege escalation",
    ),
    (
        "dangerous_curl",
        r"\bcurl\s+.*[-][-]insecure|-k\s+|--ssl-no-revoke",
        "SSL verification disabled (curl -k)",
    ),
]


def _danger_scan_skill(skill_body: str) -> list[dict[str, str]]:
    """Scan SKILL.md body for dangerous patterns. Returns list of findings."""
    findings: list[dict[str, str]] = []
    for pattern_id, regex, description in _DANGEROUS_PATTERNS:
        if re.search(regex, skill_body, re.IGNORECASE | re.MULTILINE):
            # Find the matching line for context
            for line in skill_body.splitlines():
                if re.search(regex, line, re.IGNORECASE):
                    findings.append(
                        {
                            "pattern": pattern_id,
                            "description": description,
                            "line": line.strip()[:200],
                        }
                    )
                    break
    return findings


def _load_skill_md_text(skill_dir: str) -> str | None:
    """Load SKILL.md text from a directory, return None if not found."""
    md_path = os.path.join(skill_dir, "SKILL.md")
    if os.path.isfile(md_path):
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    return None


def _analyze_skill_for_confirm(
    skill_dir: str,
    name: str,
    source: str,
) -> dict[str, Any]:
    """Analyze a skill for the confirmation prompt.

    Returns a dict with skill metadata and safety scan results.
    """
    from .agent_skills_shared import split_frontmatter, parse_frontmatter_yaml

    result: dict[str, Any] = {
        "skill_name": name,
        "source": source,
    }

    md_text = _load_skill_md_text(skill_dir)
    if not md_text:
        result["description"] = ""
        result["warnings"] = ["SKILL.md not found"]
        result["danger_found"] = False
        result["danger_details"] = []
        return result

    # Extract frontmatter
    try:
        fm_text, body = split_frontmatter(md_text)
        fm = parse_frontmatter_yaml(fm_text)
        desc = fm.get("description") or ""
        if isinstance(desc, str):
            result["description"] = desc.strip()
        else:
            result["description"] = str(desc) if desc else ""
        # Also extract author if available
        author = fm.get("author")
        if author:
            result["author"] = str(author)
    except Exception:
        result["description"] = ""
        result["warnings"] = ["Could not parse SKILL.md frontmatter"]

    # Danger scan
    dangers = _danger_scan_skill(md_text)
    result["danger_found"] = len(dangers) > 0
    result["danger_details"] = dangers

    return result


def run_tool(args: dict[str, Any]) -> str:
    """Execute the skills_install tool."""
    raw_source = (args.get("source") or "").strip()
    name = (args.get("name") or "").strip()
    overwrite = args.get("overwrite", True)

    if not raw_source:
        return json.dumps(
            {
                "ok": False,
                "message": _("err.source_required", default="Source is required."),
            }
        )

    selector, source = _split_selector_source(raw_source)
    source = _normalize_source(source)

    if selector and not name and not _is_all_selector(selector):
        name = selector

    if not name:
        name = _infer_name_from_source(source)

    if "/" in name or "\\" in name or ".." in name or name in (".", ""):
        return json.dumps(
            {
                "ok": False,
                "message": _(
                    "err.invalid_name",
                    default="Invalid destination folder name: {name}",
                ).format(name=name),
            }
        )

    skills_root = os.path.join(os.path.expanduser("~"), ".uag", "skills")
    dest_dir = os.path.join(skills_root, name)

    if os.path.exists(dest_dir) and not overwrite:
        return json.dumps(
            {
                "ok": False,
                "message": _(
                    "err.already_exists",
                    default="Destination directory already exists: {path}. Use overwrite=true to update.",
                ).format(path=dest_dir),
            }
        )

    try:
        os.makedirs(skills_root, exist_ok=True)

        # Extract source to a temp directory for analysis
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = os.path.join(tmpdir, "workspace")
            _copy_source_tree(source, workspace)

            # Find the actual skill directory
            skill_dir: str | None = None
            if selector and not _is_all_selector(selector):
                skill_dir = _find_skill_dir(workspace, selector)
                if not skill_dir:
                    candidates = _iter_candidate_skill_dirs(workspace, recursive=True)
                    available = ", ".join(
                        _skill_display_name(d) for d in candidates[:20]
                    )
                    if len(candidates) > 20:
                        available += ", ..."
                    return json.dumps(
                        {
                            "ok": False,
                            "message": _(
                                "err.marketplace_skill_not_found",
                                default="Could not find skill '{selector}' in {source}. Available skills: {available}",
                            ).format(
                                selector=selector,
                                source=source,
                                available=available or "(none)",
                            ),
                        }
                    )

                if not args.get("name"):
                    new_name = os.path.basename(os.path.normpath(skill_dir)) or selector
                    name = new_name
                    dest_dir = os.path.join(skills_root, name)
            else:
                # Whole package: use the workspace itself or its single-child dir
                root_skill_md = os.path.join(workspace, "SKILL.md")
                if os.path.isfile(root_skill_md):
                    skill_dir = workspace
                else:
                    nested = _iter_candidate_skill_dirs(workspace, recursive=False)
                    if len(nested) == 1:
                        skill_dir = nested[0]
                    else:
                        skill_dir = workspace

            # --- Always confirm with the user ---
            if skill_dir:
                analysis = _analyze_skill_for_confirm(skill_dir, name, source)

                # Print analysis
                print("")
                print("=" * 60)
                print(
                    _(
                        "title.install_confirm",
                        default="Skill Installation Confirmation",
                    )
                )
                print("=" * 60)
                print(
                    _("label.skill_name", default="Skill:  %(name)s")
                    % {"name": analysis.get("skill_name", name)}
                )
                if analysis.get("author"):
                    print(
                        _("label.author", default="Author: %(author)s")
                        % {"author": analysis["author"]}
                    )
                desc = analysis.get("description", "") or _(
                    "msg.no_description", default="(no description)"
                )
                print(
                    _("label.description", default="Description: %(desc)s")
                    % {"desc": desc[:200]}
                )
                print(
                    _("label.source", default="Source: %(source)s")
                    % {"source": analysis.get("source", source)}
                )

                if analysis.get("danger_found"):
                    print("")
                    print(
                        _(
                            "warn.danger_found",
                            default="!! WARNING: Dangerous patterns detected !!",
                        )
                    )
                    for d in analysis["danger_details"]:
                        print(f"  - [{d['pattern']}] {d['description']}")
                        print(f"    {d['line'][:120]}")
                else:
                    print("")
                    print(
                        _(
                            "label.safe",
                            default="Safety: No dangerous patterns detected.",
                        )
                    )
                print("")

                # Ask user
                from .context import get_callbacks

                cb = get_callbacks()
                prompt = _(
                    "prompt.install",
                    default="Install this skill? [y/N] ",
                )
                print(prompt, end="", flush=True)

                user_input = ""
                try:
                    q = cb.human_ask_queue_ref()
                    if q is not None:
                        user_input = q.get(timeout=300)
                    else:
                        # Fallback: read from stdin
                        try:
                            user_input = input("")
                        except Exception:
                            user_input = "n"
                except Exception:
                    user_input = "n"

                user_input = user_input.strip().lower()
                if user_input not in ("y", "yes"):
                    print(_("msg.cancelled", default="Installation cancelled."))
                    return json.dumps(
                        {
                            "ok": False,
                            "message": _(
                                "msg.cancelled_detail",
                                default="User cancelled skill installation.",
                            ),
                        }
                    )

                print(_("msg.proceeding", default="Proceeding with installation..."))

            # --- Installation phase ---
            if os.path.exists(dest_dir):
                if not overwrite:
                    return json.dumps(
                        {
                            "ok": False,
                            "message": _(
                                "err.already_exists",
                                default="Destination directory already exists: {path}. Use overwrite=true to update.",
                            ).format(path=dest_dir),
                        }
                    )
                shutil.rmtree(dest_dir)

            if skill_dir:
                _copy_skill_dir_contents(skill_dir, dest_dir)
            else:
                _copy_skill_dir_contents(workspace, dest_dir)

            # Report result
            root_md = os.path.join(dest_dir, "SKILL.md")
            if os.path.isfile(root_md):
                if selector:
                    return json.dumps(
                        {
                            "ok": True,
                            "path": dest_dir,
                            "skill": name,
                            "message": _(
                                "success.installed_selected",
                                default="Successfully installed skill '{name}' from {source} to {path}",
                            ).format(name=name, source=source, path=dest_dir),
                        }
                    )
                return json.dumps(
                    {
                        "ok": True,
                        "path": dest_dir,
                        "message": _(
                            "success.installed",
                            default="Successfully installed skill '{name}' to {path}",
                        ).format(name=name, path=dest_dir),
                    }
                )

            nested = _iter_candidate_skill_dirs(dest_dir, recursive=True)
            if nested:
                return json.dumps(
                    {
                        "ok": True,
                        "path": dest_dir,
                        "skill_count": len(nested),
                        "message": _(
                            "success.installed_marketplace",
                            default="Successfully installed marketplace/package '{name}' to {path} ({count} skill definitions found).",
                        ).format(name=name, path=dest_dir, count=len(nested)),
                    }
                )

            return json.dumps(
                {
                    "ok": True,
                    "path": dest_dir,
                    "message": _(
                        "warn.missing_skill_md",
                        default="Skill installed at {path}, but SKILL.md was not found in the root.",
                    ).format(path=dest_dir),
                }
            )

    except Exception as e:
        return json.dumps(
            {
                "ok": False,
                "message": _(
                    "err.unexpected", default="An unexpected error occurred: {error}"
                ).format(error=str(e)),
            }
        )


def handle_cmd_install(arg: str, **kwargs: Any) -> Any:
    """CLI command handler for :skills install <source> [name].

    Marketplace selectors are supported via `skill@source` and `all@source`.
    """
    from ..util_tools import CommandResult

    parts = arg.strip().split(maxsplit=1)
    if not parts:
        print(_("err.source_required", default="Source is required."))
        return CommandResult()

    source = parts[0]
    name = parts[1] if len(parts) > 1 else ""

    res_json = run_tool({"source": source, "name": name, "overwrite": True})
    res = json.loads(res_json)

    if res.get("ok"):
        print(f"{_('prefix.skills', default='[skills]')} {res.get('message')}")
    else:
        print(
            f"{_('prefix.skills_error', default='[skills error]')} {res.get('message')}"
        )

    return CommandResult()


CMD_SPEC = {
    "command": "skills",
    "subcommand": "install",
    "handler": handle_cmd_install,
    "help_text": _(
        "help_text.install",
        default="  :skills install <source> [name]   Install a skill or marketplace-style package from a source",
    ),
}
