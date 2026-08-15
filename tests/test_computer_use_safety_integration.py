"""Regression tests for safe Computer Use round-loop integration."""

from __future__ import annotations

import json

from uagent.computer_use import ComputerUsePolicy, configure_computer_use
from uagent.computer_use.runtimes.mock import MockComputerRuntime


class Core:
    computer_use_runtime = None
    computer_use_handler = None
    computer_use_turn_id = "1"


def policy(**kwargs):
    values = {
        "enabled": True,
        "environment": "browser",
        "require_confirmation": False,
        "allowed_actions": frozenset({"screenshot"}),
        "allowed_domains": frozenset(),
        "max_actions": 2,
        "max_turns": 1,
        "timeout": 30.0,
    }
    values.update(kwargs)
    return ComputerUsePolicy(**values)


def test_missing_runtime_is_safe_noop_bootstrap():
    core = Core()
    assert (
        configure_computer_use(core, provider="custom", model="test", runtime=None)
        is None
    )
    assert core.computer_use_handler is None


def test_confirmation_callback_is_forwarded():
    core = Core()
    runtime = MockComputerRuntime()
    core.computer_use_confirmation = lambda action: True
    core.computer_use_handler = None
    # Configure from environment is tested elsewhere; install directly with a
    # policy that requires confirmation to isolate the callback contract.
    from uagent.computer_use.integration import install_computer_use_handler

    handler = install_computer_use_handler(
        core=core,
        provider="custom",
        model="test",
        policy=policy(require_confirmation=True),
        runtime=runtime,
    )
    result = json.loads(
        handler(
            tool_call={"id": "a1"},
            action={"action": "screenshot"},
            messages=[],
            core=core,
        )
    )
    assert result["success"] is True


def test_action_limit_is_enforced_before_runtime():
    core = Core()

    class CountingRuntime(MockComputerRuntime):
        def __init__(self):
            super().__init__()
            self.count = 0

        def execute(self, action):
            self.count += 1
            return super().execute(action)

    runtime = CountingRuntime()
    from uagent.computer_use.integration import install_computer_use_handler

    handler = install_computer_use_handler(
        core=core,
        provider="custom",
        model="test",
        policy=policy(max_actions=1),
        runtime=runtime,
    )
    first = json.loads(
        handler(
            tool_call={"id": "a1"},
            action={"action": "screenshot"},
            messages=[],
            core=core,
        )
    )
    second = json.loads(
        handler(
            tool_call={"id": "a2"},
            action={"action": "screenshot"},
            messages=[],
            core=core,
        )
    )
    assert first["success"] is True
    assert second["success"] is False
    assert "max_actions" in second["error"]
    assert runtime.count == 1
