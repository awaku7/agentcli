from __future__ import annotations

import json

from uagent.runtime.history import rewrite_jsonl_log
from uagent.runtime.session_store import SessionStore
from uagent.runtime.tool_result_persistence import sanitize_message_for_history


def test_history_sanitizer_removes_binary_fields_without_mutating_ui_payload():
    message = {
        "role": "tool",
        "content": "generated media",
        "attachments": [
            {
                "type": "image",
                "mime": "image/png",
                "path": "/tmp/image.png",
                "artifact_id": "a" * 32,
                "data_base64": "a" * 1000,
            }
        ],
        "data_url": "data:image/png;base64," + "b" * 1000,
    }

    sanitized = sanitize_message_for_history(message)

    assert message["attachments"][0]["data_base64"] == "a" * 1000
    assert sanitized["attachments"][0]["data_base64"].startswith(
        "[binary payload omitted"
    )
    assert sanitized["attachments"][0]["path"] == "/tmp/image.png"
    assert sanitized["attachments"][0]["artifact_id"] == "a" * 32
    assert sanitized["data_url"].startswith("[binary payload omitted")


def test_session_store_persists_tool_payload_without_binary_body(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session = store.create_session(project="demo", entry_point="test")
    payload = {
        "role": "tool",
        "content": "saved",
        "attachments": [
            {
                "type": "audio",
                "mime": "audio/mpeg",
                "path": "~/.uag/artifacts/id/speech.mp3",
                "data_base64": "c" * 5000,
            }
        ],
    }

    store.append_message(session.session_id, "tool", "saved", payload=payload)

    stored = store.list_messages(session.session_id)[0]
    assert stored["attachments"][0]["path"].endswith("speech.mp3")
    assert stored["attachments"][0]["data_base64"].startswith("[binary payload omitted")
    assert "c" * 100 not in json.dumps(stored, ensure_ascii=False)


def test_jsonl_rewrite_persists_tool_payload_without_binary_body(tmp_path):
    log_path = tmp_path / "conversation.jsonl"
    message = {
        "role": "tool",
        "content": "saved",
        "attachments": [{"data_base64": "d" * 5000, "mime": "application/pdf"}],
    }

    rewrite_jsonl_log(
        str(log_path),
        [message],
        [],
        lambda item: item,
    )

    stored = json.loads(log_path.read_text(encoding="utf-8"))
    assert stored["attachments"][0]["mime"] == "application/pdf"
    assert stored["attachments"][0]["data_base64"].startswith("[binary payload omitted")
    assert "d" * 100 not in log_path.read_text(encoding="utf-8")


def test_non_tool_messages_are_not_binary_sanitized():
    message = {"role": "assistant", "data_base64": "keep-this"}

    assert sanitize_message_for_history(message) == message
