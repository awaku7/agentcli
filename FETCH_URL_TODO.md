# fetch_url ツールの機能改善ロードマップ (FETCH_URL_TODO.md)

`src/uagent/tools/fetch_url_tool.py` における、ローカル実行エージェントとしての堅牢性と利便性を向上させるための未実装機能・改善項目のまとめです。

---

## 1. 優先度：高（安定性と堅牢性の向上）

### 1.1 タイムアウト処理の追加
* **現状**: `urlopen` にタイムアウトが指定されておらず、応答のないサーバーに対して無限にハングアップするリスクがあります。
* **改善案**: 
  * デフォルトのタイムアウト（例: `10` 秒）を設定する。
  * パラメータに `timeout` (整数/浮動小数点数) を追加し、呼び出し側からカスタマイズ可能にする。
* **詳細仕様**:
  * パラメータ名: `timeout` (integer, default: `10`)
  * `urlopen(req, timeout=timeout)` のように指定する。

### 1.2 HTTP ステータスコードのハンドリング
* **現状**: `404 Not Found` や `500 Internal Server Error` などのエラー時、`urllib.error.HTTPError` が発生して汎用例外として処理され、詳細なステータスコードが呼び出し元に伝わりません。
* **改善案**:
  * `HTTPError` を個別にキャッチする。
  * `{"ok": false, "status_code": 404, "error": "HTTP Error 404: Not Found"}` のような構造化された JSON 応答を返す。
* **詳細仕様**:
  * `urllib.error.HTTPError` をキャッチし、`status_code` フィールドに `e.code` を格納する。
  * `urllib.error.URLError` もキャッチし、適切なエラーメッセージを返す。

---

## 2. 優先度：中（ローカル開発・特殊環境への対応）

### 2.1 SSL 検証の制御（自己署名証明書対応）
* **現状**: SSL 証明書の検証を強制するため、自己署名証明書（オレオレ証明書）を使用するローカル開発環境や社内 LAN の HTTPS サイトへのアクセスで SSL エラーになります。
* **改善案**:
  * パラメータに `verify_ssl` (boolean, デフォルト: `true`) を追加する。
  * `verify_ssl=false` の場合、`ssl._create_unverified_context()` を作成して `urlopen(..., context=context)` に渡す。
* **詳細仕様**:
  * パラメータ名: `verify_ssl` (boolean, default: `true`)
  * `verify_ssl` が `False` の場合、`ssl._create_unverified_context()` を作成し、`urlopen` の `context` 引数に渡す。

### 2.2 リダイレクトループ対策
* **現状**: `urllib` のデフォルト挙動に依存しており、リダイレクトループが発生した際の制御ができません。
* **改善案**:
  * カスタムの `HTTPRedirectHandler` を使用するか、リダイレクト回数を制限・検知して安全にエラーを返す仕組みを導入する。
* **詳細仕様**:
  * `urllib.request.HTTPRedirectHandler` を継承した `SafeRedirectHandler` を実装する。
  * 最大リダイレクト回数（例: 5回）を超えた場合は `ValueError` などの例外を発生させ、安全にエラーレスポンスを返す。
  * `urllib.request.build_opener(SafeRedirectHandler())` を用いてリクエストを送信する。

---

## 3. 優先度：低（LLM 向けの情報最適化）

### 3.1 Markdown 変換モードの追加 (`extract="markdown"`)
* **現状**: `extract="text"` では `BeautifulSoup` の `get_text()` によるプレーンテキスト抽出のみをサポートしており、リンク（`<a>`）や見出し（`<h1>`〜`<h6>`）などの重要な構造情報が失われます。
* **改善案**:
  * `extract` パラメータの選択肢に `"markdown"` を追加する。
  * HTML 構造を維持したまま、リンクや強調、リストなどを簡易的な Markdown 形式に変換して返却するパーサーを実装する。
* **詳細仕様**:
  * `extract` の enum に `"markdown"` を追加。
  * `BeautifulSoup` を用いて、HTML要素を再帰的に Markdown 形式に変換する。
  * 変換ルール:
    * `<h1>` 〜 `<h6>` -> `#` 〜 `######`
    * `<a>` -> `[text](href)`
    * `<strong>`, `<b>` -> `**text**`
    * `<em>`, `<i>` -> `*text*`
    * `<ul>`, `<ol>`, `<li>` -> リスト形式 (`- ` または `1. `)
    * `<p>`, `<br>` -> 改行
    * その他のタグはテキストのみを抽出、または適切な改行を挟む。
