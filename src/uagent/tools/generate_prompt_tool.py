from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from .arg_util import get_path, get_str
from .context import get_callbacks
from .i18n_helper import make_tool_translator
from .safe_file_ops_extras import ensure_within_workdir

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:generate_prompt"


def _json_err(message: str, **extra: Any) -> str:
    obj: Dict[str, Any] = {"ok": False, "error": message}
    obj.update(extra)
    return json.dumps(obj, ensure_ascii=False)


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "generate_prompt",
        "description": _(
            "tool.description",
            default=(
                "Generate a prompt string from a file using a Python format template. "
                "The template can reference variables like {content}, {lines}, {bytes}, {basename}, {path}."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Read a text file under workdir and generate a prompt string by applying a template (Python str.format).\n"
                "Available template variables:\n"
                "- content: full file content (text)\n"
                "- lines: number of lines\n"
                "- bytes: file size in bytes\n"
                "- basename: file basename\n"
                "- path: absolute resolved path\n"
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path of the input file (must be under workdir).",
                    ),
                },
                "filename": {
                    "type": "string",
                    "description": _(
                        "param.filename.description",
                        default="(Compatibility) Alias of path.",
                    ),
                },
                "template": {
                    "type": "string",
                    "description": _(
                        "param.template.description",
                        default=(
                            "Python format template. Example: '{lines} lines\n\n{content}'."
                        ),
                    ),
                },
            },
            "required": ["template"],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()

    raw_path = get_path(args, "path", get_path(args, "filename", ""))
    if not raw_path:
        msg = _(
            "err.path_missing",
            default="[generate_prompt error] path/filename is not specified",
        )
        return _json_err(msg)

    template = get_str(args, "template", "")
    if not template:
        msg = _(
            "err.template_missing",
            default="[generate_prompt error] template is not specified",
        )
        return _json_err(msg)

    try:
        safe_path = ensure_within_workdir(raw_path)
    except Exception as e:
        return _json_err(f"[generate_prompt error] {type(e).__name__}: {e}")

    try:
        p = Path(safe_path)
        if not p.is_file():
            return _json_err(
                _(
                    "err.not_a_file",
                    default="[generate_prompt error] not a file: {path}",
                ).format(path=str(p))
            )

        # Keep it simple: treat as UTF-8 text; replace undecodable bytes.
        content = p.read_text(encoding="utf-8", errors="replace")
        lines = content.count("\n") + (
            1 if content and not content.endswith("\n") else 0
        )
        bsz = p.stat().st_size

        vars_map: Dict[str, Any] = {
            "content": content,
            "lines": lines,
            "bytes": bsz,
            "basename": os.path.basename(str(p)),
            "path": str(p),
        }

        try:
            out = template.format(**vars_map)
        except KeyError as e:
            return _json_err(
                _(
                    "err.bad_template",
                    default="[generate_prompt error] template has unknown key: {key}",
                ).format(key=str(e)),
                available=list(vars_map.keys()),
            )
        except Exception as e:
            return _json_err(
                f"[generate_prompt error] template format failed: {type(e).__name__}: {e}"
            )

        if cb.truncate_output:
            return cb.truncate_output("generate_prompt", out, limit=10000)
        return out

    except Exception as e:
        return _json_err(f"[generate_prompt error] {type(e).__name__}: {e}")
