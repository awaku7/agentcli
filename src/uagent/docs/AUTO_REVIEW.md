# AUTO_REVIEW — :auto command review & refactoring (complete)

This document describes the `:auto` command implementation and the refactoring
that was applied. It serves as both a design reference and an implementation record.

**Status: Complete.** All changes have been implemented, tested (ruff/mypy/black/py_compile),
and merged into `src/uagent/uagent_llm.py` and `src/uagent/util_tools.py`.

______________________________________________________________________

## 1. Current implementation

### 1.1 Entry points

| File | Symbol | Role |
|---|---|---|
| `util_tools.py` | `_handle_cmd_auto()` (L2342) | Parse `:auto <goal>` / `:auto off` |
| `util_tools.py` | `_run_auto_pilot_loop()` (L2262) | Main auto-pilot round loop |
| `util_tools.py` | `_ask_reviewer_judgment()` (L2219) | Meta query: judge completion |
| `util_tools.py` | `_build_judgment_messages()` (L2187) | Build separate messages for judgment |
| `util_tools.py` | `_get_followup_prompt()` (L2177) | Build continuation prompt |
| `cli.py` | `main()` (L918) | Orchestrates first LLM round + auto-pilot loop |
| `core.py` | `auto_pilot_*` globals | State flags and lock |

### 1.2 Flow

```
User: ":auto translate README to Japanese"
  │
  ├─ stdin_loop thread → event_queue → main() thread
  │
  ├─ handle_command("auto ...") → _handle_cmd_auto()
  │   └─ sets core.auto_pilot_active = True
  │   └─ returns CommandResult(run_llm=True, prompt=goal)
  │
  ├─ main(): run_llm_rounds()  ──  Step A (first round, same context)
  │
  └─ main(): _run_auto_pilot_loop()
       │
       └─ while True:
            ├─ [check] auto_pilot_exit_requested? → return
            ├─ [check] round > max_rounds? → return
            │
            ├─ Step A: run_llm_rounds()  ──  main query (BLOCKING, same context)
            │
            └─ Step B: _ask_reviewer_judgment()
                 └─ client.chat.completions.create() directly
                      ├─ On success → parse COMPLETE / CONTINUE
                      └─ On fallback → always CONTINUE
```

### 1.3 Known problems

| # | Problem | Detail |
|---|---|---|
| P1 | `x` key exit is not immediate | Flag is checked only at loop top; during `run_llm_rounds()` (Step A) the main thread is blocked, so `x` takes effect only after the current round finishes. |
| P2 | LLM round cannot be interrupted mid-flight | `run_llm_rounds()` has no mechanism to abort on `auto_pilot_exit_requested`. The interrupt monitor (`c` key → `interrupt_requested`) works but only injects a stop prompt, it doesn't exit the auto-pilot loop. |
| P3 | Judgment bypasses `run_llm_rounds()` | `_ask_reviewer_judgment()` calls `client.chat.completions.create()` directly. This means it does NOT use the same code path as the main query — no Responses API, no provider-specific handling. |
| P4 | Judgment fallback for non-OpenAI providers | Providers like Gemini/Claude raise `AttributeError`/`NotImplementedError` in `_ask_reviewer_judgment()`, which is caught and silently returns `"CONTINUE"`. Result: auto-pilot never terminates via judgment on those providers. |
| P5 | Judgment shares main context | `_build_judgment_messages()` builds a separate message list for the reviewer, but the judgment itself is performed inline in `_run_auto_pilot_loop()`. Not truly separated. |

______________________________________________________________________

## 2. Proposed refactoring

### 2.1 Goal

- Make `:auto` exit work reliably and immediately
- Use the same LLM code path (Responses API included) for judgment
- Keep judgment in a **separate message context** (not polluting main messages)
- Keep changes minimal and backward-compatible

### 2.2 Changes to `run_llm_rounds()` in `uagent_llm.py`

Add two optional parameters:

```python
def run_llm_rounds(
    ...,
    judgment_mode: bool = False,
    judgment_messages: list[dict] | None = None,
) -> str | None:
```

When `judgment_mode=True`:

1. Use `judgment_messages` instead of the main `messages` list
1. Do NOT modify the main `messages` list (no append, no log)
1. Force `send_tools=False` (no tool execution in judgment rounds)
1. Run exactly **1 round** only — if tool_calls are returned, ignore them and return the assistant text as-is
1. Skip all side effects: outfile append, image open, streaming to web UI, etc.
1. Return the final `assistant_text` (or empty string on failure)
1. When `judgment_mode=False` (default), behavior is unchanged and return value is `None`

### 2.3 Changes to `_ask_reviewer_judgment()` in `util_tools.py`

Replace the direct `client.chat.completions.create()` call with a call to `run_llm_rounds()` in judgment mode:

```python
def _ask_reviewer_judgment(
    provider, client, depname, messages, core,
) -> str:
    judgment_msgs = _build_judgment_messages(messages, core.auto_pilot_goal)

    result_text = run_llm_rounds(
        provider, client, depname, messages,
        core=core,
        make_client_fn=...,
        append_result_to_outfile_fn=...,
        try_open_images_from_text_fn=...,
        judgment_mode=True,
        judgment_messages=judgment_msgs,
    )

    text = (result_text or "").strip().upper()
    print(_("\n[AUTO:judge] %(judgment)s") % {"judgment": text})
    return "COMPLETE" if "COMPLETE" in text else "CONTINUE"
```

### 2.4 Interrupt improvements

#### 2.4.1 Mid-round exit check in `run_llm_rounds()`

Add `auto_pilot_exit_requested` checks in `run_llm_rounds()` alongside the existing `interrupt_requested` checks:

```python
# Inside run_llm_rounds(), at each "--- Interrupt check ---" point:
with _core_module.interrupt_lock:
    if _core_module.interrupt_requested:
        _core_module.interrupt_requested = False
        _inject_stop_prompt(messages, core)
        break

# NEW: auto-pilot exit check
if judgment_mode:
    with _core_module.auto_pilot_exit_lock:
        if _core_module.auto_pilot_exit_requested:
            _core_module.auto_pilot_exit_requested = False
            return ""  # signal exit
```

This allows `x` key to abort even during an LLM call, without waiting for the round to finish.

#### 2.4.2 Better `x` key UX

The interrupt monitor already detects `x` key and sets `auto_pilot_exit_requested`. The missing piece is that `_run_auto_pilot_loop()` only checks this flag at the top of the while loop. With the mid-round check above, `x` can now take effect:

- During Step A (`run_llm_rounds`) → mid-round check triggers and returns early
- During Step B (`_ask_reviewer_judgment` → `run_llm_rounds` in judgment mode) → same

If `x` is pressed between rounds, the existing top-of-loop check handles it.

### 2.5 Backward compatibility

- `judgment_mode` defaults to `False` → all existing callers (`:skills`, normal user messages, timer events, inject-message, etc.) are unaffected
- The return type changes only when `judgment_mode=True`; existing callers expect `None` return and get it

______________________________________________________________________

## 3. Files to modify

| File | Changes |
|---|---|
| `src/uagent/uagent_llm.py` | Add `judgment_mode` / `judgment_messages` params to `run_llm_rounds()`; add mid-round `auto_pilot_exit_requested` check; skip logging/side effects in judgment mode; return `assistant_text` in judgment mode |
| `src/uagent/util_tools.py` | Replace `_ask_reviewer_judgment()` body with `run_llm_rounds(judgment_mode=True)` call |

______________________________________________________________________

## 4. Test scenarios

After implementation, verify with these scenarios:

| # | Scenario | Expected result |
|---|---|---|
| T1 | `:auto "say hello and stop" --max-rounds 1` | Runs 1 round, then completes (no infinite loop). |
| T2 | `:auto "count from 1 to 5"` → press `x` during round 2 | `x` takes effect immediately, loop exits before round 2 finishes. |
| T3 | `:auto "analyze this file"` on Gemini/Claude provider | Judgment uses the same provider path; COMPLETE/CONTINUE works (no silent fallback). |
| T4 | `:auto off` | Stops auto-pilot immediately regardless of state. |
| T5 | Normal (non-auto) usage after `:auto` has finished | No side effects from judgment mode; main messages are clean. |

______________________________________________________________________

## 5. Concerns and countermeasures

### C1: `messages.append` のガードがプロバイダごとに必要

**Problem**: judgment mode では `_append_assistant_message()` / `messages.append()` / `core.log_message()` を全プロバイダ分岐でスキップする必要がある。6系統あり漏れやすい。

**Solution**: `run_llm_rounds()` の先頭で、judgment mode 用に `messages` を差し替える。

```python
# At the very top of run_llm_rounds(), before the while loop:
_actual_messages = messages  # keep original reference
if judgment_mode:
    messages = judgment_messages or []
```

これで以降の全コードが自動的に judgment_messages を使用する。`messages.append()` も `core.log_message()` も judgment_messages に対して動作する。メイン messages は一切変更されない。
→ プロバイダごとの個別ガードが不要になる。

ただし `core.log_message()` が judgment_messages をログに書いてしまう。judgment mode では `core.log_message()` の呼び出し自体を抑制するガードが必要（後述）。

### C2: Interrupt 時の `_inject_stop_prompt` がメイン `messages` を汚染

**Problem**: `_inject_stop_prompt(messages, core)` が judgment mode でもメイン `messages` に `[STOP]` を追記してしまう。

**Solution**: C1 の `messages` 差し替えにより、`_inject_stop_prompt` は judgment_messages に対して追記する。メイン messages は汚染されない。judgment mode で interrupt が来たら単に `return ""` すればよい（judgment_messages への `[STOP]` 追記は無害なので放置可）。

### C3: `finish_skill` コールバックがメイン `messages` を捕捉

**Problem**:

```python
cb.finish_skill = make_finish_skill_handler(messages, core)
```

のクロージャがメイン `messages` を捕捉している。judgment 中に finish_skill が呼ばれるとメイン messages が書き換わる。

**Solution**: judgment mode では `cb.finish_skill` の上書きをスキップする。

```python
if not judgment_mode:
    cb.finish_skill = make_finish_skill_handler(messages, core)
```

また `finally` ブロックでの復元は常に実行する（judgment mode で上書きしなかった場合は prev と同じなので安全）。

### C4: 翻訳レイヤーを通る

**Problem**: judgment のシステムプロンプトは英語固定（`COMPLETE` / `CONTINUE`）だが、翻訳レイヤーが有効だとメッセージが翻訳され期待したトークンを返さない可能性がある。

**Solution**: judgment mode では `load_translate_config()` の結果を無視し、翻訳をスキップする。

```python
# Before translate config loading:
if judgment_mode:
    tr_cfg = None  # signal: skip translate
else:
    tr_cfg = load_translate_config()
```

各 translate 呼び出し側で `if tr_cfg and not judgment_mode:` とガードするか、`tr_cfg = None` にしておけば `_translate_call_messages(call_messages, None)` が何もしない設計になっていればそれでよい（内部実装次第）。

### C5: `gemini_cache_name` / `_maybe_auto_shrink_messages`

**Problem**: `_init_gemini_cache()` がメイン messages に対して実行される。`_maybe_auto_shrink_messages` が judgment_messages に対して走る可能性がある。

**Solution**:

- `_init_gemini_cache()` → judgment mode では `cache_mgr = None` / `gemini_cache_name = None` でスキップ
- `_maybe_auto_shrink_messages()` → judgment mode ではスキップ（1ラウンドしか回らないので shrink 不要）

```python
if judgment_mode:
    cache_mgr, gemini_cache_name = None, None
else:
    cache_mgr, gemini_cache_name = _init_gemini_cache(...)
```

### C6: `run_llm_rounds()` の複雑さ

**Problem**: 400行の関数に judgment mode ガードを追加するとさらに読みづらくなる。

**Solution**: 以下の方針で最小限のガードに抑える:

1. C1 の `messages` 差し替えにより、各プロバイダ分岐での個別ガードが不要
1. ガードが必要な共通処理は早期 return / 早期スキップでまとめる:

```python
# Top of run_llm_rounds():
_actual_messages = messages
if judgment_mode:
    messages = judgment_messages or []
    # judgment mode: no tools, no cache, no translate
    send_tools_this_round = False
    cache_mgr, gemini_cache_name = None, None
    tr_cfg = None
    # (skip finish_skill override, skip outfile, etc.)
```

各プロバイダ分岐の後処理（`_emit_final_answer_if_any`, `_append_assistant_message`）も `messages` 差し替えで自動的に judgment_messages に作用する。メイン messages は触らない。

### C7: エラー時の振る舞い

**Problem**: 現在の `_ask_reviewer_judgment()` は例外をキャッチして `"CONTINUE"` を返すフェイルソフト。judgment mode で `run_llm_rounds()` が例外を投げた場合の設計が必要。

**Solution**: `run_llm_rounds()` の呼び出し元 `_ask_reviewer_judgment()` で catch する:

```python
def _ask_reviewer_judgment(...) -> str:
    try:
        result_text = llm_util.run_llm_rounds(
            ..., judgment_mode=True, judgment_messages=judgment_msgs
        )
    except Exception:
        warnings.warn(f"[AUTO] Judgment call failed: {traceback.format_exc()}")
        return "CONTINUE"
    text = (result_text or "").strip().upper()
    return "COMPLETE" if "COMPLETE" in text else "CONTINUE"
```

`run_llm_rounds()` 内部で例外が発生しても、呼び出し元でフェイルソフトできる。

### C8: `_maybe_auto_shrink_messages` が judgment_messages にかかる

**Problem**: judgment mode でも `_maybe_auto_shrink_messages()` が呼ばれると、意図せず judgment_messages を shrink する可能性がある。

**Solution**: C5 同様、judgment mode では `_maybe_auto_shrink_messages()` をスキップ。ループが1ラウンドしか回らないので shrink は不要。

______________________________________________________________________

## 6. Implementation strategy summary

### Core insight

`run_llm_rounds()` の先頭で `messages` を差し替える（C1）ことで、大多数のプロバイダ分岐のガードが不要になる。

```python
# Top of run_llm_rounds():
_actual_messages = messages
if judgment_mode:
    messages = judgment_messages or []
```

これにより、各プロバイダ分岐内の `messages.append()` / `_append_assistant_message()` / `core.log_message()` / `_inject_stop_prompt()` は自動的に judgment_messages に対して動作する。

### What needs explicit guard

| Feature | Guard condition |
|---|---|
| `send_tools` | `if judgment_mode: send_tools_this_round = False` |
| `cb.finish_skill` override | `if not judgment_mode:` |
| `cache_mgr` / `gemini_cache` | `if judgment_mode: cache_mgr, gemini_cache_name = None, None` |
| Translate config | `if judgment_mode: tr_cfg = None` |
| `_maybe_auto_shrink_messages` | `if judgment_mode: skip` |
| `_emit_final_answer_if_any` | `if judgment_mode: skip` |
| `core.log_message()` calls | `if judgment_mode: skip`（各プロバイダ分岐内で個別ガード） |
| `auto_pilot_exit_requested` check | `if auto_pilot_exit_requested: break`（judgment_mode に関わらず常にチェック） |
| Loop termination | `if judgment_mode: break after 1 round` |
| Return value | `if judgment_mode: return assistant_text` |

### What is automatically safe (due to messages swap)

- `messages.append(...)` → goes to judgment_messages
- `_append_assistant_message(messages=messages, ...)` → same
- `_inject_stop_prompt(messages, core)` → same

### What still needs individual guard (no automation possible)

- `core.log_message(text)`: writes to a log file; does not go through `messages`. Must be guarded per call site.
- `_emit_final_answer_if_any(...)`: triggers outfile append and image open; must be guarded per call site.

______________________________________________________________________

## 7. Open questions

- Should `run_llm_rounds()` in judgment mode print streaming output or suppress it entirely?
  → Proposal: suppress. Judgment is a meta-operation; showing tokens to the user is noise.
- Should `x` key also trigger `:auto off` equivalent (reset `auto_pilot_active`)?
  → Already done: `_run_auto_pilot_loop()` sets `core.auto_pilot_active = False` on exit.

## 8. 統合前の設計記録（旧 `docs/AUTO_REVIEW.md`）

この節は、旧ユーザー向け設計記録にのみ存在した要求・CLIフロー・i18n・割り込み仕様を保持するためのものです。実装状況と現在の正本は本書の前半を優先します。

## 目的

ユーザーに代わってシステムが **レビュワー役** として LLM と自動で対話を継続する機能。
ユーザーが **目的（ゴール）** を指定すると、システムがレビュワーとして LLM にフォローアップ質問を自動生成して送信し続け、
**レビュワー（システム）が目的達成を判断した時点**で自動モードを終了する。

**ユースケース**: コードレビュー、バグ調査、設計検討、要件整理など、複数ラウンドの深掘りが必要なタスク。

## 要求

- **トリガー**: コマンド `:auto <目的>` で起動
- **自動応答生成**: システム（レビュワー）が LLM に対して目的達成のために次の適切な質問/指示を自動生成する（言語は現在の UI 言語に従う）
- **完了判定**: **レビュワー（システム）が、LLM に meta-judgment クエリを送って判断する**。1ラウンド = 2回のLLM呼び出し
  1. メインクエリ: レビュー/分析のための質問
  1. メタクエリ: 「レビュワーとして、目的は達成されたか？」を判定
- **安全弁**: 最大ラウンド数 `--max-rounds N`（デフォルト 10）を超えたら強制終了
- **割り込み**: `x` キーで自動モードを即座に終了し、通常の手動対話に戻る
- **既存の `c` キーとの関係**: `c` = 今のLLM応答を中断（"停止"注入、モードは継続）。`x` = 自動モード自体を抜ける

## アーキテクチャ

### 1ラウンドの構成（2回のLLM呼び出し）

```
ラウンド N:
  Step A: メインクエリ
    [System] 目的に基づいたフォローアップ質問（i18n）
    [LLM] 分析/レビュー結果...

  Step B: メタクエリ（レビュワー判断）
    [System] あなたはレビュワーです。目的は達成されましたか？
              COMPLETE / CONTINUE で答えてください。
    [LLM-as-reviewer] CONTINUE (or COMPLETE)

  CONTINUE → 次のラウンドへ
  COMPLETE → 自動モード終了
```

### フロー

```
:auto このコードをレビューして
  ↓
[初期プロンプトを user message として送信]
run_llm_rounds() → LLMがレビュー結果を返す
  ↓
[自動モードループ]
1. x キーチェック → 押されていたら break
2. ラウンド数チェック → max 超えていたら break
3. Step A: 継続用プロンプト（i18n）を追加 → run_llm_rounds()
4. Step B: メタクエリ（reviewer judgment）を実行
5. COMPLETE → break（終了）。CONTINUE → ループ継続
  ↓
通常モードに戻る
```

## 変更対象ファイル

| ファイル | 変更内容 |
|---|---|
| `core.py` | 自動モード状態変数 + `x` キー検出を `_check_key_win/posix` に追加 |
| `cli.py` | `:auto` コマンド + `_run_auto_pilot_loop()` + メタクエリ判定関数 |
| `web.py` | WebSocket `"auto_pilot"` ハンドラ |
| `templates/index.html` | 自動モード中は入力欄ロック＋「Auto running...」表示 |
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
auto_pilot_max_rounds = 10
auto_pilot_goal: str = ""

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
    max_rounds = 10
    i = 0
    while i < len(args):
        if args[i] == "--max-rounds" and i + 1 < len(args):
            max_rounds = int(args[i + 1])
            i += 2
        else:
            goal_parts.append(args[i])
            i += 1

    goal = " ".join(goal_parts)

    core.auto_pilot_goal = goal
    core.auto_pilot_max_rounds = max_rounds
    core.auto_pilot_round = 0
    core.auto_pilot_exit_requested = False
    core.auto_pilot_active = True

    # Send initial goal
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

### 3. cli.py: \_run_auto_pilot_loop()

```python
def _run_auto_pilot_loop(provider, client, depname, messages, core, ...):
    """
    Auto-pilot loop.
    1ラウンド = 2回のLLM呼び出し:
      Step A: メインクエリ（レビュー/分析の継続）
      Step B: メタクエリ（レビュワーとして完了判定）
    """
    while True:
        # 1. x key exit check
        with core.auto_pilot_exit_lock:
            if core.auto_pilot_exit_requested:
                core.auto_pilot_exit_requested = False
                core.auto_pilot_active = False
                print(_("\n[AUTO] Exited by user (x key)."))
                return

        # 2. Max rounds check
        core.auto_pilot_round += 1
        if core.auto_pilot_round >= core.auto_pilot_max_rounds:
            core.auto_pilot_active = False
            print(_("\n[AUTO] Max rounds (%(max)d) reached. Stopping.")
                  % {"max": core.auto_pilot_max_rounds})
            return

        # === Step A: メインクエリ ===
        next_prompt = _get_followup_prompt(core.auto_pilot_goal)

        core.set_status(True, "AUTO")
        print(_("\n[AUTO] Round %(round)d/%(max)d")
              % {"round": core.auto_pilot_round,
                 "max": core.auto_pilot_max_rounds})

        user_msg = {"role": "user", "content": next_prompt}
        messages.append(user_msg)
        core.log_message(user_msg)

        llm_util.run_llm_rounds(...)

        core.set_status(True, "AUTO")

        # === Step B: メタクエリ（レビュワー判断） ===
        judgment = _ask_reviewer_judgment(
            provider, client, depname, messages, core,
            make_client_fn, ...)

        if judgment == "COMPLETE":
            core.auto_pilot_active = False
            print(_("\n[AUTO] Review/analysis completed."))
            return
        # CONTINUE → continue loop
```

### 4. メタクエリ（レビュワー判断）

```python
def _get_followup_prompt(goal):
    """メインクエリ用の継続プロンプトを生成（i18n）。"""
    lang = detect_lang()
    if lang == "ja":
        return _("続けてください。目的: %(goal)s") % {"goal": goal}
    else:
        return _("Continue. Goal: %(goal)s") % {"goal": goal}


def _build_judgment_messages(messages, goal):
    """レビュワー判断用メッセージを構築。"""
    lang = detect_lang()

    if lang == "ja":
        system_prompt = (
            "あなたはレビュワーです。以下の会話を評価し、"
            "目的「%(goal)s」が達成されたか判定してください。\n"
            "達成された → COMPLETE\n"
            "まだ必要   → CONTINUE\n"
            "必ず COMPLETE または CONTINUE のみを答えてください。"
        )
    else:
        system_prompt = (
            "You are a reviewer. Evaluate the conversation below and "
            "determine whether the goal '%(goal)s' has been achieved.\n"
            "Achieved    → COMPLETE\n"
            "More needed → CONTINUE\n"
            "Reply with exactly COMPLETE or CONTINUE."
        )

    system_prompt = system_prompt % {"goal": goal}

    msgs = [{"role": "system", "content": system_prompt}]

    # 直近の会話履歴（最大6メッセージ = 3往復）を追加
    history = []
    for m in reversed(messages):
        if m.get("role") in ("user", "assistant"):
            content = m.get("content", "")
            if isinstance(content, str) and content.strip():
                history.append({"role": m["role"], "content": content[:500]})
                if len(history) >= 6:
                    break

    for h in reversed(history):
        msgs.append(h)

    msgs.append({"role": "user", "content": _("COMPLETE or CONTINUE?")})
    return msgs


def _ask_reviewer_judgment(provider, client, depname, messages, core, ...):
    """レビュワーとして完了判定をLLMに問い合わせる。"""
    judgment_msgs = _build_judgment_messages(messages, core.auto_pilot_goal)

    core.set_status(True, "AUTO:judge")

    # ツール無しの単発呼び出し（tool loop不要）
    resp = client.chat.completions.create(
        model=depname,
        messages=judgment_msgs,
        temperature=0.0,
        max_tokens=10,
    )

    text = ""
    if resp.choices and resp.choices[0].message:
        text = (resp.choices[0].message.content or "").strip().upper()

    print(_("\n[AUTO:judge] %(judgment)s") % {"judgment": text})

    return "COMPLETE" if "COMPLETE" in text else "CONTINUE"
```

### 5. プロンプト表示

```python
def get_prompt() -> str:
    if auto_pilot_active:
        return "[AUTO] > "
    # ... existing logic ...
```

## 動作例

```
workdir> :auto このコードをレビューしてください。バグ、スタイル、テスト不足を重点的に。
[AUTO] Started.
[LLMの応答... バグA、スタイル問題B...]

[AUTO] Round 1/10
[LLMの応答... さらに設計面の指摘]

[AUTO:judge] CONTINUE

[AUTO] Round 2/10
[LLMの応答... テスト不足の指摘]

[AUTO:judge] CONTINUE

[AUTO] Round 3/10
[LLMの応答... 「以上でレビューを完了します」的な内容]

[AUTO:judge] COMPLETE
[AUTO] Review/analysis completed.
workdir>
```

## 未解決の設計課題

- **プロバイダ依存**: `_ask_reviewer_judgment()` は `client.chat.completions.create` を直接呼んでいる。Gemini/Claude では別のAPIになる。`run_llm_rounds` を tool無し＋`max_tokens=10` で呼ぶラッパーが必要
- **トークン消費**: 2回/ラウンドのLLM呼び出し。`--max-rounds 10` で最大20回のAPI呼び出しになる。継続プロンプトやメタクエリの履歴は直近のみにして節約
- **WEB/GUI**: 自動モード中は入力欄ロックと状況表示が必要

## 実装順序（推奨）

1. `core.py`: 状態変数 + `x` キー監視
1. `cli.py`: `:auto` コマンド + `_run_auto_pilot_loop()` + `_ask_reviewer_judgment()`
1. 動作確認（CLI, OpenAI/Azure で）
1. 他プロバイダ（Gemini/Claude）対応
1. WEB/GUI 対応
1. 全 `.po` に翻訳追加
