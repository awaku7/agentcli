from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from uagent.tools import human_ask_tool


def test_parallel_human_asks_are_serialized(monkeypatch):
    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()
    active = 0
    max_active = 0
    state_lock = threading.Lock()

    def fake_run(args):
        nonlocal active, max_active
        with state_lock:
            active += 1
            max_active = max(max_active, active)
        try:
            if args["message"] == "first":
                first_entered.set()
                assert release_first.wait(timeout=5)
            else:
                second_entered.set()
            return args["message"]
        finally:
            with state_lock:
                active -= 1

    monkeypatch.setattr(human_ask_tool, "_run_tool_unserialized", fake_run)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(human_ask_tool.run_tool, {"message": "first"})
        assert first_entered.wait(timeout=5)

        second = executor.submit(human_ask_tool.run_tool, {"message": "second"})
        assert not second_entered.wait(timeout=0.1)

        release_first.set()
        assert first.result(timeout=5) == "first"
        assert second.result(timeout=5) == "second"

    assert max_active == 1
