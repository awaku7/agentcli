from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from uagent.computer_use.adapters.meta import MetaComputerAdapter
from uagent.computer_use.capability import ComputerUseCapabilityError
from uagent.computer_use.results import ComputerActionResult, Screenshot


class MetaCapability:
    supported = True
    native = True
    provider = "meta"
    api_type = "responses"
    tool_type = "computer"


def _enabled_policy():
    from uagent.computer_use.policy import ComputerUsePolicy

    return ComputerUsePolicy(
        enabled=True,
        environment="desktop",
        require_confirmation=False,
        allowed_actions=frozenset({"click", "type"}),
        allowed_domains=frozenset(),
        max_actions=20,
        max_turns=10,
        timeout=60.0,
    )


def test_meta_builds_provider_specific_computer_tool():
    assert MetaComputerAdapter().build_tool(MetaCapability()) == {"type": "computer"}


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("provider", "openai", "provider must be 'meta'"),
        ("api_type", "messages", "requires the Responses API"),
        ("tool_type", "computer_use_preview", "tool_type must be 'computer'"),
    ],
)
def test_meta_adapter_rejects_protocol_family_mismatch(field, value, message):
    capability = type("Capability", (MetaCapability,), {field: value})()
    with pytest.raises(ComputerUseCapabilityError, match=message):
        MetaComputerAdapter().build_tool(capability)


def test_meta_parses_computer_call_actions_and_safety_metadata():
    check = {
        "id": "csc-1",
        "code": "malicious_instructions",
        "message": "Potentially unsafe action detected.",
    }
    receipt = {"opaque": ["keep", "unchanged"]}
    call = MetaComputerAdapter().parse_call(
        {
            "type": "computer_call",
            "id": "item-1",
            "call_id": "call-1",
            "actions": [
                {"type": "click", "button": "left", "x": 12, "y": 30},
                {"type": "type", "text": "search"},
                {"type": "keypress", "keys": ["Enter"]},
            ],
            "pending_safety_checks": [check],
            "meta_safety_replay_receipt": receipt,
        }
    )

    assert call.call_id == "call-1"
    assert [action.action for action in call.actions] == ["click", "type", "keypress"]
    assert call.actions[0].coordinate == (12, 30)
    assert call.raw_actions[0] == {
        "type": "click",
        "button": "left",
        "x": 12,
        "y": 30,
    }
    assert call.pending_safety_checks == (check,)
    assert call.meta_safety_replay_receipt == receipt


def test_meta_rejects_unknown_action_and_malformed_safety_check():
    adapter = MetaComputerAdapter()
    with pytest.raises(ValueError, match="unsupported Meta Computer Use action"):
        adapter.parse_call(
            {
                "type": "computer_call",
                "call_id": "call-1",
                "actions": [{"type": "launch_shell"}],
            }
        )
    with pytest.raises(ValueError, match="include id, code, and message"):
        adapter.parse_call(
            {
                "type": "computer_call",
                "call_id": "call-1",
                "actions": [{"type": "screenshot"}],
                "pending_safety_checks": [{"id": "missing-fields"}],
            }
        )


def test_meta_builds_output_with_screenshot_acknowledgement_and_receipt():
    check = {"id": "csc-1", "code": "risk", "message": "review"}
    receipt = {"token": [1, 2, 3]}
    result = MetaComputerAdapter().build_tool_result(
        call_id="call-1",
        image_url="data:image/png;base64,cG5n",
        acknowledged_safety_checks=[check],
        meta_safety_replay_receipt=receipt,
    )

    assert result == {
        "type": "computer_call_output",
        "call_id": "call-1",
        "acknowledged_safety_checks": [check],
        "meta_safety_replay_receipt": receipt,
        "output": {
            "type": "computer_screenshot",
            "image_url": "data:image/png;base64,cG5n",
        },
    }
    with pytest.raises(ValueError, match="requires an image data URL"):
        MetaComputerAdapter().build_tool_result(call_id="c", image_url="")


def test_meta_response_parser_preserves_checks_and_receipt_in_tool_arguments():
    from uagent.providers.responses_common import parse_responses_response

    check = {"id": "csc-1", "code": "risk", "message": "review"}
    receipt = {"opaque": {"receipt": "abc"}}
    response = SimpleNamespace(
        id="resp-1",
        output=[
            SimpleNamespace(
                type="computer_call",
                id="item-1",
                call_id="call-1",
                actions=[{"type": "screenshot"}],
                pending_safety_checks=[check],
                meta_safety_replay_receipt=receipt,
            )
        ],
    )

    _, _, calls, _, _ = parse_responses_response(response, provider="meta")
    parsed = json.loads(calls[0]["function"]["arguments"])

    assert calls[0]["id"] == "call-1"
    assert calls[0]["function"]["name"] == "computer"
    assert parsed["actions"] == [{"type": "screenshot"}]
    assert parsed["pending_safety_checks"] == [check]
    assert parsed["meta_safety_replay_receipt"] == receipt


def test_meta_stream_parser_handles_computer_call_output_items():
    from uagent.providers.responses_common import parse_responses_stream

    check = {"id": "csc-stream", "code": "risk", "message": "review"}
    call = SimpleNamespace(
        type="computer_call",
        id="item-stream",
        call_id="call-stream",
        actions=[{"type": "screenshot"}],
        pending_safety_checks=[check],
        meta_safety_replay_receipt={"stream": "opaque"},
    )
    event = SimpleNamespace(type="response.output_item.done", item=call)

    _, _, calls, _, _ = parse_responses_stream([event], provider="meta")

    parsed = json.loads(calls[0]["function"]["arguments"])
    assert calls[0]["id"] == "call-stream"
    assert calls[0]["function"]["name"] == "computer"
    assert parsed["pending_safety_checks"] == [check]
    assert parsed["meta_safety_replay_receipt"] == {"stream": "opaque"}


def test_meta_native_request_adds_tool_and_initial_screenshot():
    from uagent.providers.llm_openai_responses import build_responses_request

    class Runtime:
        def screenshot(self):
            return Screenshot(data=b"png", media_type="image/png")

    core = SimpleNamespace(
        computer_use_native_tool={"type": "computer"},
        computer_use_native_provider="meta",
        computer_use_native_active=False,
        computer_use_runtime=Runtime(),
    )
    _, input_items, response_tools = build_responses_request(
        [{"role": "user", "content": "Open the page"}],
        send_tools_this_round=True,
        provider="meta",
        tool_specs=[],
        core=core,
    )

    assert response_tools == [{"type": "computer"}]
    assert core.computer_use_native_active is True
    user_content = input_items[0]["content"]
    assert [item["type"] for item in user_content] == ["input_text", "input_image"]
    assert user_content[-1]["image_url"] == "data:image/png;base64,cG5n"


def test_meta_native_request_keeps_existing_user_image_without_recapturing(monkeypatch):
    from uagent.providers.llm_openai_responses import build_responses_request

    class Runtime:
        def screenshot(self):
            raise AssertionError("should retain the user-provided image")

    image_url = "data:image/png;base64,cG5n"
    core = SimpleNamespace(
        computer_use_native_tool={"type": "computer"},
        computer_use_native_provider="meta",
        computer_use_native_active=False,
        computer_use_runtime=Runtime(),
    )
    _, input_items, _ = build_responses_request(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Use this screen"},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
        send_tools_this_round=True,
        provider="meta",
        tool_specs=[],
        core=core,
    )

    assert (
        sum(item.get("type") == "input_image" for item in input_items[0]["content"])
        == 1
    )


def test_meta_native_tool_output_is_one_screenshot_with_ack_and_replay_receipt():
    from uagent.providers.llm_openai_responses import _responses_tool_output

    checks = [{"id": "csc-1", "code": "risk", "message": "review"}]
    receipt = {"opaque": "receipt"}
    result = _responses_tool_output(
        "call-1",
        json.dumps(
            {
                "success": True,
                "screenshot_data": "cG5n",
                "screenshot_media_type": "image/png",
                "acknowledged_safety_checks": checks,
                "meta_safety_replay_receipt": receipt,
            }
        ),
        "computer",
        SimpleNamespace(
            computer_use_native_active=True,
            computer_use_native_provider="meta",
        ),
        provider="meta",
    )

    assert result == {
        "type": "computer_call_output",
        "call_id": "call-1",
        "acknowledged_safety_checks": checks,
        "meta_safety_replay_receipt": receipt,
        "output": {
            "type": "computer_screenshot",
            "image_url": "data:image/png;base64,cG5n",
        },
    }


def test_meta_native_stateless_replay_is_rejected_explicitly():
    from uagent.providers.llm_openai_responses import build_responses_request

    core = SimpleNamespace(
        computer_use_native_tool={"type": "computer"},
        computer_use_native_provider="meta",
        computer_use_native_active=True,
        computer_use_runtime=SimpleNamespace(
            screenshot=lambda: Screenshot(data=b"png")
        ),
    )
    messages = [
        {"role": "user", "content": "start"},
        {"role": "tool", "name": "computer", "tool_call_id": "call-1", "content": "{}"},
    ]

    with pytest.raises(RuntimeError, match="stateless replay is disabled"):
        build_responses_request(
            messages,
            send_tools_this_round=True,
            provider="meta",
            tool_specs=[],
            core=core,
        )


def test_meta_computer_output_requires_a_screenshot():
    from uagent.providers.llm_openai_responses import _responses_tool_output

    with pytest.raises(RuntimeError, match="Meta Computer Use requires a screenshot"):
        _responses_tool_output(
            "call-1",
            json.dumps({"success": False, "screenshot_data": None}),
            "computer",
            SimpleNamespace(
                computer_use_native_active=True,
                computer_use_native_provider="meta",
                computer_use_runtime=SimpleNamespace(
                    screenshot=lambda: (_ for _ in ()).throw(RuntimeError("capture"))
                ),
            ),
            provider="meta",
        )


def test_meta_safety_denial_fails_closed_before_any_runtime_action():
    from uagent.computer_use.integration import install_computer_use_handler

    class Runtime:
        def __init__(self):
            self.calls = 0

        def execute(self, action):
            self.calls += 1
            return ComputerActionResult(action_id=action.action_id, success=True)

        def screenshot(self):
            return Screenshot(data=b"png")

    check = {"id": "csc-1", "code": "risk", "message": "Review me"}
    receipt = {"opaque": "unchanged"}
    runtime = Runtime()
    core = SimpleNamespace(
        computer_use_runtime=runtime,
        computer_use_turn_id="turn-1",
        computer_use_safety_check_confirmation=lambda received: False,
    )
    handler = install_computer_use_handler(
        core=core,
        provider="meta",
        model="muse-spark-1.3",
        policy=_enabled_policy(),
        runtime=runtime,
    )

    result = json.loads(
        handler(
            tool_call={"id": "call-1"},
            action={
                "actions": [{"type": "click", "button": "left", "x": 1, "y": 2}],
                "pending_safety_checks": [check],
                "meta_safety_replay_receipt": receipt,
            },
            messages=[],
            core=core,
        )
    )

    assert result["success"] is False
    assert result["acknowledged_safety_checks"] == []
    assert result["meta_safety_replay_receipt"] == receipt
    assert runtime.calls == 0


def test_meta_approved_checks_are_echoed_and_failed_batch_stops():
    from uagent.computer_use.integration import install_computer_use_handler

    class FailSecondRuntime:
        def __init__(self):
            self.calls = 0

        def execute(self, action):
            self.calls += 1
            return ComputerActionResult(
                action_id=action.action_id,
                success=self.calls == 1,
                error=None if self.calls == 1 else "input failed",
            )

        def screenshot(self):
            return Screenshot(data=b"png")

    check = {"id": "csc-2", "code": "risk", "message": "Review me"}
    approvals = []
    runtime = FailSecondRuntime()
    core = SimpleNamespace(
        computer_use_runtime=runtime,
        computer_use_turn_id="turn-2",
        computer_use_safety_check_confirmation=lambda received: approvals.append(
            received
        )
        or True,
    )
    handler = install_computer_use_handler(
        core=core,
        provider="meta",
        model="muse-spark-1.3",
        policy=_enabled_policy(),
        runtime=runtime,
    )

    result = json.loads(
        handler(
            tool_call={"id": "call-2"},
            action={
                "actions": [
                    {"type": "click", "button": "left", "x": 1, "y": 2},
                    {"type": "type", "text": "x"},
                    {"type": "click", "button": "left", "x": 3, "y": 4},
                ],
                "pending_safety_checks": [check],
            },
            messages=[],
            core=core,
        )
    )

    assert approvals == [check]
    assert result["success"] is False
    assert result["acknowledged_safety_checks"] == [check]
    assert len(result["results"]) == 2
    assert runtime.calls == 2


def test_meta_native_prepare_requires_exact_meta_responses_capability(monkeypatch):
    from uagent.computer_use.native import prepare_native_computer_use

    monkeypatch.setattr(
        "uagent.computer_use.capability.get_computer_use_capability",
        lambda model, provider: MetaCapability(),
    )
    core = SimpleNamespace(computer_use_runtime=object())

    assert prepare_native_computer_use(
        core=core, provider="meta", model="muse-spark-1.3"
    )
    assert core.computer_use_native_tool == {"type": "computer"}
    assert core.computer_use_native_provider == "meta"


def test_meta_partial_safety_approval_echoes_only_approved_checks():
    from uagent.computer_use.integration import install_computer_use_handler

    class Runtime:
        def __init__(self):
            self.calls = 0

        def execute(self, action):
            self.calls += 1
            return ComputerActionResult(action_id=action.action_id, success=True)

        def screenshot(self):
            return Screenshot(data=b"png")

    first = {"id": "csc-1", "code": "risk-one", "message": "first"}
    second = {"id": "csc-2", "code": "risk-two", "message": "second"}
    reviewed = []

    def approve(check):
        reviewed.append(check)
        return check["id"] == "csc-1"

    runtime = Runtime()
    core = SimpleNamespace(
        computer_use_runtime=runtime,
        computer_use_safety_check_confirmation=approve,
    )
    handler = install_computer_use_handler(
        core=core,
        provider="meta",
        model="muse-spark-1.3",
        policy=_enabled_policy(),
        runtime=runtime,
    )

    result = json.loads(
        handler(
            tool_call={"id": "call-partial"},
            action={
                "actions": [{"type": "click", "button": "left", "x": 1, "y": 2}],
                "pending_safety_checks": [first, second],
            },
            messages=[],
            core=core,
        )
    )

    assert reviewed == [first, second]
    assert result["acknowledged_safety_checks"] == [first]
    assert result["success"] is False
    assert runtime.calls == 0
