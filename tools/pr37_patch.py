from pathlib import Path

path = Path("src/uagent/uagent_llm.py")
text = path.read_text(encoding="utf-8")
old = '''def check_consecutive_tool_calls(
    tool_calls_list: list[dict[str, Any]],
    *,
    record: bool = True,
    threshold: int | None = None,
) -> tuple[bool, str, int]:
    \"\"\"Detect too many consecutive calls of the same tool.

    A different tool starts a new streak. Arguments are intentionally ignored,
    so calls of the same tool with different arguments still count together.
    \"\"\"
    global _CONSECUTIVE_TOOL_CALL_COUNT, _CONSECUTIVE_TOOL_CALL_NAME
    # Keep a model from using one discovery tool as a general-purpose reader.
    # Users can raise this for intentionally long workflows, but the default
    # must be low enough to stop a discovery tool from being selected
    # repeatedly across rounds.
    raw_limit = env_get("UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT", "8")
    try:
        default_limit = max(1, int(raw_limit))
    except (TypeError, ValueError):
        default_limit = 100
    limit = default_limit if threshold is None else max(1, int(threshold))
    if not tool_calls_list:
        if record:
            clear_consecutive_tool_call_streak()
        return False, "", 0

    count = _CONSECUTIVE_TOOL_CALL_COUNT
    name = _CONSECUTIVE_TOOL_CALL_NAME
    for tool_call in tool_calls_list:
        function = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}
        current_name = (
            str(function.get("name", "")).strip() if isinstance(function, dict) else ""
        )
        if not current_name:
            continue
        if current_name == name:
            count += 1
        else:
            name = current_name
            count = 1

    if record:
        _CONSECUTIVE_TOOL_CALL_NAME = name
        _CONSECUTIVE_TOOL_CALL_COUNT = count
    return count >= limit, _("consecutive tool calls"), count
'''
new = '''def check_consecutive_tool_calls(
    tool_calls_list: list[dict[str, Any]],
    *,
    record: bool = True,
    threshold: int | None = None,
) -> tuple[bool, str, int]:
    \"\"\"Detect too many consecutive *rounds* using only the same tool.

    One invocation of this function represents one LLM tool round. Multiple
    calls of the same tool in that round (for example parallel ``read_file``
    calls for different files) count as a single round. A round containing
    more than one tool name resets the streak. Arguments remain intentionally
    ignored here; repeated identical arguments are handled by the general
    tool-loop fingerprint guard.
    \"\"\"
    global _CONSECUTIVE_TOOL_CALL_COUNT, _CONSECUTIVE_TOOL_CALL_NAME
    # Keep a model from using one discovery tool as a general-purpose reader
    # across many consecutive rounds without penalizing legitimate parallel
    # fan-out inside one round.
    raw_limit = env_get("UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT", "8")
    try:
        default_limit = max(1, int(raw_limit))
    except (TypeError, ValueError):
        default_limit = 100
    limit = default_limit if threshold is None else max(1, int(threshold))
    if not tool_calls_list:
        if record:
            clear_consecutive_tool_call_streak()
        return False, "", 0

    round_names: list[str] = []
    for tool_call in tool_calls_list:
        function = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}
        current_name = (
            str(function.get("name", "")).strip() if isinstance(function, dict) else ""
        )
        if current_name and current_name not in round_names:
            round_names.append(current_name)

    if not round_names:
        if record:
            clear_consecutive_tool_call_streak()
        return False, "", 0

    if len(round_names) != 1:
        if record:
            clear_consecutive_tool_call_streak()
        return False, _("consecutive tool calls"), 0

    current_name = round_names[0]
    if current_name == _CONSECUTIVE_TOOL_CALL_NAME:
        count = _CONSECUTIVE_TOOL_CALL_COUNT + 1
    else:
        count = 1

    if record:
        _CONSECUTIVE_TOOL_CALL_NAME = current_name
        _CONSECUTIVE_TOOL_CALL_COUNT = count
    return count >= limit, _("consecutive tool calls"), count
'''
if old not in text:
    raise SystemExit("target function block not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

test_path = Path("tests/test_general_tool_loop.py")
tests = test_path.read_text(encoding="utf-8")
marker = '''\ndef test_empty_round_resets_consecutive_tool_calls() -> None:\n'''
addition = '''\n\ndef test_parallel_same_tool_calls_count_as_one_round() -> None:\n    calls = [_tc("read_file", filename=f"file-{i}.py") for i in range(5)]\n\n    blocked, name, count = check_consecutive_tool_calls(calls, threshold=3)\n    assert blocked is False\n    assert name == "consecutive tool calls"\n    assert count == 1\n\n    blocked, _, count = check_consecutive_tool_calls(\n        [_tc("read_file", filename="next-a.py"), _tc("read_file", filename="next-b.py")],\n        threshold=3,\n    )\n    assert blocked is False\n    assert count == 2\n\n    blocked, name, count = check_consecutive_tool_calls(\n        [_tc("read_file", filename="third.py")], threshold=3\n    )\n    assert blocked is True\n    assert name == "consecutive tool calls"\n    assert count == 3\n\n\ndef test_mixed_tool_round_resets_consecutive_round_streak() -> None:\n    blocked, _, count = check_consecutive_tool_calls(\n        [_tc("read_file", filename="one.py")], threshold=3\n    )\n    assert blocked is False\n    assert count == 1\n\n    blocked, name, count = check_consecutive_tool_calls(\n        [\n            _tc("read_file", filename="two.py"),\n            _tc("list_dir", path="."),\n        ],\n        threshold=3,\n    )\n    assert blocked is False\n    assert name == "consecutive tool calls"\n    assert count == 0\n\n    blocked, _, count = check_consecutive_tool_calls(\n        [_tc("read_file", filename="three.py")], threshold=3\n    )\n    assert blocked is False\n    assert count == 1\n'''
if "def test_parallel_same_tool_calls_count_as_one_round" not in tests:
    if marker not in tests:
        raise SystemExit("test insertion marker not found")
    tests = tests.replace(marker, addition + marker, 1)
test_path.write_text(tests, encoding="utf-8")
