from __future__ import annotations

# tools/human_ask_tool.py
from typing import Any, Dict
import json
import queue
from .context import get_callbacks

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = False  # human_ask は Busy を解除する（tools/__init__.py 側で特別扱い）

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "human_ask",
        "x_scheck": {"emit_tool_trace": False},
        "description": _("tool.description", default="モデル自身では完結しない操作・判断を、人間ユーザーに依頼し、その回答テキストを受け取るためのツール。注意: 秘匿情報(パスワード等)は is_password=True で「1項目だけ」尋ねること。ユーザー名+パスワード等の複数項目を同時に要求してはいけません（必要なら複数回呼び出す）。"),
        "system_prompt": _("tool.system_prompt", default="""このツールは次の目的で使われます: モデル自身では完結しない操作・判断を、人間ユーザーに依頼し、その回答テキストを受け取るためのツール。

重要: このツールは 1回の呼び出しで 1つの回答テキストしか受け取れません。入力を複数フィールドに分割したり、フィールドごとにマスク有無を切り替える機能はありません。

【最重要: セキュリティ】
- 秘匿情報（パスワード、APIキー、トークン、秘密鍵、セッションCookie等）を入力させる場合は、必ず is_password=True を指定してください。
- is_password=True で取得した回答（user_reply）は、以後のあなたの返答（Assistant message）の中で**絶対に復唱しないでください**。
  - 悪い例: 「パスワード『password123』を受け取りました。ログインします」
  - 良い例: 「パスワードを受け取りました。ログイン処理を開始します」
- パスワード等の秘匿情報を長期記憶や共有メモに保存しないでください。

このツールの動作指針:
- 追加のユーザー入力が必要な場合は必ず human_ask ツールを使用してください。
- is_password=True の呼び出しでは、秘匿情報 1項目のみを尋ねてください。
- ユーザー名 + パスワード等が必要な場合は、必ず human_ask を2回以上に分けてください。
- 1回の human_ask で複数項目の入力を同時に要求してはいけません。
- 相対日付（今日／今年など）を扱う場合は get_current_time を呼んで現在時刻を参照してください。
- ファイルやコード出力は原文全体を省略せずに出力すること（ユーザー指示がない場合）。

キャンセル方法:
- キャンセルしたい場合は 1 行で「c」または「cancel」と入力してください。
"""),
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": _("param.message.description", default="人間に依頼したい内容を、日本語で丁寧にそのまま表示できる形で書く。"),
                },
                "is_password": {
                    "type": "boolean",
                    "description": _("param.is_password.description", default="true の場合、入力文字を非表示（マスク）にします。パスワードやトークンの入力に使用してください。"),
                    "default": False,
                },
            },
            "required": ["message"],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    """human_ask は stdin から直接読むのではなく、
    scheck.py 側の stdin_loop スレッドに処理を任せて
    共有状態（callbacks）経由で結果を受け取る。
    """

    cb = get_callbacks()

    message = (
        args.get("message")
        or "（LLMからの依頼内容が空です。必要な操作や判断をここに日本語で書いてください。）"
    )

    is_password = bool(args.get("is_password", False))

    if True:
        print("=== 人への依頼 (human_ask) ===", flush=True)
        print(message, flush=True)
        print("=== /human_ask ===", flush=True)
        # GUI の場合は回答方法の説明を表示しない（GUI で操作可能）
        if not cb.is_gui:
            print(
                "回答方法:\n"
                "  - そのまま入力して Enter で送信\n"
                "  - 'f' 入力で複数行モードへ\n"
                '  - 複数行モード中: \'"""retry\' でクリア、\'"""end\' で送信\n'
                "  - 'c' または 'cancel' で中断\n",
                flush=True,
            )

    if cb.human_ask_lock is None:
        return "[human_ask error] human_ask_lock コールバックが初期化されていません。"

    if cb.human_ask_active_ref is None or cb.human_ask_set_active is None:
        return "[human_ask error] human_ask_active コールバックが初期化されていません。"

    if cb.human_ask_set_queue is None:
        return "[human_ask error] human_ask_queue コールバックが初期化されていません。"

    if cb.human_ask_lines_ref is None:
        return "[human_ask error] human_ask_lines コールバックが初期時されていません。"

    if cb.human_ask_set_multiline_active is None:
        return "[human_ask error] human_ask_multiline_active コールバックが初期化されていません。"

    if cb.human_ask_set_password is None:
        return "[human_ask error] human_ask_set_password コールバックが初期化されていません。"

    # この human_ask 呼び出し専用のキュー
    local_q: "queue.Queue[str]" = queue.Queue()

    with cb.human_ask_lock:
        if cb.human_ask_active_ref():
            return "[human_ask error] すでに別の human_ask が実行中です。"

        cb.human_ask_set_active(True)
        cb.human_ask_set_password(is_password)
        cb.human_ask_set_queue(local_q)

        lines = cb.human_ask_lines_ref()
        try:
            lines.clear()
        except Exception:
            pass

        cb.human_ask_set_multiline_active(False)

    try:
        # 全ての状態をセットし終わった後に Busy を解除することで、stdin_loop が
        # 確実に is_password=True を検知してからプロンプトを表示できるようにする。
        if cb.set_status:
            cb.set_status(False, "")
        # stdin_loop/GUI が human_ask 用の入力を local_q に投げる
        user_reply = local_q.get() or ""

        def _split_keep_lines(s: str) -> list:
            # normalize CRLF/CR to LF
            s2 = str(s).replace("\r\n", "\n").replace("\r", "\n")
            return s2.split("\n")

        def _strip_trailing_end_sentinel(text: str) -> str:
            """Remove a trailing end-marker (triple-quote + end) that may be appended by some frontends."""
            t = "" if text is None else str(text)
            # normalize CRLF/CR to LF for stable handling
            t = t.replace("\r\n", "\n").replace("\r", "\n")
            marker = '"""end'
            while True:
                t2 = t.rstrip("\n")
                if t2.endswith("\n" + marker):
                    t = t2[: -len("\n" + marker)]
                    continue
                if t2.endswith(marker):
                    t = t2[: -len(marker)]
                    continue
                break
            # Avoid leaving only trailing newlines
            t = t.rstrip("\n")
            return t

        def _ensure_gui_sentinel(text: str) -> str:
            """GUI からの返答は multi_input_sentinel 行で必ず終わるようにする。"""
            t = str(text or "")
            # キャンセルは sentinel を付けず、そのまま扱う
            if t.strip().lower() in ("c", "cancel"):
                return t
            lines0 = _split_keep_lines(t)
            # 既に sentinel 行が含まれていればそのまま（途中出現も許容）
            if any((ln.strip() == cb.multi_input_sentinel) for ln in lines0):
                return t
            # 空入力も含めて sentinel で確定できるようにする
            if t.endswith("\n") or t == "":
                return t + cb.multi_input_sentinel + "\n"
            return t + "\n" + cb.multi_input_sentinel + "\n"

        # GUI の場合は sentinel 付きに正規化
        if cb.is_gui:
            user_reply = _ensure_gui_sentinel(user_reply)

        # Strip trailing """end marker if present
        user_reply = _strip_trailing_end_sentinel(user_reply)

        reply_lines = _split_keep_lines(user_reply) if user_reply else []

        # ---------------------------------------------------------
        # 内部状態 (core.human_ask_lines) の同期
        # ---------------------------------------------------------
        # stdin_loop が既に入力を処理して local_q に投げた後の場合、
        # ここで再度解析すると誤判定の恐れがあるため、同期のみを行う。
        if cb.is_gui:
            # GUI の場合: 全行を積む
            cb.human_ask_set_multiline_active(True)
            lines.clear()
            for line in reply_lines:
                lines.append(line)
        else:
            # CUI の場合: 既に stdin_loop で処理済みの文字列が来ている
            # lines に全内容を同期する（履歴保存等のため）
            lines.clear()
            for line in reply_lines:
                lines.append(line)

        if not user_reply:
            user_reply = "(no user reply)"
        # normalize cancel
        ur = user_reply.strip().lower()
        cancelled = ur in ("c", "cancel")

        display_reply = "[SECRET]" if is_password and not cancelled else user_reply
        payload = {
            "tool": "human_ask",
            "message": message,
            "user_reply": user_reply,
            "display_reply": display_reply,
            "cancelled": cancelled,
        }
        # モデルには user_reply を渡すが、ログ等で display_reply を見るように促す
        return json.dumps(payload, ensure_ascii=False)
    finally:
        with cb.human_ask_lock:
            cb.human_ask_set_active(False)
            cb.human_ask_set_password(False)
            cb.human_ask_set_queue(None)
            cb.human_ask_set_multiline_active(False)
