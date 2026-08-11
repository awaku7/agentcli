"""Unit-aware calculations using Pint, installed lazily when needed."""

from __future__ import annotations

import json
import re
from typing import Any

from .._pip_auto import install_with_status as _auto_install
from .arg_util import get_int, get_str
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "utility",
    "x_parallel_safe": True,
    "function": {
        "name": "quantities",
        "description": _(
            "tool.description",
            default=(
                "Convert units and evaluate unit-aware physical quantities using Pint. "
                "Supports expressions such as '25 degC to degF' or "
                "'2.5 kW * 8 hour to kWh'."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "quantities",
                "units",
                "unit conversion",
                "convert units",
                "physical quantities",
                "temperature conversion",
                "pressure conversion",
                "power calculation",
                "engineering units",
                "Pint",
            ],
        ),
        "x_search_terms_en": [
            "quantities",
            "units",
            "unit conversion",
            "convert units",
            "physical quantities",
            "temperature conversion",
            "pressure conversion",
            "power calculation",
            "engineering units",
            "Pint",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": _(
                        "param.expression.description",
                        default=(
                            "A Pint quantity expression, optionally followed by "
                            "'to UNIT'; examples: '25 degC to degF', "
                            "'1 meter + 20 centimeter to meter'."
                        ),
                    ),
                },
                "to_unit": {
                    "type": "string",
                    "description": _(
                        "param.to_unit.description",
                        default=(
                            "Optional target unit. Use this instead of the 'to UNIT' "
                            "suffix when preferred."
                        ),
                    ),
                },
                "precision": {
                    "type": "integer",
                    "description": _(
                        "param.precision.description",
                        default="Number of decimal places in the formatted result (default: 6).",
                    ),
                    "default": 6,
                    "minimum": 0,
                    "maximum": 15,
                },
            },
            "required": ["expression"],
        },
    },
}

_UNSAFE_EXPRESSION = re.compile(
    r"(?:__|\b(?:import|exec|eval|lambda|globals|locals|open)\b|[\[\]{};`])",
    re.IGNORECASE,
)
_TO_SUFFIX = re.compile(r"\s+(?:to|in)\s+(.+?)\s*$", re.IGNORECASE)


def _error(message: str, **extra: Any) -> str:
    result: dict[str, Any] = {"ok": False, "error": message}
    result.update(extra)
    return json.dumps(result, ensure_ascii=False)


def _load_pint() -> Any:
    try:
        import pint
    except ImportError:
        if not _auto_install("Pint", "pint", version_spec=">=0.24.4"):
            raise RuntimeError(
                _(
                    "err.pint_unavailable",
                    default="Pint is not installed and automatic installation failed.",
                )
            )
        import pint

    return pint


def _split_expression(expression: str, explicit_target: str) -> tuple[str, str]:
    target = explicit_target.strip()
    if target:
        return expression.strip(), target
    match = _TO_SUFFIX.search(expression)
    if not match:
        return expression.strip(), ""
    return expression[: match.start()].strip(), match.group(1).strip()


def _format_result(quantity: Any, precision: int) -> str:
    magnitude = quantity.magnitude
    if isinstance(magnitude, complex):
        magnitude_text = str(magnitude)
    else:
        magnitude_text = f"{float(magnitude):.{precision}f}".rstrip("0").rstrip(".")
        if magnitude_text in {"-0", ""}:
            magnitude_text = "0"
    return f"{magnitude_text} {quantity.units:~P}"


def run_tool(args: dict[str, Any]) -> str:
    """Evaluate a Pint expression and optionally convert it to another unit."""
    expression = get_str(args, "expression", "").strip()
    if not expression:
        return _error(
            _(
                "err.expression_missing",
                default="No quantity expression was provided.",
            )
        )
    if _UNSAFE_EXPRESSION.search(expression):
        return _error(
            _(
                "err.expression_unsafe",
                default="The quantity expression contains unsupported syntax.",
            )
        )

    target_arg = get_str(args, "to_unit", "").strip()
    source, target = _split_expression(expression, target_arg)
    if _UNSAFE_EXPRESSION.search(target):
        return _error(
            _(
                "err.target_unsafe",
                default="The target unit contains unsupported syntax.",
            )
        )
    precision = max(0, min(15, get_int(args, "precision", 6)))
    if not source:
        return _error(
            _(
                "err.expression_missing",
                default="No quantity expression was provided.",
            )
        )

    try:
        pint = _load_pint()
        registry = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)
        quantity = registry.parse_expression(source)
        if target:
            quantity = quantity.to(target)
        result = _format_result(quantity, precision)
        output = {
            "ok": True,
            "expression": expression,
            "result": result,
            "magnitude": quantity.magnitude,
            "unit": str(quantity.units),
        }
        return json.dumps(output, ensure_ascii=False, default=str)
    except Exception as exc:
        return _error(
            _(
                "err.evaluation",
                default="Unable to evaluate the quantity expression: %(error)s",
            )
            % {"error": str(exc)},
            expression=expression,
        )


__all__ = ["TOOL_SPEC", "run_tool"]
