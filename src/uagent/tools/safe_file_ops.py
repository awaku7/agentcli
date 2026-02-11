"""

safe_file_ops.py



ローカルでのファイル書き込み／削除／リネーム(移動)／プロンプト生成に対する安全ラッパー。



方針(B: 中):

- 露骨に危険な操作（workdir 外、絶対パス、パス traversal など）を検出したら必ずユーザー確認。

- それ以外は従来どおり実行。



確認UI:

- 原則として human_ask と同等の仕組み（stdin_loop が拾う共有キュー）で確認する。

- 他の human_ask がアクティブな場合は一定時間待機してから確認を開始する。

- コールバックが利用できない場合のみ input() にフォールバック。



キャンセル:

- 'c' または 'cancel' でキャンセル。

"""

from __future__ import annotations


import hashlib

import os

import shutil

import time

from pathlib import Path

from typing import Optional


from .context import get_callbacks

_allowed_paths: set[str] = set()


def _resolve_path(p: str) -> str:

    return str(Path(p).expanduser().resolve())


def _workdir_root() -> str:

    return str(Path(os.getcwd()).resolve())


def _is_under(root: str, target: str) -> bool:

    try:

        Path(target).relative_to(Path(root))

        return True

    except Exception:

        return False


def _is_trigger_path(p: str) -> bool:
    """トリガー条件(B: 中):

    - パスに ".." が含まれる

    - 絶対パス

    - workdir(cwd) 配下ではない

    """

    try:

        path_obj = Path(p)

    except Exception:

        return True

    if ".." in str(p).replace("\\", "/"):

        return True

    if path_obj.is_absolute():

        return True

    resolved = _resolve_path(p)

    if not _is_under(_workdir_root(), resolved):

        return True

    return False


def _human_confirm(message: str) -> bool:

    cb = get_callbacks()

    # If callbacks are not available, fallback.

    if (
        cb.human_ask_lock is None
        or cb.human_ask_active_ref is None
        or cb.human_ask_set_active is None
        or cb.human_ask_queue_ref is None
        or cb.human_ask_set_queue is None
        or cb.human_ask_lines_ref is None
        or cb.human_ask_set_multiline_active is None
    ):

        try:

            resp = input(message + "\n[y/c/N]: ")

        except Exception:

            return False

        r = resp.strip().lower()

        return r == "y"

    import queue as _queue

    local_q: "_queue.Queue[str]" = _queue.Queue()

    # Wait until no other human_ask is active.

    # This avoids rejecting confirmations during nested workflows.

    wait_timeout_sec = 30.0

    poll_interval_sec = 0.1

    start = time.time()

    while True:

        with cb.human_ask_lock:

            busy = cb.human_ask_active_ref()

            if not busy:

                cb.human_ask_set_active(True)

                cb.human_ask_set_queue(local_q)

                lines = cb.human_ask_lines_ref()

                try:

                    lines.clear()

                except Exception:

                    pass

                cb.human_ask_set_multiline_active(False)

                break

        if time.time() - start > wait_timeout_sec:

            return False

        time.sleep(poll_interval_sec)

    try:

        print("\n=== 人への依頼 (confirm) ===", flush=True)

        print(message, flush=True)

        print("=== /confirm ===\n", flush=True)

        print("回答方法: y=実行 / c=キャンセル / その他=拒否\n", flush=True)

        user_reply = local_q.get()

    finally:

        with cb.human_ask_lock:

            cb.human_ask_set_active(False)

            cb.human_ask_set_queue(None)

            cb.human_ask_set_multiline_active(False)

    ur = (user_reply or "").strip().lower()

    return ur == "y"


def _ask_user_confirm(path: str, operation: str) -> bool:

    msg = (
        "この操作は危険な可能性があるため確認します。\n"
        f"操作: {operation}\n"
        f"パス: {path}\n"
        "実行してよければ y、キャンセルなら c と入力してください。"
    )

    return _human_confirm(msg)


def _ask_user_confirm_rename(src: str, dst: str, details: str) -> bool:

    msg = (
        "rename/move は実ファイルを移動します（上書きや削除を伴う場合があります）。\n"
        f"src: {src}\n"
        f"dst: {dst}\n"
        f"details: {details}\n\n"
        "実行してよければ y、キャンセルなら c と入力してください。"
    )

    return _human_confirm(msg)


def _ensure_parent_dir_exists(path: str) -> None:

    parent = Path(path).parent

    if not parent.exists():

        parent.mkdir(parents=True, exist_ok=True)


def safe_create_file(
    filename: str, content: str, encoding: str = "utf-8", overwrite: bool = False
) -> None:

    resolved = _resolve_path(filename)

    if _is_trigger_path(filename) and resolved not in _allowed_paths:

        ok = _ask_user_confirm(filename, "create")

        if not ok:

            raise PermissionError(
                f"ユーザーが許可しなかったため作成を中止しました: {filename}"
            )

        _allowed_paths.add(resolved)

    p = Path(filename)

    if p.exists() and not overwrite:

        raise FileExistsError(
            f"ファイルが既に存在します（overwrite=False）: {filename}"
        )

    _ensure_parent_dir_exists(filename)

    with open(filename, "w", encoding=encoding) as f:

        f.write(content)


def safe_delete_file(filename: str, missing_ok: bool = False) -> None:

    resolved = _resolve_path(filename)

    if _is_trigger_path(filename) and resolved not in _allowed_paths:

        ok = _ask_user_confirm(filename, "delete")

        if not ok:

            raise PermissionError(
                f"ユーザーが許可しなかったため、削除を中止しました: {filename}"
            )

        _allowed_paths.add(resolved)

    try:

        os.remove(filename)

    except FileNotFoundError:

        if missing_ok:

            return

        raise


def safe_delete_path(path: str, missing_ok: bool = False) -> None:
    """パスを安全に削除する。

    - ファイル: os.remove
    - ディレクトリ: shutil.rmtree

    安全方針:
    - trigger path 条件（絶対パス/..含む/workdir外 等）に該当する場合はユーザー確認。
    - ディレクトリ削除は危険操作なので、常にユーザー確認。
    """

    resolved = _resolve_path(path)

    # まず trigger path 判定による確認
    if _is_trigger_path(path) and resolved not in _allowed_paths:
        ok = _ask_user_confirm(path, "delete")
        if not ok:
            raise PermissionError(
                f"ユーザーが許可しなかったため、削除を中止しました: {path}"
            )
        _allowed_paths.add(resolved)

    p = Path(path)

    # 存在しない
    if not p.exists():
        if missing_ok:
            return
        raise FileNotFoundError(f"path が存在しません: {path}")

    # ディレクトリは常に確認（trigger判定とは別）
    if p.is_dir():
        ok = _ask_user_confirm(path, "delete_dir")
        if not ok:
            raise PermissionError(
                f"ユーザーが許可しなかったため、ディレクトリ削除を中止しました: {path}"
            )
        shutil.rmtree(path)
        return

    # ファイル
    os.remove(path)


def safe_rename_path(
    src: str,
    dst: str,
    overwrite: bool = False,
    mkdirs: bool = False,
) -> None:
    """ファイル/ディレクトリの rename/move を安全確認つきで行う。



    - src/dst はファイル/ディレクトリ両対応

    - overwrite=True の場合、dst が存在していれば削除して置換（削除を伴う）

    - mkdirs=True の場合、dst 親ディレクトリを作成



    安全確認:

    - src/dst いずれかが trigger path の場合は確認

    - overwrite=True の場合は確認（削除を伴うため）

    """

    if not src or not dst:

        raise ValueError("src/dst は必須です")

    src_p = Path(src)

    if not src_p.exists():

        raise FileNotFoundError(f"src が存在しません: {src}")

    src_resolved = _resolve_path(src)

    dst_resolved = _resolve_path(dst)

    need_confirm = False

    reasons = []

    if _is_trigger_path(src) and src_resolved not in _allowed_paths:

        need_confirm = True

        reasons.append("src が危険パス条件に該当")

    if _is_trigger_path(dst) and dst_resolved not in _allowed_paths:

        need_confirm = True

        reasons.append("dst が危険パス条件に該当")

    dst_exists = Path(dst).exists()

    if dst_exists and overwrite:

        need_confirm = True

        reasons.append("overwrite=True で既存 dst を削除して置換")

    elif dst_exists and not overwrite:

        raise FileExistsError(f"dst が既に存在します（overwrite=False）: {dst}")

    if mkdirs:

        parent = Path(dst).parent

        if parent and not parent.exists():

            # mkdirs は原則安全側ではあるが、dst が trigger の場合は上で確認対象になる。

            pass

    if need_confirm:

        detail = ", ".join(reasons) if reasons else "(no detail)"

        ok = _ask_user_confirm_rename(src, dst, detail)

        if not ok:

            raise PermissionError(
                f"ユーザーが許可しなかったため rename/move を中止しました: {src} -> {dst}"
            )

        _allowed_paths.add(src_resolved)

        _allowed_paths.add(dst_resolved)

    if mkdirs:

        _ensure_parent_dir_exists(dst)

    # overwrite の場合は dst を削除してから move

    if dst_exists and overwrite:

        d = Path(dst)

        if d.is_dir():

            shutil.rmtree(dst)

        else:

            os.remove(dst)

    # rename/move 本体

    os.replace(src, dst)


def safe_generate_prompt(path: str, template: Optional[str] = None) -> str:

    if not Path(path).exists():

        raise FileNotFoundError(f"解析対象ファイルが見つかりません: {path}")

    resolved = _resolve_path(path)

    if _is_trigger_path(path) and resolved not in _allowed_paths:

        ok = _ask_user_confirm(path, "generate_prompt (read)")

        if not ok:

            raise PermissionError(
                f"ユーザーが許可しなかったためプロンプト生成を中止しました: {path}"
            )

        _allowed_paths.add(resolved)

    excerpt_lines = []

    with open(path, "r", encoding="utf-8", errors="ignore") as f:

        for _ in range(20):

            line = f.readline()

            if not line:

                break

            excerpt_lines.append(line)

    excerpt = "".join(excerpt_lines)

    timestamp = int(time.time())

    digest = hashlib.sha1((resolved + str(timestamp)).encode("utf-8")).hexdigest()[:10]

    out_dir = Path("files")

    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / f"generated_prompt_{digest}.txt"

    if template:

        content = template.format(
            path=path,
            lines=excerpt.count("\n")
            + (1 if excerpt and not excerpt.endswith("\n") else 0),
            size=Path(path).stat().st_size,
            mtime=Path(path).stat().st_mtime,
            excerpt=excerpt,
            timestamp=timestamp,
        )

    else:

        content = f"# Generated prompt for {path}\n# excerpt:\n{excerpt}\n"

    with open(out_path, "w", encoding="utf-8") as outf:

        outf.write(content)

    return str(out_path)


def clear_session_allowlist() -> None:

    _allowed_paths.clear()
