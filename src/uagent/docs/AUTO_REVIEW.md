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
2. Do NOT modify the main `messages` list (no append, no log)
3. Force `send_tools=False` (no tool execution in judgment rounds)
4. Run exactly **1 round** only — if tool_calls are returned, ignore them and return the assistant text as-is
5. Skip all side effects: outfile append, image open, streaming to web UI, etc.
6. Return the final `assistant_text` (or empty string on failure)
7. When `judgment_mode=False` (default), behavior is unchanged and return value is `None`

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
2. ガードが必要な共通処理は早期 return / 早期スキップでまとめる:

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
