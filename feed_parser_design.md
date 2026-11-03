# RSS/Atom フィードパーサーツール 設計書

## 1. 概要
RSS 0.9x / 1.0 (RDF) / 2.0 および Atom 形式のフィード（XML）を入力とし、規格差および国際化（I18N）に関わるエンコーディング・言語・日時の差異を吸収して統一された JSON データモデルに正規化して返却するエージェント向けツールの仕様。

---

## 2. 目的・解決する課題
1. **規格差の吸収**: 異なる要素名・構造（`<item>` / `<entry>`、`<link>` のテキスト / href属性、日時フォーマット）を統一スキーマに変換。
2. **国際化（I18N）対応**:
   - 多様な文字コード（UTF-8, Shift_JIS/Windows-31J, EUC-JP, GB2312, Big5, ISO-8859-* 等）の正確な検出と UTF-8 正規化。
   - `xml:lang` / `<language>` 属性の言語コード（BCP 47 形式）正規化。
   - 多言語特有の特殊文字・HTMLエンティティ・絵文字・RTL（右横書き）テキストの保持。
   - タイムゾーン付きローカル日時の UTC または ISO 8601 (RFC 3339) 統一。
3. **LLM トークン最適化**: 本文全文（HTML）のサニタイズ（プレーンテキスト化）および取得件数上限（`limit`）によるコンテキスト溢れの防止。

---

## 3. 国際化 (I18N) 詳細要件

### 3.1 文字エンコーディング判定の優先順位
1. **HTTP Content-Type ヘッダー** の `charset` パラメータ
2. **XML 宣言**（`<?xml version="1.0" encoding="..."?>`）
3. **自動判定フォールバック**: `chardet` / `cchardet` によるバイト列解析
4. **出力正規化**: 全文字列を Python 内部で `Unicode (str)` として扱い、返却 JSON は一律 `UTF-8`（エスケープなし）で出力

### 3.2 言語識別 (Language Tag)
- フィード全体 (`<channel><language>` または `<feed xml:lang="...">`) および個別エントリ (`<entry xml:lang="...">`) の言語タグを抽出。
- `ja-JP`, `ja`, `en-US` などを BCP 47 小文字ハイフン区切り（`ja-jp` / `en-us`）に正規化。

### 3.3 日時・タイムゾーンの正規化
- 各種日時規格（RFC 822 / RFC 1123 / ISO 8601 / W3CDTF / 日本語固有表記など）をパース。
- 出力は必ず **ISO 8601 / RFC 3339** 形式（タイムゾーンオフセット保持、例: `2026-11-03T20:30:00+09:00`）。タイムゾーン指定がない場合は UTC（`+00:00` または `Z`）とみなす。

### 3.4 テキスト処理・エンティティ
- HTML/XML 数値文字参照（`&#x3042;` 等）および名前文字参照（`&nbsp;`, `&amp;` 等）を完全デコード。
- 右横書き言語（アラビア語、ヘブライ語等）の Unicode 制御文字（RLM/LRM 等）を欠損させずに保持。

---

## 4. ツール定義 (インターフェース)

### 4.1 ツール名
`parse_feed`

### 4.2 パラメータ (JSON Schema)
| パラメータ名 | 型 | 必須 | デフォルト | 説明 |
| :--- | :--- | :--- | :--- | :--- |
| `url` | string | 任意* | - | 取得対象のフィード URL（HTTP/HTTPS） |
| `content` | string | 任意* | - | 直接パースする XML/RSS 文字列またはバイト列 |
| `encoding` | string | いいえ | null | 明示的なエンコーディング指定（自動判定を上書き） |
| `limit` | integer | いいえ | 10 | 取得する記事エントリの最大件数 (1〜100) |
| `strip_html` | boolean | いいえ | true | 概要・本文から HTML タグを除去してプレーンテキスト化するか |
| `timeout` | integer | いいえ | 10 | URL 取得時のタイムアウト秒数 |

> ※ `url` または `content` のいずれか片方が必須。

---

## 5. 出力データスキーマ (JSON)

```json
{
  "ok": true,
  "feed_type": "rss2.0",  // "rss0.9" | "rss1.0" | "rss2.0" | "atom" | "unknown"
  "title": "フィードタイトル",
  "link": "https://example.com",
  "description": "フィードの説明文",
  "language": "ja-jp",    // BCP 47 形式
  "encoding": "utf-8",    // ソースの検出エンコーディング
  "updated_at": "2026-11-03T20:30:00+09:00",  // ISO 8601 形式
  "total_items": 25,
  "items": [
    {
      "id": "一意識別子 (guid / id / link)",
      "title": "記事タイトル",
      "link": "https://example.com/article/1",
      "language": "ja-jp", // エントリ固有の言語指定がある場合
      "published_at": "2026-11-03T20:00:00+09:00",  // ISO 8601 形式
      "updated_at": "2026-11-03T20:15:00+09:00",
      "summary": "記事の要約または抜粋（HTMLタグ除去済み、UTF-8）",
      "author": "執筆者名",
      "categories": ["政治", "国際"]
    }
  ]
}
```

---

## 6. 各バージョン・規格のマッピング定義

| 共通フィールド | RSS 1.0 (RDF) | RSS 2.0 | Atom 1.0 |
| :--- | :--- | :--- | :--- |
| エントリ単位 | `<item>` | `<item>` | `<entry>` |
| タイトル | `title` | `title` | `title` |
| リンク | `link` | `link` | `<link href="...">` (rel="alternate") |
| 言語 | `dc:language` | `<language>` | `xml:lang` 属性 |
| 識別子 (id) | `rdf:about` 属性 | `guid` (なければ `link`) | `id` |
| 公開日時 | `dc:date` | `pubDate` | `published` または `updated` |
| 更新日時 | `dc:date` | - | `updated` |
| 本文 / 要約 | `description` / `content:encoded` | `description` / `content:encoded` | `summary` / `content` |
| 著者 | `dc:creator` | `author` | `author/name` |
| カテゴリ | `dc:subject` | `category` | `<category term="...">` |

---

## 7. 実装方針

### 7.1 推奨ライブラリ
- **Python**: `feedparser`
  - 各規格（RSS 0.90〜2.0, Atom）のパース、HTTP 取得時の ETag / Last-Modified 処理、日付正規化、文字コード自動判別を内包。
- **補完**: `chardet` / `charset_normalizer`（HTTP ヘッダーや XML 宣言の charset が嘘・欠落している場合のフォールバック）
- **HTML 除去 / サニタイズ**: `BeautifulSoup4` または `html` モジュールによるエンティティ復元とプレーンテキスト変換。

### 7.2 エラーハンドリング & フォールバック
- **エンコーディングデコード失敗**: `errors="replace"` 等でクラッシュを回避しつつ、置換文字でパースを継続。
- **ネットワークエラー**: HTTP ステータスコード（4xx / 5xx）、タイムアウトを適切にキャッチし `ok: false, error: "..."` で返却。
- **XML 構文エラー**: `bozo=1` の軽微な構文エラーでも抽出可能なエントリは取得し、`bozo_exception` 情報を保持。
