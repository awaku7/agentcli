"""scheck tool: git_ops

安全第一で Git の主要操作を提供します。

このツールは「日常操作をできるだけ tool 経由で完結させる」ことを目的にしています。
一方で、Git は破壊的操作や外部への書き込み（push）を簡単に実行できるため、
以下の方針で厳しめに制限します。

設計方針（重要）
- 対話を伴う操作を避ける
  - PAGER/EDITOR を無効化
  - commit/merge は --no-edit を付与（できる限り）
  - 資格情報入力を避けるため GIT_TERMINAL_PROMPT=0
- 危険操作はデフォルト禁止
  - 例: push --force, reset --hard, checkout -f, clean -fdx, rebase --onto 等
- それでも必要な場合のみ allow_danger=true を明示して実行可能にする
  - ただし「事故率が高い/取り返しがつきにくい」ものは allow_danger でも禁止する
- 引数は「許可リスト」方式
  - すべてのオプション（-x / --xxx）を網羅許可せず、用途に応じて明示許可
  - 明らかなメタ文字（; && || | > < `）を含む引数は拒否

注意
- このツールは git の全機能を無制限に提供するものではありません。
- 設計上、安全性を優先して「できない」操作があります。
"""

from __future__ import annotations

import locale
import os
import subprocess
from typing import Any, Dict, List, Tuple

BUSY_LABEL = True
STATUS_LABEL = "tool:git_ops"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "git_ops",
        "description": "Gitコマンドを実行してバージョン管理操作を行います（安全第一の制限あり）。",
        "system_prompt": (
            "このツールは次の目的で使われます: Gitコマンドを実行してバージョン管理操作を行います。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": [
                        "status",
                        "diff",
                        "log",
                        "add",
                        "commit",
                        "show",
                        "rev-parse",
                        "branch",
                        "switch",
                        "checkout",
                        "remote",
                        "fetch",
                        "pull",
                        "push",
                        "tag",
                        "merge",
                        "rebase",
                        "stash",
                        "reset",
                        "restore",
                        "apply",
                    ],
                    "description": "実行するGitサブコマンド（安全第一の制限あり）。",
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "コマンドに渡す引数のリスト。",
                },
                "allow_danger": {
                    "type": "boolean",
                    "description": "危険な操作を許可するか（既定 false）。例: push --force, reset --hard 等。",
                    "default": False,
                },
            },
            "required": ["command"],
        },
    },
}


class GitArgsError(ValueError):
    """引数検証で弾いたときの例外"""


def _env_for_git() -> Dict[str, str]:
    """git 実行用の環境変数を整える（対話/ページャ/エディタ抑止）。"""

    base = os.environ.copy()
    base.update(
        {
            # pager 無効化
            "GIT_PAGER": "cat",
            "PAGER": "cat",
            # editor 無効化（commit --amend 等で editor が起動しないように）
            "GIT_EDITOR": ":",
            "EDITOR": ":",
            # WindowsでもUTF-8出力を優先させたい
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            # 資格情報入力などのプロンプト抑止（ブロック回避）
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return base


def _decode_bytes(b: bytes) -> str:
    encodings = [locale.getpreferredencoding(), "utf-8", "cp932"]
    for enc in encodings:
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace")  # 最終fallback


def run_git_command(args: List[str], timeout_sec: int = 30) -> str:
    """実際に git コマンドを実行するヘルパー。"""

    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=False,
            env=_env_for_git(),
            timeout=timeout_sec,
        )

        stdout_b = result.stdout or b""
        stderr_b = result.stderr or b""

        decoded = _decode_bytes(stdout_b)
        decoded_stderr = _decode_bytes(stderr_b)

        output = decoded
        if decoded_stderr.strip():
            output += f"\n[stderr]\n{decoded_stderr}"

        if result.returncode != 0:
            return f"[git_ops error] command failed (code={result.returncode}):\n{output.strip()}"

        return output.strip()

    except FileNotFoundError:
        return "[git_ops error] git コマンドが見つかりません。Gitがインストールされているか確認してください。"
    except subprocess.TimeoutExpired:
        return "[git_ops error] コマンドがタイムアウトしました。"
    except Exception as e:
        return f"[git_ops error] 予期せぬエラー: {e}"


def _contains_any(args: List[str], needles: List[str]) -> bool:
    for a in args:
        for n in needles:
            if a == n or a.startswith(n + "="):
                return True
    return False


def _validate_no_shell_metacharacters(args: List[str]) -> None:
    """list 引数で subprocess を呼ぶので原則安全だが、明らかな危険文字列を拒否。"""

    bad = [";", "&&", "||", "|", ">", "<", "`"]
    for a in args:
        for b in bad:
            if b in a:
                raise GitArgsError(f"危険なメタ文字を含む引数は拒否します: {a}")


def _validate_paths(args: List[str], *, allow_outside_workdir: bool = False) -> None:
    """非オプション引数（ファイルパスなど）が workdir 配下のみかを検証（ディレクトリトラバーサル防止）。

    allow_outside_workdir=True の場合は workdir 外も許可するが、scheck が管理する安全な
    一時領域（~/.scheck/tmp/patch）配下のみ許可する。
    """

    workdir = os.getcwd()
    scheck_patch_tmp = os.path.abspath(
        os.path.join(os.path.expanduser("~"), ".scheck", "tmp", "patch")
    )

    for a in args:
        if a.startswith("-"):
            continue
        abs_path = os.path.abspath(a)

        # normal policy: workdir only
        if abs_path.startswith(workdir + os.sep) or abs_path == workdir:
            continue

        if allow_outside_workdir:
            # allow only scheck-managed tmp patch directory
            if (
                abs_path.startswith(scheck_patch_tmp + os.sep)
                or abs_path == scheck_patch_tmp
            ):
                continue

        raise GitArgsError(f"許可されていないパスです（workdir 外）: {a}")


def _reject(reason: str) -> None:
    raise GitArgsError(reason)


def _ensure_allowed_flags(
    args: List[str],
    allowed_prefixes: Tuple[str, ...],
    *,
    allow_danger: bool,
    dangerous_prefixes: Tuple[str, ...] = (),
    deny_exact: Tuple[str, ...] = (),
    deny_prefixes: Tuple[str, ...] = (),
) -> None:
    """許可リスト方式のフラグ検証。

    - 引数のうち "-" 始まりのものをオプション扱いとして検証
    - allowed_prefixes に含まれるもののみ許可
      - prefix 判定なので "-n" は "-n10" なども許可
    - dangerous_prefixes は allow_danger=false の場合に拒否
    - deny_exact/deny_prefixes は常に拒否

    注意:
    - 非オプション引数（ブランチ名、パス、リビジョンなど）はこの関数では検証しません。
    """

    _validate_no_shell_metacharacters(args)

    for a in args:
        if not a.startswith("-"):
            continue

        opt = a.split("=", 1)[0]  # -n=10 -> -n

        if opt in deny_exact:
            _reject(f"禁止オプションが含まれています: {opt}")

        for p in deny_prefixes:
            if opt == p or opt.startswith(p):
                _reject(f"禁止オプションが含まれています: {opt}")

        for p in dangerous_prefixes:
            if opt == p or opt.startswith(p):
                if not allow_danger:
                    _reject(f"危険オプションは allow_danger=true が必要です: {opt}")

        ok = False
        for ap in allowed_prefixes:
            if opt == ap or opt.startswith(ap):
                ok = True
                break

        if not ok:
            _reject(f"未許可のオプションが含まれています: {opt}")


def _parse_allow_danger(tool_args: Dict[str, Any]) -> bool:
    return bool(tool_args.get("allow_danger", False))


def run_tool(args: Dict[str, Any]) -> str:
    """Git操作ツール（安全第一）。"""

    command = args.get("command", "")
    cmd_args: List[str] = args.get("args", [])
    allow_danger = _parse_allow_danger(args)

    if command not in (
        "status",
        "diff",
        "log",
        "apply",
        "add",
        "commit",
        "show",
        "rev-parse",
        "branch",
        "switch",
        "checkout",
        "remote",
        "fetch",
        "pull",
        "push",
        "tag",
        "merge",
        "rebase",
        "stash",
        "reset",
        "restore",
    ):
        return f"[git_ops error] 未サポートまたは無効なコマンドです: {command}"

    # --------------------
    # status
    # --------------------
    if command == "status":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "-s",
                    "--short",
                    "-b",
                    "--branch",
                    "--porcelain",
                    "--ignored",
                    "-u",
                    "--untracked-files",
                ),
                allow_danger=allow_danger,
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"

        return run_git_command(["status"] + cmd_args)

    # --------------------
    # diff
    # --------------------
    if command == "diff":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "--staged",
                    "--cached",
                    "--stat",
                    "--name-only",
                    "--name-status",
                    "--",
                    "-U",
                    "--unified",
                ),
                allow_danger=allow_danger,
                deny_prefixes=("--no-index",),
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"

        return run_git_command(["diff"] + cmd_args)

    # --------------------
    # log
    # --------------------
    if command == "log":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "-n",
                    "--max-count",
                    "--oneline",
                    "--decorate",
                    "--graph",
                    "--all",
                    "--",
                ),
                allow_danger=allow_danger,
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"

        if not any(a.startswith("-n") or a.startswith("--max-count") for a in cmd_args):
            cmd_args = ["-n", "10"] + cmd_args
        return run_git_command(["log"] + cmd_args)

    # --------------------
    # apply
    # --------------------
    if command == "apply":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "--check",
                    "--numstat",
                    "--whitespace",
                    "--ignore-whitespace",
                    "-p",
                    "--",
                ),
                allow_danger=allow_danger,
            )
            # patch file is a non-option arg -> validate. allow_outside_workdir allows only ~/.scheck/tmp/patch
            _validate_paths(cmd_args, allow_outside_workdir=True)
        except GitArgsError as e:
            return f"[git_ops error] {e}"

        return run_git_command(["apply"] + cmd_args)

    # --------------------
    # add
    # --------------------
    if command == "add":
        if not cmd_args:
            return (
                "[git_ops error] git add には対象ファイルの指定が必要です（'.' も可）。"
            )

        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "-A",
                    "--all",
                    "-u",
                    "--update",
                    "-N",
                    "--intent-to-add",
                    "--",
                ),
                allow_danger=allow_danger,
            )
            _validate_paths(cmd_args)
        except GitArgsError as e:
            return f"[git_ops error] {e}"

        return run_git_command(["add"] + cmd_args)

    # --------------------
    # commit
    # --------------------
    if command == "commit":
        has_message = any(
            a == "-m"
            or a.startswith("-m")
            or a == "--message"
            or a.startswith("--message")
            for a in cmd_args
        )
        if not has_message:
            return "[git_ops error] コミットメッセージが必要です。args に ['-m', 'message'] を含めてください。"

        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "-m",
                    "--message",
                    "--no-verify",
                    "--amend",
                    "--",
                ),
                allow_danger=allow_danger,
                dangerous_prefixes=("--amend",),
                deny_prefixes=("--interactive", "-i", "--patch", "-p"),
            )
            _validate_paths(cmd_args)
        except GitArgsError as e:
            return f"[git_ops error] {e}"

        final_args = ["commit"] + cmd_args
        if "--no-edit" not in final_args:
            final_args.append("--no-edit")
        return run_git_command(final_args)

    # --------------------
    # show
    # --------------------
    if command == "show":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "--stat",
                    "--name-only",
                    "--name-status",
                    "--oneline",
                    "--",
                    "-U",
                    "--unified",
                ),
                allow_danger=allow_danger,
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"

        # デフォルトは最新コミットの要約
        return run_git_command(["show"] + (cmd_args if cmd_args else ["--stat"]))

    # --------------------
    # rev-parse
    # --------------------
    if command == "rev-parse":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "--abbrev-ref",
                    "--verify",
                    "--show-toplevel",
                    "--",
                ),
                allow_danger=allow_danger,
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"

        return run_git_command(["rev-parse"] + cmd_args)

    # --------------------
    # branch
    # --------------------
    if command == "branch":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "-a",
                    "--all",
                    "-v",
                    "--verbose",
                    "--show-current",
                    "--",
                    "-d",
                    "-D",
                ),
                allow_danger=allow_danger,
                dangerous_prefixes=("-D",),
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"

        return run_git_command(["branch"] + cmd_args)

    # --------------------
    # switch / checkout
    # --------------------
    if command in ("switch", "checkout"):
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "-c",
                    "--create",
                    "-C",
                    "--force-create",
                    "--",
                ),
                allow_danger=allow_danger,
                dangerous_prefixes=("-C", "--force-create"),
                deny_prefixes=("-f", "--force"),
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"

        return run_git_command([command] + cmd_args)

    # --------------------
    # remote
    # --------------------
    if command == "remote":
        sub = cmd_args[0] if cmd_args else ""
        if sub in ("add", "remove", "set-url", "rename") and not allow_danger:
            return "[git_ops error] remote の変更操作は allow_danger=true が必要です。"

        try:
            _ensure_allowed_flags(
                cmd_args[1:] if cmd_args else [],
                allowed_prefixes=("-v", "--verbose"),
                allow_danger=allow_danger,
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"

        return run_git_command(["remote"] + cmd_args)

    # --------------------
    # fetch
    # --------------------
    if command == "fetch":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=("--all", "--prune", "--tags", "--"),
                allow_danger=allow_danger,
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"

        return run_git_command(["fetch"] + cmd_args, timeout_sec=60)

    # --------------------
    # pull
    # --------------------
    if command == "pull":
        # pull は merge/rebase を伴うので事故率が高い。
        # デフォルトで --ff-only を付与。
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "--ff-only",
                    "--rebase",
                    "--",
                ),
                allow_danger=allow_danger,
                dangerous_prefixes=("--rebase",),
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"

        final = ["pull"] + cmd_args
        if "--ff-only" not in final and "--rebase" not in final:
            final.append("--ff-only")
        return run_git_command(final, timeout_sec=120)

    # --------------------
    # push
    # --------------------
    if command == "push":
        # push は外部書き込み。force 系は allow_danger が必要。
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "-u",
                    "--set-upstream",
                    "--tags",
                    "--follow-tags",
                    "--",
                    "--force-with-lease",
                    "--force",
                ),
                allow_danger=allow_danger,
                dangerous_prefixes=("--force", "--force-with-lease"),
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"

        return run_git_command(["push"] + cmd_args, timeout_sec=120)

    # --------------------
    # tag
    # --------------------
    if command == "tag":
        # タグ削除は allow_danger 必須
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "-l",
                    "--list",
                    "-n",
                    "-a",
                    "-d",
                    "--delete",
                    "-m",
                    "--message",
                    "--",
                ),
                allow_danger=allow_danger,
                dangerous_prefixes=("-d", "--delete"),
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"

        return run_git_command(["tag"] + cmd_args)

    # --------------------
    # merge
    # --------------------
    if command == "merge":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=("--no-ff", "--ff-only", "--abort", "--"),
                allow_danger=allow_danger,
                deny_prefixes=("--strategy", "-s"),
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"

        final = ["merge"] + cmd_args
        if "--no-edit" not in final:
            final.append("--no-edit")
        return run_git_command(final, timeout_sec=120)

    # --------------------
    # rebase
    # --------------------
    if command == "rebase":
        # rebase は危険度高。allow_danger=true の時のみ許可。
        if not allow_danger:
            return "[git_ops error] rebase は危険な操作のため allow_danger=true が必要です。"

        # 特に危険（事故率が高い）なので禁止
        if _contains_any(cmd_args, ["--onto"]):
            return "[git_ops error] rebase --onto は事故率が高いため禁止します。"

        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "--abort",
                    "--continue",
                    "--skip",
                    "--",
                    "--rebase-merges",
                ),
                allow_danger=allow_danger,
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"

        return run_git_command(["rebase"] + cmd_args, timeout_sec=300)

    # --------------------
    # stash
    # --------------------
    if command == "stash":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=(
                    "push",
                    "pop",
                    "apply",
                    "list",
                    "show",
                    "-m",
                    "--message",
                    "--",
                ),
                allow_danger=allow_danger,
            )
        except GitArgsError as e:
            return f"[git_ops error] {e}"

        return run_git_command(["stash"] + cmd_args, timeout_sec=120)

    # --------------------
    # reset
    # --------------------
    if command == "reset":
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=("--soft", "--mixed", "--hard", "--"),
                allow_danger=allow_danger,
                dangerous_prefixes=("--hard",),
            )
            _validate_paths(cmd_args)
        except GitArgsError as e:
            return f"[git_ops error] {e}"

        return run_git_command(["reset"] + cmd_args)

    # --------------------
    # restore
    # --------------------
    if command == "restore":
        # --source は事故りやすいので allow_danger 必須
        try:
            _ensure_allowed_flags(
                cmd_args,
                allowed_prefixes=("--staged", "--worktree", "--", "--source"),
                allow_danger=allow_danger,
                dangerous_prefixes=("--source",),
            )
            _validate_paths(cmd_args)
        except GitArgsError as e:
            return f"[git_ops error] {e}"

        return run_git_command(["restore"] + cmd_args)

    return "[git_ops error] 不明な内部エラー"
