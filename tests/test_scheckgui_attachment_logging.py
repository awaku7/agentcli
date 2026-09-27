from __future__ import annotations

from uagent import core
from uagent.runtime.observability.content_runtime import capture_logged_message
from uagent.scheckgui_impl.worker import _log_gui_user_message


def test_gui_attachment_log_envelope_preserves_capture_denial(monkeypatch) -> None:
    logged: list[dict[str, object]] = []
    monkeypatch.setattr(core, "log_message", logged.append)

    message = {
        "role": "user",
        "content": "[Attached File] report.txt (C:/private/report.txt)",
    }
    _log_gui_user_message(message, attachment_derived=True)

    assert logged == [
        {
            "role": "user",
            "content": "[Attached File] report.txt (C:/private/report.txt)",
            "attachments": True,
        }
    ]
    assert capture_logged_message(logged[0]) is False
    assert "attachments" not in message


def test_gui_plain_log_envelope_is_unchanged(monkeypatch) -> None:
    logged: list[dict[str, object]] = []
    monkeypatch.setattr(core, "log_message", logged.append)
    message = {"role": "user", "content": "plain text"}

    _log_gui_user_message(message, attachment_derived=False)

    assert logged == [message]
    assert logged[0] is message
