from __future__ import annotations

import json
import threading
import time
from types import SimpleNamespace

from uagent import core
from uagent.cli_impl.sub_agent_jobs import (
    CLIJobConfirmationBroker,
    current_cli_job_owner,
    display_job_notice,
    format_job_notice,
    handle_cli_job_command,
    is_cli_session_transition_command,
    prepare_cli_session_transition,
)
from uagent.runtime.prompt_context import format_prompt
from uagent.runtime.sub_agent_jobs import (
    SubAgentJobManager,
    SubAgentJobOwner,
    SubAgentJobSettings,
)


def _manager() -> SubAgentJobManager:
    return SubAgentJobManager(
        SubAgentJobSettings(
            workers=1,
            queue_limit=2,
            owner_limit=4,
            completed_limit=10,
            result_ttl_sec=60,
            event_limit=10,
            log_max_bytes=4096,
            result_max_bytes=4096,
            task_max_bytes=4096,
            shutdown_timeout_sec=0.1,
        )
    )


def _owner() -> SubAgentJobOwner:
    return SubAgentJobOwner(entry_point="cli", session_id="cli-session")


def _confirmation_core() -> SimpleNamespace:
    return SimpleNamespace(
        human_ask_lock=threading.RLock(),
        human_ask_active=False,
        human_ask_is_password=False,
        human_ask_prompt="",
        human_ask_job_id=None,
        human_ask_generation=0,
        human_ask_queue=None,
        human_ask_lines=[],
        human_ask_multiline_active=False,
        prompt_needs_redraw=False,
        print_lock=threading.RLock(),
        _stream_line_open=False,
        _reasoning_stream_open=False,
        _prompt_line_open=False,
        _cli_prompt_toolkit_active=False,
        status_busy=False,
    )


def test_background_badge_only_changes_idle_prompts():
    assert (
        format_prompt(busy=False, label="", cwd_name="agentcli", background_jobs=2)
        == "agentcli[bg:2]> "
    )
    assert (
        format_prompt(
            busy=False,
            label="",
            cwd_name="agentcli",
            reasoning_label="LLM:auto->high",
            background_jobs=1,
        )
        == "agentcli[LLM:auto->high][bg:1]> "
    )
    assert (
        format_prompt(busy=True, label="LLM", cwd_name="agentcli", background_jobs=2)
        == "[BUSY:LLM] > "
    )


def test_job_notice_is_short_and_background_display_does_not_change_busy(capsys):
    notice = {
        "event": "finished",
        "job_id": "sa_123",
        "agent_name": "planner",
        "state": "completed",
        "elapsed_sec": 2.25,
    }
    assert format_job_notice(notice) == "[JOB sa_123 planner] completed (2.2s)"
    fake_core = SimpleNamespace(
        print_lock=threading.RLock(),
        status_busy=False,
        _stream_line_open=False,
        _reasoning_stream_open=False,
        _prompt_line_open=True,
        _cli_prompt_toolkit_active=False,
        prompt_needs_redraw=False,
    )
    display_job_notice(fake_core, notice)
    assert capsys.readouterr().out.endswith("[JOB sa_123 planner] completed (2.2s)\n")
    assert fake_core.status_busy is False
    assert fake_core.prompt_needs_redraw is True
    assert fake_core._prompt_line_open is False


def test_cli_jobs_commands_are_owner_scoped_and_do_not_print_result(capsys):
    manager = _manager()
    owner = _owner()
    started = threading.Event()
    release = threading.Event()
    try:
        accepted = manager.spawn(
            owner=owner,
            agent_name="planner",
            task="research",
            worker=lambda ctx: (
                ctx.log("tool", "collected evidence"),
                started.set(),
                release.wait(1),
                json.dumps({"status": "complete", "answer": "hidden result"}),
            )[-1],
        )
        assert started.wait(1)
        assert handle_cli_job_command(":jobs", manager=manager, owner=owner) is True
        output = capsys.readouterr().out
        assert accepted["job_id"] in output
        assert "running" in output

        assert (
            handle_cli_job_command(
                f":job logs {accepted['job_id']}", manager=manager, owner=owner
            )
            is True
        )
        assert "collected evidence" in capsys.readouterr().out

        assert (
            handle_cli_job_command(
                f":job {accepted['job_id']}", manager=manager, owner=owner
            )
            is True
        )
        detail = capsys.readouterr().out
        assert "state: running" in detail
        assert "hidden result" not in detail

        assert (
            handle_cli_job_command(
                f":job cancel {accepted['job_id']}", manager=manager, owner=owner
            )
            is True
        )
        assert "cancelled" in capsys.readouterr().out
    finally:
        release.set()
        manager.shutdown()


def test_cli_job_commands_hide_other_owners(capsys):
    manager = _manager()
    owner = _owner()
    other = SubAgentJobOwner(entry_point="cli", session_id="another-session")
    try:
        accepted = manager.spawn(
            owner=owner, agent_name="planner", task="private", worker=lambda _ctx: "ok"
        )
        manager.wait(owner=owner, job_id=accepted["job_id"], timeout=2)
        assert handle_cli_job_command(
            f":job {accepted['job_id']}", manager=manager, owner=other
        )
        assert "not found" in capsys.readouterr().out
    finally:
        manager.shutdown()


def test_non_job_input_is_not_consumed():
    assert handle_cli_job_command("hello", manager=None, owner=None) is False
    assert handle_cli_job_command(":sessions", manager=None, owner=None) is False


def test_background_subagent_status_and_messages_stay_out_of_foreground(monkeypatch):
    from uagent.core_impl import logs as core_logs
    from uagent.core_impl import status as core_status

    previous_busy = core.status_busy
    previous_label = core.status_label
    core.status_busy = False
    core.status_label = ""

    def fail_if_global_log(*_args, **_kwargs):
        raise AssertionError("background log leaked into the CLI transcript")

    monkeypatch.setattr(
        "uagent.runtime.logging_setup.append_masked_message", fail_if_global_log
    )
    manager = _manager()
    try:

        def worker(_ctx):
            core_status.set_status(True, "Sub-Agent (planner)")
            core_logs.log_message(
                {"role": "assistant", "content": "private background detail"}
            )
            return "done"

        accepted = manager.spawn(
            owner=_owner(), agent_name="planner", task="background", worker=worker
        )
        result = manager.wait(owner=_owner(), job_id=accepted["job_id"], timeout=2)
        assert result["state"] == "completed"
        assert core.status_busy is False
        assert core.status_label == ""
        events = manager.get_events(owner=_owner(), job_id=accepted["job_id"])["events"]
        assert any("private background detail" in event["message"] for event in events)
    finally:
        core.status_busy = previous_busy
        core.status_label = previous_label
        manager.shutdown()


def test_cli_session_transition_cancels_old_owner_work_and_pauses_admission():
    manager = _manager()
    owner = _owner()
    started = threading.Event()
    stopped = threading.Event()
    try:

        def worker(ctx):
            started.set()
            ctx.cancel_event.wait(2)
            try:
                ctx.raise_if_cancelled()
            except Exception:
                stopped.set()
                raise

        accepted = manager.spawn(
            owner=owner, agent_name="planner", task="transition", worker=worker
        )
        assert started.wait(1)
        ready, lingering = prepare_cli_session_transition(manager, owner, timeout=1)
        assert ready is True
        assert lingering == []
        assert stopped.is_set()
        rejected = manager.spawn(
            owner=owner,
            agent_name="planner",
            task="paused",
            worker=lambda _ctx: "ok",
        )
        assert rejected == {"status": "rejected", "reason": "owner_transition"}
        assert (
            manager.get(owner=owner, job_id=accepted["job_id"])["state"] == "cancelled"
        )
    finally:
        manager.resume_owner(owner)
        manager.shutdown()


def test_session_transition_command_detection_and_owner_selection():
    assert is_cli_session_transition_command(":load 0")
    assert is_cli_session_transition_command(":cont")
    assert is_cli_session_transition_command(":sessions load session-2")
    assert is_cli_session_transition_command(":sessions resume session-3")
    assert not is_cli_session_transition_command(":sessions")
    assert not is_cli_session_transition_command(":sessions load")
    fake_core = SimpleNamespace(session_id="loaded-session", SESSION_ID="process")
    owner = current_cli_job_owner(fake_core, "fallback")
    assert owner == SubAgentJobOwner(entry_point="cli", session_id="loaded-session")


def test_core_idle_prompt_reads_owner_scoped_job_count(monkeypatch):
    from uagent.core_impl.status import get_prompt

    owner = _owner()
    manager = SimpleNamespace(running_count=lambda *, owner: 2)
    monkeypatch.setattr(core, "_sub_agent_job_manager", manager, raising=False)
    monkeypatch.setattr(core, "_sub_agent_job_owner", owner, raising=False)
    monkeypatch.setattr(core, "status_busy", False)
    monkeypatch.setattr(core, "status_label", "")
    monkeypatch.setattr(core, "auto_pilot_active", False)
    monkeypatch.setattr(core, "last_reasoning_label", "")
    monkeypatch.setattr(core, "human_ask_active", False)
    prompt = get_prompt()
    assert prompt.endswith("[bg:2]> ")


def test_background_human_ask_fails_closed_without_touching_foreground_prompt():
    from uagent.tools.human_ask_tool import run_tool

    previous_active = core.human_ask_active
    core.human_ask_active = False
    manager = _manager()
    try:
        accepted = manager.spawn(
            owner=_owner(),
            agent_name="reviewer",
            task="confirmation",
            worker=lambda _ctx: run_tool(
                {"message": "Confirm the dangerous operation?", "is_password": False}
            ),
        )
        result = manager.wait(owner=_owner(), job_id=accepted["job_id"], timeout=2)
        payload = json.loads(result["result"])
        assert payload["status"] == "blocked"
        assert payload["cancelled"] is True
        assert core.human_ask_active is False
    finally:
        core.human_ask_active = previous_active
        manager.shutdown()


def test_background_confirmation_does_not_suppress_foreground_idle_transition():
    from uagent.core_impl.status import set_status

    previous_busy = core.status_busy
    previous_label = core.status_label
    previous_job_id = core.human_ask_job_id
    core.status_busy = True
    core.status_label = "LLM"
    core.human_ask_job_id = "sa_confirmation"
    try:
        set_status(False, "")
        assert core.status_busy is False
        assert core.status_label == ""
    finally:
        core.status_busy = previous_busy
        core.status_label = previous_label
        core.human_ask_job_id = previous_job_id


def test_job_confirmation_broker_labels_prompt_and_returns_reply():
    from uagent.tools.human_ask_tool import run_tool

    fake_core = _confirmation_core()
    broker = CLIJobConfirmationBroker(fake_core, enabled=True)
    manager = SubAgentJobManager(
        SubAgentJobSettings(
            workers=1,
            queue_limit=2,
            owner_limit=4,
            completed_limit=10,
            result_ttl_sec=60,
            event_limit=20,
            log_max_bytes=4096,
            result_max_bytes=4096,
            task_max_bytes=4096,
            shutdown_timeout_sec=0.2,
        ),
        confirmation_handler=broker.ask,
    )
    try:
        accepted = manager.spawn(
            owner=_owner(),
            agent_name="patch_designer",
            task="ask for approval",
            worker=lambda _ctx: run_tool(
                {"message": "Approve this change?", "is_password": False}
            ),
        )
        deadline = time.monotonic() + 2
        while not fake_core.human_ask_active and time.monotonic() < deadline:
            time.sleep(0.01)
        assert fake_core.human_ask_active is True
        assert fake_core.human_ask_job_id == accepted["job_id"]
        assert fake_core.human_ask_prompt == f"[REPLY job:{accepted['job_id']}] > "
        assert (
            manager.get(owner=_owner(), job_id=accepted["job_id"])["state"]
            == "waiting_for_user"
        )
        fake_core.human_ask_queue.put("yes")
        result = manager.wait(owner=_owner(), job_id=accepted["job_id"], timeout=2)
        payload = json.loads(result["result"])
        assert payload["user_reply"] == "yes"
        assert payload["cancelled"] is False
        assert fake_core.human_ask_active is False
        assert fake_core.human_ask_job_id is None
    finally:
        manager.shutdown()
        broker.shutdown()


def test_job_confirmation_cancel_purges_active_prompt_and_wakes_worker():
    fake_core = _confirmation_core()
    broker = CLIJobConfirmationBroker(fake_core, enabled=True)
    manager = SubAgentJobManager(
        SubAgentJobSettings(
            workers=1,
            queue_limit=2,
            owner_limit=4,
            completed_limit=10,
            result_ttl_sec=60,
            event_limit=20,
            log_max_bytes=4096,
            result_max_bytes=4096,
            task_max_bytes=4096,
            shutdown_timeout_sec=0.2,
        ),
        confirmation_handler=broker.ask,
    )
    try:
        accepted = manager.spawn(
            owner=_owner(),
            agent_name="patch_designer",
            task="cancel confirmation",
            worker=lambda ctx: ctx.ask_user("Approve this?"),
        )
        deadline = time.monotonic() + 2
        while not fake_core.human_ask_active and time.monotonic() < deadline:
            time.sleep(0.01)
        assert fake_core.human_ask_job_id == accepted["job_id"]
        cancelled = manager.cancel(owner=_owner(), job_id=accepted["job_id"])
        assert cancelled["state"] == "cancelled"
        assert manager.wait_owner_workers(_owner(), timeout=2) is True
        assert fake_core.human_ask_active is False
        assert fake_core.human_ask_job_id is None
    finally:
        manager.shutdown()
        broker.shutdown()


def test_confirmation_requests_are_served_fifo():
    fake_core = _confirmation_core()
    broker = CLIJobConfirmationBroker(fake_core, enabled=True)
    manager = SubAgentJobManager(
        SubAgentJobSettings(
            workers=2,
            queue_limit=4,
            owner_limit=4,
            completed_limit=10,
            result_ttl_sec=60,
            event_limit=20,
            log_max_bytes=4096,
            result_max_bytes=4096,
            task_max_bytes=4096,
            shutdown_timeout_sec=0.2,
        ),
        confirmation_handler=broker.ask,
    )
    try:
        first = manager.spawn(
            owner=_owner(),
            agent_name="reviewer",
            task="first question",
            worker=lambda ctx: ctx.ask_user("First?"),
        )
        deadline = time.monotonic() + 2
        while (
            fake_core.human_ask_job_id != first["job_id"]
            and time.monotonic() < deadline
        ):
            time.sleep(0.01)
        assert fake_core.human_ask_job_id == first["job_id"]

        second = manager.spawn(
            owner=_owner(),
            agent_name="reviewer",
            task="second question",
            worker=lambda ctx: ctx.ask_user("Second?"),
        )
        deadline = time.monotonic() + 2
        while (
            not any(
                event["kind"] == "confirmation"
                and event["message"] == "Confirmation request queued"
                for event in manager.get_events(
                    owner=_owner(), job_id=second["job_id"]
                )["events"]
            )
            and time.monotonic() < deadline
        ):
            time.sleep(0.01)
        assert fake_core.human_ask_job_id == first["job_id"]

        fake_core.human_ask_queue.put("yes-first")
        deadline = time.monotonic() + 2
        while (
            fake_core.human_ask_job_id != second["job_id"]
            and time.monotonic() < deadline
        ):
            time.sleep(0.01)
        assert fake_core.human_ask_job_id == second["job_id"]
        fake_core.human_ask_queue.put("yes-second")

        assert (
            manager.wait(owner=_owner(), job_id=first["job_id"], timeout=2)["result"]
            == "yes-first"
        )
        assert (
            manager.wait(owner=_owner(), job_id=second["job_id"], timeout=2)["result"]
            == "yes-second"
        )
    finally:
        manager.shutdown()
        broker.shutdown()
