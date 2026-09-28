from uagent.i18n import _preserve_command_syntax


def test_translated_skill_hint_keeps_command_and_subcommand():
    msgid = "Tip: :skills clear  (remove applied skills)"
    translated = "ヒント: :skills クリア (適用されたスキルを削除します)"
    assert _preserve_command_syntax(msgid, translated) == (
        "ヒント: :skills clear (適用されたスキルを削除します)"
    )


def test_translated_command_without_whitespace_keeps_command():
    msgid = ":skills clear  (remove applied skills)"
    translated = "提示：:skills清除（删除已应用的技能）"
    assert _preserve_command_syntax(msgid, translated) == (
        "提示：:skills clear（删除已应用的技能）"
    )


def test_translated_multiline_message_preserves_trailing_newline():
    msgid = "[MCP Servers]\n- No servers registered.\n"
    translated = "[MCP Servers]\n- サーバーが登録されていません。\n"

    result = _preserve_command_syntax(msgid, translated)

    assert result == translated
    assert result.endswith("\n")


def test_translated_multiline_message_without_trailing_newline_stays_unterminated():
    msgid = "[MCP Servers]\n- No servers registered."
    translated = "[MCP Servers]\n- サーバーが登録されていません。"

    assert _preserve_command_syntax(msgid, translated) == translated
