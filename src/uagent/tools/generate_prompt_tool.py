from __future__ import annotations

from datetime import datetime
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "generate_prompt",
        "description": _(
            "tool.description",
            default=(
                "Analyze a single file and generate a prompt based on the analysis, then save it as a unique file under files/."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "This tool is used for the following purpose: analyze a single file and generate a prompt based on the analysis, then save it as a unique file under files/."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path of the file to analyze (required).",
                    ),
                },
                "template": {
                    "type": "string",
                    "description": _(
                        "param.template.description",
                        default=(
                            "(Optional) Prompt template. You can use placeholders: {path},{lines},{size},{mtime},{excerpt},{timestamp}."
                        ),
                    ),
                },
            },
            "required": ["path"],
        },
    },
}


DEFAULT_TEMPLATE = (
    "Please analyze the following file, point out issues, propose improvements, and generate a fix patch.\n"
    "Target file: {path}\n"
    "File summary: lines={lines}, size={size} bytes, mtime={mtime}\n\n"
    "Excerpt (first up to 20 lines):\n{excerpt}\n\n"
    "Output requirements:\n"
    "1) List up to 3 issues in bullet points.\n"
    "2) Propose 2 improvement approaches and briefly explain trade-offs for each.\n"
    "3) If you would modify the file, generate a diff (patch/unified diff format).\n\n"
    "This prompt was auto-generated. Generated at: {timestamp}\n"
)


SafeGeneratePrompt = Callable[[str, str | None], str]

# Use safe wrapper when available; it may ask for confirmation for risky reads
safe_generate_prompt: Optional[SafeGeneratePrompt]
try:
    from .safe_file_ops import safe_generate_prompt as safe_generate_prompt
except Exception:
    safe_generate_prompt = None


def _derive_result_path(out_path: Path) -> Path:
    """Derive the default result output file path from a generated prompt file."""
    # files/prompt_YYYYmmddTHHMMSS.txt -> files/result_prompt_YYYYmmddTHHMMSS.txt
    stem = out_path.stem
    return out_path.with_name(f"result_{stem}.txt")


def run_tool(args: Dict[str, Any]) -> str:
    """Prompt generator tool.

    args:
      - path: path to the target file (required)
      - template: optional template

    Behavior:
      - validate file existence
      - collect metadata and an excerpt
      - render a template and save to files/ with a unique name
      - return prompt file path and suggested result file path
    """

    path = (args.get("path") or "").strip()
    template = args.get("template") or DEFAULT_TEMPLATE

    if not path:
        return _(
            "err.path_required", default="[generate_prompt error] path is required"
        )

    p = Path(path)
    if not p.exists() or not p.is_file():
        return f"[generate_prompt error] file not found: {path}"

    # Prefer safe wrapper if available (may ask for confirmation even on reads)
    try:
        if safe_generate_prompt is not None:
            out = safe_generate_prompt(path, template)
            out_path = Path(str(out))
            result_path = _derive_result_path(out_path)
            return (
                "[generate_prompt] Prompt created:\n"
                f"  prompt_file: {out_path}\n"
                f"  result_file(suggested): {result_path}"
            )
    except PermissionError as e:
        return f"[generate_prompt error] PermissionError: {e}"
    except Exception:
        # fallthrough to builtin logic
        pass

    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        try:
            text = p.read_text(encoding="latin-1")
        except Exception as e:
            return f"[generate_prompt error] failed to read file: {e}"

    lines = text.splitlines()
    excerpt = "\n".join(lines[:20])
    stat = p.stat()
    size = stat.st_size
    mtime = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime))
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")

    prompt_text = template.format(
        path=str(p),
        lines=len(lines),
        size=size,
        mtime=mtime,
        excerpt=excerpt,
        timestamp=timestamp,
    )

    from uagent.utils.paths import get_files_dir

    files_dir = get_files_dir()
    try:
        files_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return f"[generate_prompt error] failed to create files directory: {e}"

    base_name = f"prompt_{timestamp}.txt"
    out_path = files_dir / base_name
    # If collision occurs, append a counter
    i = 1
    while out_path.exists():
        out_path = files_dir / f"prompt_{timestamp}_{i}.txt"
        i += 1

    try:
        out_path.write_text(prompt_text, encoding="utf-8")
    except Exception as e:
        return f"[generate_prompt error] failed to write prompt file: {e}"

    result_path = _derive_result_path(out_path)

    return (
        "[generate_prompt] Prompt created:\n"
        f"  prompt_file: {out_path}\n"
        f"  result_file(suggested): {result_path}"
    )
