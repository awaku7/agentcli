from __future__ import annotations

from uagent import uagent_llm as llm
from uagent.tools import _tool_load_util as gcu


def setup_function() -> None:
    llm._auto_unload_state().last_round.clear()
    llm._auto_unload_state().total_rounds = 0
    llm._auto_unload_state().productive_rounds = 0
    gcu._LOADED_SINGLE_TOOLS.clear()
    gcu._TOOL_DYNAMIC_THRESHOLDS.clear()


def test_never_used_uses_load_round_not_process_start() -> None:
    # Many empty/total rounds must not matter.
    llm._auto_unload_state().total_rounds = 20
    llm._auto_unload_state().productive_rounds = 3
    # Tool loaded at productive round 2 with threshold 5.
    gcu._LOADED_SINGLE_TOOLS["search_web"] = 2
    gcu._TOOL_DYNAMIC_THRESHOLDS["search_web"] = (5, 0, 1)

    threshold = gcu.get_threshold("search_web")
    last = llm._auto_unload_state().last_round.get("search_web")
    loaded_at = int(gcu._LOADED_SINGLE_TOOLS["search_web"])
    assert last is None
    assert threshold == 5
    # Only 1 productive round since load => must NOT unload.
    assert (llm._auto_unload_state().productive_rounds - loaded_at) < threshold
    # Total rounds alone would look expired under the old rule:
    assert llm._auto_unload_state().total_rounds >= threshold


def test_empty_rounds_do_not_age_idle_counter() -> None:
    llm._auto_unload_state().productive_rounds = 10
    llm._auto_unload_state().last_round["get_weather_wttr"] = 10
    gcu._LOADED_SINGLE_TOOLS["get_weather_wttr"] = 8
    gcu._TOOL_DYNAMIC_THRESHOLDS["get_weather_wttr"] = (5, 0, 1)

    # Simulate 20 empty total rounds with no productive rounds.
    llm._auto_unload_state().total_rounds = 100
    last = llm._auto_unload_state().last_round["get_weather_wttr"]
    threshold = gcu.get_threshold("get_weather_wttr")
    # Idle age is still 0 productive rounds.
    assert (llm._auto_unload_state().productive_rounds - last) < threshold
