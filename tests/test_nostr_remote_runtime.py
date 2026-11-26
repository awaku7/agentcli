from __future__ import annotations

import asyncio
import json
import queue
import threading
import time
from types import SimpleNamespace

import pytest

from uagent.nostr_nip17 import (
    create_nip17_private_messages,
    unwrap_nip17_private_message,
)
from uagent.nostr_remote_dispatch import RemoteCLIRequestError
from uagent.nostr_remote_inbox import SQLiteNostrInboxStore
from uagent.nostr_remote_pairing import SQLitePairingStore
from uagent.nostr_remote_runtime import (
    NostrRemoteRuntime,
    dispatch_nostr_remote_inbox_event,
    start_nostr_remote_runtime,
    stop_nostr_remote_runtime,
)


def _secret(value: int) -> bytes:
    return value.to_bytes(32, "big")


def _setup_request(tmp_path, text: str = "hello"):
    sender_key = _secret(1)
    recipient_key = _secret(2)
    now = int(time.time())
    wrap = create_nip17_private_messages(
        text, sender_key, _public_key_bytes(recipient_key), now=now
    )[0]
    rumor = unwrap_nip17_private_message(wrap, recipient_key)
    inbox = SQLiteNostrInboxStore(tmp_path / "inbox.sqlite3")
    pairings = SQLitePairingStore(tmp_path / "pairings.sqlite3")
    pairings.pair(rumor["pubkey"], "phone", approved=True, paired_at=now)
    inbox.enqueue_verified_wrap(
        rumor["pubkey"],
        rumor["id"],
        wrap,
        created_at=rumor["created_at"],
        received_at=now,
        session_id="active-session",
    )
    event = {
        "kind": "nostr_remote_request",
        "sender_pubkey": rumor["pubkey"],
        "rumor_id": rumor["id"],
        "created_at": rumor["created_at"],
        "session_id": "active-session",
        "text": text,
    }
    return inbox, pairings, recipient_key, event


def _public_key_bytes(secret: bytes) -> bytes:
    from uagent.nostr_nip17 import _public_key_x

    return _public_key_x(secret)


def test_durable_dispatch_stays_claimed_until_foreground_finishes(tmp_path) -> None:
    inbox, pairings, private_key, event = _setup_request(tmp_path)
    try:
        runtime = NostrRemoteRuntime(
            event_queue=queue.Queue(),
            private_key=private_key,
            relays=["wss://relay.example.org"],
            session_id="active-session",
            inbox_store=inbox,
            pairing_store=pairings,
        )
        action = runtime.dispatch_event(event, current_session_id="active-session")
        assert action.kind == "user"
        assert action.text == "hello"
        record = inbox.get(event["sender_pubkey"], event["rumor_id"])
        assert record is not None
        assert record.status == "dispatching"
        assert record.wrapped_event is not None
        assert runtime.finish_event(event, "completed")
        record = inbox.get(event["sender_pubkey"], event["rumor_id"])
        assert record is not None
        assert record.status == "completed"
        assert record.wrapped_event is None

        with pytest.raises(RemoteCLIRequestError, match="already claimed"):
            dispatch_nostr_remote_inbox_event(
                event,
                inbox_store=inbox,
                pairing_store=pairings,
                private_key=private_key,
                current_session_id="active-session",
            )
    finally:
        inbox.close()
        pairings.close()


def test_durable_dispatch_rejects_revoked_sender_and_finishes_tombstone(
    tmp_path,
) -> None:
    inbox, pairings, private_key, event = _setup_request(tmp_path)
    try:
        assert pairings.revoke(event["sender_pubkey"])
        with pytest.raises(RemoteCLIRequestError, match="not paired"):
            dispatch_nostr_remote_inbox_event(
                event,
                inbox_store=inbox,
                pairing_store=pairings,
                private_key=private_key,
                current_session_id="active-session",
            )
        record = inbox.get(event["sender_pubkey"], event["rumor_id"])
        assert record is not None
        assert record.status == "rejected"
        assert record.wrapped_event is None
    finally:
        inbox.close()
        pairings.close()


def test_durable_dispatch_rejects_queue_ciphertext_mismatch(tmp_path) -> None:
    inbox, pairings, private_key, event = _setup_request(tmp_path)
    try:
        event["text"] = "altered message"
        with pytest.raises(RemoteCLIRequestError, match="does not match"):
            dispatch_nostr_remote_inbox_event(
                event,
                inbox_store=inbox,
                pairing_store=pairings,
                private_key=private_key,
                current_session_id="active-session",
            )
        record = inbox.get(event["sender_pubkey"], event["rumor_id"])
        assert record is not None
        assert record.status == "rejected"
    finally:
        inbox.close()
        pairings.close()


def test_runtime_recovery_and_dispatch_are_scoped_to_session(
    tmp_path, monkeypatch
) -> None:
    import uagent.nostr_remote_runtime as runtime_module

    async def wait_for_stop(_relay, _key, _callback, *, stop_event, **_kwargs):
        await stop_event.wait()

    monkeypatch.setattr(runtime_module, "listen_nip17_messages", wait_for_stop)
    inbox, pairings, private_key, session_a_event = _setup_request(tmp_path)
    sender_key = _secret(1)
    other_wrap = create_nip17_private_messages(
        "session B request", sender_key, _public_key_bytes(private_key)
    )[0]
    other_rumor = unwrap_nip17_private_message(other_wrap, private_key)
    inbox.enqueue_verified_wrap(
        other_rumor["pubkey"],
        other_rumor["id"],
        other_wrap,
        created_at=other_rumor["created_at"],
        session_id="session-b",
    )
    runtime = NostrRemoteRuntime(
        event_queue=queue.Queue(),
        private_key=private_key,
        relays=["wss://relay.example.org"],
        session_id="session-b",
        inbox_store=inbox,
        pairing_store=pairings,
    )
    try:
        with pytest.raises(RemoteCLIRequestError, match="different CLI session"):
            runtime.dispatch_event(session_a_event, current_session_id="session-b")
        session_a_record = inbox.get(
            session_a_event["sender_pubkey"], session_a_event["rumor_id"]
        )
        assert session_a_record is not None
        assert session_a_record.status == "pending"

        runtime.start()
        recovered = runtime.event_queue.get_nowait()
        assert recovered["rumor_id"] == other_rumor["id"]
        assert recovered["session_id"] == "session-b"
        assert runtime.event_queue.empty()
        assert inbox.list_pending(session_id="active-session")
    finally:
        runtime.stop()


def test_listener_runtime_stops_cleanly(tmp_path, monkeypatch) -> None:
    import uagent.nostr_remote_runtime as runtime_module

    async def wait_for_stop(_relay, _key, _callback, *, stop_event, **_kwargs):
        await stop_event.wait()

    monkeypatch.setattr(runtime_module, "listen_nip17_messages", wait_for_stop)
    monkeypatch.setattr("uagent.utils.paths.get_dbs_dir", lambda: tmp_path / "db")
    core = SimpleNamespace(event_queue=queue.Queue(), session_id="active-session")
    runtime = start_nostr_remote_runtime(
        core,
        private_key=_secret(2),
        relays=["wss://relay.example.org"],
    )
    try:
        assert runtime.status()["state"] == "running"
        assert callable(core._nostr_remote_authorize_sender)
        assert stop_nostr_remote_runtime(core)["stopped"]
        assert runtime.status()["state"] == "stopped"
        assert not hasattr(core, "_nostr_remote_runtime")
    finally:
        if not runtime._closed:
            stop_nostr_remote_runtime(core)


def test_pairing_prompt_restores_idle_status_after_an_answer(
    tmp_path, monkeypatch
) -> None:
    import uagent.nostr_remote_runtime as runtime_module

    async def wait_for_stop(_relay, _key, _callback, *, stop_event, **_kwargs):
        await stop_event.wait()

    monkeypatch.setattr(runtime_module, "listen_nip17_messages", wait_for_stop)
    monkeypatch.setattr("uagent.utils.paths.get_dbs_dir", lambda: tmp_path / "db")
    core = SimpleNamespace(
        event_queue=queue.Queue(),
        session_id="active-session",
        human_ask_lock=threading.Lock(),
        human_ask_active=False,
        human_ask_queue=None,
        human_ask_message="",
        human_ask_prompt="",
        human_ask_multiline_active=False,
        human_ask_lines=[],
        status_busy=False,
        status_label="",
    )

    def _set_status(busy, label=""):
        core.status_busy = busy
        core.status_label = label if busy else ""

    core.set_status = _set_status
    runtime = start_nostr_remote_runtime(
        core, private_key=_secret(2), relays=["wss://relay.example.org"]
    )
    try:
        answers: list[str | None] = []
        thread = threading.Thread(
            target=lambda: answers.append(runtime._pairing_asker("npub1example"))
        )
        thread.start()
        deadline = time.time() + 5
        while not core.human_ask_active and time.time() < deadline:
            time.sleep(0.01)
        assert core.human_ask_active
        # The reply path marks the CLI busy before delivering the answer.
        core.set_status(True, "replying")
        core.human_ask_queue.put("no")
        thread.join(timeout=5)
        assert answers == ["no"]
        # No turn follows a refusal, so the prompt itself restored idle.
        assert core.status_busy is False
    finally:
        if not runtime._closed:
            stop_nostr_remote_runtime(core)


def test_listener_runtime_retries_failed_relay_independently(
    tmp_path, monkeypatch
) -> None:
    import asyncio
    import uagent.nostr_remote_runtime as runtime_module

    calls: dict[str, int] = {}

    async def flaky_listener(relay, _key, _callback, *, stop_event, **_kwargs):
        calls[relay] = calls.get(relay, 0) + 1
        if relay == "wss://broken.example.org" and calls[relay] == 1:
            raise RuntimeError("temporary relay failure")
        if relay == "wss://broken.example.org":
            stop_event.set()
        await stop_event.wait()

    monkeypatch.setattr(runtime_module, "listen_nip17_messages", flaky_listener)
    monkeypatch.setattr("uagent.utils.paths.get_dbs_dir", lambda: tmp_path / "db")
    inbox = SQLiteNostrInboxStore(tmp_path / "retry-inbox.sqlite3")
    pairings = SQLitePairingStore(tmp_path / "retry-pairings.sqlite3")
    runtime = NostrRemoteRuntime(
        event_queue=queue.Queue(),
        private_key=_secret(2),
        relays=["wss://broken.example.org", "wss://healthy.example.org"],
        session_id="active-session",
        inbox_store=inbox,
        pairing_store=pairings,
    )
    try:
        asyncio.run(runtime._listen())
        assert calls["wss://broken.example.org"] == 2
        assert calls["wss://healthy.example.org"] == 1
        assert "temporary relay failure" in runtime._error
    finally:
        inbox.close()
        pairings.close()


def test_invalid_rumor_is_queued_by_reference_without_plaintext(tmp_path) -> None:
    event_queue = queue.Queue()
    inbox = SQLiteNostrInboxStore(tmp_path / "invalid-rumor-inbox.sqlite3")
    pairings = SQLitePairingStore(tmp_path / "invalid-rumor-pairings.sqlite3")
    runtime = NostrRemoteRuntime(
        event_queue=event_queue,
        private_key=_secret(2),
        relays=["wss://relay.example.org"],
        session_id="active-session",
        inbox_store=inbox,
        pairing_store=pairings,
    )
    try:
        runtime._queue_rumor(
            {
                "kind": 14,
                "pubkey": "ab" * 32,
                "id": "cd" * 32,
                "created_at": int(time.time()),
                "content": "",
            }
        )
        queued = event_queue.get_nowait()
        assert queued["kind"] == "nostr_remote_request"
        assert queued["text"] == ""
    finally:
        inbox.close()
        pairings.close()


def test_receive_diagnostics_track_connections_and_drop_counts_in_memory(
    tmp_path,
) -> None:
    inbox = SQLiteNostrInboxStore(tmp_path / "diagnostics-inbox.sqlite3")
    pairings = SQLitePairingStore(tmp_path / "diagnostics-pairings.sqlite3")
    relay = "wss://relay.example.org"
    runtime = NostrRemoteRuntime(
        event_queue=queue.Queue(),
        private_key=_secret(2),
        relays=[relay],
        session_id="active-session",
        inbox_store=inbox,
        pairing_store=pairings,
    )
    try:
        runtime._record_receive_diagnostic(relay, "connected")
        runtime._record_receive_diagnostic(relay, "gift_wraps")
        runtime._record_receive_diagnostic(relay, "unauthorized")
        runtime._record_receive_diagnostic(relay, "queued")
        status = runtime.status()
        diagnostics = status["diagnostics"]
        assert diagnostics["connected_relays"] == 1
        assert diagnostics["gift_wraps"] == 1
        assert diagnostics["unauthorized"] == 1
        assert diagnostics["queued"] == 1
        assert diagnostics["decrypt_failed"] == 0
        assert set(diagnostics) == {
            "connected_relays",
            "gift_wraps",
            "invalid",
            "decrypt_failed",
            "unauthorized",
            "stale",
            "duplicate",
            "inbox_rejected",
            "queued",
            "delivery_rejections",
            "delivery_readback",
            "last_unwrap_error",
            "own_relay_list_accepted",
        }
        assert diagnostics["delivery_rejections"] == []
        assert diagnostics["delivery_readback"] == []
        assert diagnostics["last_unwrap_error"] == ""
        assert diagnostics["own_relay_list_accepted"] == 0
        runtime._record_receive_diagnostic(
            relay, "unwrap_error:gift wrap is not addressed to this recipient"
        )
        assert (
            runtime.status()["diagnostics"]["last_unwrap_error"]
            == "gift wrap is not addressed to this recipient"
        )
        runtime._record_receive_diagnostic(relay, "disconnected")
        assert runtime.status()["diagnostics"]["connected_relays"] == 0
    finally:
        inbox.close()
        pairings.close()


def test_publish_own_relay_list_counts_accepting_relays(tmp_path, monkeypatch) -> None:
    import asyncio

    import uagent.nostr_remote_transport as transport
    from uagent.nostr_nip17 import _public_key_x

    inbox = SQLiteNostrInboxStore(tmp_path / "relay-list-inbox.sqlite3")
    pairings = SQLitePairingStore(tmp_path / "relay-list-pairings.sqlite3")
    relays = ["wss://relay-a.example", "wss://relay-b.example"]
    runtime = NostrRemoteRuntime(
        event_queue=queue.Queue(),
        private_key=_secret(2),
        relays=relays,
        session_id="active-session",
        inbox_store=inbox,
        pairing_store=pairings,
    )
    calls: list[tuple[str, dict]] = []

    async def fake_publish(relay_url, event, _key, *, allowed_relay_urls):
        calls.append((relay_url, event))
        return SimpleNamespace(
            accepted=relay_url == "wss://relay-a.example",
            relay_url=relay_url,
            event_id=event["id"],
            message="",
        )

    monkeypatch.setattr(transport, "publish_relay_list_event", fake_publish)
    try:
        asyncio.run(runtime._publish_own_relay_list())  # noqa: SLF001
        assert [relay for relay, _event in calls] == relays
        event = calls[0][1]
        assert event["kind"] == 10050
        assert event["pubkey"] == _public_key_x(_secret(2)).hex()
        assert event["tags"] == [["relay", relay] for relay in relays]
        assert runtime.status()["diagnostics"]["own_relay_list_accepted"] == 1
    finally:
        inbox.close()
        pairings.close()


def test_authenticated_incoming_message_is_echoed_once(tmp_path) -> None:
    from uagent.nostr_remote_runtime import _display_nostr_incoming

    inbox, pairings, private_key, request = _setup_request(
        tmp_path, text="hello from 0xChat"
    )
    event_queue = queue.Queue()
    core = SimpleNamespace(prompt_needs_redraw=False)
    seen: list[dict] = []
    runtime = NostrRemoteRuntime(
        event_queue=event_queue,
        private_key=private_key,
        relays=["wss://relay.example.org"],
        session_id="active-session",
        inbox_store=inbox,
        pairing_store=pairings,
        incoming_message_display=lambda rumor: (
            seen.append(rumor),
            _display_nostr_incoming(core, rumor),
        ),
    )
    try:
        sender = request["sender_pubkey"]
        rumor = {
            "kind": 14,
            "pubkey": sender,
            "id": request["rumor_id"],
            "created_at": request["created_at"],
            "content": request["text"],
        }
        runtime._queue_rumor(rumor)
        assert event_queue.get_nowait()["text"] == "hello from 0xChat"
        assert len(seen) == 1
        assert core.prompt_needs_redraw is True

        # An invalid/empty command must never be printed to the terminal.
        runtime._queue_rumor({**rumor, "content": ""})
        assert len(seen) == 1
    finally:
        inbox.close()
        pairings.close()


def test_remote_cli_echo_stops_spinner_before_serialized_output(
    monkeypatch, capsys
) -> None:
    from uagent.nostr_remote_runtime import _display_nostr_incoming
    from uagent.runtime import spinner

    actions: list[str] = []

    class RecordingLock:
        def __enter__(self):
            actions.append("lock")
            return self

        def __exit__(self, *_args):
            actions.append("unlock")

    monkeypatch.setattr(spinner, "is_running", lambda: False)
    monkeypatch.setattr(spinner, "stop_quietly", lambda: actions.append("stop_spinner"))
    core = SimpleNamespace(
        print_lock=RecordingLock(),
        _stream_line_open=True,
        _reasoning_stream_open=True,
        _prompt_line_open=True,
        _cli_prompt_toolkit_active=False,
        prompt_needs_redraw=False,
    )

    _display_nostr_incoming(core, {"pubkey": "ab" * 32, "content": "hello from Nostr"})

    assert actions == ["stop_spinner", "lock", "unlock"]
    assert capsys.readouterr().out == (
        "\n[NOSTR] Received from abababababab: hello from Nostr\n"
    )
    assert core._stream_line_open is False
    assert core._reasoning_stream_open is False
    assert core._prompt_line_open is False
    assert core.prompt_needs_redraw is True


@pytest.mark.parametrize(
    ("busy", "stream_open", "expected_resume"),
    [(True, False, True), (False, False, False), (True, True, False)],
)
def test_remote_cli_echo_restores_only_active_busy_spinner(
    monkeypatch, capsys, busy, stream_open, expected_resume
) -> None:
    from uagent.nostr_remote_runtime import _display_nostr_incoming
    from uagent.runtime import spinner

    actions: list[str] = []

    class RecordingLock:
        def __enter__(self):
            actions.append("lock")
            return self

        def __exit__(self, *_args):
            actions.append("unlock")

    monkeypatch.setattr(spinner, "is_running", lambda: True)
    monkeypatch.setattr(spinner, "stop_quietly", lambda: actions.append("stop"))
    monkeypatch.setattr(spinner, "start", lambda: actions.append("start"))
    core = SimpleNamespace(
        print_lock=RecordingLock(),
        status_busy=busy,
        _stream_line_open=stream_open,
        _reasoning_stream_open=False,
        _prompt_line_open=False,
        _cli_prompt_toolkit_active=False,
        prompt_needs_redraw=False,
    )
    _display_nostr_incoming(core, {"pubkey": "ab" * 32, "content": "hello"})
    capsys.readouterr()

    assert actions == [
        "stop",
        "lock",
        "unlock",
        *(["start"] if expected_resume else []),
    ]


def test_remote_cli_echo_falls_back_to_direct_print_without_prompt_app(
    monkeypatch, capsys
) -> None:
    from uagent.nostr_remote_runtime import _display_nostr_incoming
    from uagent.runtime import spinner

    monkeypatch.setattr(spinner, "is_running", lambda: False)
    monkeypatch.setattr(spinner, "stop_quietly", lambda: None)
    core = SimpleNamespace(
        _cli_prompt_toolkit_active=True,
        _prompt_line_open=True,
        prompt_needs_redraw=False,
    )

    _display_nostr_incoming(core, {"pubkey": "ab" * 32, "content": "hello"})

    assert "[NOSTR] Received from abababababab: hello" in capsys.readouterr().out
    assert core._prompt_line_open is True
    assert core.prompt_needs_redraw is False


def test_remote_cli_echo_prints_above_an_open_toolkit_prompt(
    monkeypatch, capsys
) -> None:
    import io
    import threading

    pytest.importorskip("prompt_toolkit")
    from prompt_toolkit import PromptSession
    from prompt_toolkit.data_structures import Size
    from prompt_toolkit.input.defaults import create_pipe_input
    from prompt_toolkit.output.vt100 import Vt100_Output

    from uagent.nostr_remote_runtime import _display_nostr_incoming
    from uagent.runtime import spinner

    monkeypatch.setattr(spinner, "is_running", lambda: False)
    monkeypatch.setattr(spinner, "stop_quietly", lambda: None)

    term_out = io.StringIO()
    output = Vt100_Output(term_out, lambda: Size(columns=80, rows=24))
    # Keep the context manager alive: dropping it closes the pipe and the
    # prompt reads EOF immediately.
    pipe_cm = create_pipe_input()
    pipe_input = pipe_cm.__enter__()
    session = PromptSession(input=pipe_input, output=output)
    result: dict = {}

    def _run() -> None:
        try:
            result["text"] = session.prompt("User> ")
        except Exception as exc:  # noqa: BLE001 - surfaced by assertions
            result["error"] = exc

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    try:
        deadline = time.time() + 5
        while time.time() < deadline:
            app = session.app
            if app is not None and app.is_running and "User>" in term_out.getvalue():
                break
            time.sleep(0.02)
        else:
            raise AssertionError("toolkit prompt did not start")
        pipe_input.send_text("draft")
        deadline = time.time() + 5
        while "draft" not in term_out.getvalue() and time.time() < deadline:
            time.sleep(0.02)

        core = SimpleNamespace(
            print_lock=threading.RLock(),
            _stream_line_open=False,
            _reasoning_stream_open=False,
            _prompt_line_open=True,
            _cli_prompt_toolkit_active=True,
            _cli_prompt_app=session.app,
            prompt_needs_redraw=False,
        )
        mark = len(term_out.getvalue())
        _display_nostr_incoming(core, {"pubkey": "ab" * 32, "content": "hello"})

        # The notice was printed (above the prompt), not written into the
        # line being edited.
        assert "[NOSTR] Received from abababababab: hello" in capsys.readouterr().out
        # The prompt redraws below the notice with the edit buffer intact,
        # and still owns the line afterwards.
        deadline = time.time() + 5
        redrawn = ""
        while time.time() < deadline:
            redrawn = term_out.getvalue()[mark:]
            if "User>" in redrawn and "draft" in redrawn:
                break
            time.sleep(0.02)
        assert "User>" in redrawn
        assert "draft" in redrawn
        assert core._prompt_line_open is True
        assert core.prompt_needs_redraw is False

        pipe_input.send_text("\r")
        thread.join(timeout=5)
        assert result.get("text") == "draft"
    finally:
        pipe_input.close()


def test_remote_cli_echo_escapes_terminal_controls(capsys) -> None:
    from uagent.nostr_remote_runtime import _display_nostr_incoming

    core = SimpleNamespace(prompt_needs_redraw=False)
    _display_nostr_incoming(
        core,
        {"pubkey": "ab" * 32, "content": "hello\n\x1b[31mRED\x1b[0m"},
    )
    printed = capsys.readouterr().out
    assert "[NOSTR] Received from abababababab: hello" in printed
    assert "RED" in printed
    assert "\x1b" not in printed
    assert "hello\n" not in printed
    assert core.prompt_needs_redraw is True


def _make_runtime(tmp_path, *, ask_state_provider=None, pairing_asker=None):
    inbox, pairings, private_key, event = _setup_request(tmp_path)
    runtime = NostrRemoteRuntime(
        event_queue=queue.Queue(),
        private_key=private_key,
        relays=["wss://relay.example.org"],
        session_id="active-session",
        inbox_store=inbox,
        pairing_store=pairings,
        ask_state_provider=ask_state_provider,
        pairing_asker=pairing_asker,
    )
    return inbox, pairings, private_key, event, runtime


def test_progress_notes_queue_tool_and_reasoning_in_order(tmp_path) -> None:
    inbox, pairings, _key, event, runtime = _make_runtime(tmp_path)
    try:
        runtime.dispatch_event(event, current_session_id="active-session")
        runtime.note_reasoning("thinking about it")
        runtime.note_tool_action("shell", "About to use shell: ls")
        runtime.note_tool_action("shell", "About to use shell: pwd")  # dup name
        runtime.note_tool_action("read_file", "About to use read_file: a.txt")
        runtime.note_reasoning("x" * 700)  # crosses the flush threshold

        queued = []
        while not runtime._progress_queue.empty():
            queued.append(runtime._progress_queue.get_nowait()[1])
        assert queued == [
            "💭 thinking about it",
            "🔧 About to use shell: ls",
            "🔧 About to use read_file: a.txt",
            "💭 " + "x" * 700,
        ]

        assert runtime.finish_event(event, "completed")
        runtime.note_tool_action("shell", "About to use shell: ls")  # no request
        assert runtime._progress_queue.empty()
    finally:
        inbox.close()
        pairings.close()


def test_progress_notes_forward_tool_action_sentences(tmp_path) -> None:
    inbox, pairings, _key, event, runtime = _make_runtime(tmp_path)
    try:
        runtime.dispatch_event(event, current_session_id="active-session")
        # The dispatcher hands over the tool's localized action sentence
        # (describer text with argument summary), one note per tool start.
        runtime.note_tool_action(
            "get_weather_wttr", 'get_weather_wttr を実行します: city="東京"'
        )
        runtime.note_tool_action(
            "get_current_location", "get_current_location を実行します"
        )
        runtime.note_tool_action("get_weather_wttr", "get_weather_wttr を実行します")

        queued = []
        while not runtime._progress_queue.empty():
            queued.append(runtime._progress_queue.get_nowait()[1])
        assert queued == [
            '🔧 get_weather_wttr を実行します: city="東京"',
            "🔧 get_current_location を実行します",
            "🔧 get_weather_wttr を実行します",
        ]
        assert runtime.finish_event(event, "completed")
    finally:
        inbox.close()
        pairings.close()


def test_progress_drain_wait_is_bounded_and_clears_on_publish(tmp_path) -> None:
    import asyncio

    inbox, pairings, _key, event, runtime = _make_runtime(tmp_path)
    try:
        runtime.dispatch_event(event, current_session_id="active-session")
        runtime.note_tool_action("shell", "About to use shell: ls")
        key = runtime._progress_key(event)
        assert runtime._progress_pending.get(key) == 1

        # Progress sender not running: the wait is skipped, never a stall.
        started = time.monotonic()
        runtime._wait_for_progress_drain(event, timeout=5.0)
        assert time.monotonic() - started < 1.0

        # Sender running but not draining: the wait is bounded by timeout.
        runtime._stop_event = asyncio.Event()
        started = time.monotonic()
        runtime._wait_for_progress_drain(event, timeout=0.3)
        assert time.monotonic() - started >= 0.25
        assert runtime._progress_pending.get(key) == 1

        # Once the note is published, the wait returns at once.
        item = runtime._progress_queue.get_nowait()
        runtime._note_progress_published(item[0])
        started = time.monotonic()
        runtime._wait_for_progress_drain(event, timeout=5.0)
        assert time.monotonic() - started < 1.0
    finally:
        inbox.close()
        pairings.close()


def test_reply_waits_for_queued_progress_notes(tmp_path, monkeypatch) -> None:
    import asyncio
    import threading

    import uagent.nostr_remote_transport as transport
    from uagent.nostr_remote_outbox import SQLiteNostrOutboxStore

    inbox, pairings, _key, event, runtime = _make_runtime(tmp_path)
    runtime.outbox_store = SQLiteNostrOutboxStore(
        tmp_path / "progress-order-outbox.sqlite3"
    )
    order: list[str] = []

    async def fake_fetch(pubkey, lookup_relays, *, allowed_relay_urls, **_kwargs):
        return ["wss://relay.example.org"]

    async def fake_publish(
        events,
        relay_lists_by_pubkey,
        auth_private_key,
        *,
        allowed_relay_urls,
        **_kwargs,
    ):
        order.append("reply")
        return [SimpleNamespace(event_id=e["id"], accepted=True) for e in events]

    monkeypatch.setattr(transport, "fetch_nip17_relay_list", fake_fetch)
    monkeypatch.setattr(transport, "publish_nip17_gift_wraps", fake_publish)

    async def slow_progress_publish(request, text):
        await asyncio.sleep(0.3)
        order.append("note")
        return True

    runtime._publish_progress_text = slow_progress_publish
    runtime._stop_event = asyncio.Event()

    def run_sender() -> None:
        async def main() -> None:
            try:
                await asyncio.wait_for(runtime._progress_sender(), timeout=3.0)
            except asyncio.TimeoutError:
                pass

        asyncio.run(main())

    sender = threading.Thread(target=run_sender, daemon=True)
    try:
        runtime.dispatch_event(event, current_session_id="active-session")
        sender.start()
        runtime.note_reasoning("final thoughts")
        # CLI order at turn end: finish (which flushes the buffered
        # reasoning into the progress queue), then send the reply. The
        # reply must not overtake the still-queued reasoning note.
        assert runtime.finish_event(event, "completed")
        result = runtime.send_reply(event, "the answer")
        assert result["ok"] is True
        assert order == ["note", "reply"]
    finally:
        sender.join(timeout=4.0)
        inbox.close()
        pairings.close()


def test_progress_publish_wraps_for_the_requester(tmp_path, monkeypatch) -> None:
    import asyncio

    import uagent.nostr_remote_transport as transport

    inbox, pairings, _key, event, runtime = _make_runtime(tmp_path)
    published = {}

    async def fake_fetch(pubkey, relays, **kwargs):
        return ["wss://relay.example.org"]

    async def fake_publish(events, relay_lists, private_key, **kwargs):
        published["events"] = events
        published["relay_lists"] = relay_lists
        return []

    monkeypatch.setattr(transport, "fetch_nip17_relay_list", fake_fetch)
    monkeypatch.setattr(transport, "publish_nip17_gift_wraps", fake_publish)
    try:
        asyncio.run(runtime._publish_progress_text(event, "🔧 shell"))
        sender_private = _secret(1)
        received = unwrap_nip17_private_message(published["events"][0], sender_private)
        assert received["content"] == "🔧 shell"
        assert published["relay_lists"][event["sender_pubkey"]] == [
            "wss://relay.example.org"
        ]
    finally:
        inbox.close()
        pairings.close()


def test_ask_question_forwarded_and_answer_routed_to_ask_queue(
    tmp_path,
) -> None:
    ask_queue: queue.Queue = queue.Queue()
    state = {
        "active": True,
        "is_password": False,
        "message": "proceed?",
        "queue": ask_queue,
    }
    inbox, pairings, recipient_key, event, runtime = _make_runtime(
        tmp_path, ask_state_provider=lambda: dict(state)
    )
    try:
        runtime.dispatch_event(event, current_session_id="active-session")
        runtime._forward_pending_ask_once()
        runtime._forward_pending_ask_once()  # same ask: queued only once
        assert runtime._question_queue.qsize() == 1
        assert runtime._question_queue.get_nowait()[1] == "❓ proceed?"
        # Answer routing arms only once the question is actually delivered.
        runtime._note_question_result(ask_queue, True)

        # The requester's next DM is the answer, not a new request.
        sender_key = _secret(1)
        now = int(time.time())
        wrap = create_nip17_private_messages(
            "yes", sender_key, _public_key_bytes(recipient_key), now=now
        )[0]
        rumor = unwrap_nip17_private_message(wrap, recipient_key)
        inbox.enqueue_verified_wrap(
            rumor["pubkey"],
            rumor["id"],
            wrap,
            created_at=rumor["created_at"],
            received_at=now,
            session_id="active-session",
        )
        runtime._queue_rumor(rumor)
        assert ask_queue.get_nowait() == "yes"
        assert runtime.event_queue.empty()
        record = inbox.get(rumor["pubkey"], rumor["id"])
        assert record is not None and record.status == "completed"
    finally:
        inbox.close()
        pairings.close()


def test_ask_answer_from_a_revoked_device_is_not_consumed(tmp_path) -> None:
    ask_queue: queue.Queue = queue.Queue()
    state = {
        "active": True,
        "is_password": False,
        "message": "proceed?",
        "queue": ask_queue,
    }
    inbox, pairings, recipient_key, event, runtime = _make_runtime(
        tmp_path, ask_state_provider=lambda: dict(state)
    )
    try:
        runtime.dispatch_event(event, current_session_id="active-session")
        runtime._forward_pending_ask_once()
        runtime._note_question_result(ask_queue, True)
        # The device is revoked while the question is outstanding.
        assert pairings.revoke(event["sender_pubkey"])

        sender_key = _secret(1)
        now = int(time.time())
        wrap = create_nip17_private_messages(
            "yes", sender_key, _public_key_bytes(recipient_key), now=now
        )[0]
        rumor = unwrap_nip17_private_message(wrap, recipient_key)
        inbox.enqueue_verified_wrap(
            rumor["pubkey"],
            rumor["id"],
            wrap,
            created_at=rumor["created_at"],
            received_at=now,
            session_id="active-session",
        )
        runtime._queue_rumor(rumor)
        # The revoked device's DM is not consumed as the ask answer;
        # it keeps its normal routing as a fresh request event.
        assert ask_queue.empty()
        queued_event = runtime.event_queue.get_nowait()
        assert queued_event["rumor_id"] == rumor["id"]
        record = inbox.get(rumor["pubkey"], rumor["id"])
        assert record is not None and record.status == "pending"
    finally:
        inbox.close()
        pairings.close()


def test_ask_password_is_never_forwarded_or_routed(tmp_path) -> None:
    ask_queue: queue.Queue = queue.Queue()
    state = {
        "active": True,
        "is_password": True,
        "message": "password?",
        "queue": ask_queue,
    }
    inbox, pairings, recipient_key, event, runtime = _make_runtime(
        tmp_path, ask_state_provider=lambda: dict(state)
    )
    try:
        runtime.dispatch_event(event, current_session_id="active-session")
        runtime._forward_pending_ask_once()
        assert runtime._question_queue.empty()

        sender_key = _secret(1)
        now = int(time.time())
        wrap = create_nip17_private_messages(
            "hello again", sender_key, _public_key_bytes(recipient_key), now=now
        )[0]
        rumor = unwrap_nip17_private_message(wrap, recipient_key)
        inbox.enqueue_verified_wrap(
            rumor["pubkey"],
            rumor["id"],
            wrap,
            created_at=rumor["created_at"],
            received_at=now,
            session_id="active-session",
        )
        runtime._queue_rumor(rumor)
        assert ask_queue.empty()
        queued_event = runtime.event_queue.get_nowait()
        assert queued_event["text"] == "hello again"
    finally:
        inbox.close()
        pairings.close()


def test_status_dispatch_does_not_take_over_active_request(tmp_path) -> None:
    inbox, pairings, _key, event, runtime = _make_runtime(tmp_path)
    try:
        runtime.dispatch_event(event, current_session_id="active-session")

        # A status query dispatched by the side worker mid-turn must not
        # replace (or, on finish, clear) the turn's active request.
        sender_key = _secret(1)
        recipient_key = _secret(2)
        now = int(time.time())
        wrap = create_nip17_private_messages(
            "/uag status",
            sender_key,
            _public_key_bytes(recipient_key),
            now=now,
        )[0]
        rumor = unwrap_nip17_private_message(wrap, recipient_key)
        inbox.enqueue_verified_wrap(
            rumor["pubkey"],
            rumor["id"],
            wrap,
            created_at=rumor["created_at"],
            received_at=now,
            session_id="active-session",
        )
        status_event = {
            "kind": "nostr_remote_request",
            "sender_pubkey": rumor["pubkey"],
            "rumor_id": rumor["id"],
            "created_at": rumor["created_at"],
            "session_id": "active-session",
            "text": "/uag status",
        }
        action = runtime.dispatch_event(
            status_event, current_session_id="active-session"
        )
        assert action.kind == "status"
        assert runtime.finish_event(status_event, "completed")

        runtime.note_tool_action("shell", "About to use shell: ls")
        queued = runtime._progress_queue.get_nowait()
        assert queued[0] is event
        assert queued[1] == "🔧 About to use shell: ls"

        assert runtime.finish_event(event, "completed")
        runtime.note_tool_action("read_file", "About to use read_file: a.txt")
        assert runtime._progress_queue.empty()
    finally:
        inbox.close()
        pairings.close()


def test_ask_question_retried_until_delivered(tmp_path) -> None:
    ask_queue: queue.Queue = queue.Queue()
    state = {
        "active": True,
        "is_password": False,
        "message": "proceed?",
        "queue": ask_queue,
    }
    inbox, pairings, recipient_key, event, runtime = _make_runtime(
        tmp_path, ask_state_provider=lambda: dict(state)
    )
    try:
        runtime.dispatch_event(event, current_session_id="active-session")
        runtime._forward_pending_ask_once()
        assert runtime._question_queue.qsize() == 1
        runtime._question_queue.get_nowait()

        # Not yet delivered: a DM from the requester is a new request,
        # not an answer to a question they never saw.
        sender_key = _secret(1)
        now = int(time.time())
        wrap = create_nip17_private_messages(
            "fresh request", sender_key, _public_key_bytes(recipient_key), now=now
        )[0]
        rumor = unwrap_nip17_private_message(wrap, recipient_key)
        inbox.enqueue_verified_wrap(
            rumor["pubkey"],
            rumor["id"],
            wrap,
            created_at=rumor["created_at"],
            received_at=now,
            session_id="active-session",
        )
        runtime._queue_rumor(rumor)
        assert ask_queue.empty()
        assert runtime.event_queue.get_nowait()["text"] == "fresh request"

        # A failed delivery is retried by the next watcher pass; a
        # successful one stops the offers.
        runtime._note_question_result(ask_queue, False)
        runtime._forward_pending_ask_once()
        assert runtime._question_queue.qsize() == 1
        runtime._question_queue.get_nowait()
        runtime._note_question_result(ask_queue, True)
        runtime._forward_pending_ask_once()
        assert runtime._question_queue.empty()
    finally:
        inbox.close()
        pairings.close()


def test_progress_publish_stops_when_pairing_revoked(tmp_path, monkeypatch) -> None:
    import asyncio

    import uagent.nostr_remote_transport as transport

    inbox, pairings, _key, event, runtime = _make_runtime(tmp_path)
    published = []

    async def fake_fetch(pubkey, relays, **kwargs):
        return ["wss://relay.example.org"]

    async def fake_publish(events, relay_lists, private_key, **kwargs):
        published.append(events)
        return [
            transport.RelayDelivery(
                relay_url="wss://relay.example.org",
                event_id=events[0]["id"],
                accepted=True,
            )
        ]

    monkeypatch.setattr(transport, "fetch_nip17_relay_list", fake_fetch)
    monkeypatch.setattr(transport, "publish_nip17_gift_wraps", fake_publish)
    try:
        assert asyncio.run(runtime._publish_progress_text(event, "🔧 shell"))
        assert len(published) == 1
        pairings.revoke(event["sender_pubkey"])
        assert not asyncio.run(runtime._publish_progress_text(event, "🔧 shell"))
        assert len(published) == 1
    finally:
        inbox.close()
        pairings.close()


def test_question_arms_only_on_recipient_acceptance(tmp_path, monkeypatch) -> None:
    import asyncio

    import uagent.nostr_remote_transport as transport

    ask_queue: queue.Queue = queue.Queue()
    state = {
        "active": True,
        "is_password": False,
        "message": "proceed?",
        "queue": ask_queue,
    }
    inbox, pairings, _key, event, runtime = _make_runtime(
        tmp_path, ask_state_provider=lambda: dict(state)
    )
    accept = {"recipient": False}
    calls: list[int] = []

    async def fake_fetch(pubkey, relays, **kwargs):
        return ["wss://relay.example.org"]

    async def fake_publish(events, relay_lists, private_key, **kwargs):
        calls.append(len(events))
        return [
            transport.RelayDelivery(
                relay_url="wss://relay.example.org",
                event_id=events[0]["id"],
                accepted=accept["recipient"],
            )
        ]

    monkeypatch.setattr(transport, "fetch_nip17_relay_list", fake_fetch)
    monkeypatch.setattr(transport, "publish_nip17_gift_wraps", fake_publish)
    try:
        runtime.dispatch_event(event, current_session_id="active-session")
        runtime._forward_pending_ask_once()
        request, text, queued_queue = runtime._question_queue.get_nowait()

        # Rejected by every recipient relay: not delivered, retry stays open.
        asyncio.run(runtime._publish_question_text(request, text, queued_queue))
        assert runtime._ask_forwarded_queue is None
        assert runtime._ask_queued_queue is None
        assert calls == [1]  # recipient wrap only; no sender copy

        # Accepted: routing arms, then the sender copy is published.
        accept["recipient"] = True
        runtime._forward_pending_ask_once()
        request, text, queued_queue = runtime._question_queue.get_nowait()
        asyncio.run(runtime._publish_question_text(request, text, queued_queue))
        assert runtime._ask_forwarded_queue is ask_queue
        assert calls == [1, 1, 1]
    finally:
        inbox.close()
        pairings.close()


def test_status_command_is_not_consumed_as_ask_answer(tmp_path) -> None:
    ask_queue: queue.Queue = queue.Queue()
    state = {
        "active": True,
        "is_password": False,
        "message": "proceed?",
        "queue": ask_queue,
    }
    inbox, pairings, recipient_key, event, runtime = _make_runtime(
        tmp_path, ask_state_provider=lambda: dict(state)
    )
    try:
        runtime.dispatch_event(event, current_session_id="active-session")
        runtime._note_question_result(ask_queue, True)

        sender_key = _secret(1)
        now = int(time.time())
        wrap = create_nip17_private_messages(
            "/uag status", sender_key, _public_key_bytes(recipient_key), now=now
        )[0]
        rumor = unwrap_nip17_private_message(wrap, recipient_key)
        inbox.enqueue_verified_wrap(
            rumor["pubkey"],
            rumor["id"],
            wrap,
            created_at=rumor["created_at"],
            received_at=now,
            session_id="active-session",
        )
        runtime._queue_rumor(rumor)

        # The status query keeps its routing; the ask stays unanswered.
        assert ask_queue.empty()
        queued = runtime.event_queue.get_nowait()
        assert queued["text"] == "/uag status"
        record = inbox.get(rumor["pubkey"], rumor["id"])
        assert record is not None and record.status == "pending"
    finally:
        inbox.close()
        pairings.close()


def test_question_not_published_after_ask_ends(tmp_path, monkeypatch) -> None:
    import asyncio

    import uagent.nostr_remote_transport as transport

    ask_queue: queue.Queue = queue.Queue()
    state = {
        "active": True,
        "is_password": False,
        "message": "proceed?",
        "queue": ask_queue,
    }
    inbox, pairings, _key, event, runtime = _make_runtime(
        tmp_path, ask_state_provider=lambda: dict(state)
    )
    published: list = []

    async def fake_fetch(pubkey, relays, **kwargs):
        return ["wss://relay.example.org"]

    async def fake_publish(events, relay_lists, private_key, **kwargs):
        published.append(events)
        return [
            transport.RelayDelivery(
                relay_url="wss://relay.example.org",
                event_id=events[0]["id"],
                accepted=True,
            )
        ]

    monkeypatch.setattr(transport, "fetch_nip17_relay_list", fake_fetch)
    monkeypatch.setattr(transport, "publish_nip17_gift_wraps", fake_publish)
    try:
        runtime.dispatch_event(event, current_session_id="active-session")
        runtime._forward_pending_ask_once()
        request, text, queued_queue = runtime._question_queue.get_nowait()

        # The ask ends (local answer / timeout) before the sender runs.
        state["active"] = False
        asyncio.run(runtime._publish_question_text(request, text, queued_queue))
        assert published == []
        assert runtime._ask_forwarded_queue is None
        assert runtime._ask_queued_queue is None
    finally:
        inbox.close()
        pairings.close()


def _enqueue_request(inbox, sender_key, recipient_key, text):
    """Enqueue one more verified request from an existing sender."""
    now = int(time.time())
    wrap = create_nip17_private_messages(
        text, sender_key, _public_key_bytes(recipient_key), now=now
    )[0]
    rumor = unwrap_nip17_private_message(wrap, recipient_key)
    inbox.enqueue_verified_wrap(
        rumor["pubkey"],
        rumor["id"],
        wrap,
        created_at=rumor["created_at"],
        received_at=now,
        session_id="active-session",
    )
    return {
        "kind": "nostr_remote_request",
        "sender_pubkey": rumor["pubkey"],
        "rumor_id": rumor["id"],
        "created_at": rumor["created_at"],
        "session_id": "active-session",
        "text": text,
    }


def test_dispatch_offers_pairing_and_processes_request_on_approval(
    tmp_path,
) -> None:
    inbox, pairings, private_key, event = _setup_request(tmp_path)
    try:
        assert pairings.revoke(event["sender_pubkey"])
        offered: list[str] = []

        def _approve(sender: str) -> bool:
            offered.append(sender)
            pairings.pair(sender, "phone", approved=True)
            return True

        action = dispatch_nostr_remote_inbox_event(
            event,
            inbox_store=inbox,
            pairing_store=pairings,
            private_key=private_key,
            current_session_id="active-session",
            on_unpaired_sender=_approve,
        )
        assert offered == [event["sender_pubkey"]]
        assert action.kind == "user"
        assert action.text == "hello"
        # The request was not rejected; it stays claimed for the
        # foreground turn, exactly like an already-paired dispatch.
        record = inbox.get(event["sender_pubkey"], event["rumor_id"])
        assert record is not None
        assert record.status == "dispatching"
    finally:
        inbox.close()
        pairings.close()


def test_dispatch_rejects_unpaired_sender_when_pairing_declined(
    tmp_path,
) -> None:
    inbox, pairings, private_key, event = _setup_request(tmp_path)
    try:
        assert pairings.revoke(event["sender_pubkey"])
        with pytest.raises(RemoteCLIRequestError, match="not paired"):
            dispatch_nostr_remote_inbox_event(
                event,
                inbox_store=inbox,
                pairing_store=pairings,
                private_key=private_key,
                current_session_id="active-session",
                on_unpaired_sender=lambda _sender: False,
            )
        record = inbox.get(event["sender_pubkey"], event["rumor_id"])
        assert record is not None
        assert record.status == "rejected"
    finally:
        inbox.close()
        pairings.close()


def test_dispatch_does_not_offer_pairing_for_other_failures(tmp_path) -> None:
    # A stale request from an unpaired sender fails freshness before
    # the pairing check, so the operator is never prompted for it.
    sender_key = _secret(1)
    recipient_key = _secret(2)
    stale = int(time.time()) - 10_000
    wrap = create_nip17_private_messages(
        "hello", sender_key, _public_key_bytes(recipient_key), now=stale
    )[0]
    rumor = unwrap_nip17_private_message(wrap, recipient_key)
    inbox = SQLiteNostrInboxStore(tmp_path / "inbox.sqlite3")
    pairings = SQLitePairingStore(tmp_path / "pairings.sqlite3")
    try:
        inbox.enqueue_verified_wrap(
            rumor["pubkey"],
            rumor["id"],
            wrap,
            created_at=rumor["created_at"],
            received_at=int(time.time()),
            session_id="active-session",
        )
        event = {
            "kind": "nostr_remote_request",
            "sender_pubkey": rumor["pubkey"],
            "rumor_id": rumor["id"],
            "created_at": rumor["created_at"],
            "session_id": "active-session",
            "text": "hello",
        }
        offered: list[str] = []
        with pytest.raises(RemoteCLIRequestError, match="stale"):
            dispatch_nostr_remote_inbox_event(
                event,
                inbox_store=inbox,
                pairing_store=pairings,
                private_key=recipient_key,
                current_session_id="active-session",
                on_unpaired_sender=lambda sender: offered.append(sender) or True,
            )
        assert offered == []
        record = inbox.get(rumor["pubkey"], rumor["id"])
        assert record is not None
        assert record.status == "rejected"
    finally:
        inbox.close()
        pairings.close()


def test_pairing_prompt_approval_pairs_and_processes_the_message(
    tmp_path,
) -> None:
    asked: list[str] = []

    def _asker(npub: str) -> str:
        asked.append(npub)
        return "yes"

    inbox, pairings, _key, event, runtime = _make_runtime(
        tmp_path, pairing_asker=_asker
    )
    try:
        assert pairings.revoke(event["sender_pubkey"])
        action = runtime.dispatch_event(
            event, current_session_id="active-session", allow_pairing_prompt=True
        )
        assert action.kind == "user"
        assert action.text == "hello"
        assert len(asked) == 1
        assert asked[0].startswith("npub1")
        assert pairings.is_authorized(event["sender_pubkey"])
    finally:
        inbox.close()
        pairings.close()


def test_pairing_prompt_requires_the_allow_flag(tmp_path) -> None:
    asked: list[str] = []
    inbox, pairings, _key, event, runtime = _make_runtime(
        tmp_path, pairing_asker=lambda npub: asked.append(npub) or "yes"
    )
    try:
        assert pairings.revoke(event["sender_pubkey"])
        with pytest.raises(RemoteCLIRequestError, match="not paired"):
            runtime.dispatch_event(event, current_session_id="active-session")
        assert asked == []
        assert not pairings.is_authorized(event["sender_pubkey"])
    finally:
        inbox.close()
        pairings.close()


def test_pairing_refusal_is_remembered_for_the_session(tmp_path) -> None:
    asked: list[str] = []

    def _asker(npub: str) -> str:
        asked.append(npub)
        return "no"

    inbox, pairings, private_key, event, runtime = _make_runtime(
        tmp_path, pairing_asker=_asker
    )
    try:
        assert pairings.revoke(event["sender_pubkey"])
        with pytest.raises(RemoteCLIRequestError, match="not paired"):
            runtime.dispatch_event(
                event,
                current_session_id="active-session",
                allow_pairing_prompt=True,
            )
        second = _enqueue_request(inbox, _secret(1), private_key, "hello again")
        with pytest.raises(RemoteCLIRequestError, match="not paired"):
            runtime.dispatch_event(
                second,
                current_session_id="active-session",
                allow_pairing_prompt=True,
            )
        # The second message from the refused sender did not prompt again.
        assert len(asked) == 1
        assert not pairings.is_authorized(event["sender_pubkey"])
    finally:
        inbox.close()
        pairings.close()


def test_pairing_prompt_without_an_answer_asks_again_next_time(
    tmp_path,
) -> None:
    answers: list[str | None] = [None, "yes"]
    asked: list[str] = []

    def _asker(npub: str) -> str | None:
        asked.append(npub)
        return answers.pop(0)

    inbox, pairings, private_key, event, runtime = _make_runtime(
        tmp_path, pairing_asker=_asker
    )
    try:
        assert pairings.revoke(event["sender_pubkey"])
        with pytest.raises(RemoteCLIRequestError, match="not paired"):
            runtime.dispatch_event(
                event,
                current_session_id="active-session",
                allow_pairing_prompt=True,
            )
        second = _enqueue_request(inbox, _secret(1), private_key, "hello again")
        action = runtime.dispatch_event(
            second,
            current_session_id="active-session",
            allow_pairing_prompt=True,
        )
        assert action.text == "hello again"
        # No answer (timeout/cancel) is not a refusal: the operator
        # was asked again for the next message.
        assert len(asked) == 2
        assert pairings.is_authorized(event["sender_pubkey"])
    finally:
        inbox.close()
        pairings.close()


def test_pairing_prompt_is_never_forwarded_to_a_remote_requester(
    tmp_path,
) -> None:
    state = {
        "active": True,
        "is_password": False,
        "message": "Register this device?",
        "queue": queue.Queue(),
    }
    inbox, pairings, _key, event, runtime = _make_runtime(
        tmp_path, ask_state_provider=lambda: state
    )
    try:
        # A paired request is active, so a pending question would
        # normally be forwarded to its sender.
        runtime.dispatch_event(event, current_session_id="active-session")
        runtime._pairing_prompt_open = True
        runtime._forward_pending_ask_once()
        assert runtime._question_queue.empty()
    finally:
        inbox.close()
        pairings.close()


def test_pairing_prompt_cancel_sentinel_is_not_a_refusal(tmp_path) -> None:
    answers: list[str | None] = ["cancel", "yes"]
    asked: list[str] = []

    def _asker(npub: str) -> str | None:
        asked.append(npub)
        return answers.pop(0)

    inbox, pairings, private_key, event, runtime = _make_runtime(
        tmp_path, pairing_asker=_asker
    )
    try:
        assert pairings.revoke(event["sender_pubkey"])
        with pytest.raises(RemoteCLIRequestError, match="not paired"):
            runtime.dispatch_event(
                event,
                current_session_id="active-session",
                allow_pairing_prompt=True,
            )
        second = _enqueue_request(inbox, _secret(1), private_key, "hello again")
        action = runtime.dispatch_event(
            second,
            current_session_id="active-session",
            allow_pairing_prompt=True,
        )
        assert action.text == "hello again"
        # Ctrl+C at the prompt arrives as the ask channel's "cancel"
        # sentinel: it is no answer, so the operator was asked again
        # instead of the sender being remembered as refused.
        assert len(asked) == 2
        assert pairings.is_authorized(event["sender_pubkey"])
    finally:
        inbox.close()
        pairings.close()


class _FakeListenSocket:
    """Minimal relay socket: delivers one scripted event, then stops."""

    def __init__(self, event: dict) -> None:
        self.event = event
        self.sent: list[list[object]] = []
        self.delivered = False

    async def __aenter__(self) -> "_FakeListenSocket":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def send(self, raw: str) -> None:
        self.sent.append(json.loads(raw))

    async def recv(self) -> str:
        if not self.delivered:
            self.delivered = True
            subscription_id = self.sent[0][1]
            return json.dumps(["EVENT", subscription_id, self.event])
        await asyncio.sleep(0.01)
        raise RuntimeError("listener should stop after callback")


def test_listener_persists_verified_unknown_sender_request(tmp_path) -> None:
    from uagent.nostr_remote_transport import listen_nip17_messages

    sender_key = _secret(3)
    recipient_key = _secret(2)
    now = int(time.time())
    wrap = create_nip17_private_messages(
        "hello", sender_key, _public_key_bytes(recipient_key), now=now
    )[0]
    rumor = unwrap_nip17_private_message(wrap, recipient_key)
    inbox = SQLiteNostrInboxStore(tmp_path / "inbox.sqlite3")
    pairings = SQLitePairingStore(tmp_path / "pairings.sqlite3")
    runtime = NostrRemoteRuntime(
        event_queue=queue.Queue(),
        private_key=recipient_key,
        relays=["wss://relay.example.org"],
        session_id="active-session",
        inbox_store=inbox,
        pairing_store=pairings,
    )
    try:
        # Dispatch authorization stays strict for the unpaired sender;
        # only the ingress gate admits the verified first contact.
        assert not runtime.authorize_sender(rumor["pubkey"])
        assert runtime.authorize_ingress_sender(rumor["pubkey"])
        socket = _FakeListenSocket(wrap)
        delivered: list[dict] = []
        with pytest.raises(RuntimeError, match="listener should stop"):
            asyncio.run(
                listen_nip17_messages(
                    "wss://relay.example.org",
                    recipient_key,
                    delivered.append,
                    authorize_sender=runtime.authorize_ingress_sender,
                    inbox_store=inbox,
                    target_session_id="active-session",
                    now_fn=lambda: now,
                    connect_factory=lambda _url, **_kwargs: socket,
                )
            )
        pending = inbox.list_pending(limit=10, session_id="active-session")
        assert [record.sender_pubkey for record in pending] == [rumor["pubkey"]]
        assert delivered[0]["pubkey"] == rumor["pubkey"]
    finally:
        inbox.close()
        pairings.close()
