"""The common runtime can host Web adapters without importing Web packages."""

from dataclasses import replace
from types import SimpleNamespace

from uagent.runtime import sub_agent_job_access as access
from uagent.runtime.identity_context import TurnContext, bind_turn_context
from uagent.runtime.sub_agent_jobs import CURRENT_SUB_AGENT_JOB_MODE


def _turn():
    return TurnContext(
        principal_id="alice",
        room_id="room-a",
        project_id="project-a",
        session_id="session-a",
        entry_point="web",
        authenticated=True,
        authn_kind="oidc",
    )


def test_external_job_resolver_retains_runtime_security_gates(monkeypatch):
    calls = []
    runtime = (object(), object())
    monkeypatch.setattr(access, "_web_job_runtime_resolver", None)
    access.register_web_job_runtime_resolver(lambda turn: calls.append(turn) or runtime)
    turn = _turn()
    with bind_turn_context(turn):
        assert access.get_job_runtime_context() == runtime
    with bind_turn_context(replace(turn, authenticated=False)):
        assert access.get_job_runtime_context() is None
    with bind_turn_context(turn):
        token = CURRENT_SUB_AGENT_JOB_MODE.set("background")
        try:
            assert access.get_job_runtime_context() is None
        finally:
            CURRENT_SUB_AGENT_JOB_MODE.reset(token)
    assert calls == [turn]


def test_external_job_resolver_absent_or_failed_is_unavailable(monkeypatch):
    with bind_turn_context(_turn()):
        monkeypatch.setattr(access, "_web_job_runtime_resolver", None)
        assert access.get_job_runtime_context() is None

        def unavailable(_turn):
            raise RuntimeError("host unavailable")

        access.register_web_job_runtime_resolver(unavailable)
        assert access.get_job_runtime_context() is None


def test_external_tool_sink_receives_masked_bounded_text(monkeypatch, capsys):
    from uagent import core, tools

    received = []
    monkeypatch.setattr(core, "_is_web", True, raising=False)
    monkeypatch.setattr(tools, "_spinner_stop_quietly", lambda: None)
    monkeypatch.setattr(
        tools,
        "get_callbacks",
        lambda: SimpleNamespace(tool_trace=lambda *x: received.append(x)),
    )
    monkeypatch.setattr(tools, "_tool_trace_body", lambda *_: "masked " + "x" * 10000)
    tools._emit_tool_trace("probe", {"secret": "never delivered"})
    assert len(received) == 1
    assert received[0][0] == "probe"
    assert len(received[0][1]) < 10000
    assert "never delivered" not in received[0][1]
    assert capsys.readouterr().out == ""


def test_absent_tool_sink_does_not_print_web_trace(monkeypatch, capsys):
    from uagent import core, tools

    monkeypatch.setattr(core, "_is_web", True, raising=False)
    monkeypatch.setattr(tools, "_spinner_stop_quietly", lambda: None)
    monkeypatch.setattr(tools, "get_callbacks", lambda: SimpleNamespace())
    tools._emit_tool_trace("probe", {})
    assert capsys.readouterr().out == ""
