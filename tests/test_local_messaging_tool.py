from __future__ import annotations

import json
import os
import queue
from pathlib import Path
from types import SimpleNamespace

import psutil

from uagent.runtime.local_messaging import LocalMessageStore
from uagent.cli_impl.main import (
    _accept_cli_local_message,
    _start_cli_local_messaging,
    _stop_cli_local_messaging,
)
from uagent.runtime.local_messaging import LocalMessageRuntime, current_endpoint_id
from uagent.tools import local_messaging_tool


def test_local_messaging_tool_is_loadable_on_demand() -> None:
    from uagent.tools._tool_load_util import is_tool_loadable

    assert "tool_genre" not in local_messaging_tool.TOOL_SPEC
    assert local_messaging_tool.TOOL_SPEC["tool_level"] == 1
    assert is_tool_loadable(local_messaging_tool.TOOL_SPEC, local_messaging_tool)


def test_local_messaging_tool_translations_cover_all_shipped_locales() -> None:
    tools_dir = Path(__file__).resolve().parents[1] / "src" / "uagent" / "tools"
    locales_dir = Path(__file__).resolve().parents[1] / "src" / "uagent" / "locales"
    catalog = json.loads(
        (tools_dir / "local_messaging_tool.json").read_text(encoding="utf-8")
    )
    expected_locales = {
        path.name for path in locales_dir.iterdir() if path.is_dir()
    } - {"en"}

    assert set(catalog) == expected_locales
    expected_keys = set(catalog["ja"])
    for locale, messages in catalog.items():
        assert set(messages) == expected_keys, locale
        assert all(
            value.strip() for key, value in messages.items() if isinstance(value, str)
        ), locale
        assert all(
            term.strip()
            for terms in messages.values()
            if isinstance(terms, list)
            for term in terms
            if isinstance(term, str)
        ), locale


def _register(
    store: LocalMessageStore,
    endpoint_id: str,
    *,
    principal_id: str = "",
    room_id: str = "",
    project_id: str = "",
    workdir: str = "",
    purpose: str = "",
) -> None:
    process = psutil.Process(os.getpid())
    store.register_endpoint(
        endpoint_id,
        entrypoint="cli",
        pid=process.pid,
        create_time=process.create_time(),
        principal_id=principal_id,
        room_id=room_id,
        project_id=project_id,
        workdir=workdir,
        purpose=purpose,
    )


def test_local_messaging_tool_lists_opted_in_peers_and_sends(
    tmp_path, monkeypatch
) -> None:
    store = LocalMessageStore(tmp_path / "messages.sqlite3")
    _register(store, "sender")
    _register(store, "peer")
    monkeypatch.setattr(
        local_messaging_tool,
        "_store_for_active_endpoint",
        lambda: (
            SimpleNamespace(
                list_peers=lambda: store.list_peers(exclude_endpoint_id="sender")
            ),
            store,
            "sender",
        ),
    )

    listed = json.loads(local_messaging_tool.run_tool({"action": "list"}))
    assert listed["ok"] is True, listed
    assert [peer["endpoint_id"] for peer in listed["peers"]] == ["peer"]

    sent = json.loads(
        local_messaging_tool.run_tool(
            {"action": "send", "recipient": "peer", "message": "hello"}
        )
    )
    assert sent["ok"] is True
    assert sent["recipient"] == "peer"
    assert store.claim_messages("peer")[0]["body"] == "hello"


def test_local_messaging_tool_fails_closed_when_not_opted_in(monkeypatch) -> None:
    monkeypatch.setattr(
        local_messaging_tool,
        "_store_for_active_endpoint",
        lambda: (None, None, "cli:pid"),
    )
    result = json.loads(local_messaging_tool.run_tool({"action": "list"}))
    assert result["ok"] is False
    assert result["error"]["code"] == "LOCAL_MESSAGING_DISABLED"


def test_local_messaging_tool_rejects_unknown_peer(tmp_path, monkeypatch) -> None:
    store = LocalMessageStore(tmp_path / "messages.sqlite3")
    _register(store, "sender")
    monkeypatch.setattr(
        local_messaging_tool,
        "_store_for_active_endpoint",
        lambda: (
            SimpleNamespace(
                list_peers=lambda: store.list_peers(exclude_endpoint_id="sender")
            ),
            store,
            "sender",
        ),
    )
    result = json.loads(
        local_messaging_tool.run_tool(
            {"action": "send", "recipient": "not-a-peer", "message": "hello"}
        )
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_REQUEST"


def test_a2a_inbox_is_explicit_and_returns_untrusted_messages(
    tmp_path, monkeypatch
) -> None:
    from uagent.runtime import identity_context

    store = LocalMessageStore(tmp_path / "messages.sqlite3")
    _register(store, "sender")
    _register(store, "a2a")
    message_id = store.send_message("sender", "a2a", "hello from CLI")
    runtime = SimpleNamespace(entrypoint="a2a", endpoint_id="a2a", store=store)
    callbacks = SimpleNamespace(
        set_status=None, local_messaging_runtime_ref=lambda: runtime
    )
    monkeypatch.setattr(local_messaging_tool, "get_callbacks", lambda: callbacks)
    monkeypatch.setattr(
        local_messaging_tool,
        "_store_for_active_endpoint",
        lambda: (runtime, store, "a2a"),
    )
    monkeypatch.setattr(
        identity_context,
        "get_current_turn_context",
        lambda: SimpleNamespace(entry_point="a2a"),
    )

    result = json.loads(local_messaging_tool.run_tool({"action": "inbox"}))
    assert result["ok"] is True
    assert result["messages"][0]["message_id"] == message_id
    assert "---BEGIN_UAGENT_EXTERNAL_CONTENT---" in result["messages"][0]["message"]
    assert store.claim_messages("a2a") == []
    with store._connect() as connection:
        status = connection.execute(
            "SELECT status FROM messages WHERE message_id=?", (message_id,)
        ).fetchone()["status"]
    assert status == "accepted"


def test_non_a2a_inbox_action_is_rejected(tmp_path, monkeypatch) -> None:
    store = LocalMessageStore(tmp_path / "messages.sqlite3")
    runtime = SimpleNamespace(entrypoint="cli", endpoint_id="cli", store=store)
    callbacks = SimpleNamespace(
        set_status=None, local_messaging_runtime_ref=lambda: runtime
    )
    monkeypatch.setattr(local_messaging_tool, "get_callbacks", lambda: callbacks)
    monkeypatch.setattr(
        local_messaging_tool,
        "_store_for_active_endpoint",
        lambda: (runtime, store, "cli"),
    )

    result = json.loads(local_messaging_tool.run_tool({"action": "inbox"}))
    assert result["ok"] is False
    assert result["error"]["code"] == "INBOX_UNAVAILABLE"


def test_a2a_endpoint_requires_both_opt_in_settings(monkeypatch) -> None:
    from uagent.a2a.server import _a2a_local_messaging_enabled

    monkeypatch.setenv("UAGENT_LOCAL_MESSAGING", "on")
    monkeypatch.delenv("UAGENT_LOCAL_MESSAGING_A2A", raising=False)
    assert not _a2a_local_messaging_enabled()
    monkeypatch.setenv("UAGENT_LOCAL_MESSAGING_A2A", "on")
    assert _a2a_local_messaging_enabled()
    monkeypatch.setenv("UAGENT_LOCAL_MESSAGING", "off")
    assert not _a2a_local_messaging_enabled()


def test_cli_endpoint_natural_tool_list_and_send(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("UAGENT_LOCAL_MESSAGING", "on")
    core = SimpleNamespace(event_queue=queue.Queue(), base_dir=str(tmp_path / "stale"))
    monkeypatch.setattr(
        local_messaging_tool,
        "get_callbacks",
        lambda: SimpleNamespace(
            set_status=None,
            local_messaging_runtime_ref=lambda: getattr(
                core, "_local_messaging_runtime", None
            ),
        ),
    )

    runtime, peers = _start_cli_local_messaging(core)
    try:
        assert runtime.endpoint_id == current_endpoint_id("cli")
        assert runtime.store.active_endpoint(runtime.endpoint_id) is not None
        assert peers == []
        _register(
            runtime.store,
            "peer",
            workdir=str(tmp_path),
            purpose="peer task",
        )
        result = json.loads(
            local_messaging_tool.run_tool(
                {"action": "list", "purpose": "Implement peer status sharing"}
            )
        )
        assert result["ok"] is True, result
        assert [peer["endpoint_id"] for peer in result["peers"]] == ["peer"]
        assert result["work_status"]["purpose"] == "Implement peer status sharing"
        assert result["work_status"]["workdir"] == str(Path.cwd())
        assert str(tmp_path) in result["peers"][0]["workdir"]
        assert "peer task" in result["peers"][0]["purpose"]
        assert "---BEGIN_UAGENT_EXTERNAL_CONTENT---" in result["peers"][0]["purpose"]
        sent = json.loads(
            local_messaging_tool.run_tool(
                {"action": "send", "recipient": "peer", "message": "hello"}
            )
        )
        assert sent["ok"] is True
        assert sent["status"] == "pending"
        assert runtime.store.claim_messages("peer")[0]["body"] == "hello"
    finally:
        assert _stop_cli_local_messaging(core)
    assert not hasattr(core, "_local_messaging_runtime")


def test_incoming_messages_are_accepted_automatically(tmp_path) -> None:
    store = LocalMessageStore(tmp_path / "messages.sqlite3")
    _register(store, "peer")
    runtime = LocalMessageRuntime(queue.Queue(), store=store, poll_interval=0.05)
    runtime.start()
    core = SimpleNamespace(set_status=lambda *_args: None)
    try:
        # Every peer message becomes a user turn with no confirmation,
        # including the very first one from a new sender.
        for body in ("first", "second", "third"):
            message_id = store.send_message("peer", runtime.endpoint_id, body)
            claimed = store.claim_messages(runtime.endpoint_id)[0]
            assert claimed["message_id"] == message_id
            accepted = _accept_cli_local_message(core, runtime, claimed)
            assert accepted is not None
            assert accepted["kind"] == "user"
            assert accepted["src"] == "local_messaging"
            assert body in accepted["text"]
        # Sender approval state plays no role in acceptance.
        assert not runtime.is_sender_approved("peer")
    finally:
        runtime.stop()
