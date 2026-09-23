from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sys

import pytest

from uagent.scheduler.os_payload import (
    consume_scheduled_payload,
    create_scheduled_payload,
    scheduled_payload_directory,
)
from uagent.tools import os_scheduler_helper as os_scheduler


def test_os_schedule_keeps_prompt_and_workdir_out_of_command(monkeypatch, tmp_path):
    monkeypatch.setenv("UAGENT_STATE_DIR", str(tmp_path / "state"))
    captured = {}

    def fake_create(name, argv, at_dt):
        captured.update(name=name, argv=argv)
        return {"ok": True, "job_name": name, "message": "created"}

    monkeypatch.setattr(os_scheduler, "detect_os", lambda: "linux")
    monkeypatch.setattr(os_scheduler, "_create_unix_schedule", fake_create)
    prompt = "private prompt; $(touch SHOULD_NOT_RUN)"
    workdir = str(tmp_path / "private workspace")

    result = os_scheduler.create_os_schedule(
        at_dt=datetime.now(timezone.utc) + timedelta(minutes=1),
        message="private notice",
        on_timeout_prompt=prompt,
        workdir=workdir,
        enable_tools=["calculator"],
    )

    command_text = " ".join(captured["argv"])
    assert prompt not in command_text
    assert "private notice" not in command_text
    assert workdir not in command_text
    assert "calculator" not in command_text
    assert result["ok"]
    assert result["job_name"].endswith(result["payload_id"])

    payload = consume_scheduled_payload(
        result["payload_id"], str(scheduled_payload_directory())
    )
    assert payload["on_timeout_prompt"] == prompt
    assert payload["message"] == "private notice"
    assert payload["workdir"] == workdir
    assert payload["enable_tools"] == ["calculator"]
    with pytest.raises(ValueError, match="missing or already consumed"):
        consume_scheduled_payload(
            result["payload_id"], str(scheduled_payload_directory())
        )


def test_windows_task_command_contains_only_opaque_payload_reference(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("UAGENT_STATE_DIR", str(tmp_path / "state"))
    captured = {}

    def fake_schtasks(args):
        captured["args"] = args

        class Result:
            returncode = 0
            stdout = "created"
            stderr = ""

        return Result()

    monkeypatch.setattr(os_scheduler, "detect_os", lambda: "windows")
    monkeypatch.setattr(os_scheduler, "_run_schtasks", fake_schtasks)
    secret = "hidden prompt & whoami"
    workdir = str(tmp_path / "space & scripts")
    result = os_scheduler.create_os_schedule(
        at_dt=datetime.now(timezone.utc) + timedelta(minutes=1),
        message=secret,
        workdir=workdir,
    )
    tr_command = captured["args"][captured["args"].index("/tr") + 1]
    assert secret not in tr_command
    assert workdir not in tr_command
    assert "--scheduled-payload-id" in tr_command
    assert "/Z" in captured["args"]
    payload = consume_scheduled_payload(
        result["payload_id"], str(scheduled_payload_directory())
    )
    assert payload["message"] == secret


def test_scheduled_payload_cli_consumes_file_and_sets_noninteractive(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("UAGENT_STATE_DIR", str(tmp_path / "state"))
    payload_id = create_scheduled_payload(
        {
            "message": "timer message",
            "on_timeout_prompt": "timer prompt",
            "workdir": str(tmp_path),
            "enable_tools": ["calculator"],
        }
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "uagent",
            "--scheduled-payload-id",
            payload_id,
            "--scheduled-payload-dir",
            str(scheduled_payload_directory()),
        ],
    )

    from uagent.util_common import parse_startup_args

    args, unknown = parse_startup_args()
    assert unknown == []
    assert args["inject_message"] == "timer prompt"
    assert args["workdir"] == str(tmp_path)
    assert args["enable_tools"] == ["calculator"]
    assert args["non_interactive"] is True


def test_schtasks_invocation_uses_argv_without_shell(monkeypatch):
    calls = []

    class Result:
        returncode = 0
        stdout = b"ok"
        stderr = b""

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return Result()

    monkeypatch.setattr(os_scheduler.subprocess, "run", fake_run)
    os_scheduler._run_schtasks(["/delete", "/tn", "uag_timer_abc", "/f"])
    assert calls[0][0][0] == "schtasks"
    assert calls[0][1]["shell"] is False
