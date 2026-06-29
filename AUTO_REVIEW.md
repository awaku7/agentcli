# 自動対話モード（Auto-Pilot）

## 目的

ユーザーに代わって LLM と自動で対話を継続する機能。
ユーザーが **目的（ゴール）** を指定すると、システムが LLM に対して適切なフォローアップ質問を自動生成して送信し続ける。
**LLM 自身が「完了した」と判断した時点**で自動モードを終了する。

**ユースケース**: コードレビュー、バグ調査、設計検討、要件整理など、複数ラウンドの深掘りが必要なタスク。

## 要求

- **トリガー**: コマンド `:auto <目的>` で起動（例: `:auto このコードをレビューして。バグ、スタイル、テスト不足を重点的に。`）
- **自動応答生成**: LLM の応答を受けて、システムが目的達成のために次の適切な質問/指示を自動生成する（言語は現在の UI 言語に従う）
- **完了判定**: LLM 自身に「完了したかどうか」を尋ねる。LLM が「完了」「以上」「done」等を表明したら終了
- **安全弁**: 最大ラウンド数 `--max-rounds N`（デフォルト 5）を超えたら強制終了
- **割り込み**: `x` キーで自動モードを即座に終了し、通常の手動対話に戻る
- **既存の `c` キーとの関係**: `c` = 今のLLM応答を中断（"停止"注入、モードは継続）。`x` = 自動モード自体を抜ける

## アーキテクチャ

### 自動生成メッセージの仕組み

自動モードでは、以下のようなメッセージを LLM に送信する:

```
[言語] = 現在のUI言語 (ja/en/...)

継続用プロンプト（英語）:
"Continue your analysis. If you have more points to add, please elaborate. 
If you have completed your review/analysis, please respond with exactly 'DONE'."

継続用プロンプト（日本語）:
"続けてください。追加の指摘があれば詳しく説明してください。
レビュー/分析が完了した場合は、'完了' とだけ答えてください。"
```

LLM が `DONE` / `完了` 等を返したら自動モード終了。
それ以外の内容を返したら、それが次のラウンドの応答として表示され、再度継続用プロンプトを送る。

### フロー

```
:auto このコードをレビューして
  ↓
[初期プロンプトを user message として送信]
run_llm_rounds() → LLMがレビュー結果を返す
  ↓
[自動モードループ]
1. x キーチェック → 押されていたら break（自動モード終了）
2. ラウンド数チェック → max 超えていたら break
3. 継続用プロンプト（i18n）を user message として追加
4. run_llm_rounds() → LLMが応答
5. LLMの応答が「完了」「DONE」等 → break（自動モード終了）
6. それ以外 → ループ継続（step 1 へ）
  ↓
通常モードに戻る
```

### スレッド構成

```
[main thread]                  [interrupt_monitor thread]
  event_queue.get()              kbhit() / select() ループ
  run_llm_rounds()                c → interrupt_requested
  _run_auto_pilot_loop()          x → auto_pilot_exit_requested
    └─ run_llm_rounds()
    └─ run_llm_rounds() ...
```

`x` キーは `interrupt_monitor` スレッドで `c` と同様に監視する（別フラグで管理）。

## 変更対象ファイル

| ファイル | 変更内容 |
|---|---|
| `core.py` | 自動モード状態変数 + `x` キー検出を `_check_key_win/posix` に追加 |
| `cli.py` | `:auto` コマンド + `_run_auto_pilot_loop()` + auto exit on "DONE"/"完了" |
| `web.py` | WebSocket `"auto_pilot"` ハンドラ |
| `templates/index.html` | 自動モード中は入力欄をロック＋「Auto (x to stop)」表示 |
| `scheckgui.py` | 自動モード中は入力欄ロック＋中止ボタン表示 |
| `locales/*/uag.po` | 自動モード用メッセージの翻訳 |

## 実装詳細

### 1. core.py: 状態変数 + x キー監視

```python
# --- Auto-Pilot ---
auto_pilot_active = False
auto_pilot_exit_requested = False
auto_pilot_exit_lock = threading.Lock()
auto_pilot_round = 0
auto_pilot_max_rounds = 5
auto_pilot_goal: str = ""  # ユーザーが指定した目的

# _check_key_win / _check_key_posix に x 検出を追加:
if key in (b"c", b"C"):
    with interrupt_lock:
        interrupt_requested = True
elif key in (b"x", b"X"):
    with auto_pilot_exit_lock:
        auto_pilot_exit_requested = True
```

### 2. cli.py: :auto コマンド

```python
if line.startswith(":auto"):
    args = shlex.split(line[5:].strip())
    if not args:
        print(_("Usage: :auto <goal> [--max-rounds N]"))
        print(_("       :auto off"))
        return
    
    subcmd = args[0]
    if subcmd == "off":
        _stop_auto_pilot()
        return
    
    # Parse goal and options
    goal_parts = []
    max_rounds = 5
    i = 0
    while i < len(args):
        if args[i] == "--max-rounds" and i + 1 < len(args):
            max_rounds = int(args[i + 1])
            i += 2
        else:
            goal_parts.append(args[i])
            i += 1
    
    goal = " ".join(goal_parts)
    
    # Set auto-pilot state
    core.auto_pilot_goal = goal
    core.auto_pilot_max_rounds = max_rounds
    core.auto_pilot_round = 0
    core.auto_pilot_exit_requested = False
    core.auto_pilot_active = True
    
    # Send initial goal as user message
    user_msg = {"role": "user", "content": goal}
    messages.append(user_msg)
    core.log_message(user_msg)
    core.set_status(True, "AUTO")
    
    # First LLM call
    llm_util.run_llm_rounds(...)
    
    # Auto-pilot loop
    _run_auto_pilot_loop(...)
    return
```

### 3. cli.py: 自動ループ _run_auto_pilot_loop()

```python
def _run_auto_pilot_loop(provider, client, depname, messages, core, ...):
    """Auto-pilot loop. Asks LLM to continue or conclude after each response."""
    while True:
        # 1. Check x key exit
        with core.auto_pilot_exit_lock:
            if core.auto_pilot_exit_requested:
                core.auto_pilot_exit_requested = False
                core.auto_pilot_active = False
                print(_("\n[AUTO] Exited by user (x key)."))
                return

        # 2. Check max rounds (safety valve)
        core.auto_pilot_round += 1
        if core.auto_pilot_round >= core.auto_pilot_max_rounds:
            core.auto_pilot_active = False
            print(_("\n[AUTO] Max rounds (%(max)d) reached. Stopping.") 
                  % {"max": core.auto_pilot_max_rounds})
            return

        # 3. Check if LLM indicated completion
        last_text = _get_last_assistant_text(messages)
        if _is_completion_response(last_text):
            core.auto_pilot_active = False
            print(_("\n[AUTO] Review/analysis completed."))
            return

        # 4. Generate continue prompt (i18n)
        next_prompt = _get_continue_prompt()
        
        core.set_status(True, "AUTO")
        print(_("\n[AUTO] Round %(round)d/%(max)d") 
              % {"round": core.auto_pilot_round, 
                 "max": core.auto_pilot_max_rounds})
        
        user_msg = {"role": "user", "content": next_prompt}
        messages.append(user_msg)
        core.log_message(user_msg)
        
        llm_util.run_llm_rounds(...)
        
        core.set_status(True, "AUTO")


def _get_last_assistant_text(messages):
    for m in reversed(messages):
        if m.get("role") == "assistant":
            c = m.get("content", "")
            if isinstance(c, str) and c.strip():
                return c.strip()
    return ""


def _is_completion_response(text):
    """LLM自身が完了を表明したかチェック。"""
    t = text.strip().lower()
    # 単語のみ（他に内容がない）場合
    if t in ("done", "完了", "dоне", "termine", " hecho", "finished", "complete"):
        return True
    # それ以外は未完了とみなす
    return False


def _get_continue_prompt():
    """継続用プロンプトを現在のUI言語で返す。"""
    lang = detect_lang()
    if lang == "ja":
        return _("続けてください。追加の指摘があれば詳しく説明してください。\n"
                 "レビュー/分析が完了した場合は、'完了' とだけ答えてください。")
    else:
        return _("Continue your analysis. If you have more points to add, "
                 "please elaborate. If you have completed your review/analysis, "
                 "please respond with exactly 'DONE'.")
```

### 4. core.py: get_prompt() 変更

```python
def get_prompt() -> str:
    if auto_pilot_active:
        return "[AUTO] > "
    # ... existing logic ...
```

### 5. WEB/GUI 対応

**WEB UI**:
- 自動モード中: 入力欄を readonly + 「Auto running... press 'x' to stop」表示
- Stop ボタンの代わりに Auto off ボタン（websocket で `{type: "auto_pilot_off"}`）
- `{type: "auto_pilot_status"}` イベントで現在のラウンド数等を表示

**Desktop GUI**:
- 自動モード中: 入力欄をロック、ステータスバーに `[AUTO] round 3/5` 表示
- 停止ボタンが「Auto off」になる

## 動作例

### CLI

```
workdir> :auto このコードをレビューしてください。バグ、スタイル違反、テスト不足を重点的に。
[AUTO] Started.

[LLMのレビュー応答... バグ指摘、スタイル修正提案など]

[AUTO] Round 1/5

[LLMの応答... さらに深掘りした指摘]

[AUTO] Round 2/5

[LLMの応答... 「以上でレビューを完了します」]
[AUTO] Review/analysis completed.
workdir> 
```

### xキー割り込み

```
[AUTO] Round 2/5 > 
[ユーザーが x キーを押す]
[AUTO] Exited by user (x key).
workdir> 
```

## 考慮点

| 項目 | 内容 |
|---|---|
| **トークン消費** | 自動モード中はトークンを消費し続ける。`--max-rounds` が安全弁 |
| **完了判定の堅牢性** | LLM によっては「完了」と言わずにダラダラ続ける可能性がある。その場合は `--max-rounds` または `x` キーで止める |
| **i18n** | 継続用プロンプトは `_()` 経由。`.po` ファイルで全言語分用意する |
| **c キーとの共存** | `c` はストリーミング中断のみ。自動モードは継続される。`x` でモード終了 |
| **ツール実行** | LLM がツールを呼び出しても既存の tool loop で処理される |
| **WEB/GUI** | 自動モード中は入力欄ロック。`x` キーは CLI 専用（キーボード監視スレッドが必要）。WEB はボタン、GUI はボタンで代用 |

## 実装順序（推奨）

1. `core.py`: 状態変数追加 + `x` キー監視を interrupt monitor に追加
2. `cli.py`: `:auto` コマンド + `_run_auto_pilot_loop()` + `_get_continue_prompt()`
3. 動作確認（CLI）
4. WEB/GUI 対応
5. 全 `.po` に翻訳追加
