from __future__ import annotations

import json
from pathlib import Path

import pytest

from uagent.tools.space_steganography_tool import run_tool

CARRIER = "word " * 80


def _run_embed(tmp_path: Path, hidden_text: str = "SBC", repeat: bool = False) -> Path:
    carrier_path = tmp_path / "carrier.txt"
    output_path = tmp_path / "encoded.txt"
    carrier_path.write_text(CARRIER, encoding="utf-8")
    result = json.loads(
        run_tool(
            {
                "action": "embed",
                "carrier_path": str(carrier_path),
                "output_path": str(output_path),
                "hidden_text": hidden_text,
                "repeat": repeat,
            }
        )
    )
    assert result["ok"] is True
    assert output_path.exists()
    return output_path


def test_embed_and_extract_utf8_text(tmp_path: Path) -> None:
    encoded_path = _run_embed(tmp_path, "秘密")

    result = json.loads(
        run_tool(
            {
                "action": "extract",
                "carrier_path": str(encoded_path),
                "byte_length": len("秘密".encode("utf-8")),
            }
        )
    )

    assert result["message"] == "秘密"
    assert result["nbsp_count"] > 0


def test_detect_reports_repeated_messages(tmp_path: Path) -> None:
    encoded_path = _run_embed(tmp_path, "OK", repeat=True)

    result = json.loads(
        run_tool(
            {
                "action": "detect",
                "carrier_path": str(encoded_path),
                "byte_length": 2,
            }
        )
    )

    assert result["action"] == "detect"
    assert result["message"].split(" | ")
    assert all(message == "OK" for message in result["message"].split(" | "))
    assert len(result["bits"]) == result["space_bit_count"]


def test_embed_rejects_insufficient_spaces(tmp_path: Path) -> None:
    carrier_path = tmp_path / "carrier.txt"
    output_path = tmp_path / "encoded.txt"
    carrier_path.write_text("one two", encoding="utf-8")

    with pytest.raises(ValueError):
        run_tool(
            {
                "action": "embed",
                "carrier_path": str(carrier_path),
                "output_path": str(output_path),
                "hidden_text": "too long",
            }
        )


def test_invalid_action_is_rejected(tmp_path: Path) -> None:
    carrier_path = tmp_path / "carrier.txt"
    carrier_path.write_text(CARRIER, encoding="utf-8")

    with pytest.raises(ValueError):
        run_tool({"action": "unknown", "carrier_path": str(carrier_path)})
