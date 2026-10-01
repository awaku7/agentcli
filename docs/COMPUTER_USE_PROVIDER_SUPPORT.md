# Computer Use プロバイダー対応に必要な変更

## 目的

llmcapa がモデルの Computer Use capability を正規情報源として扱う設計を維持しながら、Anthropic Sonnet と Meta Muse Spark の公式 Computer Use API を agentcli から利用できるようにするための実装計画。

この文書は現状調査と変更要件を記録するもので、以下の未対応機能を実装済みとは扱わない。

## 現状

### agentcli の共通処理

- `src/uagent/computer_use/capability.py` は llmcapa の `computer_use` 情報を必須とし、情報がないモデルは capability 不明として拒否する。
- `src/uagent/computer_use/native.py::prepare_native_computer_use` は OpenAI/Azure、Anthropic、Gemini/Vertex を許可するが、Meta は許可リストにない。
- OpenAI/Anthropic/Gemini 用 Adapter と共通 Browser/Desktop Runtime は存在する。
- `src/uagent/providers/llm_meta_responses.py` は Meta Responses の reasoning summary 用互換処理であり、Computer Use の tool/result や safety-check を処理しない。

### llmcapa の確認結果

この環境にインストールされた llmcapa では、次のモデルレコードに `computer_use` 情報がなかった。したがって、現状の capability lookup はこれらを Computer Use 対応として認識しない。

- Meta: `muse-spark-1.3`、`muse-spark-1.2`（モデルレコードあり、`computer_use` なし）。`muse-spark-1.0` はレコードを解決できなかった。
- Claude: `claude-sonnet-4-5`、`claude-sonnet-4-6`、`claude-sonnet-5`、`claude-sonnet-5-5`（モデルレコードあり、`computer_use` なし）。

これはカタログの状態であって、各提供元 API の実際のモデル機能を否定する根拠ではない。提供元の公式仕様を capability データへ反映する必要がある。

### 提供元のプロトコル差

| 提供元／モデル | 公式 Computer Use 方式 | agentcli の現状 |
|---|---|---|
| Claude Sonnet 4.6 | 旧 `computer_20251124`。Anthropic のベータヘッダーが必要 | `AnthropicComputerAdapter` は旧形式の tool 登録、ヘッダー、`tool_use` 入力を処理する実装とテストを持つ。ただし llmcapa レコードがないため Sonnet capability から有効化できない。 |
| Claude Sonnet 5／5.5 | 新 `computer_toolset_20260801`。member tool ごとの `tool_use` と `tool_result` を返す方式 | 未対応。現 Adapter の単一 `computer` tool／旧形式の action payload とは異なる。 |
| Meta Muse Spark | Meta Responses API の native `computer` tool。`computer_call` は actions をまとめて返し、`computer_call_output` で画面を返す | Meta Responses transport はあるが、native Computer Use の有効化・safety-check処理は未対応。 |

## 必要な変更

### 1. llmcapa capability データを追加・更新

llmcapa 側で、提供元の公式モデル／API情報に基づき、対象モデルの `computer_use` capability を登録する。agentcli 内に別のモデル対応表を作って llmcapa と二重管理しない。

capability には少なくとも次の情報が必要。

- 対応モデルIDとprovider
- `supported`, `native`, tool type／toolset version
- 対応アクションと対象環境
- 必要なベータヘッダー（旧Anthropic形式の場合）
- provider／model／API surface ごとの互換条件

llmcapa に新しい capability schema が必要なら、llmcapa と agentcli の依存バージョンおよび fixtures を合わせて更新する。

### 2. Sonnet の Anthropic 対応をバージョン別に完成させる

- Sonnet 4.6 は旧 `computer_20251124` 経路を使用できるよう、llmcapa 登録後に実 API の request/response 形を確認する。
- Sonnet 5／5.5 は `computer_toolset_20260801` 用の Adapter を追加する。member tool 名、`toolset_name: "computer"`、tool_useごとの結果形式を旧 Adapter と混同しない。
- 新 toolset は screenshot／zoom に画像結果を返し、その他の member tool はテキスト結果を返す。member toolごとに対応する tool_result を返し、batch順序と失敗後の処理を公式仕様どおりにする。
- toolset に zoom など未実装操作が含まれる場合、toolset configs で無効化するか Runtime に実装し、モデルへ宣言した操作と実行可能操作を一致させる。

### 3. Meta Muse Spark の Computer Use 経路を追加

- `prepare_native_computer_use` に Meta の分岐を追加し、Meta Responses で `{"type":"computer"}` を有効にする。Meta のネイティブ capability がない／local Runtimeを使う場合の既存安全動作は維持する。
- 共通の `ComputerAction`／Runtimeを再利用しつつ、Meta の `computer_call`、batched `actions`、`computer_call_output` を扱う provider Adapter を実装する。
- 各 computer_call の actions を順番に実行し、**batch完了後の最終スクリーンショットを1枚**返す。中間画像を返さない。
- `pending_safety_checks` を読み、実行前に既存のユーザー確認／ポリシーへ結び付ける。承認した check のみ `acknowledged_safety_checks` として応答に含め、未承認時は fail-closed にする。
- stateless replay をサポートする場合、`meta_safety_replay_receipt` を変更せず対応する入力 item に引き継ぐ。未対応ならその再生方式を無効として明示する。
- Meta の Responses tool output では screenshot が必須。撮影に失敗した場合、`image_url: null` を送らず分かりやすいエラーとして停止する。

### 4. 正規化と Runtime の境界を確認

既存の共通アクション名を使い、provider固有入力だけを Adapter 境界で正規化する。特に、クリック修飾キー、scrollの座標／delta、drag path、キー配列、wait、zoom、スクリーンショットの各フィールドを実レスポンスで検証する。未認識の provider payload を成功扱いしない。

## テスト・受け入れ条件

1. llmcapa fixtureで、対象Meta／SonnetモデルのComputer Use capability lookupが期待するversion/tool typeを返す。未登録モデルは従来どおり拒否する。
1. providerごとに、送信するtool schema／toolset、beta header、応答action parsing、tool result schemaを単体テストする。
1. Metaの複数action batchについて、順序実行、途中失敗時の挙動、最終状態のスクリーンショット1枚、同一call_idへの単一 output を確認する。
1. Meta safety checkの未承認／承認／一部承認をテストし、承認前の実行がないこと、および承認内容だけを応答へ反映することを確認する。
1. Anthropic旧形式（Sonnet 4.6）と新toolset形式（Sonnet 5/5.5）を別々にテストし、protocolの取り違えを拒否する。
1. Computer Use関連テスト全体、既存のAnthropic/Meta Responsesテスト、構文・lintを実行する。APIを利用するE2Eは明示的なopt-inと安全な専用環境で行う。

## 公式仕様

- [Anthropic Computer Use tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool)
- [Meta Model API: Build a computer-use agent](https://dev.meta.ai/docs/computer-use)
