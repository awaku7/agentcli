"""A Stop during a streamed reply must not leave output behind (INT-02).

After a Stop the waiter returns while the abandoned call thread may keep
reading the provider stream. Its tokens must not be printed after the turn
has returned. Runs the real round loop in a subprocess against a local fake
OpenAI-compatible server (tests/fake_openai_stream_server.py).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from uagent.llm_helpers import _LLM_CALL_ABANDONED, is_abandoned_stream_output

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src"

_SCRIPT = r"""
import io, json, os, sys, threading, time
src, tests = sys.argv[1], sys.argv[2]
sys.path[:0] = [src, tests]
import fake_openai_stream_server as fake

port = fake.start()
os.environ.update({
    "UAGENT_PROVIDER": "openai",
    "UAGENT_OPENAI_BASE_URL": f"http://127.0.0.1:{port}/v1",
    "UAGENT_OPENAI_API_KEY": "dummy",
    # A model llmcapa knows: unknown models make plugin loading slow.
    "UAGENT_OPENAI_DEPNAME": "gpt-4o-mini",
    "UAGENT_RESPONSES": "1",
    "UAGENT_STREAMING": "1",
})

writes = []
class Recorder(io.TextIOBase):
    def write(self, s):
        if s:
            writes.append((time.time(), s))
        return len(s)
    def flush(self):
        pass

from uagent import core, tools
from uagent.providers import util_providers as providers
from uagent import uagent_llm

provider, client, depname = providers.make_client(core)
tools._ensure_loaded()
messages = [{"role": "user", "content": "count"}]
marks = {}

def stop_mid_stream():
    deadline = time.time() + 60
    while time.time() < deadline:
        live = [s for s in fake.STATS if s["path"].endswith("/responses")]
        if live and live[-1]["sent"] >= 10:
            break
        time.sleep(0.005)
    marks["stop"] = time.time()
    with core.interrupt_lock:
        core.interrupt_requested = True

real_stdout = sys.stdout
sys.stdout = Recorder()
threading.Thread(target=stop_mid_stream, daemon=True).start()
uagent_llm.run_llm_rounds(
    provider, client, depname, messages, core=core,
    make_client_fn=providers.make_client,
    append_result_to_outfile_fn=lambda *a, **k: None,
    try_open_images_from_text_fn=lambda *a, **k: None,
)
marks["returned"] = time.time()
time.sleep(fake.N_CHUNKS * fake.DT + 0.8)  # longer than the rest of the stream
sys.stdout = real_stdout
late = "".join(s for t, s in writes if t >= marks["returned"])
print("RESULT=" + json.dumps({
    "stopped": "stop" in marks,
    "return_after_stop_s": marks["returned"] - marks.get("stop", marks["returned"]),
    "late_tokens": late.count("tok"),
    "assistant_messages": sum(1 for m in messages if m.get("role") == "assistant"),
}), flush=True)
os._exit(0)
"""


def test_stop_mid_stream_leaves_no_output_after_the_turn(tmp_path) -> None:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.update(
        {
            "UAGENT_STATE_DIR": str(tmp_path / "state"),
            "UAGENT_WORKDIR": str(tmp_path),
            "UAGENT_AUTO_INSTALL": "off",
            "UAGENT_TOOLS_WARMUP": "0",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(SRC_DIR), str(TESTS_DIR)],
        cwd=str(tmp_path),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT=")]
    assert lines, proc.stderr[-3000:]
    result = json.loads(lines[-1][len("RESULT=") :])
    assert result["stopped"] is True
    assert result["return_after_stop_s"] < 1.0
    assert result["late_tokens"] == 0
    assert result["assistant_messages"] == 0


@pytest.fixture
def abandoned():
    import threading

    signal = threading.Event()
    signal.set()
    token = _LLM_CALL_ABANDONED.set(signal)
    yield
    _LLM_CALL_ABANDONED.reset(token)


def test_display_helpers_drop_output_of_an_abandoned_call(abandoned, capsys) -> None:
    from uagent import core  # core_impl.display must be imported via core

    core.print_stream_delta("late token")
    core.print_reasoning_delta("late reasoning")
    assert capsys.readouterr().out == ""


def test_display_helpers_still_print_for_a_live_call(capsys, monkeypatch) -> None:
    from uagent import core
    from uagent.core_impl import display

    monkeypatch.setattr(display, "_stop_spinner_quietly", lambda: None)
    core.print_stream_delta("live token")
    assert "live token" in capsys.readouterr().out


def test_only_stream_messages_of_an_abandoned_call_are_dropped(abandoned) -> None:
    assert is_abandoned_stream_output({"type": "assistant_stream_delta", "delta": "x"})
    assert is_abandoned_stream_output({"type": "assistant_reasoning_delta"})
    assert not is_abandoned_stream_output({"role": "assistant", "content": "x"})


def test_stream_messages_of_a_live_call_are_kept() -> None:
    assert not is_abandoned_stream_output({"type": "assistant_stream_delta"})
