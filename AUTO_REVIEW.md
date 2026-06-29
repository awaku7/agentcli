# 自動対話モード（Auto-Pilot）

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
  2. メタクエリ: 「レビュワーとして、目的は達成されたか？」を判定
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

### 3. cli.py: _run_auto_pilot_loop()

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
2. `cli.py`: `:auto` コマンド + `_run_auto_pilot_loop()` + `_ask_reviewer_judgment()`
3. 動作確認（CLI, OpenAI/Azure で）
4. 他プロバイダ（Gemini/Claude）対応
5. WEB/GUI 対応
6. 全 `.po` に翻訳追加
