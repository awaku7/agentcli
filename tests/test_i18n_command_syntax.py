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
