"""Tests for all hook events and types.

Covers http, prompt, agent hook types and PreToolUse/PostToolUse integration.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture()
def tool_hooks_registry(repo_tmp_path: Path) -> str:
    """Create a hooks registry with tool-related hooks."""
    registry = {
        "plugins": {
            "tool-guard": {
                "PreToolUse": [
                    {
                        "matcher": "Write|Edit|Delete",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "echo 'pre-tool: guarded'",
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
                "PostToolUse": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": "echo 'post-tool: ok'",
                            }
                        ],
                    }
                ],
                "PostToolUseFailure": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": "echo 'post-tool: failed'",
                            }
                        ],
                    }
                ],
            }
        }
    }
    path = repo_tmp_path / "tool_hooks_registry.json"
    path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    return str(path)


class TestPreToolUse:
    """Tests for PreToolUse hook event."""

    def test_pre_tool_use_fires_before_tool(self, tool_hooks_registry: str) -> None:
        """PreToolUse should fire before tool execution."""
        from uagent.hooks_engine import (
            fire_tool_event,
            load_hooks_registry,
        )

        hooks = load_hooks_registry(tool_hooks_registry)
        results = fire_tool_event("PreToolUse", hooks, tool_name="Write")
        assert len(results) >= 1
        assert any("pre-tool" in r.get("stdout", "") for r in results)


class TestPostToolUse:
    """Tests for PostToolUse hook event."""

    def test_post_tool_use_fires(self, tool_hooks_registry: str) -> None:
        """PostToolUse should fire after successful tool execution."""
        from uagent.hooks_engine import (
            fire_tool_event,
            load_hooks_registry,
        )

        hooks = load_hooks_registry(tool_hooks_registry)
        results = fire_tool_event("PostToolUse", hooks, tool_name="Read")
        assert len(results) >= 1
        assert any("post-tool: ok" in r.get("stdout", "") for r in results)

    def test_post_tool_use_failure_fires(self, tool_hooks_registry: str) -> None:
        """PostToolUseFailure should fire after failed tool execution."""
        from uagent.hooks_engine import (
            fire_tool_event,
            load_hooks_registry,
        )

        hooks = load_hooks_registry(tool_hooks_registry)
        results = fire_tool_event("PostToolUseFailure", hooks, tool_name="Write")
        assert len(results) >= 1
        assert any("post-tool: failed" in r.get("stdout", "") for r in results)


class TestHttpHookType:
    """Tests for http-type hooks."""

    def test_http_hook_invalid_url(self) -> None:
        """http hook with invalid URL should return error."""
        from uagent.hooks_engine import execute_hook

        hook = {
            "type": "http",
            "url": "http://nonexistent.example.com/hook",
            "method": "POST",
        }
        result = execute_hook(hook, timeout_ms=500)
        assert result["ok"] is False

    def test_http_hook_no_url(self) -> None:
        """http hook without url should return error."""
        from uagent.hooks_engine import execute_hook

        hook = {"type": "http", "method": "POST"}
        result = execute_hook(hook)
        assert result["ok"] is False

    def test_http_hook_unsupported_method(self) -> None:
        """Unsupported HTTP method should return error."""
        from uagent.hooks_engine import execute_hook

        hook = {
            "type": "http",
            "url": "http://example.com/hook",
            "method": "OPTIONS",
        }
        result = execute_hook(hook)
        assert result["ok"] is False


class TestPromptHookType:
    """Tests for prompt-type hooks."""

    def test_prompt_hook_execution(self) -> None:
        """prompt-type hook should be callable."""
        from uagent.hooks_engine import execute_hook

        hook = {
            "type": "prompt",
            "prompt": "Say hello",
            "model": "sonnet",
        }
        result = execute_hook(hook)
        # No LLM client configured in test, should return error gracefully
        assert result["ok"] is False
        assert (
            "prompt" in result.get("error", "").lower()
            or "not supported" in result.get("error", "").lower()
        )


class TestAgentHookType:
    """Tests for agent-type hooks."""

    def test_agent_hook_execution(self) -> None:
        """agent-type hook should be callable."""
        from uagent.hooks_engine import execute_hook

        hook = {
            "type": "agent",
            "prompt": "Verify the result",
            "model": "sonnet",
        }
        result = execute_hook(hook)
        # No LLM client configured in test, should return error gracefully
        assert result["ok"] is False


class TestHookContextHelpers:
    """Tests for the context helper functions."""

    def test_get_active_hook_count(self, tool_hooks_registry: str) -> None:
        """Should return the count of registered hooks for each event."""
        from uagent.hooks_engine import (
            get_active_hook_count,
            load_hooks_registry,
        )

        hooks = load_hooks_registry(tool_hooks_registry)
        count = get_active_hook_count(hooks)
        assert "PreToolUse" in count
        assert "PostToolUse" in count
        assert "PostToolUseFailure" in count
        assert count["PreToolUse"] >= 2

    def test_get_active_hook_count_empty(self) -> None:
        """Empty hooks should return empty dict."""
        from uagent.hooks_engine import get_active_hook_count

        count = get_active_hook_count({})
        assert count == {}


class TestUserPromptSubmit:
    """Tests for UserPromptSubmit hook event."""

    def test_user_prompt_submit_fires(self, repo_tmp_path: Path) -> None:
        """UserPromptSubmit should fire with user prompt text."""
        from uagent.hooks_engine import fire_event, load_hooks_registry
        import json

        registry = {
            "plugins": {
                "test": {
                    "UserPromptSubmit": [
                        {
                            "hooks": [
                                {"type": "command", "command": "echo 'prompt received'"}
                            ]
                        }
                    ]
                }
            }
        }
        path = repo_tmp_path / "ups_hooks.json"
        path.write_text(json.dumps(registry), encoding="utf-8")

        hooks = load_hooks_registry(str(path))
        results = fire_event("UserPromptSubmit", hooks)
        assert len(results) >= 1
        assert any("prompt received" in r.get("stdout", "") for r in results)


class TestSubagentHooks:
    """Tests for SubagentStart/Stop hook events."""

    def test_subagent_start_fires(self, repo_tmp_path: Path) -> None:
        """SubagentStart should fire with agent name."""
        from uagent.hooks_engine import fire_event, load_hooks_registry
        import json

        registry = {
            "plugins": {
                "test": {
                    "SubagentStart": [
                        {
                            "hooks": [
                                {"type": "command", "command": "echo 'agent started'"}
                            ]
                        }
                    ]
                }
            }
        }
        path = repo_tmp_path / "sa_start_hooks.json"
        path.write_text(json.dumps(registry), encoding="utf-8")

        hooks = load_hooks_registry(str(path))
        results = fire_event("SubagentStart", hooks)
        assert len(results) >= 1
        assert any("agent started" in r.get("stdout", "") for r in results)

    def test_subagent_stop_fires(self, repo_tmp_path: Path) -> None:
        """SubagentStop should fire after agent execution."""
        from uagent.hooks_engine import fire_event, load_hooks_registry
        import json

        registry = {
            "plugins": {
                "test": {
                    "SubagentStop": [
                        {
                            "hooks": [
                                {"type": "command", "command": "echo 'agent stopped'"}
                            ]
                        }
                    ]
                }
            }
        }
        path = repo_tmp_path / "sa_stop_hooks.json"
        path.write_text(json.dumps(registry), encoding="utf-8")

        hooks = load_hooks_registry(str(path))
        results = fire_event("SubagentStop", hooks)
        assert len(results) >= 1
        assert any("agent stopped" in r.get("stdout", "") for r in results)

    def test_subagent_hooks_no_interference(self, repo_tmp_path: Path) -> None:
        """SubagentStart and SubagentStop should be independent."""
        from uagent.hooks_engine import fire_event, load_hooks_registry
        import json

        registry = {
            "plugins": {
                "test": {
                    "SubagentStart": [
                        {"hooks": [{"type": "command", "command": "echo start"}]}
                    ],
                    "SubagentStop": [
                        {"hooks": [{"type": "command", "command": "echo stop"}]}
                    ],
                }
            }
        }
        path = repo_tmp_path / "sa_both_hooks.json"
        path.write_text(json.dumps(registry), encoding="utf-8")

        hooks = load_hooks_registry(str(path))
        start_results = fire_event("SubagentStart", hooks)
        stop_results = fire_event("SubagentStop", hooks)

        assert len(start_results) == 1
        assert len(stop_results) == 1
        assert "start" in start_results[0].get("stdout", "")
        assert "stop" in stop_results[0].get("stdout", "")


class TestPostToolBatch:
    """Tests for PostToolBatch hook event."""

    def test_post_tool_batch_fires(self, repo_tmp_path: Path) -> None:
        """PostToolBatch should fire after parallel tool batch."""
        from uagent.hooks_engine import fire_event, load_hooks_registry
        import json

        registry = {
            "plugins": {
                "test": {
                    "PostToolBatch": [
                        {"hooks": [{"type": "command", "command": "echo 'batch done'"}]}
                    ]
                }
            }
        }
        path = repo_tmp_path / "ptb_hooks.json"
        path.write_text(json.dumps(registry), encoding="utf-8")

        hooks = load_hooks_registry(str(path))
        results = fire_event("PostToolBatch", hooks)
        assert len(results) == 1
        assert "batch done" in results[0].get("stdout", "")


class TestSetupHook:
    """Tests for Setup hook event."""

    def test_setup_fires(self, repo_tmp_path: Path) -> None:
        """Setup should fire at non-interactive startup."""
        from uagent.hooks_engine import fire_event, load_hooks_registry
        import json

        registry = {
            "plugins": {
                "test": {
                    "Setup": [
                        {"hooks": [{"type": "command", "command": "echo 'setup done'"}]}
                    ]
                }
            }
        }
        path = repo_tmp_path / "setup_hooks.json"
        path.write_text(json.dumps(registry), encoding="utf-8")

        hooks = load_hooks_registry(str(path))
        results = fire_event("Setup", hooks)
        assert len(results) == 1
        assert "setup done" in results[0].get("stdout", "")


class TestStopFailureHook:
    """Tests for StopFailure hook event."""

    def test_stop_failure_fires(self, repo_tmp_path: Path) -> None:
        """StopFailure should fire on API errors."""
        from uagent.hooks_engine import fire_event, load_hooks_registry
        import json

        registry = {
            "plugins": {
                "test": {
                    "StopFailure": [
                        {
                            "hooks": [
                                {"type": "command", "command": "echo 'failure logged'"}
                            ]
                        }
                    ]
                }
            }
        }
        path = repo_tmp_path / "stf_hooks.json"
        path.write_text(json.dumps(registry), encoding="utf-8")

        hooks = load_hooks_registry(str(path))
        results = fire_event("StopFailure", hooks)
        assert len(results) == 1
        assert "failure logged" in results[0].get("stdout", "")


class TestSessionEndHook:
    """Tests for SessionEnd hook event."""

    def test_session_end_fires(self, repo_tmp_path: Path) -> None:
        """SessionEnd should fire at session termination."""
        from uagent.hooks_engine import fire_event, load_hooks_registry
        import json

        registry = {
            "plugins": {
                "test": {
                    "SessionEnd": [
                        {
                            "hooks": [
                                {"type": "command", "command": "echo 'session ended'"}
                            ]
                        }
                    ]
                }
            }
        }
        path = repo_tmp_path / "se_hooks.json"
        path.write_text(json.dumps(registry), encoding="utf-8")

        hooks = load_hooks_registry(str(path))
        results = fire_event("SessionEnd", hooks)
        assert len(results) == 1
        assert "session ended" in results[0].get("stdout", "")
