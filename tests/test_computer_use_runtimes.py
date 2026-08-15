from uagent.computer_use.actions import ComputerAction
from uagent.computer_use.runtimes.browser import BrowserRuntime
from uagent.computer_use.runtimes.desktop import DesktopRuntime


class FakeMouse:
    def __init__(self):
        self.calls = []

    def click(self, x, y, button="left"):
        self.calls.append(("click", x, y, button))

    def move(self, x, y):
        self.calls.append(("move", x, y))

    def wheel(self, dx, dy):
        self.calls.append(("wheel", dx, dy))


class FakeKeyboard:
    def __init__(self):
        self.calls = []

    def type(self, text):
        self.calls.append(("type", text))

    def press(self, key):
        self.calls.append(("press", key))


class FakePage:
    def __init__(self):
        self.mouse = FakeMouse()
        self.keyboard = FakeKeyboard()

    def screenshot(self):
        return b"browser-png"


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
