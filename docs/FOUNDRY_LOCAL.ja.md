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

Foundry SDK の直接利用が必要になった場合は、後で別機能として追加できます。
