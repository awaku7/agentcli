# Computer Use プロバイダー対応に必要な変更

## 目的

llmcapa がモデルの Computer Use capability を正規情報源として扱う設計を維持しながら、Anthropic Sonnet と Meta Muse Spark の公式 Computer Use API を agentcli から利用できるようにするための実装計画。

この文書は実装状況も記録する。完了として明記されていない機能は未実装または未検証として扱う。

## 現状

### agentcli の共通処理

- `src/uagent/computer_use/capability.py` は llmcapa の `computer_use` 情報を必須とし、情報がないモデルは capability 不明として拒否する。
- `src/uagent/computer_use/native.py::prepare_native_computer_use` は OpenAI/Azure、Anthropic、Gemini/Vertex、Meta の provider-native Computer Use を capability に基づいて準備する。
- OpenAI/Anthropic/Gemini/Meta 用 Adapter と共通 Browser/Desktop Runtime が存在する。
- `src/uagent/providers/llm_meta_responses.py` は Meta Responses の reasoning summary 用互換処理であり、Computer Use の tool/result や safety-check を処理しない。

### llmcapa の確認結果

llmcapa 0.5.51 では、公式仕様に基づく provider-specific な Computer Use capability が登録されている。agentcli はこの PR から `llmcapa>=0.5.51` を最低バージョンとし、agentcli 内に別のモデル対応表を追加しない。

今回の対象では次を確認済み。

- Anthropic: `claude-sonnet-4-6` は旧 `computer_20251124`、`claude-sonnet-5` / `claude-sonnet-5-5` は新 `computer_toolset_20260801` として登録される。
- Meta: `muse-spark-1.1` と `muse-spark-1.3` は Meta Responses の native `computer` tool として登録される。`muse-spark-1.2` は公式根拠がないため native Computer Use を推測しない。
- Computer Use の置換互換性は provider、API type、tool/schema family、beta header、environment、action を考慮する。同じ `responses` / `computer` という名前だけで OpenAI と Meta を互換扱いしない。

llmcapa の capability 登録はモデルが提供元 API で対応することを示す。agentcli 側の provider Adapter / transport 実装が未完成の場合、その capability があるだけで実行可能とは扱わない。

### 提供元のプロトコル差

| 提供元／モデル | 公式 Computer Use 方式 | agentcli の現状 |
|---|---|---|
| Claude Sonnet 4.6 | 旧 `computer_20251124`。Anthropic のベータヘッダーが必要 | llmcapa 0.5.51 で capability 登録済み。`AnthropicComputerAdapter` は旧形式の tool 登録、ヘッダー、`tool_use` 入力を処理する実装とテストを持つが、実 API の request/response 境界確認は残る。 |
| Claude Sonnet 5／5.5 | 新 `computer_toolset_20260801`。member tool ごとの `tool_use` と `tool_result` を返す方式 | toolset 登録、member 入力の正規化、toolset marker 付き結果、順序実行・失敗後停止を実装し、単体テスト済み。未対応 member は toolset configs で無効化する。実 API E2E は未実施。 |
| Meta Muse Spark 1.1／1.3 | Meta Responses API の native `computer` tool。`computer_call` は actions をまとめて返し、`computer_call_output` で画面を返す | provider/API/tool family を検証する adapter、初回 screenshot、逐次 batch 実行、最終 screenshot、human safety approval、acknowledgement／receipt の受け渡しを実装し、単体テスト済み。stateless replay は明示的に無効。実 API E2E は未実施。 |

## 必要な変更

### 1. llmcapa capability データと最低依存バージョン — 完了

llmcapa 0.5.51 で provider-specific Computer Use capability が整備されたため、agentcli 側は次の方針に固定する。

- `llmcapa>=0.5.51` を core 依存とする。
- 対応モデル、provider、API type、tool type／toolset version、beta header、environment、action は llmcapa を正規情報源とする。
- agentcli 内にモデル名ベースの第二の対応表を作らない。
- 実 llmcapa カタログを使う回帰テストで、Anthropic の旧／新 Computer Use と Meta Muse Spark の provider-specific capability が取得できることを確認する。
- llmcapa が capability を持たないモデルは従来どおり fail-closed とし、近似モデルや provider 名から Computer Use 対応を推測しない。

### 2. Sonnet の Anthropic 対応をバージョン別に完成させる — Sonnet 5／5.5 実装済み

- Sonnet 4.6 は旧 `computer_20251124` 経路を保持する。実 API の request/response 境界確認は未実施。
- Sonnet 5／5.5 は `computer_toolset_20260801`、member tool 名、`toolset_name: "computer"`、tool_use ごとの結果形式を旧 Adapter と分離して実装した。
- member tool は順番に処理し、途中失敗で後続を停止する。各 tool_use に tool_result を返し、最終 batch の結果に最新スクリーンショットを添付する。
- zoom、cursor_position、button down/up、hold_key は未実装のため toolset configs で無効化する。key の repeat、pointer modifier、drag path、scroll、wait は共通 Runtime に正規化する。
- Anthropic の Computer Use は guarded local Runtime 経由で実行し、capability のないモデルは引き続き fail-closed とする。

### 3. Meta Muse Spark の Computer Use 経路を追加 — 実装済み

- `prepare_native_computer_use` は llmcapa の native capability が Meta/Responses/computer と一致する場合だけ `{"type":"computer"}` を有効にする。local Runtime の実行は共通 safety policy と confirmation を通す。
- `MetaComputerAdapter` が `computer_call` の action vocabulary、call ID、safety check 形を検証し、共通 `ComputerAction`／Runtime へ渡す。
- 各 `computer_call` の actions を順番に実行し、最初の失敗で停止する。`computer_call_output` は batch 後の最終 screenshot 1 枚だけを返し、途中画像は送らない。
- `pending_safety_checks` は実行前に human approval callback で確認する。未承認／確認不能時は fail-closed とし、承認された check のみ `acknowledged_safety_checks` へ返す。
- `meta_safety_replay_receipt` は受信時に変更せず tool output へ引き継ぐ。stateless replay は実装対象外として拒否し、continuation は `previous_response_id` を必須とする。
- 初回 Meta Computer Use request に Runtime の screenshot が無い場合、または最終 screenshot が欠落・不正・25 MiB 超過の場合は API request を送らず明確なエラーにする。

### 4. 正規化と Runtime の境界を確認 — Adapter 単体テスト済み

既存の共通アクション名を使い、provider 固有入力だけを Adapter 境界で正規化する。クリック修飾キー、scroll の座標／delta、drag path、キー配列、wait、zoom、スクリーンショットのフィールド、および未知 action の fail-closed を adapter 単体テストで確認する。実モデルを使う API E2E はまだ実施していない。

## テスト・受け入れ条件

1. llmcapa 0.5.51 の実カタログで、Anthropic旧形式、Anthropic新toolset、Meta Responses の Computer Use capability lookupが期待する provider／API／tool typeを返す。未登録モデルは従来どおり拒否する。
1. providerごとに、送信するtool schema／toolset、beta header、応答action parsing、tool result schemaを単体テストする。
1. Metaの複数action batchについて、順序実行、途中失敗時の挙動、最終状態のスクリーンショット1枚、同一call_idへの単一 output を確認する。
1. Meta safety checkの未承認／承認／一部承認をテストし、承認前の実行がないこと、および承認内容だけを応答へ反映することを確認する。
1. Anthropic旧形式（Sonnet 4.6）と新toolset形式（Sonnet 5/5.5）を別々にテストし、protocolの取り違えを拒否する。
1. Computer Use関連テスト全体、既存のAnthropic/Meta Responsesテスト、構文・lintを実行する。APIを利用するE2Eは明示的なopt-inと安全な専用環境で行う。

## 公式仕様

- [Anthropic Computer Use tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool)
- [Meta Model API: Build a computer-use agent](https://dev.meta.ai/docs/computer-use)
