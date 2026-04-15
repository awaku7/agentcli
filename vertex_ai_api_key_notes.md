# Vertex AI APIキー利用メモ

## 概要
今回の確認では、Vertex AI で API キーを使った `curl` 呼び出しを試し、以下を切り分けた。

- 401 エラーは認証方式やキーの種類の問題
- 404 エラーはモデル名またはリージョン側の解決の問題
- `gemini-2.5-flash` では疎通できた

## 結論
- Vertex AI では、通常の OAuth2 / Bearer トークン方式だけでなく、**Vertex AI の express mode 用 API キー**でも呼び出せる
- ただし、**使うキーは Google Cloud 側で作成した Vertex AI 用の API キー**である必要がある
- 最初の 401 は、API キー未展開やキー種別不一致の可能性が高い
- その後の 404 は、`gemini-2.5-flash-lite` が解決先リージョンで使えない、またはアクセス不可だった可能性が高い
- `gemini-2.5-flash` では成功したため、認証自体は通っていた

## 発生したエラーと意味

### 1. 401 UNAUTHENTICATED

### 内容
`API keys are not supported by this API. Expected OAuth2 access token or other authentication credentials that assert a principal.`

### 主な原因候補
- API キーが正しく展開されていない
- 想定しているキーではなく別種のキーを使っている
- シェルごとの環境変数展開方法が合っていない

### 2. 404 NOT_FOUND

### 内容
`Publisher Model ... gemini-2.5-flash-lite was not found or your project does not have access to it.`

### 意味
- 認証は通っている
- 失敗箇所はモデル解決
- `gemini-2.5-flash-lite` がその時点の解決先リージョンで使えなかった可能性がある

## 確認したポイント
- Google Cloud Console の Vertex AI Studio で API キーを作成していること
- そのキーが Bound account 付きであること
- `cmd.exe` では `%UAGENT_GEMINI_API_KEY%` で環境変数を展開すること

## 実際に試した cmd.exe のコマンド

### 失敗した例
```cmd
curl "https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-2.5-flash-lite:streamGenerateContent?key=%UAGENT_GEMINI_API_KEY%" ^
  -X POST ^
  -H "Content-Type: application/json" ^
  -d "{\"contents\":[{\"role\":\"user\",\"parts\":[{\"text\":\"Explain how AI works in a few words\"}]}]}"
```

### 成功確認用の例
```cmd
curl "https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-2.5-flash:streamGenerateContent?key=%UAGENT_GEMINI_API_KEY%" ^
  -X POST ^
  -H "Content-Type: application/json" ^
  -d "{\"contents\":[{\"role\":\"user\",\"parts\":[{\"text\":\"Explain how AI works in a few words\"}]}]}"
```

## 使い分けの整理

### API キー方式
- エンドポイント: `aiplatform.googleapis.com`
- 形式: `?key=...`
- 今回のような express mode の簡易呼び出し向け

### Bearer トークン方式
- エンドポイント: `aiplatform.googleapis.com`
- 形式: `Authorization: Bearer <access-token>`
- 通常の Vertex AI 利用でより安定して使いやすい

## 今後のおすすめ
- 疎通確認はまず `gemini-2.5-flash` で行う
- 本番用途では、必要に応じて Bearer トークン方式も使えるようにしておく
- `flash-lite` を使う場合は、モデル可用性やリージョン差を確認する

## メモ
今回の切り分け結果としては、

- API キーそのものは使えていた
- 問題は最終的にモデル側だった

という理解でよい。
