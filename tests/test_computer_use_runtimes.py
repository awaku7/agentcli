from uagent.computer_use.actions import ComputerAction
from uagent.computer_use.runtimes.browser import BrowserRuntime
from uagent.computer_use.runtimes.desktop import DesktopRuntime


class FakeMouse:
    def __init__(self):
        self.calls = []

    def click(self, x, y, button="left", click_count=1):
        call = ("click", x, y, button)
        self.calls.append(call if click_count == 1 else call + (click_count,))

    def move(self, x, y):
        self.calls.append(("move", x, y))

    def wheel(self, dx, dy):
        self.calls.append(("wheel", dx, dy))

    def down(self):
        self.calls.append(("down",))

    def up(self):
        self.calls.append(("up",))


class FakeKeyboard:
    def __init__(self):
        self.calls = []

    def type(self, text):
        self.calls.append(("type", text))

    def press(self, key):
        self.calls.append(("press", key))

    def down(self, key):
        self.calls.append(("down", key))

    def up(self, key):
        self.calls.append(("up", key))


class FakePage:
    def __init__(self):
        self.mouse = FakeMouse()
        self.keyboard = FakeKeyboard()
        self.waits = []

    def screenshot(self):
        return b"browser-png"

    def wait_for_timeout(self, milliseconds):
        self.waits.append(milliseconds)


def test_browser_runtime_translates_actions_without_dom_dependency():
    page = FakePage()
    runtime = BrowserRuntime(page)

    result = runtime.execute(
        ComputerAction(
            action_id="b1",
            action="click",
            coordinate=(10, 20),
            button="left",
        )
    )

    assert result.success is True
    assert page.mouse.calls == [("click", 10, 20, "left")]


def test_browser_runtime_returns_screenshot():
    runtime = BrowserRuntime(FakePage())
    result = runtime.execute(ComputerAction(action_id="b2", action="screenshot"))

    assert result.screenshot.data == b"browser-png"
    assert result.screenshot.media_type == "image/png"


def test_browser_runtime_supports_all_shared_input_actions():
    page = FakePage()
    runtime = BrowserRuntime(page)

    triple = runtime.execute(
        ComputerAction(action_id="b3", action="triple_click", coordinate=(1, 2))
    )
    dragged = runtime.execute(
        ComputerAction(action_id="b4", action="drag", region=(1, 2, 3, 4))
    )
    waited = runtime.execute(ComputerAction(action_id="b5", action="wait", text="0.25"))
    zoomed = runtime.execute(ComputerAction(action_id="b6", action="zoom", text="in"))

    assert triple.success is True
    assert dragged.success is True
    assert waited.success is True
    assert zoomed.success is True
    assert ("click", 1, 2, "left", 3) in page.mouse.calls
    assert page.mouse.calls[-4:] == [
        ("move", 1, 2),
        ("down",),
        ("move", 3, 4),
        ("up",),
    ]
    assert page.waits == [250]
    assert page.keyboard.calls == [("press", "Control+Equal")]


def test_browser_runtime_maps_openai_modifier_keys_scroll_and_drag_path():
    page = FakePage()
    runtime = BrowserRuntime(page)

    click = runtime.execute(
        ComputerAction(
            action_id="openai:0",
            action="click",
            coordinate=(5, 6),
            keys=("CTRL",),
        )
    )
    keypress = runtime.execute(
        ComputerAction(action_id="openai:1", action="keypress", keys=("CTRL", "A"))
    )
    scroll = runtime.execute(
        ComputerAction(
            action_id="openai:2",
            action="scroll",
            coordinate=(7, 8),
            scroll_y=120,
        )
    )
    drag = runtime.execute(
        ComputerAction(
            action_id="openai:3",
            action="drag",
            path=((1, 2), (3, 4), (5, 6)),
        )
    )

    assert all(result.success for result in (click, keypress, scroll, drag))
    assert page.keyboard.calls[:3] == [
        ("down", "Control"),
        ("up", "Control"),
        ("press", "Control+A"),
    ]
    assert ("move", 7, 8) in page.mouse.calls
    assert ("wheel", 0, 120) in page.mouse.calls
    assert page.mouse.calls[-5:] == [
        ("move", 1, 2),
        ("down",),
        ("move", 3, 4),
        ("move", 5, 6),
        ("up",),
    ]


def test_browser_runtime_uses_macos_history_shortcut(monkeypatch):
    import uagent.computer_use.runtimes.browser as browser_module

    monkeypatch.setattr(browser_module.sys, "platform", "darwin")
    page = FakePage()
    result = BrowserRuntime(page).execute(
        ComputerAction(
            action_id="openai:back",
            action="click",
            coordinate=(1, 2),
            button="back",
        )
    )

    assert result.success is True
    assert page.keyboard.calls == [("press", "Meta+ArrowLeft")]


def test_desktop_runtime_delegates_to_backend():
    class Backend:
        def __init__(self):
            self.calls = []

        def execute(self, action):
            self.calls.append(action)
            return {"success": True}

        def screenshot(self):
            return b"desktop-png"

    backend = Backend()
    result = DesktopRuntime(backend).execute(
        ComputerAction(action_id="d1", action="type", text="hello")
    )

    assert result.success is True
    assert backend.calls[0].action_id == "d1"
