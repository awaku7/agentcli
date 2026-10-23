# vLLM プロバイダー

UAGは、起動済みのvLLM OpenAI互換サーバーを**Chat Completions**経由で利用できます。UAG自身がvLLMの起動、モデルのダウンロード、サーバープロセスの管理を行うことはありません。

## UAGの設定

```dotenv
UAGENT_PROVIDER=vllm
UAGENT_VLLM_BASE_URL=http://localhost:8000/v1
UAGENT_VLLM_DEPNAME=local-model
# vLLMサーバーを--api-key付きで起動した場合のみ設定します（省略可）。
# UAGENT_VLLM_API_KEY=change-me
# 省略可。既定値は120秒です。
# UAGENT_VLLM_TIMEOUT_SEC=120
```

`UAGENT_VLLM_DEPNAME`は必須で、サーバーの`/v1/models`が返すモデルIDと完全一致させてください。サーバー起動時に`--served-model-name`を指定した場合は、同じ値を設定します。Base URLの既定値は`http://localhost:8000/v1`です。APIキーは省略できます。未設定時はOpenAI互換クライアント用のプレースホルダー`dummy`を送信します。`UAGENT_VLLM_API_KEY`を優先し、標準の`VLLM_API_KEY`も利用できます。

`UAGENT_RESPONSES=1`を設定してもvLLMではResponses APIを使用しません。この統合はChat Completionsに限定しています。Visionとネイティブ構造化出力は、このプロバイダーでは機能対応として通知しません。ツール呼び出しにはモデル側の対応に加え、vLLMサーバーをモデルに合ったtool-call parser付きで起動する必要があります。例: `--enable-auto-tool-choice --tool-call-parser <モデル用parser>`。

## vLLMの起動

vLLMサーバーは別途起動してください。例:

```sh
vllm serve <model> --host 127.0.0.1 --port 8000 --served-model-name local-model
```

この場合は`UAGENT_VLLM_DEPNAME=local-model`を設定します。サーバーをloopback以外に公開する場合は、APIキーと適切なネットワーク制御で保護してください。UAGのAPIキー設定はクライアント認証用であり、サーバーのネットワーク公開自体を保護するものではありません。
