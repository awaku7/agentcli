# TODO

## LLM 通信が Ctrl-C で停止できない（または停止が遅い）

### 背景 / 症状
- エージェント実行中、LLM API 呼び出しが詰まったときに **Ctrl-C を押してもすぐ止まらない**ことがある。
- 特に Windows 環境で再現しやすい。
- 「止まらない」に見えるが、実際には通信ライブラリ内のブロッキング I/O から Python へ割り込みが戻ってこないケースがある。

### 影響範囲
- `src/uagent/uagent_llm.py` の LLM 呼び出し
  - `client.responses.create(...)`（Responses API）
  - `client.chat.completions.create(...)`（ChatCompletions）
- `src/uagent/util_providers.py` の OpenAI SDK クライアント生成
  - `httpx.Client(...)` を渡すが **timeout が未設定**

### なぜ timeout だけでは不十分か
- timeout は「無限待ちを防ぐ」ための上限であり、**Ctrl-C の即時停止を保証するものではない**。
- ただし timeout を適切に短く設定できれば、最悪でも timeout 到達で抜けるため、実用上のハングをかなり軽減できる。

### 目標
1. 無限ハングを防ぐ（必須）
2. Ctrl-C で停止したときに UI 状態（BUSY 表示等）が固着しない（必須）
3. 可能なら Ctrl-C を押した瞬間に通信をキャンセルする（努力目標）

---

## 実装方針（案）

### A. OpenAI SDK に渡す httpx.Client に timeout を導入（最優先）
- 対象: `src/uagent/util_providers.py`
- `httpx.Client(...)` に `timeout=httpx.Timeout(...)` を設定する。
- connect/read/write/pool を分けて設定可能にし、環境変数で調整できるようにする。

#### 環境変数（案）
- `UAGENT_LLM_TIMEOUT_CONNECT_SEC`（default: 10）
- `UAGENT_LLM_TIMEOUT_READ_SEC`（default: 60）
- `UAGENT_LLM_TIMEOUT_WRITE_SEC`（default: 60）
- `UAGENT_LLM_TIMEOUT_POOL_SEC`（default: 10）

※ ひとまとめの `UAGENT_LLM_TIMEOUT_SEC` でも良いが、read だけを短くしたい等の運用があるため分割が望ましい。

### B. LLM 呼び出し周りで KeyboardInterrupt を明示的に処理（UI 固着防止）
- 対象: `src/uagent/uagent_llm.py`
- 各 provider ブロック（gemini/claude/openai系）の外側、または LLM 呼び出し直後に
  - `except KeyboardInterrupt:`
    - `core.set_status(False, "")`（必要なら）
    - ログ/状態を整える
    - `raise` で再送出

### C. 「即時キャンセル」を狙う場合の方針（必要になったら）
- ブロッキング I/O の最中に Python に割り込みが戻らない環境があるため、
  - LLM 通信を **別スレッド** / **別プロセス** に分離し、キャンセル/kill 可能にする
  - あるいは OpenAI SDK の transport レイヤ（httpx.Client）を明示的に close できる構造にする

---

## 確認観点 / テスト

### 手動テスト
- LLM 呼び出し中にネットワーク断/タイムアウト相当（例: DNS 不達、プロキシ遮断、FW で drop）を再現し、
  - timeout で復帰すること
  - Ctrl-C で中断できる（または中断が早くなる）こと
  - BUSY 表示が固着しないこと

### 自動テスト（案）
- `util_providers.make_client()` が `httpx.Timeout` を含む `httpx.Client` を生成することをユニットテスト。
  - OpenAI SDK 自体はモック。
  - env から値が反映されることもテスト。

---

## メモ
- 現状でも `stdin_loop` 側は Ctrl-C を握り潰しているわけではないが、
  LLM 通信中は別経路でブロッキングし得るため、timeout/cancel 設計が必要。
