import json
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "src" / "uagent" / "tools"
PACKAGE_MESSAGE_CASES = (
    ("ble_ops_tool.json", "err.pyside6_missing", "PySide6", "pip install PySide6"),
    (
        "svg_to_image_tool.json",
        "error.renderer_unavailable",
        "CairoSVG",
        "pip install CairoSVG",
    ),
    (
        "svg_to_image_tool.json",
        "error.pillow_unavailable",
        "Pillow",
        "pip install Pillow",
    ),
    (
        "exstruct_tool.json",
        "error.missing_exstruct",
        "exstruct",
        "pip install exstruct",
    ),
    ("exstruct_tool.json", "load.disabled", "exstruct", "pip install exstruct"),
)


def test_localized_dependency_messages_preserve_package_identifiers_and_commands():
    invalid = []

    for filename, key, package, command in PACKAGE_MESSAGE_CASES:
        payload = json.loads((TOOLS_DIR / filename).read_text(encoding="utf-8"))

        for lang, messages in payload.items():
            if not isinstance(messages, dict):
                continue

            message = messages.get(key)
            if message is None:
                continue

            command_index = message.find(command)
            prose = message[:command_index] if command_index >= 0 else message
            if package.lower() not in prose.lower():
                invalid.append(f"{filename}:{lang}:{key}: missing package in prose")
            if not message.rstrip().endswith(command):
                invalid.append(f"{filename}:{lang}:{key}: invalid install command")

    assert not invalid, (
        "Localized dependency messages must preserve literal package identifiers "
        "and install commands: " + ", ".join(invalid)
    )
