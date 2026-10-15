import json
from types import SimpleNamespace

import pytest

from uagent.computer_use.native import prepare_native_computer_use
from uagent.llm_flow_helpers import _execute_tool_calls
from uagent.uagent_llm import (
    _computer_use_enabled_for_current_execution,
    _maybe_navigate_computer_runtime,
)
from uagent.providers.llm_openai_responses import build_responses_request
from uagent.runtime.execution_broker import (
    SecurityProfile,
    TrustedSandboxScope,
    execution_profile,
)


class Cache:
    def record_file_access(self, filename):
        pass


def test_computer_tool_calls_use_core_handler(monkeypatch):
    calls = []
    core = SimpleNamespace(
        computer_use_handler=lambda **kwargs: calls.append(kwargs)
        or json.dumps({"ok": True}),
        show_tool_output=False,
        set_status=lambda *args: None,
        log_message=lambda *args: None,
    )
    messages = []
    tool_calls = [
        {
            "id": "computer-1",
            "type": "function",
            "function": {
                "name": "computer",
                "arguments": json.dumps({"action": "screenshot"}),
            },
        }
    ]

    monkeypatch.setattr(
        "uagent.llm_flow_helpers.tools.is_parallel_safe", lambda *a: False
    )
    executed, fresh = _execute_tool_calls(
        tool_calls_list=tool_calls,
        messages=messages,
        core=core,
        cache_mgr=Cache(),
    )

    assert executed is True
    assert fresh == tool_calls
    assert calls[0]["action"]["action"] == "screenshot"
    assert messages[-1]["content"] == json.dumps({"ok": True})


@pytest.mark.parametrize(
    ("profile", "sandbox_enabled"),
    [
        (SecurityProfile.REMOTE, False),
        (SecurityProfile.REMOTE, True),
        (SecurityProfile.LOCAL_TRUSTED, True),
    ],
)
def test_disallowed_computer_use_never_reaches_host_handler(
    monkeypatch, profile, sandbox_enabled
):
    calls = []
    core = SimpleNamespace(
        computer_use_handler=lambda **kwargs: calls.append(kwargs)
        or json.dumps({"ok": True}),
        show_tool_output=False,
        set_status=lambda *args: None,
        log_message=lambda *args: None,
    )
    tool_calls = [
        {
            "id": "computer-remote-1",
            "type": "function",
            "function": {
                "name": "computer",
                "arguments": json.dumps({"action": "screenshot"}),
            },
        }
    ]
    monkeypatch.setattr(
        "uagent.llm_flow_helpers.tools.is_parallel_safe", lambda *a: False
    )
    scope = TrustedSandboxScope(
        deployment_id="web",
        principal_id="alice",
        project_id="project-1",
        scope_kind="web-room",
        scope_id="room-1",
    )

    with execution_profile(
        profile,
        sandbox_enabled=sandbox_enabled,
        scope=scope if profile is SecurityProfile.REMOTE else None,
    ):
        _execute_tool_calls(
            tool_calls_list=tool_calls,
            messages=[],
            core=core,
            cache_mgr=Cache(),
        )

    assert calls == []


def test_responses_continuation_does_not_append_next_action_user_message(monkeypatch):
    monkeypatch.setattr(
        "uagent.llm_flow_helpers.tools.is_parallel_safe", lambda *args: False
    )
    monkeypatch.setattr(
        "uagent.llm_flow_helpers.tools.run_tool",
        lambda name, args: json.dumps(
            {
                "ok": True,
                "data": {
                    "next_action": {
                        "type": "user_message",
                        "content": "Please analyze this screenshot.",
                    }
                },
            }
        ),
    )
    core = SimpleNamespace(
        show_tool_output=False,
        set_status=lambda *args: None,
        log_message=lambda *args: None,
    )
    tool_calls = [
        {
            "id": "screenshot-1",
            "type": "function",
            "function": {"name": "screenshot", "arguments": "{}"},
        }
    ]

    messages = []
    _execute_tool_calls(
        tool_calls_list=tool_calls,
        messages=messages,
        core=core,
        cache_mgr=Cache(),
        responses_api_continuation=True,
    )

    assert [message["role"] for message in messages] == ["tool"]


def test_remote_responses_request_omits_native_and_function_computer_tools():
    core = SimpleNamespace(
        computer_use_native_tool={"type": "computer", "display_width": 1280},
        computer_use_native_active=True,
        computer_use_native_provider="openai",
        computer_use_runtime=object(),
    )
    tool_specs = [
        {
            "type": "function",
            "function": {"name": "computer", "parameters": {"type": "object"}},
        },
        {
            "type": "function",
            "function": {"name": "calculator", "parameters": {"type": "object"}},
        },
    ]
    scope = TrustedSandboxScope(
        deployment_id="web",
        principal_id="alice",
        project_id="project-1",
        scope_kind="web-room",
        scope_id="room-1",
    )

    with execution_profile(SecurityProfile.REMOTE, scope=scope):
        _instructions, _inputs, request_tools = build_responses_request(
            [{"role": "user", "content": "hello"}],
            send_tools_this_round=True,
            provider="openai",
            tool_specs=tool_specs,
            core=core,
        )

    names = [item.get("name") for item in request_tools or [] if isinstance(item, dict)]
    assert "computer" not in names
    assert "calculator" in names


@pytest.mark.parametrize(
    ("profile", "sandbox_enabled"),
    [
        (SecurityProfile.REMOTE, False),
        (SecurityProfile.REMOTE, True),
        (SecurityProfile.LOCAL_TRUSTED, True),
    ],
)
def test_disallowed_native_computer_use_stops_before_capability_setup(
    monkeypatch, profile, sandbox_enabled
):
    capability_calls = []
    monkeypatch.setattr(
        "uagent.computer_use.capability.get_computer_use_capability",
        lambda *args: capability_calls.append(args),
    )
    core = SimpleNamespace(
        computer_use_native_tool={"type": "computer"},
        computer_use_native_active=True,
    )
    scope = (
        TrustedSandboxScope(
            deployment_id="web",
            principal_id="alice",
            project_id="project-1",
            scope_kind="web-room",
            scope_id="room-1",
        )
        if profile is SecurityProfile.REMOTE
        else None
    )

    with execution_profile(profile, sandbox_enabled=sandbox_enabled, scope=scope):
        assert not prepare_native_computer_use(
            core=core, provider="openai", model="gpt-computer-use"
        )

    assert capability_calls == []
    assert core.computer_use_native_tool is None
    assert core.computer_use_native_active is None


def test_remote_execution_disables_existing_computer_runtime_before_use():
    closed = []

    class Manager:
        def close(self):
            closed.append(True)

    core = SimpleNamespace(
        computer_use_runtime_manager=Manager(),
        computer_use_runtime=object(),
        computer_use_handler=lambda **_kwargs: "should not execute",
        computer_use_native_tool={"type": "computer"},
        computer_use_native_active=True,
    )
    policy = SimpleNamespace(enabled=True)
    scope = TrustedSandboxScope(
        deployment_id="web",
        principal_id="alice",
        project_id="project-1",
        scope_kind="web-room",
        scope_id="room-1",
    )

    with execution_profile(SecurityProfile.REMOTE, scope=scope):
        assert not _computer_use_enabled_for_current_execution(core, policy)
        assert not _maybe_navigate_computer_runtime(
            [{"role": "user", "content": "open https://example.test"}],
            core,
            policy,
        )

    assert closed == [True]
    assert core.computer_use_runtime is None
    assert core.computer_use_handler is None
    assert core.computer_use_native_tool is None
    assert core.computer_use_native_active is None
