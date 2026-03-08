# tools/get_env_tool.py
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from typing import Any, Dict
from ..env_utils import env_get

from .context import get_callbacks

BUSY_LABEL = False

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_env",
        "description": _(
            "tool.description",
            default="Gets the value of a specified environment variable and returns it. Optionally masks the value.",
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default="This tool is used for the following purpose: get the value of a specified environment variable and return it. Optionally mask the value.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": _(
                        "param.name.description",
                        default="The name of the environment variable to read.",
                    ),
                },
                "missing_ok": {
                    "type": "boolean",
                    "description": _(
                        "param.missing_ok.description",
                        default="If true, returns '(not set)' instead of an error if the variable is missing. Default is false.",
                    ),
                },
                "mask": {
                    "type": "boolean",
                    "description": _(
                        "param.mask.description",
                        default="If true, masks the value (e.g., for secrets). Default is true.",
                    ),
                },
                "unmasked_chars": {
                    "type": "integer",
                    "description": _(
                        "param.unmasked_chars.description",
                        default="Number of characters to keep visible at the start and end when masking. Default is 2.",
                    ),
                },
            },
            "required": ["name"],
        },
    },
}


def _mask_value(val: str, keep: int = 2) -> str:
    if val is None:
        return ""
    s = str(val)
    if keep < 0:
        keep = 0
    # Short values: fully mask
    if len(s) <= keep * 2 + 1:
        return "***"
    head = s[:keep] if keep else ""
    tail = s[-keep:] if keep else ""
    return f"{head}***{tail}"


def run_tool(args: Dict[str, Any]) -> str:
    # NOTE:
    # - Tool call traces are handled centrally in tools/__init__.py.
    # - Avoid extra debug prints here to prevent duplicate output.

    cb = get_callbacks()

    name = str(args.get("name", "") or "").strip()
    missing_ok = bool(args.get("missing_ok", False))

    # Security default: mask unless explicitly disabled.
    mask = True if args.get("mask") is None else bool(args.get("mask"))
    try:
        unmasked_chars = int(args.get("unmasked_chars", 2))
    except Exception:
        unmasked_chars = 2

    if not name:
        return _("err.name_required", default="[get_env error] 'name' is required")

    try:
        # Prefer host-provided getter (it may enforce policies)
        if cb.get_env is not None:
            try:
                val = cb.get_env(name)
            except SystemExit:
                # Host get_env may sys.exit(1) when missing
                if missing_ok:
                    return f"{name}=(not set)"
                return f"[get_env error] {name} is not set"

            out_val = _mask_value(val, keep=unmasked_chars) if mask else str(val)
            return f"{name}={out_val}"

        # Fallback: direct os.environ
        val2 = env_get(name)
        if val2 is None:
            if missing_ok:
                return f"{name}=(not set)"
            return f"[get_env error] {name} is not set"

        out_val2 = _mask_value(val2, keep=unmasked_chars) if mask else str(val2)
        return f"{name}={out_val2}"

    except Exception as e:
        return f"[get_env error] {type(e).__name__}: {e}"
