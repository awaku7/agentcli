from pathlib import Path

flow_path = Path("src/uagent/llm_flow_helpers.py")
flow = flow_path.read_text(encoding="utf-8")

old = '''    executed_new_tool = False\n    fresh_tool_calls: list[dict[str, Any]] = []\n    pending_auto_user_msgs: list[dict[str, Any]] = []\n'''
new = '''    # Session resume is a control-transfer tool. If a provider emits it beside\n    # ordinary tools, execute only the resume call so no stale-session work can\n    # run before the queued :sessions load command is handled by the host loop.\n    session_resume_calls = [\n        tc\n        for tc in tool_calls_list\n        if isinstance(tc, dict)\n        and isinstance(tc.get("function"), dict)\n        and str(tc["function"].get("name") or "") == "session_resume"\n    ]\n    if session_resume_calls:\n        tool_calls_list = [session_resume_calls[0]]\n\n    executed_new_tool = False\n    fresh_tool_calls: list[dict[str, Any]] = []\n    pending_auto_user_msgs: list[dict[str, Any]] = []\n'''
if old in flow:
    flow = flow.replace(old, new, 1)
elif new not in flow:
    raise SystemExit("tool executor insertion point not found")

old = '''        try:\n            parsed_tool_result = json.loads(tool_result)\n        except Exception:\n            parsed_tool_result = None\n        if isinstance(parsed_tool_result, dict):\n'''
new = '''        try:\n            parsed_tool_result = json.loads(tool_result)\n        except Exception:\n            parsed_tool_result = None\n        session_resume_control_transfer = bool(\n            name == "session_resume"\n            and isinstance(parsed_tool_result, dict)\n            and parsed_tool_result.get("ok") is True\n            and parsed_tool_result.get("status") == "queued"\n            and parsed_tool_result.get("control_transfer") is True\n        )\n        if isinstance(parsed_tool_result, dict):\n'''
if old in flow:
    flow = flow.replace(old, new, 1)
elif new not in flow:
    raise SystemExit("tool result parse insertion point not found")

old = '''        elif not host_ui_active:\n            core.log_message(tool_msg)\n\n        # Responses API continuations must place function outputs directly\n'''
new = '''        elif not host_ui_active:\n            core.log_message(tool_msg)\n\n        if session_resume_control_transfer:\n            try:\n                core._session_resume_control_transfer = True\n            except Exception:\n                pass\n            break\n\n        # Responses API continuations must place function outputs directly\n'''
if old in flow:
    flow = flow.replace(old, new, 1)
elif new not in flow:
    raise SystemExit("control transfer break insertion point not found")

flow_path.write_text(flow, encoding="utf-8")

llm_path = Path("src/uagent/uagent_llm.py")
llm = llm_path.read_text(encoding="utf-8")
old = '''    executed_new_tool, fresh_tool_calls = execute_tool_continuation(\n        tool_calls_list=tool_calls_list,\n        messages=messages,\n        core=core,\n        cache_mgr=cache_mgr,\n        responses_api_continuation=response_tool_continuation,\n        responses_runtime=getattr(core, "responses_runtime", None),\n    )\n    if provider in ("gemini", "vertexai") and any(\n'''
new = '''    executed_new_tool, fresh_tool_calls = execute_tool_continuation(\n        tool_calls_list=tool_calls_list,\n        messages=messages,\n        core=core,\n        cache_mgr=cache_mgr,\n        responses_api_continuation=response_tool_continuation,\n        responses_runtime=getattr(core, "responses_runtime", None),\n    )\n    if bool(getattr(core, "_session_resume_control_transfer", False)):\n        try:\n            core._session_resume_control_transfer = False\n        except Exception:\n            pass\n        core._last_round_reason = "session_resume"\n        return (\n            _RS_BREAK,\n            client,\n            gemini_cache_name,\n            empty_no_tool_rounds,\n            assistant_text,\n        )\n    if provider in ("gemini", "vertexai") and any(\n'''
if old in llm:
    llm = llm.replace(old, new, 1)
elif new not in llm:
    raise SystemExit("uagent_llm control transfer insertion point not found")
llm_path.write_text(llm, encoding="utf-8")

control_test = Path("tests/test_session_resume_control_transfer.py")
if not control_test.exists():
    control_test.write_text(
        '''from __future__ import annotations\n\nimport json\nfrom types import SimpleNamespace\n\nfrom uagent.llm_flow_helpers import _execute_tool_calls\n\n\nclass _Cache:\n    def record_file_access(self, filename):\n        pass\n\n\ndef test_session_resume_is_exclusive_and_requests_round_stop(monkeypatch):\n    calls = []\n\n    def run_tool(name, args):\n        calls.append(name)\n        if name == "session_resume":\n            return json.dumps(\n                {\n                    "ok": True,\n                    "status": "queued",\n                    "control_transfer": True,\n                    "session_id": "yesterday-session",\n                }\n            )\n        raise AssertionError(f"unexpected stale-session tool execution: {name}")\n\n    monkeypatch.setattr(\n        "uagent.llm_flow_helpers.tools.is_parallel_safe", lambda *args: False\n    )\n    monkeypatch.setattr("uagent.llm_flow_helpers.tools.run_tool", run_tool)\n\n    messages = []\n    core = SimpleNamespace(\n        show_tool_output=False,\n        set_status=lambda *args: None,\n        log_message=lambda message: None,\n    )\n    tool_calls = [\n        {\n            "id": "resume-1",\n            "type": "function",\n            "function": {"name": "session_resume", "arguments": "{}"},\n        },\n        {\n            "id": "list-1",\n            "type": "function",\n            "function": {"name": "list_dir", "arguments": "{}"},\n        },\n    ]\n\n    executed, fresh = _execute_tool_calls(\n        tool_calls_list=tool_calls,\n        messages=messages,\n        core=core,\n        cache_mgr=_Cache(),\n    )\n\n    assert executed is True\n    assert calls == ["session_resume"]\n    assert [item["id"] for item in fresh] == ["resume-1"]\n    assert core._session_resume_control_transfer is True\n    assert len(messages) == 1\n    assert messages[0]["name"] == "session_resume"\n''',
        encoding="utf-8",
    )
