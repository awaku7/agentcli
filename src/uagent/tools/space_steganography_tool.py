from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

NORMAL_SPACE = "\u0020"
NO_BREAK_SPACE = "\u00a0"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "file",
    "x_parallel_safe": True,
    "type": "function",
    "function": {
        "name": "space_steganography",
        "description": _(
            "tool.description",
            default=(
                "Embed, extract, and detect hidden UTF-8 text represented by normal "
                "spaces and non-breaking spaces in a text file."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "steganography",
                "space steganography",
                "hidden text",
                "normal space",
                "non-breaking space",
                "NBSP",
            ],
        ),
        "x_search_terms_en": [
            "steganography",
            "space steganography",
            "hidden text",
            "normal space",
            "non-breaking space",
            "NBSP",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": _(
                        "param.action.description",
                        default="Operation: embed, extract, or detect.",
                    ),
                    "enum": ["embed", "extract", "detect"],
                },
                "carrier_path": {
                    "type": "string",
                    "description": _(
                        "param.carrier_path.description",
                        default="UTF-8 text file to read.",
                    ),
                },
                "output_path": {
                    "type": "string",
                    "description": _(
                        "param.output_path.description",
                        default="Output UTF-8 text file path for embed.",
                    ),
                },
                "hidden_text": {
                    "type": "string",
                    "description": _(
                        "param.hidden_text.description",
                        default="UTF-8 text to hide when embedding.",
                    ),
                },
                "byte_length": {
                    "type": "integer",
                    "description": _(
                        "param.byte_length.description",
                        default="Number of UTF-8 message bytes to extract or detect.",
                    ),
                },
                "repeat": {
                    "type": "boolean",
                    "description": _(
                        "param.repeat.description",
                        default="Repeat the hidden bit sequence across all available spaces.",
                    ),
                },
            },
            "required": ["action", "carrier_path"],
            "additionalProperties": False,
        },
    },
}


def _text_to_bits(value: str) -> str:
    return "".join(f"{byte:08b}" for byte in value.encode("utf-8"))


def _bits_to_text(bits: str) -> str:
    if len(bits) % 8 != 0:
        raise ValueError(
            _(
                "error.bits_not_byte_aligned",
                default="The extracted bit count must be a multiple of 8.",
            )
        )
    data = bytes(int(bits[index : index + 8], 2) for index in range(0, len(bits), 8))
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(
            _(
                "error.invalid_utf8",
                default="The extracted bytes are not valid UTF-8.",
            )
        ) from error


def _extract_bits(text: str) -> str:
    return "".join(
        "0" if char == NORMAL_SPACE else "1"
        for char in text
        if char in (NORMAL_SPACE, NO_BREAK_SPACE)
    )


def _embed_text(carrier: str, hidden_text: str, repeat: bool) -> str:
    bits = _text_to_bits(hidden_text)
    if not bits:
        raise ValueError(
            _("error.hidden_text_empty", default="hidden_text must not be empty.")
        )

    available = carrier.count(NORMAL_SPACE)
    if not repeat and available < len(bits):
        raise ValueError(
            _(
                "error.insufficient_spaces",
                default="Not enough normal spaces: required={required}, available={available}.",
            ).format(required=len(bits), available=available)
        )

    result: list[str] = []
    bit_index = 0
    for char in carrier:
        if char == NORMAL_SPACE and (repeat or bit_index < len(bits)):
            result.append(
                NO_BREAK_SPACE if bits[bit_index % len(bits)] == "1" else NORMAL_SPACE
            )
            bit_index += 1
        else:
            result.append(char)
    return "".join(result)


def _extract_text(text: str, byte_length: int, repeated: bool) -> str:
    if byte_length <= 0:
        raise ValueError(
            _(
                "error.byte_length_positive",
                default="byte_length must be greater than zero.",
            )
        )
    bits = _extract_bits(text)
    required = byte_length * 8
    if len(bits) < required:
        raise ValueError(
            _(
                "error.insufficient_bits",
                default="Not enough encoded bits: required={required}, available={available}.",
            ).format(required=required, available=len(bits))
        )

    if not repeated:
        return _bits_to_text(bits[:required])

    complete = bits[: len(bits) - (len(bits) % required)]
    if not complete:
        raise ValueError(
            _(
                "error.no_complete_message",
                default="No complete repeated message unit was found.",
            )
        )
    return " | ".join(
        _bits_to_text(complete[index : index + required])
        for index in range(0, len(complete), required)
    )


def _read_text(path_value: str) -> tuple[Path, str]:
    if not path_value.strip():
        raise ValueError(
            _("error.carrier_required", default="carrier_path is required.")
        )
    path = Path(path_value)
    try:
        return path, path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(
            _(
                "error.read_failed",
                default="Could not read carrier_path: {path}",
            ).format(path=path)
        ) from error


def run_tool(args: dict[str, Any]) -> str:
    action = str(args.get("action", "")).strip().lower()
    if action not in {"embed", "extract", "detect"}:
        raise ValueError(
            _(
                "error.invalid_action",
                default="action must be embed, extract, or detect.",
            )
        )

    carrier_path, carrier = _read_text(str(args.get("carrier_path", "") or ""))

    if action == "embed":
        output_value = str(args.get("output_path", "") or "").strip()
        if not output_value:
            raise ValueError(
                _(
                    "error.output_required",
                    default="output_path is required for embed.",
                )
            )
        hidden_text = str(args.get("hidden_text", "") or "")
        encoded = _embed_text(carrier, hidden_text, bool(args.get("repeat", False)))
        output_path = Path(output_value)
        try:
            output_path.write_text(encoded, encoding="utf-8")
        except OSError as error:
            raise ValueError(
                _(
                    "error.write_failed",
                    default="Could not write output_path: {path}",
                ).format(path=output_path)
            ) from error
        return json.dumps(
            {
                "ok": True,
                "action": action,
                "carrier_path": str(carrier_path),
                "output_path": str(output_path.resolve()),
                "hidden_bytes": len(hidden_text.encode("utf-8")),
                "space_count": carrier.count(NORMAL_SPACE),
            },
            ensure_ascii=False,
        )

    byte_length = int(args.get("byte_length", 0) or 0)
    bits = _extract_bits(carrier)
    message = _extract_text(carrier, byte_length, action == "detect")
    return json.dumps(
        {
            "ok": True,
            "action": action,
            "carrier_path": str(carrier_path),
            "space_bit_count": len(bits),
            "normal_space_count": bits.count("0"),
            "nbsp_count": bits.count("1"),
            "message": message,
            "bits": bits if action == "detect" else bits[: byte_length * 8],
        },
        ensure_ascii=False,
    )
