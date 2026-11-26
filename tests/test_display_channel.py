"""Display channel policies and producer routing (single-writer stage 1)."""

from __future__ import annotations

import threading
import types

from uagent.runtime import display_channel as dc


def test_notice_bound_drops_oldest_and_counts():
    channel = dc.DisplayChannel(notice_limit=3)
    for i in range(5):
        channel.post_notice(dc.Notice(text=f"n{i}", source="test"))
    assert channel.dropped_notices == 2
    got = [channel.take(timeout=0.1) for _ in range(3)]
    assert [event.text for event in got] == ["n2", "n3", "n4"]
    assert channel.take(timeout=0.05) is None


def test_status_redraw_is_latest_only():
    channel = dc.DisplayChannel()
    channel.post_status(dc.StatusRedraw(reason="first"))
    channel.post_status(dc.StatusRedraw(reason="second"))
    event = channel.take(timeout=0.1)
    assert isinstance(event, dc.StatusRedraw)
    assert event.reason == "second"
    assert channel.take(timeout=0.05) is None


def test_stream_deltas_are_fifo_and_unbounded():
    channel = dc.DisplayChannel(notice_limit=1)
    for i in range(50):
        channel.post_stream(dc.StreamDelta(text=f"s{i}"))
    got = [channel.take(timeout=0.1) for _ in range(50)]
    assert [event.text for event in got] == [f"s{i}" for i in range(50)]


def test_take_priority_stream_then_notice_then_status():
    channel = dc.DisplayChannel()
    channel.post_status(dc.StatusRedraw(reason="status"))
    channel.post_notice(dc.Notice(text="notice", source="test"))
    channel.post_stream(dc.StreamDelta(text="stream"))
    assert isinstance(channel.take(timeout=0.1), dc.StreamDelta)
    assert isinstance(channel.take(timeout=0.1), dc.Notice)
    assert isinstance(channel.take(timeout=0.1), dc.StatusRedraw)


def _fake_core(**overrides):
    core = types.SimpleNamespace(
        print_lock=threading.RLock(),
        _stream_line_open=False,
        _reasoning_stream_open=False,
        _prompt_line_open=False,
        _cli_prompt_toolkit_active=False,
        _cli_prompt_app=None,
        prompt_needs_redraw=False,
        status_busy=False,
    )
    for name, value in overrides.items():
        setattr(core, name, value)
    return core


def test_render_notice_now_prints_and_requests_redraw(capsys):
    core = _fake_core(_prompt_line_open=True)
    dc.render_notice(core, dc.Notice(text="hello notice", source="nostr"))
    assert "hello notice" in capsys.readouterr().out
    assert core._prompt_line_open is False
    assert core.prompt_needs_redraw is True


def test_render_notice_after_stream_uses_stream_delta():
    deltas: list[str] = []
    core = _fake_core(print_stream_delta_locked=deltas.append)
    dc.render_notice(
        core,
        dc.Notice(text="peer message", source="bitchat", wait_for_stream=True),
    )
    assert deltas == ["peer message\n"]


def test_render_notice_after_stream_lock_order_and_atomicity(monkeypatch):
    # Regression (Codex P1 + P2 on PR #481): the insertion must stay
    # atomic under print_lock, but the spinner must be stopped BEFORE
    # that lock is taken, and the writes under it must use the
    # non-spinner-stopping locked writer.  Calling print_stream_delta
    # (which stops the spinner) under print_lock deadlocks against a
    # concurrent spinner.stop(); dropping the lock entirely lets a
    # foreground delta land between the line close and the notice.
    from uagent.runtime import spinner

    lock = threading.Lock()
    events: list = []
    monkeypatch.setattr(spinner, "stop_quietly", lambda: events.append("stop_spinner"))

    def fake_locked_write(text: str) -> None:
        acquired = lock.acquire(blocking=False)
        events.append(("locked_write", text, not acquired))
        if acquired:
            lock.release()

    def fake_plain_delta(text: str) -> None:
        events.append(("plain_delta", text))

    core = _fake_core(
        print_lock=lock,
        print_stream_delta_locked=fake_locked_write,
        print_stream_delta=fake_plain_delta,
        _prompt_line_open=True,
    )
    dc.render_notice(
        core,
        dc.Notice(text="peer message", source="bitchat", wait_for_stream=True),
    )
    assert events[0] == "stop_spinner"
    writes = [event for event in events if isinstance(event, tuple)]
    assert writes
    assert all(event[0] == "locked_write" for event in writes)
    assert all(event[2] for event in writes)  # print_lock held throughout


def _patch_spinner(monkeypatch, *, running: bool) -> list[str]:
    from uagent.runtime import spinner

    calls: list[str] = []
    monkeypatch.setattr(spinner, "is_running", lambda: running)
    monkeypatch.setattr(spinner, "stop_quietly", lambda: calls.append("stop"))
    monkeypatch.setattr(spinner, "start", lambda: calls.append("start"))
    return calls


def test_render_notice_after_stream_restores_busy_spinner(monkeypatch):
    calls = _patch_spinner(monkeypatch, running=True)
    deltas: list[str] = []
    core = _fake_core(
        print_stream_delta_locked=deltas.append,
        status_busy=True,
    )
    dc.render_notice(
        core,
        dc.Notice(text="relay notice", source="nostr", wait_for_stream=True),
    )
    assert deltas == ["relay notice\n"]
    assert calls == ["stop", "start"]


def test_render_notice_after_stream_keeps_spinner_off_when_idle(monkeypatch):
    calls = _patch_spinner(monkeypatch, running=True)
    core = _fake_core(
        print_stream_delta_locked=lambda _text: None,
        status_busy=False,
    )
    dc.render_notice(
        core,
        dc.Notice(text="relay notice", source="nostr", wait_for_stream=True),
    )
    assert calls == ["stop"]


def test_render_notice_after_stream_does_not_resume_during_stream(monkeypatch):
    monkeypatch.setattr(dc, "STREAM_GRACE_SEC", 0.05)
    calls = _patch_spinner(monkeypatch, running=True)
    core = _fake_core(
        print_stream_delta_locked=lambda _text: None,
        status_busy=True,
        _stream_line_open=True,
    )
    dc.render_notice(
        core,
        dc.Notice(text="peer message", source="bitchat", wait_for_stream=True),
    )
    assert calls == ["stop"]


def test_render_notice_after_stream_closes_open_lines():
    deltas: list[str] = []
    core = _fake_core(
        print_stream_delta_locked=deltas.append,
        _stream_line_open=True,
        _prompt_line_open=True,
    )
    dc.render_notice(
        core,
        dc.Notice(text="peer message", source="bitchat", wait_for_stream=True),
    )
    assert deltas == ["\n", "\n", "peer message\n"]
    assert core._prompt_line_open is False
    assert core.prompt_needs_redraw is True


def test_bitchat_notify_posts_to_channel(monkeypatch):
    from uagent.tools import pybitchat_shared as shared

    posted: list[tuple[str, dict]] = []
    monkeypatch.setattr(dc, "post_notice", lambda text, **kw: posted.append((text, kw)))
    shared._notify_display("[bitchat] hello")
    assert posted == [
        ("[bitchat] hello", {"source": "bitchat", "wait_for_stream": True})
    ]

    posted.clear()
    shared._notify_display("[bitchat] [debug] noise")
    assert posted == []


def test_nostr_tool_notify_posts_to_channel(monkeypatch):
    from uagent.tools import nostr_transport

    posted: list[tuple[str, dict]] = []
    monkeypatch.setattr(dc, "post_notice", lambda text, **kw: posted.append((text, kw)))
    nostr_transport._notify_display("[nostr] relay up")
    assert posted == [
        ("[nostr] relay up", {"source": "nostr", "wait_for_stream": True})
    ]


def test_nostr_remote_incoming_renders_formatted_preview(monkeypatch):
    from uagent import nostr_remote_runtime

    rendered: list[dc.Notice] = []
    monkeypatch.setattr(
        dc, "render_notice", lambda core, notice: rendered.append(notice)
    )
    nostr_remote_runtime._display_nostr_incoming(
        object(), {"pubkey": "a" * 64, "content": "hello\n world"}
    )
    assert rendered == [
        dc.Notice(
            text="[NOSTR] Received from aaaaaaaaaaaa: hello world", source="nostr"
        )
    ]

    rendered.clear()
    nostr_remote_runtime._display_nostr_incoming(object(), {"pubkey": 1})
    assert rendered == []


def test_stream_drain_waits_for_all_renders():
    channel = dc.DisplayChannel()
    for i in range(3):
        channel.post_stream(dc.StreamDelta(text=f"s{i}"))
    assert channel.wait_for_stream_drain(timeout=0.05) is False

    rendered: list[str] = []

    def _render() -> None:
        while len(rendered) < 3:
            event = channel.take(timeout=1.0)
            if isinstance(event, dc.StreamDelta):
                rendered.append(event.text)
                channel.note_stream_rendered()

    renderer = threading.Thread(target=_render, daemon=True)
    renderer.start()
    assert channel.wait_for_stream_drain(timeout=5.0) is True
    renderer.join(timeout=5.0)
    assert rendered == ["s0", "s1", "s2"]


def test_pump_renders_stream_deltas_by_kind(monkeypatch):
    from uagent import core

    rendered: list[tuple[str, str]] = []
    monkeypatch.setattr(
        core, "print_stream_delta", lambda s: rendered.append(("answer", s))
    )
    monkeypatch.setattr(
        core,
        "print_reasoning_delta",
        lambda s: rendered.append(("reasoning", s)),
    )
    channel = dc.default_channel()
    channel.post_stream(dc.StreamDelta(text="think", kind="reasoning"))
    channel.post_stream(dc.StreamDelta(text="answer"))
    dc.ensure_pump()
    assert channel.wait_for_stream_drain(timeout=5.0) is True
    # The pump owns the line-state bookkeeping: it emits the
    # reasoning -> answer separator as its own printer call (the
    # real locked printer would insert the same newline itself).
    assert rendered == [
        ("reasoning", "think"),
        ("answer", "\n"),
        ("answer", "answer"),
    ]


def test_after_stream_wait_drains_queued_stream():
    # Regression (stage 2a): the pump renders the stream itself, so a
    # wait_for_stream notice must keep draining queued deltas while it
    # waits — otherwise the delta that closes the stream never renders
    # and the pump stalls behind the notice.
    core = _fake_core(
        _reasoning_stream_open=True,
        _stream_line_open=True,
        print_stream_delta_locked=lambda _text: None,
    )
    calls: list[int] = []

    def _drain() -> bool:
        calls.append(1)
        if len(calls) >= 3:
            core._reasoning_stream_open = False
            core._stream_line_open = False
        return True

    dc._render_notice_after_stream(core, "drained", stream_drain=_drain)
    assert len(calls) >= 3


def test_pump_notice_wait_does_not_stall_the_stream(monkeypatch, capsys):
    import time as _time

    from uagent import core

    rendered: list[tuple[str, str]] = []

    def _fake_reasoning(text: str) -> None:
        rendered.append(("reasoning", text))
        core._reasoning_stream_open = True
        core._stream_line_open = True

    def _fake_answer(text: str) -> None:
        rendered.append(("answer", text))
        core._reasoning_stream_open = False
        core._stream_line_open = False

    monkeypatch.setattr(core, "print_reasoning_delta", _fake_reasoning)
    monkeypatch.setattr(core, "print_stream_delta", _fake_answer)
    monkeypatch.setattr(core, "_reasoning_stream_open", False)
    monkeypatch.setattr(core, "_stream_line_open", False)
    monkeypatch.setattr(core, "_prompt_line_open", False)

    channel = dc.default_channel()
    channel.post_stream(dc.StreamDelta(text="think", kind="reasoning"))
    dc.ensure_pump()
    deadline = _time.monotonic() + 5.0
    while not rendered and _time.monotonic() < deadline:
        _time.sleep(0.01)
    assert rendered == [("reasoning", "think")]

    channel.post_notice(
        dc.Notice(text="p2-notice-marker", source="bitchat", wait_for_stream=True)
    )
    _time.sleep(0.3)  # let the pump enter the notice's stream wait
    channel.post_stream(dc.StreamDelta(text="answer-text"))
    assert channel.wait_for_stream_drain(timeout=5.0) is True
    assert rendered == [
        ("reasoning", "think"),
        ("answer", "\n"),
        ("answer", "answer-text"),
    ]
    deadline = _time.monotonic() + 5.0
    while "p2-notice-marker" not in capsys.readouterr().out:
        assert _time.monotonic() < deadline
        _time.sleep(0.01)


def test_relay_binding_redirects_core_printers(capsys):
    from uagent import core

    channel = dc.DisplayChannel()
    assert dc.stream_relay() is None
    with dc.bind_stream_relay(channel):
        assert dc.stream_relay() is channel
        core.print_stream_delta("relayed answer")
        core.print_reasoning_delta("relayed thought")
    assert dc.stream_relay() is None
    assert capsys.readouterr().out == ""
    first = channel.take(timeout=0.1)
    second = channel.take(timeout=0.1)
    assert isinstance(first, dc.StreamDelta)
    assert (first.text, first.kind) == ("relayed answer", "answer")
    assert isinstance(second, dc.StreamDelta)
    assert (second.text, second.kind) == ("relayed thought", "reasoning")


# ---------------------------------------------------------------------------
# Output document (stage 2b)
# ---------------------------------------------------------------------------


def _doc_text(document) -> str:
    segments, _version, _epoch = document.snapshot()
    return "".join(segment.text for segment in segments)


def test_document_merges_contiguous_same_kind():
    document = dc.OutputDocument()
    document.append("answer", "hel")
    document.append("answer", "lo")
    document.append("reasoning", "think")
    document.append("answer", "!")
    segments, _v, _e = document.snapshot()
    assert [(s.kind, s.text) for s in segments] == [
        ("answer", "hello"),
        ("reasoning", "think"),
        ("answer", "!"),
    ]


def test_document_strips_escapes_but_keeps_text():
    document = dc.OutputDocument()
    document.append("output", "\x1b[31mred\x1b[0m plain")
    document.append("output", "a\x1b]8;;https://example.com\x07link\x1b]8;;\x07b")
    assert _doc_text(document) == "red plainalinkb"
    assert "\x1b" not in _doc_text(document)


def test_document_holds_escape_split_across_appends():
    document = dc.OutputDocument()
    document.append("output", "a\x1b[3")
    assert _doc_text(document) == "a"
    document.append("output", "1mb")
    assert _doc_text(document) == "ab"


def test_document_cr_redraw_keeps_last_form():
    document = dc.OutputDocument()
    document.append("output", "working 10%\rworking 90%\n")
    assert _doc_text(document) == "working 90%\n"
    document.append("output", "a\r\nb")
    assert _doc_text(document) == "working 90%\na\nb"


def test_document_leading_cr_replaces_current_line():
    document = dc.OutputDocument()
    document.append("output", "done\nworking 10%")
    _segments, _v, epoch_before = document.snapshot()
    document.append("output", "\rworking 90%")
    assert _doc_text(document) == "done\nworking 90%"
    _segments, _v, epoch_after = document.snapshot()
    assert epoch_after > epoch_before


def test_document_replace_last_lines_keeps_earlier_text():
    document = dc.OutputDocument()
    document.append("answer", "intro\nsnap v1 line1\nsnap v1 line2")
    _s, _v, epoch_before = document.snapshot()
    document.replace_last_lines(2, "snap v2", kind="answer")
    assert _doc_text(document) == "intro\nsnap v2"
    _s, _v, epoch_after = document.snapshot()
    assert epoch_after > epoch_before


def test_document_trim_caps_and_bumps_epoch():
    document = dc.OutputDocument(max_chars=20)
    document.append("output", "line one\nline two\nline three\n")
    text = _doc_text(document)
    assert len(text) <= 20
    assert text.startswith("line")
    _s, _v, epoch = document.snapshot()
    assert epoch > 0


def test_split_snapshot_prefix_matches_host_renderer():
    esc = "\x1b"
    two_line = f"\r{esc}[1A{esc}[2K{esc}[1B\r{esc}[2K{esc}[1A\r" + "snap v2"
    assert dc.split_snapshot_prefix(two_line) == (2, "snap v2")
    one_line = f"\r{esc}[2K" + "snap v2"
    assert dc.split_snapshot_prefix(one_line) == (1, "snap v2")
    assert dc.split_snapshot_prefix("plain delta") is None
    assert dc.split_snapshot_prefix("\rplain") is None
