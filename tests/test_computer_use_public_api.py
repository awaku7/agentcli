import sys
from types import SimpleNamespace

sys.path.insert(0, "src")


def test_unavailable_handler_is_public_and_all_is_unique():
    import uagent.computer_use as computer_use

    assert callable(computer_use.make_unavailable_computer_use_handler)
    assert len(computer_use.__all__) == len(set(computer_use.__all__))


def test_native_preparation_clears_stale_state_for_unsupported_provider():
    from uagent.computer_use.native import prepare_native_computer_use

    core = SimpleNamespace(
        computer_use_native_tool={"type": "computer"},
        computer_use_native_headers=["stale"],
        computer_use_native_provider="openai",
    )

    assert (
        prepare_native_computer_use(core=core, provider="ollama", model="local")
        is False
    )
    assert core.computer_use_native_tool is None
    assert core.computer_use_native_headers is None
    assert core.computer_use_native_provider is None


def test_runtime_factory_is_opt_in(monkeypatch):
    from uagent.computer_use.entrypoint_runtime import create_runtime_from_env

    monkeypatch.delenv("UAGENT_COMPUTER_USE", raising=False)
    assert create_runtime_from_env() is None


def test_gpt56_luna_uses_official_computer_use_compatibility_override():
    from uagent.computer_use.capability import get_computer_use_capability

    capability = get_computer_use_capability("gpt-5.6-luna", "openai")
    assert capability.supported is True
    assert capability.native is True
    assert capability.tool_type == "computer"
    assert capability.api_type == "responses"
