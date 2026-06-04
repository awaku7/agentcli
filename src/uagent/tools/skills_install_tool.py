# tools/skills_install_tool.py
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

_ = make_tool_translator(__file__)

STATUS_LABEL = "tool:skills_install"

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "skills_install",
        "description": _(
            "tool.description",
            default="Install or update an Agent Skill from a Git repository, remote ZIP, local directory, or local ZIP file into ~/.uag/skills.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "skills_install",
                "install skill",
                "add skill",
                "download skill",
                "git clone skill",
            ],
        ),
        "x_search_terms_en": [
            "skills_install",
            "install skill",
            "add skill",
            "download skill",
            "git clone skill",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": _(
                        "param.source.description",
                        default="The source URL or path (Git URL, HTTP ZIP URL, local directory, or local ZIP).",
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
    # Remove trailing slashes
    s = source.rstrip("/\\")
    # Get the last component
    base = os.path.basename(s)
    if not base:
        # Fallback if empty
        return "downloaded-skill"

    # Remove .git or .zip suffix
    if base.lower().endswith(".git"):
        base = base[:-4]
    elif base.lower().endswith(".zip"):
        base = base[:-4]

    # Sanitize name: allow only a-z, 0-9, hyphen, underscore
    sanitized = re.sub(r"[^a-zA-Z0-9-_]", "-", base)
    sanitized = sanitized.strip("-").lower()
    return sanitized or "downloaded-skill"


def _is_git_url(source: str) -> bool:
    """Check if the source looks like a Git URL."""
    s = source.lower()
    if s.startswith("git@") or s.startswith("git://"):
        return True
    if (s.startswith("http://") or s.startswith("https://")) and (
        s.endswith(".git") or "github.com/" in s or "gitlab.com/" in s
    ):
        return True
    return False


def _is_remote_zip(source: str) -> bool:
    """Check if the source looks like a remote ZIP URL."""
    s = source.lower()
    if s.startswith("http://") or s.startswith("https://"):
        if s.endswith(".zip") or "/archive/" in s or "/zip/" in s:
            return True
    return False


def _safe_extract_zip(zip_path: str, dest_dir: str, max_size_bytes: int = 50_000_000, max_files: int = 1000) -> None:
    """Extract a ZIP file safely with size and file count limits (Zip Bomb protection)."""
    total_size = 0
    file_count = 0

    with zipfile.ZipFile(zip_path, "r") as z:
        # First pass: validate sizes and counts
        for info in z.infolist():
            file_count += 1
            if file_count > max_files:
                raise ValueError(
                    _("err.zip_too_many_files", default="ZIP archive contains too many files (limit: {max_files})").format(
                        max_files=max_files
                    )
                )
            total_size += info.file_size
            if total_size > max_size_bytes:
                raise ValueError(
                    _("err.zip_too_large", default="ZIP archive uncompressed size exceeds limit (limit: {max_size}MB)").format(
                        max_size=max_size_bytes // 1_000_000
                    )
                )

            # Directory traversal check
            # Ensure no absolute paths or parent directory references
            norm_path = os.path.normpath(info.filename)
            if norm_path.startswith("/") or norm_path.startswith("\\") or ".." in norm_path.split(os.sep):
                raise ValueError(
                    _("err.zip_traversal", default="ZIP archive contains invalid path: {filename}").format(
                        filename=info.filename
                    )
                )

        # Second pass: extract
        os.makedirs(dest_dir, exist_ok=True)
        z.extractall(dest_dir)


def run_tool(args: dict[str, Any]) -> str:
    """Execute the skills_install tool."""
    source = (args.get("source") or "").strip()
    name = (args.get("name") or "").strip()
    overwrite = args.get("overwrite", True)

    if not source:
        return json.dumps({"ok": False, "message": _("err.source_required", default="Source is required.")})

    # Resolve destination folder name
    if not name:
        name = _infer_name_from_source(source)

    # Directory traversal check on name
    if "/" in name or "\\" in name or ".." in name or name in (".", ""):
        return json.dumps(
            {
                "ok": False,
                "message": _("err.invalid_name", default="Invalid destination folder name: {name}").format(name=name),
            }
        )

    # Centralized skills directory
    skills_root = os.path.join(os.path.expanduser("~"), ".uag", "skills")
    dest_dir = os.path.join(skills_root, name)

    # Handle existing destination
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

    try:
        os.makedirs(skills_root, exist_ok=True)

        # 1. Git Repository
        if _is_git_url(source):
            # Check if git is available
            try:
                subprocess.run(["git", "--version"], capture_output=True, check=True)
            except (subprocess.SubprocessError, FileNotFoundError):
                return json.dumps(
                    {
                        "ok": False,
                        "message": _(
                            "err.git_not_found",
                            default="Git command not found. Please install Git or use a ZIP URL instead.",
                        ),
                    }
                )

            if os.path.exists(dest_dir):
                # Try to pull/update
                # Check if it's a git repo
                if os.path.exists(os.path.join(dest_dir, ".git")):
                    res = subprocess.run(
                        ["git", "pull"],
                        cwd=dest_dir,
                        capture_output=True,
                        text=True,
                    )
                    if res.returncode != 0:
                        return json.dumps(
                            {
                                "ok": False,
                                "message": _(
                                    "err.git_pull_failed",
                                    default="Failed to update Git repository: {error}",
                                ).format(error=res.stderr.strip()),
                            }
                        )
                else:
                    # Not a git repo, remove and clone
                    shutil.rmtree(dest_dir)
                    res = subprocess.run(
                        ["git", "clone", source, dest_dir],
                        capture_output=True,
                        text=True,
                    )
                    if res.returncode != 0:
                        return json.dumps(
                            {
                                "ok": False,
                                "message": _(
                                    "err.git_clone_failed",
                                    default="Failed to clone Git repository: {error}",
                                ).format(error=res.stderr.strip()),
                            }
                        )
            else:
                res = subprocess.run(
                    ["git", "clone", source, dest_dir],
                    capture_output=True,
                    text=True,
                )
                if res.returncode != 0:
                    return json.dumps(
                        {
                            "ok": False,
                            "message": _(
                                "err.git_clone_failed",
                                default="Failed to clone Git repository: {error}",
                            ).format(error=res.stderr.strip()),
                        }
                    )

        # 2. Remote ZIP Archive
        elif _is_remote_zip(source):
            with tempfile.TemporaryDirectory() as tmpdir:
                zip_temp_path = os.path.join(tmpdir, "downloaded.zip")
                # Download
                try:
                    urllib.request.urlretrieve(source, zip_temp_path)
                except Exception as e:
                    return json.dumps(
                        {
                            "ok": False,
                            "message": _(
                                "err.download_failed",
                                default="Failed to download ZIP from {url}: {error}",
                            ).format(url=source, error=str(e)),
                        }
                    )

                # Extract to a temp folder first to handle nested root folder (like GitHub archives)
                extract_tmp = os.path.join(tmpdir, "extracted")
                _safe_extract_zip(zip_temp_path, extract_tmp)

                # If there is a single top-level directory in the ZIP, use its contents instead
                items = os.listdir(extract_tmp)
                src_to_copy = extract_tmp
                if len(items) == 1 and os.path.isdir(os.path.join(extract_tmp, items[0])):
                    src_to_copy = os.path.join(extract_tmp, items[0])

                if os.path.exists(dest_dir):
                    shutil.rmtree(dest_dir)
                shutil.copytree(src_to_copy, dest_dir)

        # 3. Local ZIP Archive
        elif os.path.isfile(source) and source.lower().endswith(".zip"):
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

        # 4. Local Directory
        elif os.path.isdir(source):
            if os.path.exists(dest_dir):
                shutil.rmtree(dest_dir)
            shutil.copytree(source, dest_dir)

        else:
            return json.dumps(
                {
                    "ok": False,
                    "message": _(
                        "err.unsupported_source",
                        default="Unsupported source format or path not found: {source}",
                    ).format(source=source),
                }
            )

        # Verify that SKILL.md exists in the installed directory
        skill_md = os.path.join(dest_dir, "SKILL.md")
        if not os.path.isfile(skill_md):
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

    except Exception as e:
        return json.dumps(
            {
                "ok": False,
                "message": _("err.unexpected", default="An unexpected error occurred: {error}").format(error=str(e)),
            }
        )


def handle_cmd_install(arg: str, **kwargs: Any) -> Any:
    """CLI command handler for :skills install <source> [name]."""
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
        print(f"[skills] {res.get('message')}")
    else:
        print(f"[skills error] {res.get('message')}")

    return CommandResult()


CMD_SPEC = {
    "command": "skills",
    "subcommand": "install",
    "handler": handle_cmd_install,
}
