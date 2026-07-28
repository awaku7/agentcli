"""Tests for the hooks execution engine (hooks_engine.py).

TDD: write tests first, then implement.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


@pytest.fixture()
def hooks_registry(repo_tmp_path: Path) -> str:
    """Create a hooks registry with sample hooks."""
    registry = {
        "plugins": {
            "test-plugin": {
                "SessionStart": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": "echo 'session started'",
                            }
                        ]
                    }
                ],
                "Stop": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": "echo 'session stopped'",
                            }
                        ]
                    }
                ],
                "PreToolUse": [
                    {
                        "matcher": "Write|Edit",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "echo 'pre-tool: write/edit'",
                            }
                        ],
                    },
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": "echo 'pre-tool: default'",
                            }
                        ],
                    },
                ],
            }
        }
    }
    path = repo_tmp_path / "hooks_registry.json"
    path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    return str(path)


class TestHooksEngineLoad:
    """Tests for loading hooks from registry."""

    def test_load_hooks_from_registry(self, hooks_registry: str) -> None:
        """Should load hooks organized by event type."""
        from uagent.hooks_engine import load_hooks_registry

        hooks = load_hooks_registry(hooks_registry)
        assert "SessionStart" in hooks
        assert "Stop" in hooks
        assert "PreToolUse" in hooks

    def test_load_empty_registry(self, repo_tmp_path: Path) -> None:
        """Empty or missing registry should return empty dict."""
        from uagent.hooks_engine import load_hooks_registry

        hooks = load_hooks_registry(str(repo_tmp_path / "nonexistent.json"))
        assert hooks == {}

    def test_load_invalid_json(self, repo_tmp_path: Path) -> None:
        """Invalid JSON should return empty dict."""
        from uagent.hooks_engine import load_hooks_registry

        path = repo_tmp_path / "bad.json"
        path.write_text("{invalid}", encoding="utf-8")
        hooks = load_hooks_registry(str(path))
        assert hooks == {}

    def test_hooks_organized_by_event(self, hooks_registry: str) -> None:
        """Hooks should be organized as event_name -> list of hook entries."""
        from uagent.hooks_engine import load_hooks_registry

        hooks = load_hooks_registry(hooks_registry)
        assert len(hooks["SessionStart"]) == 1
        assert len(hooks["Stop"]) == 1
        assert len(hooks["PreToolUse"]) == 2


class TestHooksEngineExecute:
    """Tests for executing hooks."""

    def test_execute_command_hook(self) -> None:
        """A command-type hook should execute and return result."""
        from uagent.hooks_engine import execute_hook

        hook = {"type": "command", "command": "echo hello"}
        result = execute_hook(hook)
        assert result["ok"] is True
        assert "hello" in result.get("stdout", "")

    def test_execute_command_hook_failure(self) -> None:
        """A failing command should return error."""
        from uagent.hooks_engine import execute_hook

        hook = {"type": "command", "command": "nonexistent_command_xyz"}
        result = execute_hook(hook)
        assert result["ok"] is False

    def test_execute_unknown_hook_type(self) -> None:
        """Unknown hook type should return error."""
        from uagent.hooks_engine import execute_hook

        hook = {"type": "unknown_type", "command": "echo"}
        result = execute_hook(hook)
        assert result["ok"] is False


class TestHooksEngineFire:
    """Tests for firing events to hooks."""

    def test_fire_session_start(self, hooks_registry: str) -> None:
        """Firing SessionStart should execute matching hooks."""
        from uagent.hooks_engine import fire_event, load_hooks_registry

        hooks = load_hooks_registry(hooks_registry)
        results = fire_event("SessionStart", hooks)
        assert len(results) >= 1
        assert any(r.get("ok") for r in results)

    def test_fire_unknown_event(self, hooks_registry: str) -> None:
        """Firing unknown event should return empty list."""
        from uagent.hooks_engine import fire_event, load_hooks_registry

        hooks = load_hooks_registry(hooks_registry)
        results = fire_event("UnknownEvent", hooks)
        assert results == []

    def test_fire_stop(self, hooks_registry: str) -> None:
        """Firing Stop should execute matching hooks."""
        from uagent.hooks_engine import fire_event, load_hooks_registry

        hooks = load_hooks_registry(hooks_registry)
        results = fire_event("Stop", hooks)
        assert len(results) >= 1


class TestHooksEngineMatcher:
    """Tests for PreToolUse hook matching."""

    def test_matcher_matches_tool(self, hooks_registry: str) -> None:
        """Matcher should match tools based on regex pattern."""
        from uagent.hooks_engine import find_matching_hooks, load_hooks_registry

        hooks = load_hooks_registry(hooks_registry)
        # PreToolUse has: matcher "Write|Edit" (hooks), and a default (no matcher)
        matched = find_matching_hooks("PreToolUse", hooks, tool_name="Write")
        assert len(matched) >= 1

    def test_matcher_no_match(self, hooks_registry: str) -> None:
        """Matcher that doesn't match should return only default hooks."""
        from uagent.hooks_engine import find_matching_hooks, load_hooks_registry

        hooks = load_hooks_registry(hooks_registry)
        matched = find_matching_hooks("PreToolUse", hooks, tool_name="Read")
        # Should match the default hook (no matcher), not the Write|Edit one
        assert len(matched) >= 1

    def test_matcher_no_default_fallback(self) -> None:
        """When no hooks match and no default, return empty."""
        from uagent.hooks_engine import find_matching_hooks

        hooks = {
            "PreToolUse": [
                {
                    "matcher": "Write|Edit",
                    "hooks": [{"type": "command", "command": "echo match"}],
                }
            ]
        }
        matched = find_matching_hooks("PreToolUse", hooks, tool_name="Read")
        assert len(matched) == 0


class TestHooksEngineIntegration:
    """End-to-end test: register, load, fire."""

    def test_full_flow(self, repo_tmp_path: Path) -> None:
        """Full flow: install hooks via plugin_shared, load via engine, fire."""
        from uagent.plugin_shared import install_plugin_hooks
        from uagent.hooks_engine import fire_event, load_hooks_registry

        # Create a minimal plugin with hooks
        p = repo_tmp_path / "e2e-plugin"
        (p / "hooks").mkdir(parents=True)
        hooks_config = {
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"type": "command", "command": "echo e2e-start"}]}
                ],
                "Stop": [{"hooks": [{"type": "command", "command": "echo e2e-stop"}]}],
            }
        }
        (p / "hooks" / "hooks.json").write_text(
            json.dumps(hooks_config), encoding="utf-8"
        )

        # Install hooks
        registry_path = repo_tmp_path / "e2e_registry.json"
        registry_path.write_text(json.dumps({"plugins": {}}), encoding="utf-8")
        install_plugin_hooks(str(p), "e2e-plugin", registry_path=str(registry_path))

        # Load and fire
        hooks = load_hooks_registry(str(registry_path))
        start_results = fire_event("SessionStart", hooks)
        assert len(start_results) == 1
        assert start_results[0]["ok"] is True

        stop_results = fire_event("Stop", hooks)
        assert len(stop_results) == 1
        assert stop_results[0]["ok"] is True

    def test_timeout_does_not_block(self) -> None:
        """A slow hook should timeout rather than block forever."""
        from uagent.hooks_engine import execute_hook

        if os.name == "nt":
            cmd = "ping -n 3 127.0.0.1 > nul"
        else:
            cmd = "sleep 3"

        hook = {"type": "command", "command": cmd}
        # Default timeout is 5s, should not block
        result = execute_hook(hook, timeout_ms=500)
        assert result["ok"] is False  # timeout or error


class TestClaudePluginRootCompat:
    """Claude Code ${CLAUDE_PLUGIN_ROOT} compatibility."""

    def test_expand_vars_claude_plugin_root(self, repo_tmp_path: Path) -> None:
        from uagent.hooks_engine import _expand_vars

        root = str((repo_tmp_path / "myplug").resolve())
        out = _expand_vars(
            'node "${CLAUDE_PLUGIN_ROOT}/hooks/x.js"',
            plugin_root=root,
        )
        assert root in out
        assert "${CLAUDE_PLUGIN_ROOT}" not in out
        out2 = _expand_vars(
            'echo "${UAGENT_PLUGIN_ROOT}"',
            plugin_root=root,
        )
        assert root in out2

    def test_load_registry_annotates_plugin_root(self, repo_tmp_path: Path) -> None:
        from uagent.hooks_engine import load_hooks_registry

        plug = repo_tmp_path / "plugins" / "demo"
        plug.mkdir(parents=True)
        registry = {
            "plugin_roots": {"demo": str(plug.resolve())},
            "plugins": {
                "demo": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": 'echo "${CLAUDE_PLUGIN_ROOT}"',
                                }
                            ]
                        }
                    ]
                }
            },
        }
        reg_path = repo_tmp_path / "reg.json"
        reg_path.write_text(json.dumps(registry), encoding="utf-8")

        hooks = load_hooks_registry(str(reg_path))
        group = hooks["SessionStart"][0]
        assert group.get("_plugin_name") == "demo"
        assert Path(group.get("_plugin_root")).resolve() == plug.resolve()
        leaf = group["hooks"][0]
        assert leaf.get("_plugin_root")
        assert Path(leaf["_plugin_root"]).resolve() == plug.resolve()

    def test_execute_expands_claude_plugin_root(self, repo_tmp_path: Path) -> None:
        from uagent.hooks_engine import execute_hook
        import sys

        plug = repo_tmp_path / "plugdir"
        plug.mkdir()
        py = sys.executable
        hook = {
            "type": "command",
            "command": (
                f'"{py}" -c "import os; print(os.environ.get('
                f"'CLAUDE_PLUGIN_ROOT', ''))\""
            ),
            "_plugin_root": str(plug.resolve()),
            "_plugin_name": "plugdir",
        }
        result = execute_hook(hook)
        assert result.get("ok") is True, result
        assert str(plug.resolve()) in (result.get("stdout") or "")

    def test_execute_command_string_expansion(self, repo_tmp_path: Path) -> None:
        from uagent.hooks_engine import execute_hook
        import sys

        plug = repo_tmp_path / "p2"
        plug.mkdir()
        marker = plug / "hooks"
        marker.mkdir()
        target = marker / "ok.txt"
        py = sys.executable
        # _expand_vars replaces ${CLAUDE_PLUGIN_ROOT} before shell runs.
        cmd = (
            f'"{py}" -c "from pathlib import Path; '
            "Path(r'${CLAUDE_PLUGIN_ROOT}/hooks/ok.txt')"
            ".write_text('yes', encoding='utf-8')\""
        )
        hook = {
            "type": "command",
            "command": cmd,
            "_plugin_root": str(plug.resolve()),
        }
        result = execute_hook(hook)
        assert result.get("ok") is True, result
        assert target.exists()
        assert target.read_text(encoding="utf-8") == "yes"


class TestHookStdoutContextInjection:
    """Hook stdout -> [HOOK] system message injection (additive, discard-safe)."""

    def test_parse_plain_text(self) -> None:
        from uagent.hooks_engine import parse_hook_stdout_context

        assert parse_hook_stdout_context("原始人モード ON") == "原始人モード ON"
        assert parse_hook_stdout_context("  hello\nworld  ") == "hello\nworld"
        assert parse_hook_stdout_context("OK") is None
        assert parse_hook_stdout_context("ok") is None
        assert parse_hook_stdout_context("") is None
        assert parse_hook_stdout_context(None) is None
        assert parse_hook_stdout_context("{}") is None

    def test_parse_json_additional_context(self) -> None:
        from uagent.hooks_engine import parse_hook_stdout_context

        payload = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": "mode reminder",
            }
        }
        assert parse_hook_stdout_context(json.dumps(payload)) == "mode reminder"
        assert (
            parse_hook_stdout_context(
                json.dumps({"additionalContext": "top-level ctx"})
            )
            == "top-level ctx"
        )
        # decision-only JSON must not dump into context
        assert (
            parse_hook_stdout_context(
                json.dumps({"decision": "block", "reason": "nope"})
            )
            is None
        )

    def test_inject_and_replace_event(self) -> None:
        from uagent.hooks_engine import (
            HOOK_CONTEXT_MARKER,
            inject_hook_context,
            clear_hook_messages,
        )

        messages = [
            {"role": "system", "content": "SYSTEM"},
            {"role": "user", "content": "hi"},
        ]
        r1 = [{"ok": True, "stdout": "session rules"}]
        n = inject_hook_context(
            messages, r1, event_name="SessionStart", replace_event=False
        )
        assert n == 1
        assert messages[0]["content"] == "SYSTEM"
        assert messages[1]["role"] == "system"
        assert messages[1]["content"].startswith(HOOK_CONTEXT_MARKER)
        assert "session rules" in messages[1]["content"]
        assert messages[2]["role"] == "user"

        # Failed / empty results are no-ops
        assert (
            inject_hook_context(
                messages,
                [{"ok": False, "stdout": "x"}, {"ok": True, "stdout": "OK"}],
                event_name="SessionStart",
            )
            == 0
        )

        r2 = [{"ok": True, "stdout": "turn-1"}]
        inject_hook_context(
            messages, r2, event_name="UserPromptSubmit", replace_event=True
        )
        r3 = [{"ok": True, "stdout": "turn-2"}]
        inject_hook_context(
            messages, r3, event_name="UserPromptSubmit", replace_event=True
        )
        ups = [
            m
            for m in messages
            if m.get("role") == "system"
            and isinstance(m.get("content"), str)
            and "event=UserPromptSubmit" in m["content"]
        ]
        assert len(ups) == 1
        assert "turn-2" in ups[0]["content"]
        assert "turn-1" not in ups[0]["content"]

        cleared = clear_hook_messages(messages, event_name="UserPromptSubmit")
        assert cleared == 1
        assert all(
            not (
                m.get("role") == "system"
                and isinstance(m.get("content"), str)
                and "event=UserPromptSubmit" in m["content"]
            )
            for m in messages
        )

    def test_pending_session_stash(self) -> None:
        from uagent.hooks_engine import (
            note_session_start_results,
            take_pending_session_hook_texts,
            inject_pending_session_hook_context,
            HOOK_CONTEXT_MARKER,
        )

        # reset stash
        take_pending_session_hook_texts()
        note_session_start_results(
            [{"ok": True, "stdout": "genshijin body"}, {"ok": True, "stdout": "OK"}]
        )
        messages = [{"role": "system", "content": "SYS"}]
        n = inject_pending_session_hook_context(messages)
        assert n == 1
        assert messages[1]["content"].startswith(HOOK_CONTEXT_MARKER)
        assert "genshijin body" in messages[1]["content"]
        # second take is empty
        assert inject_pending_session_hook_context(messages) == 0

    def test_inject_none_messages_safe(self) -> None:
        from uagent.hooks_engine import inject_hook_context

        assert (
            inject_hook_context(None, [{"ok": True, "stdout": "x"}], event_name="E")
            == 0
        )


# =========================================================================
# UserPromptSubmit stdin + decision/block
# =========================================================================


class TestUserPromptSubmitStdinAndBlock:
    """stdin JSON feed and decision=block handling."""

    def test_build_user_prompt_submit_stdin(self) -> None:
        from uagent.hooks_engine import build_user_prompt_submit_stdin
        import json

        raw = build_user_prompt_submit_stdin("hello world", cwd="/tmp/proj")
        data = json.loads(raw)
        assert data["hook_event_name"] == "UserPromptSubmit"
        assert data["prompt"] == "hello world"
        assert data["cwd"] == "/tmp/proj"

    def test_parse_hook_decision_block(self) -> None:
        from uagent.hooks_engine import parse_hook_decision

        d = parse_hook_decision('{"decision":"block","reason":"stats only"}')
        assert d is not None
        assert d["decision"] == "block"
        assert d["reason"] == "stats only"

    def test_parse_hook_decision_none_for_context_only(self) -> None:
        from uagent.hooks_engine import parse_hook_decision

        assert parse_hook_decision('{"additionalContext":"x"}') is None
        assert parse_hook_decision("plain text") is None

    def test_collect_hook_block_decision(self) -> None:
        from uagent.hooks_engine import collect_hook_block_decision

        results = [
            {"ok": True, "stdout": "ok"},
            {
                "ok": True,
                "stdout": '{"decision":"block","reason":"nope"}',
                "decision": "block",
                "reason": "nope",
            },
        ]
        b = collect_hook_block_decision(results)
        assert b == {"decision": "block", "reason": "nope"}
        assert collect_hook_block_decision([{"ok": True, "stdout": "hi"}]) is None

    def test_command_hook_receives_stdin(self, tmp_path: Path) -> None:
        """Command hook can read UserPromptSubmit JSON from stdin."""
        import sys
        from uagent.hooks_engine import execute_hook, build_user_prompt_submit_stdin

        script = tmp_path / "read_stdin.py"
        script.write_text(
            "import sys, json\nprint(json.load(sys.stdin).get('prompt', ''))\n",
            encoding="utf-8",
        )
        hook = {
            "type": "command",
            "command": f'{sys.executable} "{script}"',
        }
        stdin_data = build_user_prompt_submit_stdin("stdin-prompt-xyz")
        result = execute_hook(hook, stdin_data=stdin_data, timeout_ms=15000)
        assert result.get("ok") is True, result
        assert "stdin-prompt-xyz" in (result.get("stdout") or "")

    def test_execute_hook_annotates_decision(self, tmp_path: Path) -> None:
        import sys
        from uagent.hooks_engine import execute_hook

        script = tmp_path / "block_hook.py"
        body = '{"decision":"block","reason":"blocked-here"}'
        script.write_text(f"print({body!r})\n", encoding="utf-8")
        hook = {
            "type": "command",
            "command": f'{sys.executable} "{script}"',
        }
        result = execute_hook(hook, timeout_ms=10000)
        assert result.get("decision") == "block"
        assert result.get("reason") == "blocked-here"

    def test_fire_user_prompt_submit_end_to_end(self, tmp_path: Path) -> None:
        import sys
        from uagent.hooks_engine import (
            fire_user_prompt_submit,
            collect_hook_block_decision,
            inject_hook_context,
            parse_hook_stdout_context,
        )

        echo_script = tmp_path / "echo_ctx.py"
        echo_script.write_text(
            "import sys,json\n"
            "d=json.load(sys.stdin)\n"
            "print(json.dumps({"
            "'hookSpecificOutput':{"
            "'additionalContext':'got:'+d.get('prompt','')"
            "}}))\n",
            encoding="utf-8",
        )
        block_script = tmp_path / "block.py"
        block_script.write_text(
            "import sys,json\n"
            "d=json.load(sys.stdin)\n"
            "if d.get('prompt','').startswith('/block-me'):\n"
            "  print(json.dumps({'decision':'block','reason':'blocked:'+d['prompt']}))\n"
            "else:\n"
            "  print('ok')\n",
            encoding="utf-8",
        )
        hooks = {
            "hooks": {
                "UserPromptSubmit": [
                    {
                        "type": "command",
                        "command": f'{sys.executable} "{echo_script}"',
                    },
                    {
                        "type": "command",
                        "command": f'{sys.executable} "{block_script}"',
                    },
                ]
            }
        }

        results = fire_user_prompt_submit("hello", hooks=hooks)
        assert collect_hook_block_decision(results) is None
        ctx = parse_hook_stdout_context(results[0].get("stdout"))
        assert ctx == "got:hello"
        msgs: list = []
        inject_hook_context(msgs, results, event_name="UserPromptSubmit")
        assert any("got:hello" in str(m.get("content")) for m in msgs)

        results2 = fire_user_prompt_submit("/block-me now", hooks=hooks)
        block = collect_hook_block_decision(results2)
        assert block is not None
        assert block["decision"] == "block"
        assert "blocked:/block-me now" in block.get("reason", "")
        assert parse_hook_stdout_context('{"decision":"block","reason":"x"}') is None
