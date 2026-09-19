from __future__ import annotations

from types import SimpleNamespace

from uagent.runtime.agent_state import AgentState, AgentStateManager
from uagent.util_common import _host_is_cancelled, _mcp_generation


def test_mcp_generation_restores_and_persists_on_cancel() -> None:
    saved: list[dict] = []
    manager = AgentStateManager(AgentState(mcp_request_generation=7))
    core = SimpleNamespace(
        interrupt_requested=True,
        cancellation_token=SimpleNamespace(is_cancelled=lambda: False),
        agent_state_manager=manager,
        save_agent_state=saved.append,
    )

    assert _mcp_generation(core) == 7
    assert _host_is_cancelled(core) is True
    assert core.mcp_request_generation == 8
    assert saved[-1]["mcp_request_generation"] == 8
    assert _host_is_cancelled(core) is True
    assert len(saved) == 1
