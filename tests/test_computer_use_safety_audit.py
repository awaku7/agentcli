from uagent.computer_use.actions import ComputerAction
from uagent.computer_use.audit import InMemoryAuditSink
from uagent.computer_use.policy import ComputerUsePolicy
from uagent.computer_use.runtime import execute_action
from uagent.computer_use.runtimes.mock import MockComputerRuntime


def policy(*, confirm=False):
    return ComputerUsePolicy(
        enabled=True,
        environment="desktop",
        require_confirmation=confirm,
        allowed_actions=frozenset({"click"}),
        allowed_domains=frozenset(),
        max_actions=10,
        max_turns=3,
        timeout=30.0,
    )


def test_confirmation_callback_controls_high_impact_action():
    action = ComputerAction(action_id="c1", action="click")
    runtime = MockComputerRuntime()

    denied = execute_action(
        action,
        policy=policy(confirm=True),
        runtime=runtime,
        confirm=lambda _: False,
    )
    assert denied.success is False
    assert "confirmation" in denied.error
    assert runtime.executed == []

    accepted = execute_action(
        action,
        policy=policy(confirm=True),
        runtime=runtime,
        confirm=lambda _: True,
    )
    assert accepted.success is True
    assert runtime.executed == [action]


def test_audit_records_before_and_after():
    action = ComputerAction(action_id="a2", action="click")
    audit = InMemoryAuditSink()

    result = execute_action(
        action,
        policy=policy(),
        runtime=MockComputerRuntime(),
        audit=audit,
        session_id="s1",
        turn_id="t1",
    )

    assert result.success is True
    assert [event.phase for event in audit.events] == [
        "before_execute",
        "after_execute",
    ]
    assert audit.events[0].action_id == "a2"
    assert audit.events[0].session_id == "s1"
    assert audit.events[0].turn_id == "t1"
    assert audit.events[1].success is True
