"""Tests for the hooks execution engine (hooks_engine.py).

TDD: write tests first, then implement.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

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
        matched = find_matching_hooks(
            "PreToolUse", hooks, tool_name="Write"
        )
        assert len(matched) >= 1

    def test_matcher_no_match(self, hooks_registry: str) -> None:
        """Matcher that doesn't match should return only default hooks."""
        from uagent.hooks_engine import find_matching_hooks, load_hooks_registry

        hooks = load_hooks_registry(hooks_registry)
        matched = find_matching_hooks(
            "PreToolUse", hooks, tool_name="Read"
        )
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
                "Stop": [
                    {"hooks": [{"type": "command", "command": "echo e2e-stop"}]}
                ],
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
