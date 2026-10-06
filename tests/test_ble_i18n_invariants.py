import json
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "src" / "uagent" / "tools"
BLE_LOCALE_FILES = (
    "ble_ops_tool.json",
    "switchbot_ble_control_tool.json",
    "switchbot_ble_scan_tool.json",
    "switchbot_ble_status_tool.json",
)


def test_bleak_dependency_messages_preserve_package_and_install_command():
    for filename in BLE_LOCALE_FILES:
        payload = json.loads((TOOLS_DIR / filename).read_text(encoding="utf-8"))

        for lang, messages in payload.items():
            if not isinstance(messages, dict):
                continue
            message = messages.get("err.bleak_missing")
            if message is None:
                continue

            assert "bleak" in message.lower(), f"{filename}:{lang}"
            assert message.splitlines()[-1].strip() == "pip install bleak", (
                f"{filename}:{lang}"
            )
