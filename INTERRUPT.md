# c キー割り込み + "停止" プロンプト注入

## 目的

LLM ストリーミング応答中に **c キー** を押すだけで応答生成を中断し、代わりに `"停止"` というプロンプトをユーザー入力として LLM へ送信する機能。

これにより「もう良い、止めて」「方向性を変えて」といった意図を、一行入力を待たずに即座に伝えられる。

## 要求

- **トリガー**: 1 回の `c` キー押下（大文字小文字不問、Ctrl+C ではない）
- **タイミング**: LLM ストリーミング出力中の任意のタイミング
- **効果**:
  1. 現在の応答生成を直ちに中断（途中までの出力は破棄 or `[interrupted]` 表記）
  2. `{"role": "user", "content": "停止"}` をメッセージ履歴に追加
  3. LLM が「停止」を受け取り、次の応答を生成する
- **既存動作との干渉**: `stdin_loop`（行入力）および `human_ask` に影響しない
- **クロスプラットフォーム**: Windows (`msvcrt`) / POSIX (`termios`+`tty`) 両対応

## アーキテクチャ

### 現状のスレッド構成

```
[main thread]                  [stdin_loop thread]
  event_queue.get()  <------     input() / prompt()
       |                              |
  run_llm_rounds()               time.sleep(0.1)  ← BUSY時は何もしない
       |
  _call_openai_azure_round()
  _call_gemini_round()  etc.
       |
  streaming loop (1 token/event ずつ print)
```

- メインスレッド: `run_llm_rounds()` → プロバイダ呼び出し（同期的）
- `stdin_loop` スレッド: `input()` / `prompt_toolkit` で行入力待ち。BUSY 中は `time.sleep(0.1); continue` で何もしない
- **単一キー "c" を検出する仕組みが存在しない**

### 変更後

```
[main thread]                  [stdin_loop thread]          [interrupt_monitor thread]  ← NEW
  event_queue.get()  <------     input() / prompt()          kbhit() / select() ループ
       |                              |                      (BUSY時のみ)
  run_llm_rounds()               time.sleep(0.1)
       |                              |
  streaming loop                     |
  └─ 毎チャンク後:                   |
       if core.interrupt_requested:  |
         break                       |
                                     |
              core.interrupt_requested = True  ← "c"検出
```

新たに **interrupt_monitor スレッド** を追加。`stdin_loop` とは独立して動作する。

## 変更対象ファイル

| ファイル | 変更内容 |
|---|---|
| `src/uagent/core.py` | 割り込みフラグ・ロック, モニタースレッド起動/停止関数 |
| `src/uagent/cli.py` | `main()` でモニタースレッド起動, 終了時停止 |
| `src/uagent/uagent_llm.py` | `run_llm_rounds()` 内で割り込み後処理（"停止"注入） |
| `src/uagent/llm_round_helpers.py` | 各プロバイダの呼び出し後に割り込みチェック追加 |
| `src/uagent/providers/llm_openai_responses.py` | `parse_responses_stream()` に割り込みチェック追加 |
| `src/uagent/providers/llm_gemini.py` | ストリーミングループに割り込みチェック追加（必要な場合） |
| `src/uagent/providers/llm_claude.py` | 同上 |
| `src/uagent/providers/llm_deepseek.py` | 同上 |
| `src/uagent/providers/llm_zai.py` | 同上 |

## 実装詳細

### 1. core.py: グローバルフラグとモニタースレッド

```python
# --- Interrupt (c-key) ---
interrupt_requested = False
"""Set True when user presses 'c' during LLM streaming."""

interrupt_lock = threading.Lock()

# モニタースレッド管理
_interrupt_monitor_thread: threading.Thread | None = None
_interrupt_monitor_stop = threading.Event()


def start_interrupt_monitor() -> None:
    """Start daemon thread that monitors for single 'c' keypress."""
    global _interrupt_monitor_thread
    if _interrupt_monitor_thread is not None:
        return

    def _monitor() -> None:
        import os as _os  # local ref for speed

        while not _interrupt_monitor_stop.is_set():
            # BUSY 時のみ監視
            if not status_busy:
                _interrupt_monitor_stop.wait(0.1)
                continue

            if _os.name == "nt":
                _check_key_win()
            else:
                _check_key_posix()

            _interrupt_monitor_stop.wait(0.05)

    _interrupt_monitor_thread = threading.Thread(
        target=_monitor, daemon=True, name="uagent-interrupt-monitor"
    )
    _interrupt_monitor_thread.start()


def stop_interrupt_monitor() -> None:
    global _interrupt_monitor_thread
    _interrupt_monitor_stop.set()
    _interrupt_monitor_thread = None
```

#### Windows 版キーチェック

```python
def _check_key_win() -> None:
    """Check for 'c' keypress on Windows (msvcrt, non-blocking)."""
    try:
        import msvcrt  # type: ignore
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key in (b"c", b"C"):
                with interrupt_lock:
                    interrupt_requested = True
    except Exception:
        pass
```

`msvcrt.kbhit()` は Windows コンソールの入力バッファをポーリングする。`sys.stdin.readline()` とは独立した低レベル API のため、`stdin_loop` の `input()` と競合しない。

#### POSIX 版キーチェック

```python
def _check_key_posix() -> None:
    """Check for 'c' keypress on POSIX (termios/tty, non-blocking).

    Safety: this is called only when status_busy == True.
    During busy periods, stdin_loop is NOT calling input() or prompt_toolkit,
    so temporarily switching stdin to raw mode is safe.
    """
    try:
        import select
        import termios
        import tty

        r, _, _ = select.select([sys.stdin], [], [], 0)
        if not r:
            return

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            # Switch to raw mode so each keypress is delivered immediately
            tty.setraw(fd)
            ch = sys.stdin.buffer.read(1)
        finally:
            # Restore original terminal settings immediately
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

        if ch and ch.lower() == b"c":
            with interrupt_lock:
                interrupt_requested = True
    except Exception:
        pass
```

**安全である理由**:
- BUSY 中は `stdin_loop` が `input()` / `prompt_toolkit` を呼ばない（`time.sleep(0.1); continue` のみ）
- `select.select()` で実際に読み取り可能なバイトがある場合のみ raw mode に切り替える
- 1バイト読み取った直後に `TCSADRAIN` で元の設定に戻す（遅延は出力ドレインまで）
- 例外が発生しても `finally` で確実に復帰する

### 2. cli.py: モニタースレッドの起動/停止

`main()` 内で `start_background_scheduler` と同様に起動し、`finally` ブロック内で停止する。

```python
# cli.py main() 内
start_interrupt_monitor()  # ← 追加

t = threading.Thread(target=stdin_loop, daemon=True)
t.start()

running = True
try:
    while running:
        ev = core.event_queue.get()
        # ... 既存コード ...
finally:
    stop_interrupt_monitor()  # ← 追加
    # ... 既存コード ...
```

### 3. ストリーミングループへの割り込みチェック挿入

各ストリーミングループで、**1 チャンク/イベント処理の直後** に以下を挿入する。

#### 3a. `parse_responses_stream()` (llm_openai_responses.py)

`for ev in it:` ループの先頭にチェックを追加:

```python
for ev in it:
    # --- 割り込みチェック: 各イベント処理の先頭で ---
    with core.interrupt_lock:
        if core.interrupt_requested:
            core.interrupt_requested = False
            # Web mode に割り込みシグナル
            try:
                if core is not None and bool(getattr(core, "_is_web", False)):
                    lm = getattr(core, "log_message", None)
                    if callable(lm):
                        lm({"type": "assistant_stream_interrupted"})
            except Exception:
                pass
            break

    # ... 既存のイベント処理 ...
```

#### 3b. その他のプロバイダのストリーミングループ

Gemini (`gemini_chat_with_tools`)、Claude (`claude_chat_with_tools`)、DeepSeek (`deepseek_chat_with_tools`)、Z.AI (`zai_chat_with_tools`) の各ストリーミングループにも同様のチェックを挿入する。

各プロバイダのストリーミングループは、トークンを print した直後の箇所にチェックを追加:

```python
# （各プロバイダのストリーミングループ内）
print(chunk_text, end="", flush=True)

# --- 割り込みチェック ---
with core.interrupt_lock:
    if core.interrupt_requested:
        core.interrupt_requested = False
        break
```

### 4. non-streaming 呼び出しの対応

`client.chat.completions.create()`（non-streaming）は同期的 HTTP 呼び出しで途中中断できない。

`_call_maybe_thread()`（llm_helpers.py）が `use_llm_thread=True` の場合に LLM 呼び出しをサブスレッドで実行し、メインスレッドは `th.join(0.05)` でポーリングしている。このポーリングループ内で割り込みフラグをチェックする。

```python
def _call_maybe_thread(fn, *, use_llm_thread, core=None):
    if not use_llm_thread:
        return fn()

    box = {"res": None, "exc": None}

    def _runner():
        try:
            box["res"] = fn()
        except BaseException as e:
            box["exc"] = e

    th = threading.Thread(target=_runner, daemon=True)
    th.start()

    while th.is_alive():
        th.join(0.05)
        # --- 割り込みチェック（non-streaming の遅延検出用）---
        if core is not None:
            with core.interrupt_lock:
                if core.interrupt_requested:
                    # スレッドは強制終了できないのでフラグは維持
                    # run_llm_rounds 側で呼び出し後チェック
                    pass

    # 呼び出し元でチェックするためにフラグを残す
    if box.get("exc") is not None:
        raise box["exc"]
    return box.get("res")
```

non-streaming では「現在の HTTP 呼び出し完了後に割り込み発動」となる。これは仕様として許容する（ストリーミング時のみ即時割り込み）。

### 5. `run_llm_rounds()` の割り込み後処理

各ラウンドの先頭と、ストリーミングループ break 後に割り込みフラグをチェックする。

```python
# run_llm_rounds() 内、各ラウンドの先頭
with core.interrupt_lock:
    if core.interrupt_requested:
        core.interrupt_requested = False
        _inject_stop_prompt(messages, core)
        continue
```

ストリーミングループ（`parse_responses_stream` 等）から戻った直後も同じチェック:

```python
# run_llm_rounds() 内、_call_openai_azure_round() 等の呼び出し直後
with core.interrupt_lock:
    if core.interrupt_requested:
        core.interrupt_requested = False
        _inject_stop_prompt(messages, core)
        continue
```

`_inject_stop_prompt()` の実装:

```python
def _inject_stop_prompt(
    messages: list[dict[str, Any]],
    core: Any,
) -> None:
    """Inject '停止' as a user message and log it."""
    print("\n[INTERRUPT] " + _("Stopped by user. Sending '停止' to LLM..."))
    user_msg = {"role": "user", "content": "停止"}
    messages.append(user_msg)
    core.log_message(user_msg)
```

## ストリーミング出力の扱い

割り込み時に **既に print したトークン** をどうするか。

| モード | 方針 |
|---|---|
| CLI (stdout) | 最後に `"\n[INTERRUPT] Stopped.\n"` を追記する。途中までの出力はそのまま残す |
| Web (core.log_message) | `assistant_stream_interrupted` イベントを送信。UI 側で途中出力を破棄/グレー表示できる |

## 動作フロー（CLI の場合の具体例）

```
User> 今日の天気を詳しく教えて
[STATE] BUSY [LLM]

今日の東京の天気は晴れで、気温は... [c キーが押される]
[INTERRUPT] Stopped. Sending '停止' to LLM...

[STATE] BUSY [LLM]
承知しました。別の質問はありますか？
```

## 考慮点・制約

| 項目 | 内容 |
|---|---|
| **Ctrl+C との競合** | Ctrl+C は `KeyboardInterrupt` として既存の終了処理に入る。c キー単体とは区別される |
| **human_ask 中の c キー** | `human_ask` がアクティブな状態では `status_busy` は False になる場合がある。`human_ask_active` チェックを追加するか、`status_busy` とは独立したフラグ `llm_streaming_active` を導入する |
| **non-streaming の遅延** | `client.chat.completions.create()`（non-streaming）は HTTP 呼び出し完了まで中断不可。完了後に割り込みが発動する |
| **tool 実行中の c キー** | tool 実行中（コード生成等）も割り込み可能とするかは別途検討。初期は LLM ストリーミング中のみ対象 |
| **prompt_toolkit との共存** | BUSY 中は `prompt_toolkit` は使われないため競合しない。Idle 時はモニタースレッドがスリープするため問題なし |
| **POSIX pipe/リダイレクト時** | `sys.stdin.isatty()` が False の場合、`tty.setraw()` は失敗する（`termios.error`）。例外キャッチで無視されるので安全 |

## 環境変数での制御（オプション）

```
UAGENT_INTERRUPT_KEY=c    # 割り込みキー（デフォルト: c）
UAGENT_INTERRUPT_PROMPT=停止  # 注入プロンプト（デフォルト: 停止）
UAGENT_INTERRUPT_ENABLED=1    # 機能のON/OFF（デフォルト: 1）
```

## 実装状況

| # | 項目 | 状態 |
|---|---|---|
| 1 | `core.py`: フラグ + モニタースレッド（Win + POSIX） | 完了 |
| 2 | `cli.py`: モニタースレッド起動/停止 | 完了 |
| 3 | `llm_openai_responses.py` `parse_responses_stream()`: 割り込みチェック | 完了 |
| 4 | `uagent_llm.py` `run_llm_rounds()`: 割り込み後処理（"停止"注入） | 完了 |
| 5 | 動作確認 | 未実施 |
| 6 | 他プロバイダ（Gemini/Claude/DeepSeek/Z.AI）のストリーミングループ内チェック | 未対応（ラウンド終了後チェックで代替） |
| 7 | non-streaming パスの遅延対応 | 未対応 |
| 8 | 環境変数によるカスタマイズ | 未対応 |

### 動作確認手順

```
uag
User> 長めの応答を引き出す質問...
# LLM がストリーミング中に c キーを押す
# → 応答が中断され、[INTERRUPT] メッセージ
# → LLM が「停止」を受け取り次の応答を生成
```
