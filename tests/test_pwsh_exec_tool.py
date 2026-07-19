"""pwsh_exec テスト: IF（パラメータ定義）だけを参照。

戻り値はプレーンテキスト（非JSON）。
cmd_exec_json と違い shell=False で直接実行するため改行問題は起きない。
"""

from __future__ import annotations


def _run(args: dict) -> str:
    from uagent.tools.pwsh_exec_tool import run_tool

    return run_tool(args)


# ===================================================================
# 正常系
# ===================================================================


def test_simple_expression() -> None:
    """1+1 が計算できる."""
    out = _run({"command": "1+1"})
    assert "2" in out


def test_write_output() -> None:
    """文字列出力."""
    out = _run({"command": "Write-Output 'hello pwsh'"})
    assert "hello pwsh" in out


def test_get_date() -> None:
    """Get-Date がエラーなく実行できる."""
    out = _run({"command": "Get-Date"})
    assert len(out) > 5
    assert "[pwsh_exec error]" not in out


def test_unicode_japanese() -> None:
    """日本語が正しく入出力できる."""
    out = _run({"command": "Write-Output 'こんにちは'"})
    assert "こんにちは" in out


def test_pipeline() -> None:
    """パイプラインが動作する."""
    out = _run({"command": "Get-Process | Select-Object -First 3"})
    assert len(out) > 10


def test_multiline_command() -> None:
    """セミコロン区切りで複数行."""
    out = _run({"command": "$a=1; $b=2; $a+$b"})
    assert "3" in out


def test_explicit_shell_pwsh() -> None:
    """shell='pwsh' を明示指定."""
    out = _run({"command": "1+1", "shell": "pwsh"})
    assert "2" in out


# ===================================================================
# 異常系
# ===================================================================


def test_empty_command() -> None:
    """command が空 -> エラーメッセージ."""
    out = _run({"command": ""})
    assert "command" in out.lower() and "required" in out.lower()


def test_missing_command_key() -> None:
    """command キー自体がない -> エラー."""
    out = _run({})
    assert "command" in out.lower() and "required" in out.lower()


def test_nonexistent_cmdlet() -> None:
    """存在しないコマンドレット -> エラー."""
    out = _run({"command": "Get-NonexistentCommand12345"})
    assert (
        "returncode" in out.lower()
        or "エラー" in out
        or "not recognized" in out.lower()
    )


def test_warning_to_stderr() -> None:
    """Write-Warning は stderr に出るはず."""
    out = _run({"command": "Write-Warning 'test warning'"})
    # stderr の内容が stdout にマージされる
    assert "test warning" in out or "[stderr]" in out


def test_return_emoji() -> None:
    """絵文字が正しく入出力できる."""
    out = _run({"command": "Write-Output '😊🔥'"})
    assert "😊🔥" in out


# ===================================================================
# shell パラメータのエッジケース
# ===================================================================


def test_shell_invalid_value() -> None:
    """shell に enum 外の値を指定 -> pwsh にフォールバック？エラー？"""
    out = _run({"command": "1+1", "shell": "invalid_shell"})
    # 不正な値は _choose_shell で無視され自動選択されるはず
    assert "2" in out or "[pwsh_exec error]" in out


# ===================================================================
# エッジケース: 出力が空のコマンド
# ===================================================================


def test_no_output_command() -> None:
    """出力がないコマンド -> '(no output)' が返る."""
    out = _run({"command": "$null=$null"})
    assert "(no output)" in out


# ===================================================================
# さらにいじわるなテスト
# ===================================================================


def test_exit_code_nonzero() -> None:
    """Exit 42 で終了コード非ゼロ -> エラーメッセージに returncode が含まれる."""
    out = _run({"command": "Exit 42"})
    assert "returncode" in out.lower() or "エラー" in out
    assert "42" in out


def test_throw_exception() -> None:
    """Throw でエラー -> エラーハンドリング."""
    out = _run({"command": "throw 'test error'"})
    assert "[pwsh_exec error]" in out or "test error" in out


def test_env_var_read() -> None:
    """環境変数 PATH を読める."""
    out = _run({"command": "$env:PATH"})
    assert len(out) > 10


def test_env_var_set_and_read() -> None:
    """環境変数を設定して読み取る."""
    out = _run({"command": "$env:UAGENT_TEST='hello'; $env:UAGENT_TEST"})
    assert "hello" in out


def test_nested_quotes_single_inside_double() -> None:
    """二重引用符の中の単一引用符."""
    out = _run({"command": 'Write-Output "it\'s a test"'})
    assert "it's a test" in out


def test_nested_quotes_double_inside_single() -> None:
    """単一引用符の中の二重引用符."""
    out = _run({"command": "Write-Output 'say \"hello\"'"})
    assert 'say "hello"' in out


def test_long_output_truncation() -> None:
    """大量出力 -> トランケートされるか？少なくともクラッシュしない."""
    out = _run({"command": "1..10000 | ForEach-Object { $_ }"})
    # 何らかの出力があるはず
    assert len(out) > 0
    assert "[pwsh_exec error]" not in out


def test_write_host() -> None:
    """Write-Host はストリーム1（stdout）に出力."""
    out = _run({"command": "Write-Host 'host message'"})
    assert "host message" in out


def test_write_error() -> None:
    """Write-Error は stderr に出力 -> stdout にマージされる."""
    out = _run({"command": "Write-Error 'err msg'; Write-Output 'ok'"})
    assert "err msg" in out
    assert "ok" in out


def test_very_long_command() -> None:
    """非常に長い1行コマンド."""
    long_str = "a" * 10000
    out = _run({"command": f"Write-Output '{long_str}'"})
    assert len(out) > 100
    assert "[pwsh_exec error]" not in out


def test_hashtable_output() -> None:
    """ハッシュテーブルの出力."""
    out = _run({"command": "@{name='test'; value=42}"})
    assert "test" in out
    assert "42" in out


def test_script_block() -> None:
    """スクリプトブロック & 呼び出し."""
    out = _run({"command": "& { param($x) $x * 2 } 21"})
    assert "42" in out


def test_write_progress_noise() -> None:
    """Write-Progress が出力に混入しないか."""
    out = _run(
        {
            "command": "Write-Progress -Activity 'test' -PercentComplete 50; Write-Output 'done'"
        }
    )
    assert "done" in out


def test_subprocess_uses_devnull_stdin(monkeypatch) -> None:
    """Child must not inherit host stdin (CLI exits on EOF from shared stdin)."""
    import subprocess
    from uagent.tools import pwsh_exec_tool as mod

    captured: dict = {}

    class _FakeProc:
        returncode = 0
        stdout = "ok\n"
        stderr = ""

    def fake_run(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return _FakeProc()

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(mod.shutil, "which", lambda _name: "C:\\fake\\pwsh.exe")
    monkeypatch.setattr(mod, "decide_cmd_exec", None)
    monkeypatch.setattr(mod, "confirm_if_needed", None)

    out = mod.run_tool({"command": "Write-Output ok", "shell": "pwsh"})
    assert "ok" in out
    assert captured["kwargs"].get("stdin") is subprocess.DEVNULL


