from __future__ import annotations

from types import SimpleNamespace

from uagent.util_tools import handle_command


class _EmptySessionStore:
    def list_sessions(self):
        return []


def _core(*, store=None):
    return SimpleNamespace(
        tr=lambda text: text,
        session_store=store,
        session_id=None,
    )


def test_sessions_aliases_share_the_same_list_dispatch(capsys) -> None:
    store = _EmptySessionStore()

    assert (
        handle_command(":sessions list", [], None, "", core=_core(store=store)) is True
    )
    plural_output = capsys.readouterr().out

    assert (
        handle_command(":session list", [], None, "", core=_core(store=store)) is True
    )
    singular_output = capsys.readouterr().out

    assert plural_output == singular_output
    assert plural_output == ""


def test_sessions_list_reports_opt_in_requirement(capsys) -> None:
    assert handle_command(":sessions list", [], None, "", core=_core()) is True

    output = capsys.readouterr().out.strip()
    assert output.startswith("[sessions] ")
    assert output


def test_sessions_search_reports_missing_query_without_touching_state(capsys) -> None:
    core = _core(store=_EmptySessionStore())

    assert handle_command(":sessions search", [], None, "", core=core) is True

    assert capsys.readouterr().out.strip() == ":sessions search <query>"
    assert not hasattr(core, "_session_search_results")
