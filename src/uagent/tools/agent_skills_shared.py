# tools/agent_skills_shared.py
"""Agent Skills shared helpers.

This module provides parsing/validation/utilities for the Agent Skills format
(https://agentskills.io/specification).

Design goals:
- Progressive disclosure:
  - skills_list should read only YAML frontmatter
  - skills_load reads full SKILL.md
  - references/assets are read only on demand via skills_read_file
- Security:
  - prevent directory traversal for skills_read_file
  - optional file size limits to avoid accidental huge loads

The tools implemented on top of this module live in:
- skills_list_tool.py
- skills_load_tool.py
- skills_validate_tool.py
- skills_read_file_tool.py

"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import yaml

# ------------------------------
# Constants
# ------------------------------

SKILL_MD_FILENAME = "SKILL.md"

# For safety: cap how much we read from SKILL.md / referenced files.
# - SKILL.md should be <500 lines recommended by spec, but we cap by bytes.
DEFAULT_MAX_SKILL_MD_BYTES = 2_000_000  # 2MB
DEFAULT_MAX_READ_FILE_BYTES = 5_000_000  # 5MB

# Agent Skills spec constraints
NAME_MAX_LEN = 64
DESCRIPTION_MAX_LEN = 1024
COMPATIBILITY_MAX_LEN = 500

_NAME_RE = re.compile(r"^[a-z0-9-]{1,64}$")


# ------------------------------
# Data structures
# ------------------------------


@dataclass
class SkillDoc:
    """Parsed SKILL.md."""

    path: str
    frontmatter: Dict[str, Any]
    body_markdown: str


# ------------------------------
# Skills roots
# ------------------------------


def get_default_skill_roots(cwd: Optional[str] = None) -> List[str]:
    """Return default skill root directories.

    Policy (as requested by user):
    - Use env var UAGENT_SKILLS_DIRS split by os.pathsep
    - If not set, fallback to ./skills (relative to cwd)

    The returned list may contain non-existing paths; callers may filter.
    """

    env = os.environ.get("UAGENT_SKILLS_DIRS")
    if env:
        parts = [p.strip() for p in env.split(os.pathsep) if p.strip()]
        return parts

    base = cwd or os.getcwd()
    return [os.path.join(base, "skills")]


# ------------------------------
# File IO
# ------------------------------


def _read_text_file(path: str, max_bytes: int) -> str:
    with open(path, "rb") as f:
        data = f.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(
            f"File too large to read safely: {path} (>{max_bytes} bytes)"
        )

    # Try utf-8 first; if it fails, fallback to 'utf-8' with replacement.
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def skill_md_path(skill_dir: str) -> str:
    return os.path.join(skill_dir, SKILL_MD_FILENAME)


def read_skill_md(skill_dir: str, max_bytes: int = DEFAULT_MAX_SKILL_MD_BYTES) -> str:
    path = skill_md_path(skill_dir)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"{SKILL_MD_FILENAME} not found: {path}")
    return _read_text_file(path, max_bytes=max_bytes)


# ------------------------------
# Frontmatter parsing
# ------------------------------


_FRONTMATTER_DELIM = "---"


def split_frontmatter(text: str) -> Tuple[str, str]:
    """Split YAML frontmatter and body.

    Returns:
        (frontmatter_yaml, body_markdown)

    Raises:
        ValueError if frontmatter is missing or malformed.
    """

    # Must start with '---' on first non-empty line.
    lines = text.splitlines()
    i = 0
    while i < len(lines) and lines[i].strip() == "":
        i += 1

    if i >= len(lines) or lines[i].strip() != _FRONTMATTER_DELIM:
        raise ValueError("Missing YAML frontmatter delimiter '---' at start")

    # Find closing delimiter
    start = i + 1
    end = None
    for j in range(start, len(lines)):
        if lines[j].strip() == _FRONTMATTER_DELIM:
            end = j
            break

    if end is None:
        raise ValueError("Missing YAML frontmatter closing delimiter '---'")

    fm = "\n".join(lines[start:end]) + "\n"
    body = "\n".join(lines[end + 1 :])
    # Preserve trailing newline preference minimally
    if body and not body.endswith("\n"):
        body += "\n"
    return fm, body


def parse_frontmatter_yaml(frontmatter_yaml: str) -> Dict[str, Any]:
    try:
        data = yaml.safe_load(frontmatter_yaml) or {}
    except Exception as e:
        raise ValueError(f"Failed to parse YAML frontmatter: {e!r}")

    if not isinstance(data, dict):
        raise ValueError("Frontmatter must be a YAML mapping (object)")

    return data


def load_skill_doc(skill_dir: str) -> SkillDoc:
    text = read_skill_md(skill_dir)
    fm_text, body = split_frontmatter(text)
    fm = parse_frontmatter_yaml(fm_text)
    return SkillDoc(path=skill_dir, frontmatter=fm, body_markdown=body)


def load_skill_frontmatter_only(skill_dir: str) -> Dict[str, Any]:
    """Load only YAML frontmatter from SKILL.md (progressive disclosure)."""

    text = read_skill_md(skill_dir)
    fm_text, _ = split_frontmatter(text)
    return parse_frontmatter_yaml(fm_text)


# ------------------------------
# Validation
# ------------------------------


def _skill_dir_basename(skill_dir: str) -> str:
    p = os.path.normpath(skill_dir)
    return os.path.basename(p)


def validate_skill_frontmatter(
    skill_dir: str, frontmatter: Dict[str, Any], strict: bool = False
) -> Tuple[bool, List[str], List[str]]:
    """Validate a skill based on the Agent Skills spec.

    Returns: (ok, errors, warnings)
    """

    errors: List[str] = []
    warnings: List[str] = []

    # name
    name = frontmatter.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("frontmatter.name is required and must be a non-empty string")
    else:
        name = name.strip()
        if len(name) > NAME_MAX_LEN:
            errors.append(f"frontmatter.name must be <= {NAME_MAX_LEN} characters")
        if not _NAME_RE.match(name):
            errors.append(
                "frontmatter.name must match ^[a-z0-9-]{1,64}$ (lowercase letters, digits, hyphen)"
            )
        if name.startswith("-") or name.endswith("-"):
            errors.append("frontmatter.name must not start or end with '-' ")
        if "--" in name:
            errors.append("frontmatter.name must not contain consecutive hyphens '--'")

        # directory name match
        base = _skill_dir_basename(skill_dir)
        if base != name:
            errors.append(
                f"frontmatter.name must match parent directory name: dir='{base}', name='{name}'"
            )

    # description
    desc = frontmatter.get("description")
    if not isinstance(desc, str) or not desc.strip():
        errors.append(
            "frontmatter.description is required and must be a non-empty string"
        )
    else:
        desc = desc.strip()
        if len(desc) > DESCRIPTION_MAX_LEN:
            errors.append(
                f"frontmatter.description must be <= {DESCRIPTION_MAX_LEN} characters"
            )

    # license (optional)
    lic = frontmatter.get("license")
    if lic is not None and not isinstance(lic, str):
        errors.append("frontmatter.license must be a string if provided")

    # compatibility (optional)
    comp = frontmatter.get("compatibility")
    if comp is not None:
        if not isinstance(comp, str):
            errors.append("frontmatter.compatibility must be a string if provided")
        else:
            comp_s = comp.strip()
            if not comp_s:
                errors.append("frontmatter.compatibility must be non-empty if provided")
            if len(comp_s) > COMPATIBILITY_MAX_LEN:
                errors.append(
                    f"frontmatter.compatibility must be <= {COMPATIBILITY_MAX_LEN} characters"
                )

    # metadata (optional)
    meta = frontmatter.get("metadata")
    if meta is not None:
        if not isinstance(meta, dict):
            errors.append("frontmatter.metadata must be a mapping (object) if provided")
        else:
            for k, v in meta.items():
                if not isinstance(k, str):
                    errors.append("frontmatter.metadata keys must be strings")
                    break
                if not isinstance(v, str):
                    errors.append("frontmatter.metadata values must be strings")
                    break

    # allowed-tools (optional)
    allowed = frontmatter.get("allowed-tools")
    if allowed is not None and not isinstance(allowed, str):
        errors.append("frontmatter.allowed-tools must be a string if provided")

    ok = len(errors) == 0 and (not strict or len(warnings) == 0)
    return ok, errors, warnings


# ------------------------------
# Safe path resolution for skill files
# ------------------------------


def safe_resolve_skill_relative_path(skill_dir: str, relative_path: str) -> str:
    """Resolve a file path under skill_dir securely.

    - Reject absolute paths
    - Reject paths containing '..'
    - Ensure resolved path stays under skill_dir (realpath check)

    Returns resolved absolute path.
    """

    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError("relative_path must be a non-empty string")

    # Normalize separators, but keep relative semantics
    rp = relative_path.replace("\\", "/")

    if os.path.isabs(rp):
        raise ValueError("absolute paths are not allowed")

    parts = [p for p in rp.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise ValueError("'..' is not allowed in relative_path")

    # Join and realpath
    skill_real = os.path.realpath(skill_dir)
    target = os.path.realpath(os.path.join(skill_real, *parts))

    # Ensure containment (case-insensitive on Windows by normcase)
    skill_cmp = os.path.normcase(skill_real)
    target_cmp = os.path.normcase(target)
    if target_cmp == skill_cmp:
        # points to dir itself
        raise ValueError("relative_path must point to a file, not the skill root")

    if not target_cmp.startswith(skill_cmp + os.sep):
        raise ValueError("path traversal detected: resolved path escapes skill_dir")

    return target
