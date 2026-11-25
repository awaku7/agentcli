from __future__ import annotations

"""Convert local files to Markdown with Microsoft MarkItDown."""

import json
from pathlib import Path
from typing import Any

from .._pip_auto import install_with_status
from .i18n_helper import make_tool_translator
from .safe_file_ops_extras import (
    ensure_within_workdir,
    is_path_dangerous,
    make_backup_before_overwrite,
)

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:markitdown"

_DEFAULT_MAX_INPUT_BYTES = 100 * 1024 * 1024
_MAX_INPUT_BYTES = 500 * 1024 * 1024
_DEFAULT_MAX_OUTPUT_CHARS = 120_000
_MAX_OUTPUT_CHARS = 2_000_000

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_level": 1,
    "external_data": True,
    "x_parallel_safe": True,
    "function": {
        "name": "markitdown",
        "description": _(
            "tool.description",
            default=(
                "Convert a local document or media file to Markdown using Microsoft "
                "MarkItDown. The package is installed on first use according to "
                "UAGENT_AUTO_INSTALL. Plugins and URL fetching are disabled; input "
                "files must be inside the current workdir."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "markitdown",
                "convert file to markdown",
                "document to markdown",
                "pdf to markdown",
                "epub to markdown",
                "extract document text",
            ],
        ),
        "x_search_terms_en": [
            "markitdown",
            "convert file to markdown",
            "document to markdown",
            "pdf to markdown",
            "epub to markdown",
            "extract document text",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "input_path": {
                    "type": "string",
                    "description": _(
                        "param.input_path.description",
                        default="Local input file under the current workdir.",
                    ),
                },
                "output_path": {
                    "type": "string",
                    "default": "",
                    "description": _(
                        "param.output_path.description",
                        default=(
                            "Optional destination .md file under the current workdir. "
                            "When omitted, Markdown is returned in the tool result."
                        ),
                    ),
                },
                "overwrite": {
                    "type": "boolean",
                    "default": False,
                    "description": _(
                        "param.overwrite.description",
                        default=(
                            "Allow replacing an existing output file; a .org backup "
                            "is created before replacement."
                        ),
                    ),
                },
                "max_input_bytes": {
                    "type": "integer",
                    "default": _DEFAULT_MAX_INPUT_BYTES,
                    "minimum": 1,
                    "maximum": _MAX_INPUT_BYTES,
                    "description": _(
                        "param.max_input_bytes.description",
                        default=(
                            "Maximum accepted input file size in bytes "
                            "(default 100 MiB; maximum 500 MiB)."
                        ),
                    ),
                },
                "max_output_chars": {
                    "type": "integer",
                    "default": _DEFAULT_MAX_OUTPUT_CHARS,
                    "minimum": 1,
                    "maximum": _MAX_OUTPUT_CHARS,
                    "description": _(
                        "param.max_output_chars.description",
                        default=(
                            "Maximum Markdown characters returned when output_path is "
                            "omitted (default 120,000; maximum 2,000,000)."
                        ),
                    ),
                },
            },
            "required": ["input_path"],
            "additionalProperties": False,
        },
    },
}


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _error(message: str) -> str:
    return _json({"ok": False, "error": message})


def _safe_input(input_path: str) -> Path:
    if not input_path or is_path_dangerous(input_path):
        raise PermissionError(
            _(
                "err.unsafe_path",
                default="Path is empty, invalid, or outside the current workdir.",
            )
        )
    path = Path(ensure_within_workdir(input_path))
    if not path.is_file():
        raise FileNotFoundError(
            _(
                "err.input_not_found",
                default="Input file could not be accessed: %(path)s",
            )
            % {"path": input_path}
        )
    return path


def _ensure_markitdown() -> bool:
    # Install the format extras once when MarkItDown itself is absent. Avoid
    # loading third-party plugins or enabling cloud-backed converters here.
    return install_with_status(
        "markitdown[all]",
        "markitdown",
        display_name="MarkItDown",
        version_spec=">=0.1.9",
    )


def _convert_local(path: Path) -> str:
    from markitdown import MarkItDown

    converter = MarkItDown(enable_plugins=False)
    convert_local = getattr(converter, "convert_local", None)
    if not callable(convert_local):
        raise RuntimeError(
            "Installed MarkItDown version does not support convert_local; "
            "please update the package."
        )
    result = convert_local(str(path))
    markdown = getattr(result, "markdown", None)
    if markdown is None:
        markdown = getattr(result, "text_content", None)
    if not isinstance(markdown, str):
        raise RuntimeError("MarkItDown returned no Markdown text.")
    return markdown


def run_tool(args: dict[str, Any]) -> str:
    """Convert a workdir-local file to Markdown, with plugins and URLs disabled."""
    input_path = str(args.get("input_path", "") or "").strip()
    if not input_path:
        return _error(
            _(
                "err.input_required",
                default="input_path is required.",
            )
        )

    try:
        source = _safe_input(input_path)
    except PermissionError as exc:
        return _json({"ok": False, "error": str(exc)})
    except FileNotFoundError as exc:
        return _json({"ok": False, "error": str(exc)})
    except Exception:
        return _error(
            _(
                "err.input_not_found",
                default="Input file could not be accessed: %(path)s",
                path=input_path,
            )
        )

    try:
        max_input_bytes = int(args.get("max_input_bytes", _DEFAULT_MAX_INPUT_BYTES))
        if not 1 <= max_input_bytes <= _MAX_INPUT_BYTES:
            raise ValueError
    except (TypeError, ValueError):
        return _error(
            _(
                "err.invalid_limit",
                default="max_input_bytes must be between 1 and 500 MiB.",
            )
        )

    input_size = source.stat().st_size
    if input_size > max_input_bytes:
        return _error(
            _(
                "err.input_too_large",
                default="Input file exceeds the configured size limit (%(limit)s bytes).",
                limit=max_input_bytes,
            )
        )

    output_value = str(args.get("output_path", "") or "").strip()
    output: Path | None = None
    if output_value:
        try:
            if is_path_dangerous(output_value):
                raise PermissionError("unsafe output path")
            output = Path(ensure_within_workdir(output_value))
            if output.suffix.lower() != ".md":
                return _error(
                    _(
                        "err.output_extension",
                        default="output_path must use the .md extension.",
                    )
                )
            if output.resolve() == source.resolve():
                return _error(
                    _(
                        "err.same_input_output",
                        default="The output path must not be the same as the input file.",
                    )
                )
            if output.exists() and not bool(args.get("overwrite", False)):
                return _error(
                    _(
                        "err.output_exists",
                        default="Output file already exists: %(path)s",
                        path=output_value,
                    )
                )
        except PermissionError:
            return _error(
                _(
                    "err.unsafe_path",
                    default="Path is empty, invalid, or outside the current workdir.",
                )
            )
        except Exception:
            return _error(
                _(
                    "err.output_path",
                    default="Output path is invalid: %(path)s",
                    path=output_value,
                )
            )

    try:
        max_output_chars = int(args.get("max_output_chars", _DEFAULT_MAX_OUTPUT_CHARS))
        if not 1 <= max_output_chars <= _MAX_OUTPUT_CHARS:
            raise ValueError
    except (TypeError, ValueError):
        return _error(
            _(
                "err.invalid_output_limit",
                default="max_output_chars must be between 1 and 2,000,000.",
            )
        )

    if not _ensure_markitdown():
        return _error(
            _(
                "err.install_failed",
                default="MarkItDown is unavailable. Check UAGENT_AUTO_INSTALL or install 'markitdown[all]' manually.",
            )
        )

    try:
        markdown = _convert_local(source)
    except Exception as exc:
        return _error(
            _(
                "err.conversion_failed",
                default="Conversion failed: %(error)s",
                error=f"{type(exc).__name__}: {exc}",
            )
        )

    if output is not None:
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            if output.exists():
                make_backup_before_overwrite(str(output))
            output.write_text(markdown, encoding="utf-8", newline="\n")
        except Exception as exc:
            return _error(
                _(
                    "err.write_failed",
                    default="Could not write Markdown output: %(error)s",
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
        return _json(
            {
                "ok": True,
                "output_path": str(output),
                "characters": len(markdown),
            }
        )

    truncated = len(markdown) > max_output_chars
    returned_markdown = markdown[:max_output_chars]
    if truncated:
        returned_markdown += "\n\n" + _(
            "msg.truncated",
            default="[Output truncated. Set output_path to save the full Markdown.]",
        )
    return _json(
        {
            "ok": True,
            "markdown": returned_markdown,
            "characters": len(markdown),
            "truncated": truncated,
        }
    )
