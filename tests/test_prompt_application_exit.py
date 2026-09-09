from __future__ import annotations

from uagent.cli_impl.input_ui import _exit_prompt_application


class _RunningApp:
    is_running = True

    def __init__(self) -> None:
        self.called = False

    def exit(self, *, result: object) -> None:
        self.called = True
        assert result is None


class _StoppedApp:
    is_running = False

    def exit(self, **_kwargs: object) -> None:
        raise AssertionError("a stopped application must not be exited")


class _RacingApp:
    is_running = True

    def exit(self, **_kwargs: object) -> None:
        raise Exception("Application is not running. Application.exit() failed.")


def test_exit_prompt_application_exits_running_app() -> None:
    app = _RunningApp()

    _exit_prompt_application(app)

    assert app.called


def test_exit_prompt_application_ignores_stopped_app() -> None:
    _exit_prompt_application(_StoppedApp())


def test_exit_prompt_application_swallows_prompt_toolkit_race() -> None:
    _exit_prompt_application(_RacingApp())
