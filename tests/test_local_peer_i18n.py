from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

from uagent.cli_impl import main as cli_main
from uagent.i18n import _, reset_contextvar_locale, set_contextvar_locale
from uagent.tools import local_messaging_tool


def test_no_online_local_peers_notice_is_translated_to_japanese(capsys) -> None:
    token = set_contextvar_locale("ja")
    try:
        cli_main._print_local_message_peers([])
    finally:
        reset_contextvar_locale(token)

    assert capsys.readouterr().out.strip() == (
        "[LOCAL] 現在オンラインの他のUAGピアはいません。"
    )


def test_other_cli_local_peer_notices_have_japanese_translations() -> None:
    token = set_contextvar_locale("ja")
    try:
        translated = [
            _("[LOCAL] Available UAG peers:"),
            _("[LOCAL] Incoming message was rejected or expired."),
            _("[LOCAL] Local messaging could not start: %(error)s"),
            _("[LOCAL] Another UAG peer is online: %(endpoint)s (pid=%(pid)s)"),
            _("[LOCAL] Local messaging shutdown failed: %(error)s"),
            _("[LOCAL] Web messaging event failed: %(error_type)s."),
            _("[LOCAL] Another UAG peer is online: %(entrypoint)s (PID %(pid)s)."),
            _("[LOCAL] Could not start the accepted message turn: %(error_type)s."),
        ]
    finally:
        reset_contextvar_locale(token)

    assert translated == [
        "[LOCAL] 利用可能なUAGピア:",
        "[LOCAL] 受信メッセージは拒否されたか、有効期限切れです。",
        "[LOCAL] ローカルメッセージングを開始できませんでした: %(error)s",
        "[LOCAL] 別のUAGピアがオンラインです: %(endpoint)s (pid=%(pid)s)",
        "[LOCAL] ローカルメッセージングの停止に失敗しました: %(error)s",
        "[LOCAL] Webメッセージングのイベントでエラーが発生しました: %(error_type)s。",
        "[LOCAL] 別のUAGピアがオンラインです: %(entrypoint)s (PID %(pid)s)。",
        "[LOCAL] 受信したメッセージのターンを開始できませんでした: %(error_type)s。",
    ]


def test_local_peer_notices_are_translated_in_all_shipped_locales() -> None:
    locales_dir = Path(__file__).resolve().parents[1] / "src" / "uagent" / "locales"
    msgids = [
        "[LOCAL] No other participating UAG peers are currently online.",
        "[LOCAL] Available UAG peers:",
        "[LOCAL] Incoming message was rejected or expired.",
        "[LOCAL] Local messaging could not start: %(error)s",
        "[LOCAL] Another UAG peer is online: %(endpoint)s (pid=%(pid)s)",
        "[LOCAL] Local messaging shutdown failed: %(error)s",
        "[LOCAL] Web messaging event failed: %(error_type)s.",
        "[LOCAL] Another UAG peer is online: %(entrypoint)s (PID %(pid)s).",
        "[LOCAL] Could not start the accepted message turn: %(error_type)s.",
    ]

    for locale_dir in locales_dir.iterdir():
        if not locale_dir.is_dir() or locale_dir.name == "en":
            continue
        token = set_contextvar_locale(locale_dir.name)
        try:
            translated = [_(msgid) for msgid in msgids]
        finally:
            reset_contextvar_locale(token)

        assert all(text != msgid for text, msgid in zip(translated, msgids)), (
            locale_dir.name,
            translated,
        )


def test_rejected_incoming_local_message_notice_is_translated(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(cli_main, "accept_incoming_message", lambda *_args: None)
    token = set_contextvar_locale("ja")
    try:
        result = cli_main._accept_cli_local_message(SimpleNamespace(), None, {})
    finally:
        reset_contextvar_locale(token)

    assert result is None
    assert capsys.readouterr().out.strip() == (
        "[LOCAL] 受信メッセージは拒否されたか、有効期限切れです。"
    )


def test_local_messaging_tool_a2a_errors_use_japanese_catalog(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_LANG", "ja")
    assert (
        local_messaging_tool._(
            "err.inbox_unavailable",
            default="Inbox retrieval is available only to explicitly enabled A2A tasks.",
        )
        == "inbox の取得は、有効化されたA2Aタスクでのみ利用できます。"
    )
    assert (
        local_messaging_tool._(
            "err.a2a_task_required",
            default="Inbox retrieval requires an authenticated A2A task context.",
        )
        == "inbox の取得には、認証済みのA2Aタスクコンテキストが必要です。"
    )
