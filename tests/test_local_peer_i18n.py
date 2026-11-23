from __future__ import annotations

from uagent.cli_impl.main import _print_local_message_peers
from uagent.i18n import reset_contextvar_locale, set_contextvar_locale


def test_no_online_local_peers_notice_is_translated_to_japanese(capsys) -> None:
    token = set_contextvar_locale("ja")
    try:
        _print_local_message_peers([])
    finally:
        reset_contextvar_locale(token)

    assert capsys.readouterr().out.strip() == (
        "[LOCAL] 現在オンラインの他のUAGピアはいません。"
    )
