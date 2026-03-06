from __future__ import annotations

import json
import os
from types import SimpleNamespace

from uagent import tools
from uagent.llm_openai_responses import build_responses_request
from uagent.uagent_llm import (
    _is_gpt54_tool_search_target,
    _select_tool_specs_for_gpt54,
    run_llm_rounds,
)


class _DummyResponses:
    def __init__(self, outputs=None) -> None:
        self.calls = []
        self.outputs = list(outputs or [])

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.outputs:
            return self.outputs.pop(0)
        return SimpleNamespace(output=[])


class _DummyOpenAICompletions:
    def __init__(self) -> None:
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        msg = SimpleNamespace(content="ok", tool_calls=[])
        choice = SimpleNamespace(message=msg)
        return SimpleNamespace(choices=[choice])


class _DummyChat:
    def __init__(self) -> None:
        self.completions = _DummyOpenAICompletions()


class _DummyFullClient:
    def __init__(self, responses_outputs=None) -> None:
        self.responses = _DummyResponses(outputs=responses_outputs)
        self.chat = _DummyChat()


class _DummyCore:
    SYSTEM_PROMPT = "sys"
    _is_web = False

    def __init__(self) -> None:
        self.logged = []

    def set_status(self, busy, label):
        return None

    def log_message(self, msg):
        self.logged.append(msg)

    def sanitize_messages_for_tools(self, messages):
        return messages

    def compress_history_with_llm(self, client, depname, messages, keep_last):
        return messages

    def rewrite_current_log_from_messages(self, messages):
        return None

    def build_tools_system_prompt(self, tool_specs):
        return "tools"


class _CatalogPatch:
    def __init__(self, rows):
        self.rows = rows
        self.orig = None

    def __enter__(self):
        self.orig = tools.get_tool_catalog
        rows = self.rows

        def _fake_get_tool_catalog(*, query, max_results=12, tool_specs=None):
            return rows[:max_results]

        tools.get_tool_catalog = _fake_get_tool_catalog
        return self

    def __exit__(self, exc_type, exc, tb):
        tools.get_tool_catalog = self.orig
        return False


class _RunToolPatch:
    def __init__(self, result_by_name=None):
        self.result_by_name = dict(result_by_name or {})
        self.calls = []
        self.orig = None

    def __enter__(self):
        self.orig = tools.run_tool
        result_by_name = self.result_by_name
        calls = self.calls

        def _fake_run_tool(name, args):
            calls.append({"name": name, "args": args})
            if name in result_by_name:
                value = result_by_name[name]
                return value(args) if callable(value) else value
            return json.dumps({"ok": True, "name": name, "args": args}, ensure_ascii=False)

        tools.run_tool = _fake_run_tool
        return self

    def __exit__(self, exc_type, exc, tb):
        tools.run_tool = self.orig
        return False


class _ToolSpecsPatch:
    def __init__(self, specs):
        self.specs = specs
        self.orig = None

    def __enter__(self):
        self.orig = tools.get_tool_specs
        specs = self.specs

        def _fake_get_tool_specs():
            return [dict(item) for item in specs]

        tools.get_tool_specs = _fake_get_tool_specs
        return self

    def __exit__(self, exc_type, exc, tb):
        tools.get_tool_specs = self.orig
        return False


def _set_responses_env(value: str | None):
    old_env = os.environ.get("UAGENT_RESPONSES")
    if value is None:
        os.environ.pop("UAGENT_RESPONSES", None)
    else:
        os.environ["UAGENT_RESPONSES"] = value
    return old_env


def _restore_responses_env(old_env: str | None) -> None:
    if old_env is None:
        os.environ.pop("UAGENT_RESPONSES", None)
    else:
        os.environ["UAGENT_RESPONSES"] = old_env


def _set_streaming_env(value: str | None):
    old_env = os.environ.get("UAGENT_STREAMING")
    if value is None:
        os.environ.pop("UAGENT_STREAMING", None)
    else:
        os.environ["UAGENT_STREAMING"] = value
    return old_env


def _restore_streaming_env(old_env: str | None) -> None:
    if old_env is None:
        os.environ.pop("UAGENT_STREAMING", None)
    else:
        os.environ["UAGENT_STREAMING"] = old_env


def _response_with_function_call(name: str, arguments: dict, *, call_id: str = "call_1"):
    return SimpleNamespace(
        output=[
            SimpleNamespace(
                type="function_call",
                name=name,
                arguments=json.dumps(arguments, ensure_ascii=False),
                call_id=call_id,
            )
        ]
    )


def _response_with_message(text: str):
    return SimpleNamespace(
        output=[
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type="output_text", text=text)],
            )
        ]
    )


def _tool_spec(name: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": f"desc for {name}",
            "parameters": {"type": "object", "properties": {}},
        },
    }


def test_is_gpt54_tool_search_target() -> None:
    assert _is_gpt54_tool_search_target(
        provider="openai", depname="gpt-5.4", use_responses_api=True
    )
    assert _is_gpt54_tool_search_target(
        provider="azure", depname="gpt-5.4-mini", use_responses_api=True
    )
    assert _is_gpt54_tool_search_target(
        provider="openrouter", depname="openai/gpt-5.4", use_responses_api=True
    )
    assert _is_gpt54_tool_search_target(
        provider="openrouter", depname="openai/gpt-5.4-pro", use_responses_api=True
    )
    assert _is_gpt54_tool_search_target(
        provider="openai", depname="gpt-5.4-codex", use_responses_api=True
    )
    assert _is_gpt54_tool_search_target(
        provider="openai", depname="gpt-5.5", use_responses_api=True
    )
    assert _is_gpt54_tool_search_target(
        provider="openrouter", depname="openai/gpt-5.10-pro", use_responses_api=True
    )
    assert not _is_gpt54_tool_search_target(
        provider="openai", depname="gpt-5.3", use_responses_api=True
    )
    assert not _is_gpt54_tool_search_target(
        provider="openai", depname="gpt-4.1", use_responses_api=True
    )
    assert not _is_gpt54_tool_search_target(
        provider="openai", depname="gpt-5", use_responses_api=True
    )
    assert not _is_gpt54_tool_search_target(
        provider="openai", depname="gpt-5.4", use_responses_api=False
    )


def test_build_responses_request_uses_explicit_tool_specs() -> None:
    instructions, input_msgs, req_tools = build_responses_request(
        [{"role": "user", "content": "hi"}],
        send_tools_this_round=True,
        provider="openai",
        tool_specs=[],
    )
    assert instructions is not None
    assert input_msgs
    assert req_tools == []


def test_tool_catalog_tool_is_registered() -> None:
    names = {
        spec.get("function", {}).get("name")
        for spec in tools.get_tool_specs()
        if isinstance(spec, dict)
    }
    assert "tool_catalog" in names

    out = tools.run_tool("tool_catalog", {"query": "read file", "max_results": 5})
    data = json.loads(out)
    assert data["ok"] is True
    assert data["count"] >= 1
    assert any(item.get("name") == "read_file" for item in data["tools"])


def test_select_tool_specs_for_gpt54_keeps_catalog_and_human_ask() -> None:
    with _CatalogPatch(
        [
            {
                "name": "read_file",
                "description": "read a file",
                "required": [],
                "parameters": [],
            }
        ]
    ):
        selected = _select_tool_specs_for_gpt54(
            [{"role": "user", "content": "please read a file"}]
        )

    names = {
        spec.get("function", {}).get("name")
        for spec in (selected or [])
        if isinstance(spec, dict)
    }
    assert "read_file" in names
    assert "tool_catalog" in names
    assert "human_ask" in names


def test_select_tool_specs_for_gpt54_zero_hit_fallback_still_keeps_catalog_and_human_ask() -> None:
    with _CatalogPatch([]):
        selected = _select_tool_specs_for_gpt54(
            [{"role": "user", "content": "totally ambiguous request"}]
        )

    names = {
        spec.get("function", {}).get("name")
        for spec in (selected or [])
        if isinstance(spec, dict)
    }
    assert "tool_catalog" in names
    assert "human_ask" in names
    assert "read_file" in names
    assert "search_files" in names
    assert "get_workdir" in names


def test_run_llm_rounds_gpt54_responses_uses_narrowed_tools() -> None:
    old_env = _set_responses_env("1")
    client = _DummyFullClient()
    core = _DummyCore()
    messages = [{"role": "user", "content": "read a file"}]

    try:
        with _CatalogPatch(
            [
                {
                    "name": "read_file",
                    "description": "read a file",
                    "required": [],
                    "parameters": [],
                }
            ]
        ):
            run_llm_rounds(
                "openai",
                client,
                "gpt-5.4",
                messages,
                core=core,
                make_client_fn=lambda _core: (None, client, None),
                append_result_to_outfile_fn=lambda text: None,
                try_open_images_from_text_fn=lambda text: None,
            )
    finally:
        _restore_responses_env(old_env)

    assert client.responses.calls
    tool_names = [tool.get("name") for tool in client.responses.calls[0].get("tools", [])]
    assert "read_file" in tool_names
    assert "tool_catalog" in tool_names
    assert "human_ask" in tool_names


def test_run_llm_rounds_non_gpt54_responses_keeps_full_tool_surface() -> None:
    old_env = _set_responses_env("1")
    client = _DummyFullClient()
    core = _DummyCore()
    messages = [{"role": "user", "content": "read a file"}]

    try:
        run_llm_rounds(
            "openai",
            client,
            "gpt-5.3",
            messages,
            core=core,
            make_client_fn=lambda _core: (None, client, None),
            append_result_to_outfile_fn=lambda text: None,
            try_open_images_from_text_fn=lambda text: None,
        )
    finally:
        _restore_responses_env(old_env)

    assert client.responses.calls
    full_count = len(tools.get_tool_specs())
    sent_count = len(client.responses.calls[0].get("tools", []))
    assert sent_count == full_count


def test_run_llm_rounds_gpt54_two_stage_tool_flow() -> None:
    old_responses_env = _set_responses_env("1")
    old_streaming_env = _set_streaming_env("0")
    client = _DummyFullClient(
        responses_outputs=[
            _response_with_function_call(
                "tool_catalog",
                {"query": "read file", "max_results": 5},
                call_id="call_catalog",
            ),
            _response_with_function_call(
                "read_file",
                {"path": "README.md", "start_line": 1, "max_lines": 5},
                call_id="call_read",
            ),
            _response_with_message("done"),
        ]
    )
    core = _DummyCore()
    messages = [{"role": "user", "content": "read file"}]

    try:
        with _CatalogPatch(
            [
                {
                    "name": "read_file",
                    "description": "read a file",
                    "required": ["path"],
                    "parameters": ["path", "start_line", "max_lines"],
                }
            ]
        ), _RunToolPatch(
            {
                "tool_catalog": json.dumps(
                    {
                        "ok": True,
                        "query": "read file",
                        "count": 1,
                        "tools": [
                            {
                                "name": "read_file",
                                "description": "read a file",
                                "required": ["path"],
                                "parameters": ["path", "start_line", "max_lines"],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                "read_file": json.dumps(
                    {"ok": True, "path": "README.md", "content": "sample"},
                    ensure_ascii=False,
                ),
            }
        ) as run_patch:
            run_llm_rounds(
                "openai",
                client,
                "gpt-5.4",
                messages,
                core=core,
                make_client_fn=lambda _core: (None, client, None),
                append_result_to_outfile_fn=lambda text: None,
                try_open_images_from_text_fn=lambda text: None,
            )
    finally:
        _restore_streaming_env(old_streaming_env)
        _restore_responses_env(old_responses_env)

    assert len(client.responses.calls) == 3

    first_tool_names = [tool.get("name") for tool in client.responses.calls[0].get("tools", [])]
    second_tool_names = [tool.get("name") for tool in client.responses.calls[1].get("tools", [])]

    assert "tool_catalog" in first_tool_names
    assert "read_file" in first_tool_names
    assert "human_ask" in first_tool_names
    assert "tool_catalog" in second_tool_names
    assert "read_file" in second_tool_names
    assert "human_ask" in second_tool_names

    executed_names = [c["name"] for c in run_patch.calls]
    assert executed_names == ["tool_catalog", "read_file"]

    tool_messages = [m for m in messages if m.get("role") == "tool"]
    assert len(tool_messages) == 2
    assert tool_messages[0]["name"] == "tool_catalog"
    assert tool_messages[1]["name"] == "read_file"


def test_run_llm_rounds_gpt54_two_stage_second_round_is_re_narrowed() -> None:
    old_responses_env = _set_responses_env("1")
    old_streaming_env = _set_streaming_env("0")
    constrained_specs = [
        _tool_spec("tool_catalog"),
        _tool_spec("human_ask"),
        _tool_spec("read_file"),
        _tool_spec("search_files"),
        _tool_spec("get_workdir"),
        _tool_spec("delete_file"),
        _tool_spec("rename_path"),
    ]
    client = _DummyFullClient(
        responses_outputs=[
            _response_with_function_call(
                "tool_catalog",
                {"query": "read file", "max_results": 5},
                call_id="call_catalog",
            ),
            _response_with_function_call(
                "read_file",
                {"path": "README.md", "start_line": 1, "max_lines": 5},
                call_id="call_read",
            ),
            _response_with_message("done"),
        ]
    )
    core = _DummyCore()
    messages = [{"role": "user", "content": "read file"}]

    try:
        with _ToolSpecsPatch(constrained_specs), _CatalogPatch(
            [
                {
                    "name": "read_file",
                    "description": "read a file",
                    "required": ["path"],
                    "parameters": ["path", "start_line", "max_lines"],
                }
            ]
        ), _RunToolPatch(
            {
                "tool_catalog": json.dumps(
                    {
                        "ok": True,
                        "query": "read file",
                        "count": 1,
                        "tools": [
                            {
                                "name": "read_file",
                                "description": "read a file",
                                "required": ["path"],
                                "parameters": ["path", "start_line", "max_lines"],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                "read_file": json.dumps(
                    {"ok": True, "path": "README.md", "content": "sample"},
                    ensure_ascii=False,
                ),
            }
        ):
            run_llm_rounds(
                "openai",
                client,
                "gpt-5.4",
                messages,
                core=core,
                make_client_fn=lambda _core: (None, client, None),
                append_result_to_outfile_fn=lambda text: None,
                try_open_images_from_text_fn=lambda text: None,
            )
    finally:
        _restore_streaming_env(old_streaming_env)
        _restore_responses_env(old_responses_env)

    assert len(client.responses.calls) == 3

    first_tool_names = [tool.get("name") for tool in client.responses.calls[0].get("tools", [])]
    second_tool_names = [tool.get("name") for tool in client.responses.calls[1].get("tools", [])]

    assert set(first_tool_names) == {
        "tool_catalog",
        "human_ask",
        "read_file",
    }
    assert set(second_tool_names) == {
        "tool_catalog",
        "human_ask",
        "read_file",
    }
    assert "delete_file" not in second_tool_names
    assert "rename_path" not in second_tool_names
    assert "search_files" not in second_tool_names
    assert "get_workdir" not in second_tool_names


def test_run_llm_rounds_gpt54_two_stage_zero_hit_fallback_second_round_keeps_safe_subset() -> None:
    old_responses_env = _set_responses_env("1")
    old_streaming_env = _set_streaming_env("0")
    constrained_specs = [
        _tool_spec("tool_catalog"),
        _tool_spec("human_ask"),
        _tool_spec("read_file"),
        _tool_spec("search_files"),
        _tool_spec("get_workdir"),
        _tool_spec("delete_file"),
        _tool_spec("rename_path"),
    ]
    client = _DummyFullClient(
        responses_outputs=[
            _response_with_function_call(
                "tool_catalog",
                {"query": "ambiguous request", "max_results": 5},
                call_id="call_catalog",
            ),
            _response_with_message("done"),
        ]
    )
    core = _DummyCore()
    messages = [{"role": "user", "content": "ambiguous request"}]

    try:
        with _ToolSpecsPatch(constrained_specs), _CatalogPatch([]), _RunToolPatch(
            {
                "tool_catalog": json.dumps(
                    {
                        "ok": True,
                        "query": "ambiguous request",
                        "count": 0,
                        "tools": [],
                    },
                    ensure_ascii=False,
                )
            }
        ) as run_patch:
            run_llm_rounds(
                "openai",
                client,
                "gpt-5.4",
                messages,
                core=core,
                make_client_fn=lambda _core: (None, client, None),
                append_result_to_outfile_fn=lambda text: None,
                try_open_images_from_text_fn=lambda text: None,
            )
    finally:
        _restore_streaming_env(old_streaming_env)
        _restore_responses_env(old_responses_env)

    assert len(client.responses.calls) == 2

    first_tool_names = [tool.get("name") for tool in client.responses.calls[0].get("tools", [])]
    second_tool_names = [tool.get("name") for tool in client.responses.calls[1].get("tools", [])]

    assert set(first_tool_names) == {
        "tool_catalog",
        "human_ask",
        "read_file",
        "search_files",
        "get_workdir",
    }
    assert set(second_tool_names) == {
        "tool_catalog",
        "human_ask",
        "read_file",
        "search_files",
        "get_workdir",
    }
    assert "delete_file" not in second_tool_names
    assert "rename_path" not in second_tool_names

    executed_names = [c["name"] for c in run_patch.calls]
    assert executed_names == ["tool_catalog"]
