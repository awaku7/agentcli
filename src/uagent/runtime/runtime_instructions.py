"""Project instruction file loader (CLAUDE.md / AGENTS.md).

Walks up from workdir to root, finds instruction files, resolves @-includes,
and optionally prompts the user before loading them into the system prompt.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from ..i18n import _

# Tracks absolute paths of instruction files already loaded in this session.
# Used by reload_instruction_files() to skip duplicates after workdir changes.
_loaded_paths: set[str] = set()


@dataclass
class InstructionCandidate:
    """A single instruction file found in the directory hierarchy."""

    path: str  # absolute file path
    basename: str  # e.g. "CLAUDE.md" or "AGENTS.md"
    content: str  # resolved content (after @-include expansion)
    resolved_includes: list[str] = field(default_factory=list)
    # list of file paths that were inlined via @-include


def _find_instruction_files(workdir: str) -> list[InstructionCandidate]:
    """Walk from workdir up to root, collect CLAUDE.md / AGENTS.md files.

    Priority per directory:
      - If CLAUDE.md exists and contains @AGENTS.md, load CLAUDE.md with include resolved.
      - If both exist but no @AGENTS.md in CLAUDE.md, add both as separate candidates.
      - If only one exists, add it.
    """
    candidates: list[InstructionCandidate] = []
    seen_dirs: set[str] = set()

    current = os.path.abspath(workdir)
    while True:
        norm = os.path.normcase(os.path.normpath(current))
        if norm in seen_dirs:
            break
        seen_dirs.add(norm)

        claude_path = os.path.join(current, "CLAUDE.md")
        agents_path = os.path.join(current, "AGENTS.md")

        has_claude = os.path.isfile(claude_path)
        has_agents = os.path.isfile(agents_path)

        if has_claude:
            raw = _read_file(claude_path)
            resolved, included = _resolve_includes(raw, os.path.dirname(claude_path))
            has_agents_ref = any(
                os.path.basename(p).lower() == "agents.md" for p in included
            )

            if has_agents and has_agents_ref:
                # AGENTS.md is already included via @AGENTS.md in CLAUDE.md.
                candidates.append(
                    InstructionCandidate(
                        path=claude_path,
                        basename="CLAUDE.md",
                        content=resolved,
                        resolved_includes=included,
                    )
                )
            elif has_claude and has_agents:
                # Both exist but no @AGENTS.md reference: add both separately.
                claude_content, _ = _resolve_includes(raw, os.path.dirname(claude_path))
                agents_content = _read_file(agents_path)
                candidates.append(
                    InstructionCandidate(
                        path=claude_path,
                        basename="CLAUDE.md",
                        content=claude_content,
                    )
                )
                candidates.append(
                    InstructionCandidate(
                        path=agents_path,
                        basename="AGENTS.md",
                        content=agents_content,
                    )
                )
            else:
                # Only CLAUDE.md
                candidates.append(
                    InstructionCandidate(
                        path=claude_path,
                        basename="CLAUDE.md",
                        content=resolved,
                        resolved_includes=included,
                    )
                )
        elif has_agents:
            agents_content = _read_file(agents_path)
            candidates.append(
                InstructionCandidate(
                    path=agents_path,
                    basename="AGENTS.md",
                    content=agents_content,
                )
            )

        # Move to parent directory
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    return candidates


def _read_file(path: str) -> str:
    """Read a text file, return empty string on error."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception:
        return ""


def _resolve_includes(content: str, base_dir: str) -> tuple[str, list[str]]:
    """Process @-include directives in instruction file content.

    Supported patterns:
      @AGENTS.md           -> include AGENTS.md from the same directory
      @agents.md           -> case-insensitive variant

    Returns (resolved_content, list_of_included_file_paths).
    """
    lines = content.splitlines(keepends=True)
    result: list[str] = []
    included: list[str] = []

    for line in lines:
        stripped = line.strip()
        # Match @filename.md or @path/to/something
        if stripped.startswith("@"):
            include_target = stripped[1:].strip()
            # Skip empty or directory-only patterns (e.g. @agents/skills/)
            if not include_target or include_target.endswith("/"):
                result.append(line)
                continue

            # Resolve relative to the base directory
            target_path = os.path.normpath(os.path.join(base_dir, include_target))
            if os.path.isfile(target_path):
                included_content = _read_file(target_path)
                if included_content:
                    result.append(included_content)
                    if not included_content.endswith("\n"):
                        result.append("\n")
                    included.append(target_path)
                    continue

        result.append(line)

    return "".join(result), included


def _prompt_user(candidates: list[InstructionCandidate]) -> list[InstructionCandidate]:
    """Ask the user which instruction files to load.

    Returns the selected subset of candidates.
    Empty list means "load none".
    """
    if not candidates:
        return []

    print()
    print(_("[INFO] Project instruction files found:"))
    for idx, c in enumerate(candidates, start=1):
        include_info = ""
        if c.resolved_includes:
            include_info = _(" (includes: %(files)s)") % {
                "files": ", ".join(os.path.basename(p) for p in c.resolved_includes)
            }
        rel = os.path.relpath(c.path, os.getcwd())
        print(
            _("  [%(idx)d] %(rel)s%(inc)s")
            % {"idx": idx, "rel": rel, "inc": include_info}
        )

    print()
    print(
        _(
            "Load which files? Enter numbers (e.g. '1 2'), 'all' to load all, or 'n' to skip:"
        )
    )

    try:
        answer = input("> ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return []

    if answer in ("n", "no", "skip", "none", ""):
        return []

    if answer in ("all", "a", "y", "yes"):
        return list(candidates)

    # Parse space-separated numbers
    selected: list[InstructionCandidate] = []
    for token in answer.split():
        try:
            idx = int(token) - 1
            if 0 <= idx < len(candidates):
                selected.append(candidates[idx])
        except ValueError:
            pass

    return selected


def load_project_instruction_files(
    *,
    workdir: str | None = None,
) -> list[str]:
    """Discover and load project instruction files.

    Returns a list of content strings to inject as system messages.
    """
    # Check opt-out env var
    if os.environ.get("UAGENT_LOAD_INSTRUCTIONS", "1").strip() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return []

    if workdir is None:
        workdir = os.getcwd()

    candidates = _find_instruction_files(workdir)
    if not candidates:
        return []

    # Determine if we're in interactive (TTY) mode
    is_interactive = bool(getattr(sys.stdin, "isatty", lambda: False)())

    if is_interactive and not os.environ.get("UAGENT_INSTRUCTIONS_SKIP_PROMPT", ""):
        selected = _prompt_user(candidates)
    else:
        # Non-interactive or skip-prompt: auto-load all
        selected = candidates

    if not selected:
        return []

    contents: list[str] = []
    for c in selected:
        header = _("[Project instructions from %(file)s]") % {
            "file": os.path.relpath(c.path, workdir)
        }
        content_block = f"--- {header} ---\n{c.content}"
        # Truncate to 100KB per file
        if len(content_block) > 100_000:
            content_block = content_block[:100_000] + "\n...[truncated at 100KB]"
        contents.append(content_block)
        _loaded_paths.add(c.path)

    return contents


def reload_instruction_files(
    *,
    workdir: str | None = None,
) -> list[str]:
    """Discover and load NEW instruction files after a workdir change.

    Walks up from the given workdir to root, but skips files that were
    already loaded in this session (tracked by _loaded_paths).

    Returns a list of content strings to inject as additional system messages.
    """
    if workdir is None:
        workdir = os.getcwd()

    candidates = _find_instruction_files(workdir)
    if not candidates:
        return []

    # Filter out already-loaded files
    new_candidates = [c for c in candidates if c.path not in _loaded_paths]
    if not new_candidates:
        return []

    contents: list[str] = []
    for c in new_candidates:
        header = _("[Project instructions from %(file)s]") % {
            "file": os.path.relpath(c.path, workdir)
        }
        content_block = f"--- {header} ---\n{c.content}"
        if len(content_block) > 100_000:
            content_block = content_block[:100_000] + "\n...[truncated at 100KB]"
        contents.append(content_block)
        _loaded_paths.add(c.path)

    return contents
