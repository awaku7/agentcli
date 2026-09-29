# Microsoft Foundry Local

UAG では Foundry Local を、通常のローカル OpenAI 互換エンドポイントとして扱います。

設定例:

```text
UAGENT_PROVIDER=foundry_local
UAGENT_FOUNDRY_LOCAL_BASE_URL=http://localhost:<port>/v1
UAGENT_FOUNDRY_LOCAL_DEPNAME=phi-4-mini   # 省略可
UAGENT_FOUNDRY_LOCAL_API_KEY=...          # 省略可
```

base URL は loopback（`localhost`、`127.0.0.1`、`::1` など）である必要があります。UAG はこの統合で Foundry Local の起動、モデルのダウンロード/ロード、localhost 探索、Foundry Local SDK の利用を行いません。

llmcapa では UAG の provider 名 `foundry_local` を `foundry-local` に対応付け、それ以外は他の provider と共通の既存 llmcapa 検索処理をそのまま使います。

UAG は既存の OpenAI 互換 transport と capability 処理を使います。Foundry 専用の Responses、tools、モデル検索、capability routing のルールは追加しません。

## オプトイン診断

Foundry Local の実機切り分けでは、次を設定すると provider 専用の診断ログを stderr に出力できます。

```text
UAGENT_DEBUG_FOUNDRY_LOCAL=1
```

診断は通常時は無効です。プロンプト本文、応答本文、ツール引数は出力せず、実際に localhost へ送信する最終 HTTP payload から次のメタデータだけを記録します。

- model / transport / streaming
- message 数
- tool 数と tool 名
- 最新 user content の文字数と SHA-256
- messages/input 全体の SHA-256
- HTTP request body の SHA-256
- 非ストリーミング応答、または Registry の streamed response text の SHA-256

異なる2つの入力で `last_user_sha256` と `request_sha256` が変わるかを見ることで、UAG 内で入力が固定化されているのか、Foundry Local へ正しい別 payload が届いているのかを切り分けられます。

既存の `UAGENT_DEBUG_OPENAI_RUNTIME=1` でも Foundry Local 診断は引き続き有効になりますが、Foundry Local だけを確認する場合は `UAGENT_DEBUG_FOUNDRY_LOCAL=1` を推奨します。

Foundry SDK の直接利用が必要になった場合は、後で別機能として追加できます。
