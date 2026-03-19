# TODO

## LLM 通信が Ctrl-C で停止できない（または停止が遅い）

### 背景 / 症状

- エージェント実行中、LLM API 呼び出しが詰まったときに **Ctrl-C を押してもすぐ止まらない**ことがある。
- 特に Windows 環境で再現しやすい。
- 「止まらない」に見えるが、実際には通信ライブラリ内のブロッキング I/O から Python へ割り込みが戻ってこないケースがある。

### 現状の精査（コード反映状況）

- UI 固着（BUSY 表示が戻らない）については、`src/uagent/uagent_llm.py::run_llm_rounds()` が
  `try: ... finally: core.set_status(False, "")` となっているため、**KeyboardInterrupt を含む例外でも基本的に固着しない**。
- OpenAI SDK 利用 provider の **timeout（無限待ち防止）** は、`src/uagent/util_providers.py` に集約して実装済み。
  - `make_httpx_timeout()` / `make_httpx_client()` を追加し、env から `httpx.Timeout(connect/read/write/pool)` を生成。
  - `azure/openai/openrouter/nvidia/grok` の各クライアントに `http_client=` で渡す（古い SDK 向けに `TypeError` フォールバックあり）。
- Ctrl-C の体感改善（メインスレッドを割り込みに反応させやすくする）として、LLM 呼び出しの **別スレッド実行** を実装済み。
  - `src/uagent/uagent_llm.py::run_llm_rounds()` に `_call_maybe_thread()` を追加し、主要な LLM 呼び出し（Gemini/Claude/OpenAI Responses/ChatCompletions、compress_history_with_llm）をラップ。
  - `UAGENT_LLM_IN_THREAD` は **デフォルト ON**（`0/false/no/off` のときのみ OFF）。
  - 注意: Python はスレッドを強制 kill できないため、即時停止は保証できない（timeout が安全網）。
- 画像生成ツールの **timeout 統一** も実装済み。
  - `src/uagent/tools/generate_image_tool.py` が `util_providers.make_httpx_client()` を使う。

### 影響範囲

- OpenAI SDK を使用する provider の LLM 呼び出し
  - `azure` / `openai` / `openrouter` / `nvidia` / `grok`
- 直接 LLM 呼び出しを行う箇所
  - `src/uagent/uagent_llm.py`（Responses / ChatCompletions）
  - `src/uagent/core.py`（互換/別経路がある場合）
  - `src/uagent/translate.py` / `src/uagent/tools/vision_openai.py` / `src/uagent/tools/vision_runtime.py`（必要に応じて確認）

______________________________________________________________________

## 目標

1. 無限ハングを防ぐ（必須）
1. Ctrl-C を押したときに UI 状態（BUSY 表示等）が固着しない（必須・現状ほぼ達成）
1. 可能なら Ctrl-C を押した瞬間に通信をキャンセルする（努力目標）

______________________________________________________________________

## 実装方針

### A. OpenAI SDK に渡す httpx.Client に timeout を導入（実装済み）

- 対象: `src/uagent/util_providers.py`
- OpenAI SDK を使用する provider（`azure/openai/openrouter/nvidia/grok`）に対して、共通の `httpx.Client(timeout=...)` を生成し `http_client=` として渡す。

#### 環境変数（timeout）

- `UAGENT_LLM_TIMEOUT_CONNECT_SEC`（default: 10）
- `UAGENT_LLM_TIMEOUT_READ_SEC`（default: 60）
- `UAGENT_LLM_TIMEOUT_WRITE_SEC`（default: 60）
- `UAGENT_LLM_TIMEOUT_POOL_SEC`（default: 10）

補足:

- timeout は無限待ちを防ぐための上限であり、Ctrl-C 即時停止を保証しない。

### B. LLM 呼び出しを「別スレッド」で実行（実装済み）

- 方針: **デフォルト ON**。
- 環境変数 `UAGENT_LLM_IN_THREAD` の解釈:
  - 既定=ON
  - 値が `0/false/no/off` のときのみ OFF
  - それ以外（未設定含む）は ON

注意:

- Python はスレッドを強制 kill できないため、完全な即時停止は保証できない。

### C. 「即時キャンセル」を本気で狙う場合（将来）

- 別プロセス化（LLM 呼び出しを子プロセスに分離して kill 可能にする）が最も確実。
- async 化は大規模改修になりやすいため、現段階では優先度を下げる。

______________________________________________________________________

## 実装ステップ（慎重運用）

1. `TODO.md`（本書）を更新（完了）
1. `util_providers.make_client()` に timeout 付き `httpx.Client` 生成関数を追加し、OpenAI SDK provider に適用（完了）
1. LLM 呼び出し経路に「別スレッド実行」ラッパを導入（完了）
1. 単体テスト追加（timeout 設定と env 反映 / `UAGENT_LLM_IN_THREAD` の判定）
1. 手動テスト（Windows でネットワーク遮断/DNS不達/Firewall drop を再現）

______________________________________________________________________

## 確認観点 / テスト

### 手動テスト

- LLM 呼び出し中にネットワーク断/タイムアウト相当（例: DNS 不達、プロキシ遮断、FW で drop）を再現し、
  - timeout で復帰すること
  - Ctrl-C で中断できる（または中断が早くなる）こと
  - BUSY 表示が固着しないこと

### 自動テスト（最低限）

- `util_providers.make_client()` が `httpx.Timeout` を含む `httpx.Client` を生成し、env 値が反映されること。
- `UAGENT_LLM_IN_THREAD` の ON/OFF 判定が仕様通りであること（ユニットテスト or 小さな結合テスト）。
