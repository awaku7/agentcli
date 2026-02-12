# -*- coding: utf-8 -*-
import json
import os

try:
    from . import __version__
except ImportError:
    __version__ = "unknown"


def get_mcp_servers_summary():
    """登録されているMCPサーバーの一覧を取得します。"""
    try:
        # 相対インポートを試行
        from .tools.mcp_servers_shared import get_default_mcp_config_path

        path = get_default_mcp_config_path()
    except (ImportError, ValueError):
        # パッケージ外からの実行やインポート失敗時のフォールバック
        path = os.path.abspath(
            os.path.join(os.path.expanduser("~"), ".scheck", "mcps", "mcp_servers.json")
        )

    if not os.path.exists(path):
        return "[MCP サーバー]\n- 設定ファイルが見つかりません。"

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        servers = data.get("mcp_servers", [])
        if not servers:
            return "[MCP サーバー]\n- 登録されているサーバーはありません。"

        lines = ["[MCP サーバー]"]
        for s in servers:
            name = s.get("name", "unknown")
            transport = s.get("transport", "stdio")
            lines.append(f"- {name} ({transport})")
        return "\n".join(lines)
    except Exception as e:
        return f"[MCP サーバー]\n- 情報の取得に失敗しました: {e}"


def get_welcome_ascii():
    return r"""
██╗   ██╗ █████╗  ██████╗ ███████╗███╗   ██╗████████╗ ██████╗██╗     ██╗
██║   ██║██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██╔════╝██║     ██║
██║   ██║███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ██║     ██║     ██║
██║   ██║██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ██║     ██║     ██║
╚██████╔╝██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ╚██████╗███████╗██║
 ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝╚══════╝╚═╝
"""


def get_welcome_message():
    ascii_art = get_welcome_ascii()
    mcp_summary = get_mcp_servers_summary()
    usage = f"v{__version__}\n" + """
[クイックガイド]
- 対話: メッセージを入力して送信（GUIでは Ctrl+Enter も可）。
- 複数行: 'f' 1文字のみの行を入力すると複数行モードに移行します（終了は \"\"\"end）。
- コマンド: ':help' でシステムコマンド（ログ管理、履歴圧縮等）を確認できます。
- 終了: ':exit' または ':quit' でセッションを終了します。
- 画像: GUIではドラッグ＆ドロップ、CUIではファイルパス入力で画像解析が可能です。
- ドキュメント: `scheck docs` で同梱ドキュメント一覧、`scheck docs webinspect` で Web Inspector の説明を表示（`--path/--open` も利用可）。

[活用例]
- 「このフォルダにあるソースコードを解析して、README.mdを作成して」
- 「現在のデスクトップを撮影して、開いているウィンドウの内容を説明して」
- 「このExcelファイルのデータから、月別の集計レポートを作って」
- 「このPDFを読んで、重要なポイントを3つ箇条書きで教えて」
- 「最新のニュースを検索して、特定のトピックについて要約して」
"""
    return ascii_art + usage + "\n" + mcp_summary


def _internal_pager(text: str) -> None:
    """Pure-Python pager (no external commands).

    - Shows page by page based on current terminal height.
    - Continue: Enter
    - Quit: q + Enter

    If stdin/stdout are not TTY, it falls back to plain print.

    Debug:
      - Set UAGENT_DEBUG_PAGER=1 to emit diagnostics to stderr.
    """

    import sys
    import shutil

    debug_pager = os.environ.get("UAGENT_DEBUG_PAGER", "").lower() in ("1", "true", "yes")

    if debug_pager:
        try:
            sys.stderr.write(
                f"[pager] stdin_tty={sys.stdin.isatty()} stdout_tty={sys.stdout.isatty()}\n"
            )
            sys.stderr.flush()
        except Exception:
            pass

    # If not interactive, paging cannot work reliably.
    if (not sys.stdin.isatty()) or (not sys.stdout.isatty()):
        if debug_pager:
            try:
                sys.stderr.write("[pager] fallback: not a tty -> plain print\n")
                sys.stderr.flush()
            except Exception:
                pass
        print(text)
        return

    # Allow users to disable paging explicitly.
    if os.environ.get("UAGENT_NOPAGER") in ("1", "true", "TRUE", "yes", "YES"):
        if debug_pager:
            try:
                sys.stderr.write("[pager] disabled by UAGENT_NOPAGER -> plain print\n")
                sys.stderr.flush()
            except Exception:
                pass
        print(text)
        return

    # Determine page height (reserve 1 line for prompt).
    try:
        height = shutil.get_terminal_size(fallback=(80, 24)).lines
    except Exception:
        height = 24

    page_lines = max(1, height - 1)
    lines = text.splitlines(True)  # keep line endings

    if debug_pager:
        try:
            sys.stderr.write(
                f"[pager] term_lines={height} page_lines={page_lines} total_lines={len(lines)}\n"
            )
            sys.stderr.flush()
        except Exception:
            pass

    i = 0
    while i < len(lines):
        chunk = lines[i : i + page_lines]
        sys.stdout.write("".join(chunk))
        sys.stdout.flush()
        i += page_lines

        if i >= len(lines):
            break

        try:
            ans = input("-- More -- (Enter: next) ")
        except EOFError:
            if debug_pager:
                try:
                    sys.stderr.write("[pager] input: EOFError -> stop paging\n")
                    sys.stderr.flush()
                except Exception:
                    pass
            sys.stdout.write("\n")
            sys.stdout.flush()
            break
        except KeyboardInterrupt:
            if debug_pager:
                try:
                    sys.stderr.write("[pager] input: KeyboardInterrupt -> stop paging\n")
                    sys.stderr.flush()
                except Exception:
                    pass
            sys.stdout.write("\n")
            sys.stdout.flush()
            break

def print_welcome(*, use_pager: bool = True) -> None:
    """Print welcome message.

    When use_pager is True, display via an internal pager so long messages are
    scrollable without relying on external commands.

    Note: This is intended for CLI usage. GUI/web call get_welcome_message()
    directly.
    """

    msg = get_welcome_message()

    if use_pager:
        _internal_pager(msg)
        return

    print(msg)
