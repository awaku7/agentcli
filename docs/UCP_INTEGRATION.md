# UCP (Universal Commerce Protocol) Integration Design

## 概要

uag に UCP (Universal Commerce Protocol) を統合し、LLM エージェントが商品検索・カート構築・決済・注文管理を実行できるようにする。

uag は **UCP Platform (Agent)** として動作し、ビジネス（加盟店）の `/.well-known/ucp` を発見して能力ネゴシエーションを行い、REST API 経由で商取引を実行する。

```
uag (UCP Platform)
  │
  ├── LLM → ucp_* tools → UCP REST API → Business (Merchant)
  │
  └── 秘密鍵・クライアント認証で保護
```

## 用語

| 用語 | 説明 |
|------|------|
| Platform | エージェント側。ユーザーに代わって商取引を実行する（uag） |
| Business | 加盟店側。商品・カート・決済の実処理を行う |
| Capability | 提供機能。`dev.ucp.shopping.checkout` など逆ドメイン形式 |
| UCP Profile | `/.well-known/ucp` で公開される能力宣言 JSON |
| AP2 | Agent Payments Protocol - エージェント間決済プロトコル |
| Payment Mandate | 支払い委任。AP2においてagentに代わって支払いを実行する許可 |
| Verifiable Credential | 検証可能な資格情報。agentの身元を暗黙的に証明 |
| continue_url | ブラウザでのユーザー操作が必要な場合の誘導URL |
| Transport | REST / MCP / A2A / Embedded の4種。BusinessのProfileで選択 |

## モジュール構成

```
src/uagent/tools/
  ucp_shared.py               # UCP クライアント（共通処理）
  ucp_discover_tool.py        # ビジネス探索・能力ネゴシエーション
  ucp_catalog_tool.py         # 商品検索・照会
  ucp_cart_tool.py            # カート操作
  ucp_checkout_tool.py        # 決済セッション
  ucp_order_tool.py           # 注文管理
  ucp_identity_tool.py        # アカウント連携
  ucp_ap2_tool.py             # AP2自律決済
```

## ucp_shared.py 共通処理

### 責務

- HTTP クライアント (署名・認証・Idempotency-Key 付与)
- UCP Profile (`/.well-known/ucp`) の取得・キャッシュ
- Capability ネゴシエーション（Platform Profile 送信 → Business 応答）
- HTTP Message Signatures (RFC 9421) の生成・検証
- API Key / OAuth 2.0 Client Credentials 認証
- JWKS 公開鍵の取得・キャッシュ

### 環境変数

```
UCP_DEFAULT_KEY_FILE=        # 署名用秘密鍵（PEM形式）
UCP_DEFAULT_CLIENT_ID=       # OAuth Client ID
UCP_DEFAULT_CLIENT_SECRET=   # OAuth Client Secret
UCP_CACHE_TTL=300            # Profile/JWKS キャッシュTTL（秒）
UCP_AP2_KEY_FILE=            # AP2用追加秘密鍵（PEM形式、別鍵推奨）
```

### インターフェース

```python
class UCPClient:
    def discover(business_url: str) -> UCPProfile
    def negotiate(profile: UCPProfile, capabilities: list[str]) -> NegotiatedCaps
    def request(method, path, body=None) -> UCPResponse
    # 署名・認証は内部で自動付与

class AP2Client(UCPClient):
    # AP2独自拡張: Payment Mandate管理、トークン生成
    def execute_token(mandate_id: str) -> AP2Token
    def complete_payment(checkout_id: str, token: AP2Token) -> PaymentResult
```

## ツール詳細

### ucp_discover

ビジネスの UCP 対応状況と能力一覧を取得する。

| 項目 | 値 |
|------|-----|
| tool_name | `ucp_discover` |
| 入力 | `business_url` (str) |
| 出力 | 対応トランスポート一覧、サポートケイパビリティ一覧、バージョン、認証方式 |
| 内部動作 | `GET {business_url}/.well-known/ucp` → Profile解析 |
| 対応UCP | Discovery, Governance, and Negotiation |

### ucp_search_catalog

商品カタログを検索する。

| 項目 | 値 |
|------|-----|
| tool_name | `ucp_catalog` (mode='search') |
| 入力 | `business_url`, `query`, `currency`(opt), `context`(opt) |
| 出力 | 商品一覧（タイトル・価格・通貨・説明・画像URL） |
| 内部動作 | `POST {endpoint}/search` |
| 対応UCP | `dev.ucp.shopping.catalog_search` |

### ucp_lookup_catalog

商品 ID で詳細情報を取得する。

| 項目 | 値 |
|------|-----|
| tool_name | `ucp_catalog` (mode='lookup') |
| 入力 | `business_url`, `item_ids` (list[str]) |
| 出力 | 商品詳細（価格・在庫・バリエーション・配送情報） |
| 内部動作 | `POST {endpoint}/lookup-catalog` |
| 対応UCP | `dev.ucp.shopping.catalog_lookup` |

### ucp_create_cart

カートを作成する。

| 項目 | 値 |
|------|-----|
| tool_name | `ucp_cart` (mode='create') |
| 入力 | `business_url`, `line_items`, `currency`, `context`(opt) |
| 出力 | カートID、見積もり合計、メッセージ |
| 内部動作 | `POST {endpoint}/carts` |
| 対応UCP | `dev.ucp.shopping.cart` |

### ucp_get_cart

カートの状態を取得する。

| 項目 | 値 |
|------|-----|
| tool_name | `ucp_cart` (mode='get') |
| 入力 | `business_url`, `cart_id` |
| 出力 | カート内容、合計、メッセージ |
| 内部動作 | `GET {endpoint}/carts/{id}` |

### ucp_update_cart

カートの内容を更新する。

| 項目 | 値 |
|------|-----|
| tool_name | `ucp_cart` (mode='update') |
| 入力 | `business_url`, `cart_id`, `line_items` |
| 出力 | 更新後のカート |
| 内部動作 | `PATCH {endpoint}/carts/{id}` |

### ucp_create_checkout

チェックアウトセッションを作成する。

| 項目 | 値 |
|------|-----|
| tool_name | `ucp_checkout` (mode='create') |
| 入力 | `business_url`, `cart_id`(opt), `line_items`(opt), `buyer`(opt), `context`(opt) |
| 出力 | checkout_id, status, payment_handlers, continue_url, totals |
| 内部動作 | `POST {endpoint}/checkout-sessions` |
| 対応UCP | `dev.ucp.shopping.checkout` |

### ucp_get_checkout

チェックアウトの状態を取得する。

| 項目 | 値 |
|------|-----|
| tool_name | `ucp_checkout` (mode='get') |
| 入力 | `business_url`, `checkout_id` |
| 出力 | ステータス（incomplete / ready_for_complete / completed / canceled）、メッセージ |
| 内部動作 | `GET {endpoint}/checkout-sessions/{id}` |

### ucp_update_checkout

チェックアウト情報を更新する。

| 項目 | 値 |
|------|-----|
| tool_name | `ucp_checkout` (mode='update') |
| 入力 | `business_url`, `checkout_id`, 更新フィールド |
| 出力 | 更新後のチェックアウト |
| 内部動作 | `PATCH {endpoint}/checkout-sessions/{id}` |

### ucp_complete_checkout

チェックアウトを完了し注文を確定する。

| 項目 | 値 |
|------|-----|
| tool_name | `ucp_checkout` (mode='complete') |
| 入力 | `business_url`, `checkout_id`, `ap2_token`(opt) |
| 出力 | 注文ID、ステータス（completed / requires_escalation）、continue_url |
| 内部動作 | `POST {endpoint}/checkout-sessions/{id}/complete` |
| 備考 | ap2_token 有＝自律完了、無＝continue_url でユーザー誘導 |

### ucp_list_orders

注文履歴を取得する。

| 項目 | 値 |
|------|-----|
| tool_name | `ucp_order` (mode='list') |
| 入力 | `business_url` |
| 出力 | 注文一覧 |
| 内部動作 | `POST {endpoint}/list-orders` |
| 対応UCP | `dev.ucp.shopping.order` |

### ucp_get_order

注文詳細を取得する。

| 項目 | 値 |
|------|-----|
| tool_name | `ucp_order` (mode='get') |
| 入力 | `business_url`, `order_id` |
| 出力 | 注文詳細（ステータス・配送状況・決済情報） |
| 内部動作 | `POST {endpoint}/get-order` |

### ucp_identity_link

アカウント連携のための認証URLを生成する。

| 項目 | 値 |
|------|-----|
| tool_name | `ucp_identity` (mode='link') |
| 入力 | `business_url`, `redirect_uri` |
| 出力 | authorization_url（ブラウザで開くURL） |
| 内部動作 | OAuth 2.0 Authorization Code flow |
| 対応UCP | `dev.ucp.common.identity_linking` |

### ucp_identity_status

アカウント連携の状態を確認する。

| 項目 | 値 |
|------|-----|
| tool_name | `ucp_identity` (mode='status') |
| 入力 | `business_url`, `link_id` |
| 出力 | 連携状態（linked / expired / pending） |
| 内部動作 | `POST {endpoint}/identity-link-status` |

### ucp_ap2_mandate_create

AP2支払いマンデートを作成する（自律決済の事前承認）。

| 項目 | 値 |
|------|-----|
| tool_name | `ucp_ap2` (mode='mandate_create') |
| 入力 | `business_url`, `merchant_name`, `max_amount`, `currency` |
| 出力 | mandate_id, signed_jwt, authorization_url |
| 内部動作 | RSA署名付き JWT 生成、Trusted Surface での承認待ち |
| 対応 | AP2 over UCP (Scenario C) |

### ucp_ap2_mandate_list

発行済みの Payment Mandate 一覧を取得する。

| 項目 | 値 |
|------|-----|
| tool_name | `ucp_ap2` (mode='mandate_list') |
| 入力 | なし |
| 出力 | Mandate一覧（有効期限・金額上限・プロバイダ） |

### ucp_ap2_execute

AP2 決済トークンを実行する（自律決済）。

| 項目 | 値 |
|------|-----|
| tool_name | `ucp_ap2` (mode='execute') |
| 入力 | `mandate_id`, `checkout_id`, `amount`, `currency` |
| 出力 | signed_token（ucp_checkout complete の ap2_token として使用） |

### ucp_ap2_verify

AP2決済トークンを検証する。

| 項目 | 値 |
|------|-----|
| tool_name | `ucp_ap2` (mode='verify') |
| 入力 | `ap2_token` |
| 出力 | デコードされたペイロード（vct, token_id, amount等） |

## データフロー例

### ケースA: continue_url 経由（ユーザー操作）

```
User: 「このスニーカー買って」
  ↓
LLM: ucp_discover("https://example.shop")
  → Profile取得（supports: catalog_search, cart, checkout）
  ↓
LLM: ucp_search_catalog("https://example.shop", query="スニーカー")
  → 商品一覧
  ↓
LLM: ucp_create_cart("https://example.shop", line_items=[{item_id: "xxx", qty: 1}])
  → cart_id: "cart_123"
  ↓
LLM: ucp_create_checkout("https://example.shop", cart_id="cart_123")
  → status: "ready_for_complete", totals: ¥12,800
  ↓
LLM: "合計¥12,800です。購入を完了しますか？"
User: 「はい」
  ↓
LLM: ucp_complete_checkout("https://example.shop", checkout_id="chk_456")
  → status: "requires_escalation", continue_url: "https://..."
  ↓
LLM: 「決済にはブラウザでの確認が必要です。以下のURLを開いてください」
  [continue_url を表示]
```

### ケースB: AP2 自律決済

```
User: 「このコーヒー豆を注文して」
  ↓
LLM: ucp_discover → Profile取得
  ↓
LLM: ucp_search_catalog → 商品特定
  ↓
LLM: ucp_create_cart → カート作成
  ↓
LLM: ucp_create_checkout → checkout_id 取得
  ↓
LLM: ucp_ap2_execute(business_url, mandate_id="mnt_xxx", checkout_id="chk_456")
  → AP2Token 発行
  ↓
LLM: ucp_complete_checkout(business_url, checkout_id="chk_456", ap2_token="tok_xxx")
  → status: "completed", order_id: "ord_789"
  ↓
LLM: 「注文完了しました。注文番号は ord_789 です」
```

### ケースC: 認証ユーザー（アカウント連携済み）

```
User: 「前回買ったスニーカーをもう一度注文して」
  ↓
LLM: ucp_identity_status → linked (access_token有効)
  ↓
LLM: ucp_list_orders → 前回注文を特定
  ↓
LLM: ucp_create_checkout（同一商品で再注文）
  → 住所・支払い方法が既に紐付いている
  → status: "ready_for_complete"
  ↓
LLM: ucp_complete_checkout → completed
```

## セキュリティ

### 認証方式（Business が選択）

| 方式 | 説明 | 実装 |
|------|------|------|
| API Key `x-api-key` | 固定キー | ヘッダに付与 |
| OAuth 2.0 Client Credentials | クライアント認証 | Bearer Token 取得+更新 |
| HTTP Message Signatures | RFC 9421 署名 | 秘密鍵でリクエスト署名 |

### AP2 セキュリティ

- AP2 は Platform（uag）と Payment Credential Provider の間で直接の暗号的証明を行う
- Payment Mandate には有効期限・金額上限・対象加盟店が含まれる
- Verifiable Credential により agent の身元を検証可能
- uag は決済情報（クレジットカード番号等）を保持・処理しない
- PCI DSS スコープ外

## テスト環境

### UCP Playground（ブラウザ上でフロー体験）

https://ucp.dev/2026-04-08/specification/playground/

8ステップのインタラクティブデモ。実際のAPIリクエストは発生せず、ブラウザ内でペイロードのシミュレーションとスキーマバリデーションを行う。開発初期の理解用。

### GitHub Samples（Python リファレンス実装）

https://github.com/Universal-Commerce-Protocol/samples

`rest/python/server/` に UCP Business（加盟店）のPython実装サンプルあり。シミュレーションエンドポイントを含むため、ローカルで起動してuagのUCP Clientと結合テストが可能。

```
# サンプルサーバーの起動
git clone https://github.com/Universal-Commerce-Protocol/samples.git
cd samples/rest/python/server
pip install -r requirements.txt
python main.py
# → http://localhost:8080 で待受
# → /.well-known/ucp でProfile公開
```

### Google Merchant Center Sandbox

https://developers.google.com/merchant/ucp/

Google Merchant Center 上のUCP統合をSandbox環境でテスト可能。Google Pay 等の決済ハンドラーの検証に使えるが、Merchant Center アカウントが必要。

### ucp-demo

https://github.com/hemanth/ucp-demo

UCPのインタラクティブデモ。フロントエンド中心だが、APIの動作イメージを掴むのに有用。

### モックサーバー（uag内蔵）

`tests/ucp_mock_server.py` に全Phase対応のモックサーバーを含む。

```
python tests/ucp_mock_server.py
# http://localhost:8080/.well-known/ucp
```

カタログ・カート・チェックアウト（continue_url + AP2）・注文・ID連携・AP2マンデート認証をすべて模擬。

## その他考慮事項

### Transport の選択

Business の Profile に複数 Transport が定義されている場合、uag は以下の優先順位で選択する。

1. REST（最もシンプル、優先）
1. MCP（既存のMCP統合基盤を活用）
1. A2A（uagはA2Aサーバにもなれる）
1. Embedded（埋め込みUI、エージェントには非対応）

### エラーハンドリング

UCP のエラーは `messages[]` 配列と `severity` フィールドで表現される。

| severity | uagの動作 |
|----------|-----------|
| `recoverable` | 自動で入力修正してリトライ |
| `requires_buyer_input` | ユーザーにcontinue_urlを提示 |
| `requires_buyer_review` | continue_urlを提示して承認待ち |
| `unrecoverable` | エラーとしてLLMに報告、新規セッション推奨 |

### Idempotency

チェックアウト完了などの冪等性が重要な操作には `Idempotency-Key` ヘッダを付与する。uagはリクエストごとにUUID v4を生成し、リトライ時も同じキーを使い回す。

### レート制限

Business 側のレート制限（429 Too Many Requests）が発生した場合、`Retry-After` ヘッダに従ってバックオフする。uag標準のリトライ機構（`_pip_auto` 相当）を流用。

### スコープの3段階

| レベル | 認証 | 用途 |
|--------|------|------|
| Public | なし | カタログ参照のみ |
| Agent-authenticated | Client ID/Secret | ゲスト購入、カート作成 |
| User-authenticated | + OAuth 2.0 token | 住所連携、過去注文参照 |

## 既知の問題点

### 解決済み

| # | 問題 | 対応 | 状態 |
|---|------|------|------|
| 1 | **AP2マンデートストアがインメモリ**：ツールリロードや再起動で消失 | `~/.uag/ucp_mandates.json` にファイル永続化。アトミック書き込み対応 | ✅ 解決 |
| 7 | **期限切れマンデートの自動削除なし** | 読み込み時に `_delete_expired_mandates()` で自動パージ | ✅ 解決 |
| 8 | **モックサーバーのデッドコード** | 無害のため温存 | ✅ 確認済み |

### 未解決（設計上の制約）

| # | 問題 | 影響 | 優先度 | 対応案 |
|---|------|------|--------|--------|
| 2 | **UCP Clientの認証情報が環境変数依存**：`UCP_DEFAULT_CLIENT_ID` / `UCP_DEFAULT_CLIENT_SECRET` は全ビジネスで共有 | マルチテナント不可 | 中 | ツールパラメータで認証情報をオーバーライド可能にする |
| 3 | **HTTP Message Signatures (RFC 9421) 未実装**：OAuth 2.0とAPI Keyのみ対応 | 一部Businessで認証エラー可能性 | 中 | `_request()` に署名生成ロジックを追加 |
| 4 | **SD-JWT（Selective Disclosure JWT）未対応**：AP2仕様の属性選択的開示が未実装 | プライバシー保護機能不足（AP2 v0.2では任意実装） | 低 | `sd-jwt` ライブラリ導入 |
| 5 | **A2A Transport未対応**：UCP over A2A（他エージェント経由購入）が不可 | ユースケース制限 | 低 | 今後の拡張候補 |

### 軽微な未対応

| # | 問題 | 備考 |
|---|------|------|
| 6 | **capability version パースがリスト構造依存**：`capabilities[cap_name][0].get("version")` がハードコード | BusinessのProfile構造次第でエラー。低優先度 |
| 9 | **fmt パラメータ未対応**：既存ツール（echonet\_\*）には `fmt=json|text` があるがUCPツールはJSON固定 | LLM用ならJSON固定で十分 |

### 現時点での制約・リスク

- UCP は 2026年4月公開の新しいプロトコル。対応Business（加盟店）がまだ少ない
- AP2 対応決済プロバイダも限定的。当面は continue_url 経由が主フローになる
- サンプルサーバー（GitHub）は開発初期。すべてのケイパビリティをカバーしていない可能性がある
- 仕様が確定したものの、バージョン更新に伴う破壊的変更のリスクがある

## ロードマップ

### Phase 1 - Core (v0.6.0) ✅ 完了

目標: カタログ検索・カート構築・チェックアウト作成までの基本フロー

- [x] `ucp_shared.py` - UCPClient（探索・認証・署名・リクエスト）
- [x] `ucp_discover_tool.py`
- [x] `ucp_catalog_tool.py`（search + lookup）
- [x] `ucp_cart_tool.py`（create + get + update）
- [x] `ucp_checkout_tool.py`（create + get + update）
- [x] テスト（モックサーバーとの疎通確認）

### Phase 2 - Continue URL Checkout (v0.6.1) ✅ 完了

目標: continue_url 経由の決済完了フロー（Scenario A/B）

- [x] `ucp_checkout_tool.py` complete モード（continue_url 返却対応）
- [x] continue_url のユーザー提示（ブラウザで開くよう促す）
- [x] Idempotency-Key 再送防止
- [x] チェックアウトステータス監視（poll モード）
- [ ] Google Merchant Center Sandbox との結合テスト（外部依存のため未実施）

### Phase 3 - AP2 Autonomous Payment (v0.6.2) ✅ 完了

目標: AP2 を使った完全自律エージェント決済（Scenario C）

- [x] `ucp_ap2_tool.py`（mandate_create / mandate_list / execute / verify）
- [x] AP2 Token Execution（RSA署名JWT）
- [x] Payment Mandate 管理（作成・一覧・期限チェック）
- [x] AP2 Token の `complete_checkout` への受け渡し
- [x] テスト（モックサーバー -> 全フロー確認）

### Phase 4 - Orders & Identity (v0.6.3) ✅ 完了

目標: 注文管理・アカウント連携

- [x] `ucp_order_tool.py`（list + get）
- [x] `ucp_identity_tool.py`（link + status）
- [x] OAuth 2.0 Authorization Code flow（モック）
- [ ] アクセストークン管理（リフレッシュ・失効）は未実装

### Phase 5 - MCP Transport (v0.7.0) ✅ 完了

目標: REST に加えて MCP トランスポート対応

- [x] MCP transport 対応（`resolve_mcp_endpoint()` 追加）
- [x] MCPサーバーツール（`ucp_mcp_server_tool.py`）：start/stop/status
- [x] MCPサーバー本体（`ucp_mcp_server_main.py`）：UCP REST を MCP tools として公開
- [x] `ucp_discover` が MCP エンドポイントを表示
- [x] 複数トランスポートの自動選択（REST > MCP > A2A > Embedded）

### Phase 6 - Extensions (v0.8.0) ✅ 完了

目標: カスタムケイパビリティ・コミュニティ拡張

- [x] ベンダー独自 capability（`com.vendor.*`）のサポート（extensions パラメータ）
- [x] 拡張スキーマの動的解決（`resolve_schema()` 追加）
- [x] Fulfillment 拡張のサポート（checkout 作成時の配送先・買い手情報）
- [x] サンプル実装の完成度向上（モックサーバーの商品を15種類に拡充、カテゴリ分類）
