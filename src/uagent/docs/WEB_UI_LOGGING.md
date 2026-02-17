# WEB_UI_LOGGING (Web UI log/message paths)

This document explains how `src/uagent/web.py` routes output to the Web UI.

Two channels:
- **log path**: stdout/stderr are captured and streamed via WebSocket as `type="log"`
- **message path**: chat messages are sent as `type="message"` / initial payload `type="init"`

Note:
- The Web UI may suppress some CLI-specific guide lines to reduce noise.

---

# WEB_UI_LOGGING（Web UI のログ/メッセージ経路）

このドキュメントは `src/uagent/web.py` の Web UI 表示に関する「ログ経路」と「メッセージ経路」を整理します。  
Web では stdout/stderr を WebSocket に流す機構があるため、どの文字列がどの経路で表示されるかを明確にします。

---

## 1. 表示経路の種類

Web UI で表示される情報は大きく2種類に分かれます。

### 1.1 log 経路（stdout/stderr → type="log"）

- `WebStdout` / `WebStderr` が `sys.stdout` / `sys.stderr` を差し替えています
- `print()` された内容を行単位でバッファリングし、WebSocket へ `type="log"` で送信します

対象コード:
- `class WebStdout`
- `class WebStderr`

特徴:
- “ログ出力” として UI に流れる
- `print(..., file=sys.stderr)` も含めて UI に出る
- UIはログとして扱うため、会話履歴（LLMに渡すmessages）とは別

### 1.2 message 経路（会話メッセージ → type="message"/type="init"）

- `WebManager.add_message()` が `type="message"` を送信する
- `WebManager.connect()` の初回送信 `type="init"` で `messages` と `status` を送る

特徴:
- UI上の “会話履歴” として表示される
- LLMへ渡す `history` と見た目がズレると混乱するため、`connect()` は `history` があれば `history` を元に init payload を構築する

---

## 2. history と messages の関係

- `web_manager.history`: LLMへ渡す実際の履歴（tools system message / long memory 等を含む）
- `web_manager.messages`: UI表示用の正規化済みメッセージ配列

初回接続（init payload）では、history が存在する場合は history を優先して UI へ送ります。

---

## 3. 「複数行」案内行の抑制（Web）

Web UI では CLI向けの操作案内（例: 「複数行」）がログやクイックガイドに混ざるとノイズになるため、Web UI 側で抑制しています。

### 3.1 log 経路での抑制

`WebStdout` / `WebStderr` の write/flush で、`"複数行"` を含む行は UI に送らないようにしています。

対象:
- stdout: `WebStdout.write()` / `WebStdout.flush()`
- stderr: `WebStderr.write()` / `WebStderr.flush()`

### 3.2 message 経路（welcome message）での抑制

`init_web()` が初回メッセージとして `get_welcome_message()` を UI に追加しますが、Web ではクイックガイド自体は表示しつつ、「複数行」行だけ除去した文字列を使います。

---

## 4. トラブルシュート

### 4.1 Web UI に「複数行」案内がまだ出る
次を疑ってください。

- ブラウザ側（HTML/JS）が独自にガイド文を生成している
- message 経路（init payload / add_message）に含まれている
- stderr 経由のログが未抑制（stdoutだけ抑制しても残る）

対処:
- “どの経路で出ているか” を切り分ける（logなのかmessageなのか）
- 該当文字列の送信箇所に絞って抑制を入れる
