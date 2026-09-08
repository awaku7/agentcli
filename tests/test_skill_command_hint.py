from uagent.util_cmd_session import _restore_skill_command_hint


def test_skill_command_hint_preserves_executable_command():
    text = "ヒント: :skills クリア (適用されたスキルを削除します)"
    assert _restore_skill_command_hint(text) == (
        "ヒント: :skills clear (適用されたスキルを削除します)"
    )
