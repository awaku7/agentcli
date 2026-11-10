from __future__ import annotations

from threading import Lock
from types import SimpleNamespace

from uagent.cli_impl.main import _nostr_remote_status_text


def test_status_summary_includes_cli_activity_and_remote_queue_state() -> None:
    runtime = SimpleNamespace(
        status=lambda: {"state": "running", "pending": 2, "dispatching": 1}
    )
    core = SimpleNamespace(
        status_lock=Lock(),
        status_busy=True,
        status_label="LLM\nworking",
        session_id="active-session",
        human_ask_lock=Lock(),
        human_ask_active=True,
        _sub_agent_job_manager=SimpleNamespace(
            running_count=lambda *, owner: 3 if owner == "owner" else 0
        ),
        _sub_agent_job_owner="owner",
        _nostr_remote_runtime=runtime,
    )

    status = _nostr_remote_status_text(core)

    assert "CLI: busy" in status
    assert "Activity: LLM working" in status
    assert "Session: active-session" in status
    assert "Waiting for human input: yes" in status
    assert "Background jobs: 3" in status
    assert "Nostr remote listener: running" in status
    assert "Pending remote requests: 2" in status
    assert "Requests needing reconciliation: 1" in status
    assert "LLM\nworking" not in status


def test_status_summary_fails_closed_to_sanitized_unavailable_state() -> None:
    core = SimpleNamespace(
        status_lock=Lock(),
        status_busy=False,
        status_label="",
        human_ask_lock=Lock(),
        human_ask_active=False,
        _nostr_remote_runtime=SimpleNamespace(
            status=lambda: (_ for _ in ()).throw(RuntimeError("private detail"))
        ),
    )

    status = _nostr_remote_status_text(core)

    assert "CLI: idle" in status
    assert "Activity:" not in status
    assert "Nostr remote listener: status unavailable" in status
    assert "private detail" not in status
