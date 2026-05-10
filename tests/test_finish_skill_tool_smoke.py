import json

from uagent.tools.context import ToolCallbacks, init_callbacks
from uagent.tools.finish_skill_tool import run_tool
from uagent.tools.skill_history import make_finish_skill_handler


class DummyCore:
    def __init__(self):
        self.rewritten = []

    def rewrite_current_log_from_messages(self, messages):
        self.rewritten.append([dict(m) for m in messages])
        return "dummy.log"


def test_finish_skill_tool_clears_skill_messages():
    messages = [
        {"role": "system", "content": "[SKILL] name=demo"},
        {"role": "user", "content": "hello"},
    ]
    core = DummyCore()
    init_callbacks(
        ToolCallbacks(finish_skill=make_finish_skill_handler(messages, core))
    )
    try:
        payload = json.loads(run_tool({"message": "Done"}))
        assert payload["status"] == "ok"
        assert "Cleared 1 skill messages" in payload["message"]
        assert messages == [{"role": "user", "content": "hello"}]
        assert core.rewritten
    finally:
        init_callbacks(ToolCallbacks())
