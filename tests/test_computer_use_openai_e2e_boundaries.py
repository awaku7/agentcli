import json
from types import SimpleNamespace


def test_openai_runtime_factory_does_not_create_playwright(monkeypatch):
    import uagent.computer_use.entrypoint_runtime as entrypoint

    calls = []
    desktop = entrypoint.EntrypointRuntimeManager("desktop")

    def no_browser():
        calls.append("browser")
        raise AssertionError("BrowserRuntime must not be created for OpenAI native")

    def make_desktop():
        calls.append("desktop")
        return desktop

    monkeypatch.setenv("UAGENT_COMPUTER_USE", "1")
    monkeypatch.setattr(entrypoint, "_create_browser_runtime", no_browser)
    monkeypatch.setattr(entrypoint, "_create_desktop_runtime", make_desktop)

    manager = entrypoint.create_runtime_from_env(
        force=True, provider="azure-openai", environment="desktop"
    )

    assert manager is not None
    assert calls == ["desktop"]
    assert manager.runtimes == {"desktop": "desktop"}


def test_gemini_browser_runtime_is_selected_without_desktop(monkeypatch):
    import uagent.computer_use.entrypoint_runtime as entrypoint

    calls = []
    browser = entrypoint.EntrypointRuntimeManager("browser")

    def make_browser():
        calls.append("browser")
        return browser

    def no_desktop():
        calls.append("desktop")
        raise AssertionError("DesktopRuntime must not be created for Gemini browser")

    monkeypatch.setenv("UAGENT_COMPUTER_USE", "1")
    monkeypatch.setattr(entrypoint, "_create_browser_runtime", make_browser)
    monkeypatch.setattr(entrypoint, "_create_desktop_runtime", no_desktop)

    manager = entrypoint.create_runtime_from_env(
        force=True, provider="gemini", environment="browser"
    )

    assert manager is not None
    assert calls == ["browser"]
    assert manager.runtimes == {"browser": "browser"}


def test_open_url_normalizes_to_navigate():
    from uagent.computer_use.actions import normalize_action

    action = normalize_action(
        action_id="call-1",
        payload={"action": "open_url", "text": "https://example.com"},
    )

    assert action.action == "navigate"
    assert action.text == "https://example.com"


def test_openai_native_computer_output_uses_original_screenshot_detail():
    from uagent.providers.llm_openai_responses import _responses_tool_output

    content = json.dumps(
        {
            "success": True,
            "screenshot_data": "ZmFrZQ==",
            "screenshot_media_type": "image/png",
        }
    )
    core = SimpleNamespace(computer_use_native_active=True)

    result = _responses_tool_output("call-native", content, "computer", core)

    assert result["type"] == "computer_call_output"
    assert result["output"]["type"] == "computer_screenshot"
    assert result["output"]["detail"] == "original"
    assert result["output"]["image_url"] == "data:image/png;base64,ZmFrZQ=="


def test_openai_native_computer_output_uses_last_screenshot_in_action_batch():
    from uagent.providers.llm_openai_responses import _responses_tool_output

    content = json.dumps(
        {
            "success": True,
            "results": [
                {
                    "screenshot_data": "aW50ZXJtZWRpYXRl",
                    "screenshot_media_type": "image/png",
                },
                {
                    "screenshot_data": "ZmluYWw=",
                    "screenshot_media_type": "image/png",
                },
            ],
        }
    )
    core = SimpleNamespace(computer_use_native_active=True)

    result = _responses_tool_output("call-batch", content, "computer", core)

    assert result["output"]["image_url"] == "data:image/png;base64,ZmluYWw="


def test_openai_responses_local_computer_result_is_not_native():
    from uagent.providers.llm_openai_responses import _responses_tool_output

    content = json.dumps(
        {
            "success": True,
            "screenshot_data": "ZmFrZQ==",
            "screenshot_media_type": "image/png",
        }
    )
    core = SimpleNamespace(
        computer_use_native_tool={"type": "computer"},
        computer_use_native_active=False,
        computer_use_runtime=None,
    )

    result = _responses_tool_output("call-1", content, "computer", core)

    assert result["type"] == "function_call_output"
    assert result["call_id"] == "call-1"
    assert "computer_screenshot" not in result



def test_openai_native_computer_output_fails_when_screenshot_is_unavailable():
    import pytest

    from uagent.providers.llm_openai_responses import _responses_tool_output

    class BrokenRuntime:
        def screenshot(self):
            raise RuntimeError("capture failed")

    content = json.dumps({"success": False, "screenshot_data": None})
    core = SimpleNamespace(
        computer_use_native_active=True,
        computer_use_runtime=BrokenRuntime(),
    )

    with pytest.raises(RuntimeError, match="requires a screenshot"):
        _responses_tool_output("call-no-shot", content, "computer", core)
