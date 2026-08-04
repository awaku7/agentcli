# web_request / web_intercept 設計

## 目的

HTTP/API確認にはhttpx、必要に応じてmitmproxyを利用する。

## web_request: httpx

### 用途

- HTTPステータス確認
- ヘッダー取得
- API呼び出し
- TLS接続確認
- JSONレスポンス取得

### 入力例

```json
{
  "url": "https://example.com/api/status",
  "method": "GET",
  "headers": {},
  "timeout": 5,
  "follow_redirects": false
}
```

### 安全制御

- URLスキームを`http`/`https`に限定
- 許可ドメインを設定可能にする
- リダイレクト回数を制限
- レスポンスサイズを制限
- 認証情報をログに出さない

## web_intercept: mitmproxy

### 用途

- HTTP/HTTPS通信の記録
- テスト用リクエスト変更
- APIデバッグ
- モック・再送

Pythonアドオンでリクエスト・レスポンスを処理する。

## Python依存

```text
httpx
mitmproxy（必要時）
```
