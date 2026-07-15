# browser_playwright セッション拡張 設計書

| 項目 | 内容 |
|---|---|
| 文書種別 | 既存ツール拡張の実装用設計書 |
| 対象 | `src/uagent/tools/browser_playwright_tool.py` |
| 版 | 1.0 |
| 目的 | LLM が同一ブラウザを継続操作できるようにする |
| 非目的 | 人がブラウザを直接操縦する UI、OS 外部ブラウザのハイジャック |

---

## 1. 概要

### 1.1 背景

現行 `browser_playwright` は 1 呼び出し完結である。

```text
起動 → actions 実行 → context/browser close → 終了
```

このため、人と LLM が対話しながら「開く → 読む → 押す → また読む」を **同じページ状態のまま** 続けることができない。

### 1.2 ゴール

1. 既存の 1 ショット `actions` 実行を完全互換で維持する
2. `session_id` により同一 browser context を保持する
3. LLM が複数回の tool call で継続操作できる
4. 新規タブ / ポップアップを page として追跡し、継続判断可能にする
5. 放置セッションや孤児 Chromium を残さない

### 1.3 非ゴール

- 人がこのツール経由でブラウザを手動操縦する UI
- 人の手動クリックを LLM にリアルタイム同期
- OS が起動した外部ブラウザ（Chrome 別プロセス等）の制御
- 複数エージェントによる同一 session の同時運転
- 新しい別ツールの新設（既存 `browser_playwright` を拡張する）

### 1.4 利用イメージ

```text
人  ←対話→  LLM  ← browser_playwright(session_id) →  同一ブラウザ session
```

1. 人: サイトを開いて  
2. LLM: `session_action=start` + `goto`  
3. 人: 内容を読んで  
4. LLM: 同じ `session_id` で `content` / `snapshot`  
5. 人: そのリンクを開いて  
6. LLM: 同じ `session_id` で `click`（必要なら新規 page 切替）  
7. 人: 終わり  
8. LLM: `close`

---

## 2. 現状と課題

### 2.1 現行仕様

- 実装: `browser_playwright_tool.py`
- Playwright async API
- `actions[]` を順実行
- 既定 `headless=true`
- 終了時に必ず `context.close()` / `browser.close()`

### 2.2 既にあるが不十分な multi-page 支持

| 機能 | 現状 |
|---|---|
| `switch_page` | index 指定で切替可能 |
| `close_page` | 現在 page を閉じ、残り最後へ |
| 新規 page 自動検知 | **なし** |
| `expect_page` / `wait_for_page` | **なし** |
| 応答の `pages[]` | **なし** |
| active page 明示 | **なし** |

### 2.3 セッション化で顕在化する穴

1. `target=_blank` / `window.open` で別タブが開いても active が変わらない
2. LLM が「何枚開いているか」を観測できない
3. 毎回 `asyncio.run()` だと session オブジェクトを跨呼び出しで使えない
4. close 忘れで Chromium が残留しうる
5. iframe 状態を page 切替後に誤って引きずる

---

## 3. 用語

| 用語 | 意味 |
|---|---|
| 1 ショット | session なし。起動〜close を 1 回で完了 |
| session | 保持された Playwright browser/context 一式 |
| page | context 内のタブ/ウィンドウ相当 |
| active page | 以降の actions の操作対象 page |
| popup | 多くは同一 context の新規 page |
| 外部ブラウザ | OS が起動する Playwright 管理外プロセス。対象外 |

---

## 4. 設計方針

### 4.1 拡張方針

- **新ツールは作らない**
- 既存 `browser_playwright` に session モードを追加
- `session_*` 未指定時は現行互換

### 4.2 別タブ / 別ウィンドウ方針

Playwright 管理下で起きる「別のブラウザが開いた」ように見える現象の多くは、実際には:

```text
同一 browser context 内の新しい page
```

である。これを一流市民として扱う。

| 現象 | 扱い |
|---|---|
| 同一タブ遷移 | active page の URL 変更 |
| 新規タブ / `window.open` | 新規 page として登録 |
| ポップアップ | 新規 page として登録 |
| 別 browser インスタンス | 原則非対応。必要なら別 session |
| OS 外部ブラウザ | 対象外 |

### 4.3 デフォルト固定値

| 項目 | 値 | 理由 |
|---|---|---|
| 新規 page 自動 focus | **しない** | 文脈が勝手に変わると危険 |
| 新規 page 通知 | **する** | LLM が切替判断できる |
| 最大 sessions | 2 | リソース保護 |
| 最大 pages / session | 10 | タブ爆発防止 |
| TTL（無操作） | 300 秒 | 放置対策 |
| hard lifetime | 1800 秒 | 長時間残留防止 |
| headless 既定 | true | 現行互換 |
| 同一 session 並列 | 禁止 | 競合防止 |

---

## 5. 外部 API

### 5.1 追加パラメータ

既存パラメータは維持。以下を追加する。

| 引数 | 型 | 必須 | 意味 |
|---|---|---|---|
| `session_id` | string | 条件付 | 既存 session を指定 |
| `session_action` | enum | 条件付 | `start` / `act` / `snapshot` / `list` / `close` |
| `session_ttl_sec` | int | 否 | 無操作 TTL。既定 300 |
| `keep_alive` | bool | 否 | 互換用。`start`/`act` 後に維持する意図の明示 |
| `auto_focus_new_page` | bool | 否 | 既定 false。true なら新規 page を active に |
| `dialog_policy` | enum | 否 | `accept` / `dismiss` / `manual`。session 開始時 |

#### 互換ルール

1. `session_action` も `session_id` もなし  
   → **現行 1 ショット**
2. `session_action=start`  
   → 新規 session。`actions` は任意
3. `session_id` + `session_action=act`（または action 省略で act 扱い）  
   → 継続操作。`actions` 必須
4. `session_action=snapshot|close|list`  
   → `actions` 不要

### 5.2 session_action 詳細

#### `start`

- browser/context/page を起動
- 初期 `actions` があれば実行
- `session_id` を発行して返す
- close しない

#### `act`

- 既存 session で `actions` を実行
- TTL を更新
- close しない

#### `snapshot`

- 操作せず状態を返す
- `url` / `title` / `pages` / active page / 可能なら簡易情報

#### `list`

- 生存中 session の一覧

#### `close`

- 対象 session を閉じ、registry から削除

### 5.3 呼び出し例

#### 1 ショット（現行互換）

```json
{
  "actions": [
    {"type": "goto", "url": "https://example.com"},
    {"type": "content"}
  ]
}
```

#### 開始

```json
{
  "session_action": "start",
  "headless": false,
  "actions": [
    {"type": "goto", "url": "https://example.com"}
  ]
}
```

#### 継続

```json
{
  "session_id": "bp_20260715_193500_ab12",
  "session_action": "act",
  "actions": [
    {"type": "click", "selector": "a"},
    {"type": "content"}
  ]
}
```

#### 新規タブ待ちを含む継続

```json
{
  "session_id": "bp_...",
  "session_action": "act",
  "actions": [
    {"type": "click", "selector": "a[target=_blank]", "expect_new_page": true},
    {"type": "switch_page", "index": -1},
    {"type": "content"}
  ]
}
```

#### 終了

```json
{
  "session_id": "bp_...",
  "session_action": "close"
}
```

---

## 6. レスポンス契約

成功・失敗を問わず、可能な範囲で共通形を返す。

```json
{
  "ok": true,
  "session_id": "bp_20260715_193500_ab12",
  "session_action": "act",
  "session_alive": true,
  "active_page_index": 1,
  "pages": [
    {
      "index": 0,
      "url": "https://a.example/",
      "title": "A",
      "open": true
    },
    {
      "index": 1,
      "url": "https://b.example/",
      "title": "B",
      "open": true
    }
  ],
  "events": [
    {
      "type": "page_opened",
      "index": 1,
      "url": "https://b.example/"
    }
  ],
  "final_url": "https://b.example/",
  "title": "B",
  "results": [],
  "ttl_sec": 300,
  "expires_at": "2026-07-15T19:40:00+09:00",
  "error": null
}
```

### 6.1 フィールド意味

| フィールド | 意味 |
|---|---|
| `session_id` | 継続操作用 ID。1 ショットでは null 可 |
| `session_alive` | いま session が有効か |
| `active_page_index` | 次の操作対象 |
| `pages` | 開いている page 一覧 |
| `events` | この呼び出し中に起きた page/dialog/download 等 |
| `results` | 既存どおり各 action の結果 |
| `final_url` / `title` | active page の現在値 |

### 6.2 エラーコード（推奨）

| code | 意味 |
|---|---|
| `session_not_found` | ID が無い/期限切れ |
| `session_dead` | browser が既に閉じている |
| `session_busy` | 同一 session が実行中 |
| `session_limit` | 最大 session 数超過 |
| `page_limit` | 最大 page 数超過 |
| `page_not_found` | switch/close 対象なし |
| `no_active_page` | 全 page 閉鎖 |
| `external_browser_unsupported` | OS 外部ブラウザは対象外 |
| `invalid_argument` | 引数不正 |

---

## 7. 内部設計

### 7.1 モジュール分割（同一ファイル内でも可）

現行 `execute_actions` を責務分割する。

```text
ensure_playwright_installed()
launch_session(options) -> BrowserSession
run_actions(session, actions) -> {results, events}
snapshot_session(session) -> status dict
close_session(session)
oneshot_execute(args)  # launch + run + close
browser_playwright_run(args)  # 分岐入口
```

### 7.2 データ構造

```python
@dataclass
class BrowserSession:
    session_id: str
    created_at: float
    last_used_at: float
    ttl_sec: int
    hard_lifetime_sec: int
    headless: bool
    auto_focus_new_page: bool
    dialog_policy: str

    # Playwright objects (dedicated loop only)
    pw: Any
    browser: Any
    context: Any
    active_page: Any
    active_frame: Any

    console_logs: list[dict]
    pending_events: list[dict]
    download_dir: str | None

    # concurrency / lifecycle
    lock: Any
    loop: Any
    thread: Any
    closed: bool
```

### 7.3 レジストリ

```python
_SESSIONS: dict[str, BrowserSession] = {}
_SESSIONS_LOCK = threading.RLock()
```

- `session_id` 形式例: `bp_YYYYMMDD_HHMMSS_<rand>`
- `list` / TTL 掃除 / atexit で参照

### 7.4 実行モデル（必須）

Playwright async オブジェクトは生成した event loop に束縛される。

そのため:

- 1 ショット: 従来どおり一時 loop で launch→run→close してよい
- session: **session 専用スレッド + 専用 event loop** を持ち、すべての操作をそこに投稿する

擬似:

```text
worker thread:
  loop = new_event_loop()
  loop.run_forever()

main tool call:
  future = asyncio.run_coroutine_threadsafe(coro, session.loop)
  return future.result(timeout=...)
```

**禁止:** session オブジェクトに対する呼び出しごとの `asyncio.run()`。

### 7.5 入口分岐

```text
browser_playwright_run(args):
  prune_expired_sessions()

  if no session_action and no session_id:
      return oneshot_execute(args)

  action = session_action or infer(session_id, actions)

  if action == "list":
      return list_sessions()
  if action == "start":
      return start_session(args)
  if action == "act":
      return act_session(args)
  if action == "snapshot":
      return snapshot(args)
  if action == "close":
      return close(args)
  return invalid_argument
```

---

## 8. page / frame ライフサイクル

### 8.1 初期 page

`start` 時:

1. `browser.launch`
2. `browser.new_context`
3. `page = context.new_page`
4. active page/frame を設定
5. listener を付与

### 8.2 新規 page 検知

`start` 時に必須:

```text
context.on("page", on_new_page)
```

`on_new_page(page)`:

1. pages に登録
2. console listener 付与
3. `pending_events` に `page_opened`
4. `auto_focus_new_page=true` なら active を切替
5. page 数が上限超なら:
   - 非 active の最古を close する、または
   - エラーにして caller に判断させる  
   （推奨: **エラーを events に出し、操作は継続可能なら継続**。厳密制限は設定で）

### 8.3 page close 検知

```text
page.on("close", on_page_close)
```

- `page_closed` event
- active が閉じられたら残存 page の最後（または index 0）へ切替
- ゼロ枚なら `no_active_page`

### 8.4 active page 規則

1. 明示 `switch_page` が最優先
2. `expect_new_page` 付き click 成功時は新規 page を active にしてよい
3. それ以外の自動 focus は既定 off
4. page 切替時は `active_frame` を **main frame にリセット**

### 8.5 iframe

- 既存 `switch_to_frame` / `switch_to_parent_frame` を維持
- session に `active_frame` を保持
- `snapshot` で frame 位置が分かるとよい（少なくとも main か否か）

---

## 9. action 拡張

### 9.1 既存 action

現行 enum は維持し、session でも同じ実装を使う。

### 9.2 追加・拡張

| action / オプション | 内容 |
|---|---|
| `list_pages` | page 一覧を results に返す |
| `wait_for_page` | 新規 page を待つ。`timeout` 対応 |
| `switch_page` | `index` に加え `url_contains` を許可。`index=-1` は最新 |
| `close_page` | `index` 指定可。省略時は active |
| `click.expect_new_page` | click 後に新規 page を待って結果へ含める |

#### `wait_for_page` 例

```json
{"type": "wait_for_page", "timeout": 10000}
```

#### `switch_page` 例

```json
{"type": "switch_page", "index": -1}
{"type": "switch_page", "url_contains": "login"}
```

#### `click` 拡張例

```json
{
  "type": "click",
  "selector": "a.external",
  "expect_new_page": true,
  "timeout": 10000
}
```

実装イメージ:

```text
async with context.expect_page() as new_page_info:
    await page.click(selector)
page = await new_page_info.value
register/focus according to policy
```

---

## 10. dialog / download / network

### 10.1 dialog

- session 開始時 `dialog_policy`:
  - `accept`: 自動 accept
  - `dismiss`: 自動 dismiss
  - `manual`: 既存 `handle_dialog` で設定するまで既定動作に依存
- page 切替後も policy を新規 page に適用
- 発生したら `events` に `dialog` を残せるのが望ましい

### 10.2 download

- session ごとに download 保存先を持てるとよい  
  例: `data/browser_sessions/<session_id>/downloads`
- 既存 `download` action を維持
- 結果 path は絶対 path で返す（現行踏襲）

### 10.3 network intercept

- listener は page に紐づくため、active page 変更時の付け替え規則を持つ
- 最低限: 現行どおり「設定した page」で動作、と文書化する
- 可能なら context レベル route を推奨（将来改善）

---

## 11. ライフサイクル / 安全策

### 11.1 TTL

- 各 `act` / `snapshot` で `last_used_at` 更新
- `now - last_used_at > ttl_sec` なら自動 close

### 11.2 hard lifetime

- `now - created_at > hard_lifetime_sec` なら自動 close
- TTL より優先して切る

### 11.3 最大数

- sessions > max で `start` されたら:
  - 推奨: エラー `session_limit`
  - あるいは最古を evict（方針はエラーの方が安全）

### 11.4 排他

- session 単位 lock
- 実行中に次の act が来たら `session_busy`

### 11.5 切断検知

- `browser.is_connected()` や page 操作例外で切断を検知
- session を `dead` 扱いにし registry から除去または `session_alive=false`

### 11.6 プロセス終了

- `atexit` で全 session close
- worker thread / loop も停止
- 孤児 Chromium を残さない

### 11.7 並列実行フラグ

- session を使う呼び出しは parallel safe ではない
- 同一 session の並列 tool call を禁止

---

## 12. 1 ショット互換

| 項目 | 互換内容 |
|---|---|
| 引数 | 既存引数だけで動く |
| 動作 | 実行後 close |
| 応答 | 最低限現行の `ok/results/final_url/video_path` を維持 |
| 追加フィールド | あってもよいが既存利用を壊さない |

1 ショットでも内部的に `pages/events` を付けてよい。  
ただし必須依存にしてはいけない。

---

## 13. シナリオ試験一覧

### 13.1 互換

1. 既存 `goto + content` が成功し、終了後プロセスが残らない
2. `headless=false` の 1 ショットが成功

### 13.2 基本 session

1. start → act → act → close
2. close 後 act で `session_not_found` or `session_dead`
3. snapshot で url/title/pages が取れる

### 13.3 新規タブ

1. `target=_blank` click 後、`events` に `page_opened`
2. `pages` が 2 件以上
3. 既定では active は親のまま
4. `switch_page index=-1` で新規へ移動できる
5. `click.expect_new_page=true` で新規待ちできる

### 13.4 ポップアップ

1. `window.open` 系で page 増加
2. 操作後 `close_page` で親に戻れる

### 13.5 iframe

1. frame 切替後に selector が当たる
2. page 切替後は main frame に戻る

### 13.6 寿命

1. TTL 経過で自動 close
2. hard lifetime で自動 close
3. エージェント終了後に Chromium が残らない

### 13.7 競合

1. 同一 session に重ねがけで `session_busy`

### 13.8 対象外

1. OS 外部ブラウザ起動は制御できないことを文書とエラーで明示

---

## 14. 実装タスク

### Phase 1: 内部分割

- [ ] `ensure_playwright_installed`
- [ ] `run_actions(context/page, actions)` 抽出
- [ ] 1 ショットが分割後も通る

### Phase 2: multi-page 観測

- [ ] `context.on("page")` / page close 追跡
- [ ] `pages[]` / `events[]` / `active_page_index` を応答へ
- [ ] `list_pages`
- [ ] `wait_for_page`
- [ ] `switch_page` 強化（`-1`, `url_contains`）
- [ ] `close_page` の index 指定
- [ ] `click.expect_new_page`

### Phase 3: session 本体

- [ ] `BrowserSession` + registry
- [ ] dedicated thread/loop
- [ ] `start` / `act` / `snapshot` / `list` / `close`
- [ ] TOOL_SPEC 更新

### Phase 4: 安全策

- [ ] TTL / hard lifetime / prune
- [ ] max sessions/pages
- [ ] busy lock
- [ ] atexit cleanup
- [ ] dead session 検出

### Phase 5: 検証

- [ ] 1 ショット回帰
- [ ] start-act-close
- [ ] 新規タブシナリオ
- [ ] TTL/atexit

---

## 15. TOOL_SPEC 変更方針

- `required: ["actions"]` をやめる  
  → session_action によっては actions 不要
- validation は run 時に行う:
  - 1 ショット: actions 必須
  - act: session_id + actions 必須
  - start: session_id 不要
  - snapshot/close: session_id 必須
  - list: 追加引数不要

説明文に明記:

```text
Use session_action=start/act/close to keep the same browser across multiple calls.
New tabs/popups appear as pages[] events; switch explicitly unless auto_focus_new_page=true.
Always close sessions when finished.
```

---

## 16. ログ / プライバシー

- URL や title はデバッグに有用だが機微情報を含みうる
- storage_state や cookie をログに出さない
- download path は出してよい
- 認証コードやパスワードを results にエコーしない

---

## 17. 受け入れ条件

1. 既存の actions のみ呼び出しが従来どおり成功する  
2. start → act → act で cookie / ページ状態が維持される  
3. 新規タブが `pages/events` に現れ、明示切替できる  
4. 既定では新規タブに自動 focus しない  
5. close / TTL / hard lifetime / atexit のいずれかで必ず解放される  
6. 同一 session の並列実行が安全に拒否される  
7. OS 外部ブラウザ制御を謳わない  

---

## 18. 判断ルール（実装中に迷ったら）

1. **互換を壊さない**（1 ショット最優先）
2. **勝手に active page を変えない**
3. **観測情報（pages/events/url）を厚く返す**
4. **session は単一 loop でのみ触る**
5. **閉じる経路を複数用意し、孤児を残さない**
6. **管理外ブラウザは追わない**

---

## 19. 将来拡張（今はやらない）

- context 共有の remote debugging 接続
- 人の手動操作イベントの双方向ストリーム
- 永続 browser profile の高度管理
- 複数 session をまたぐ page 移動
- 動画の常時プレビュー UI

---

## 20. 設計宣言（最終）

`browser_playwright` は、既存の 1 ショット自動操作を維持したまま、  
**同一 Playwright browser context を `session_id` で保持して LLM が継続指示できるモード**を追加する。  

別タブやポップアップは同一 session の page として追跡し、  
毎回 `pages` / `events` / `active_page_index` を返して次の判断を可能にする。  

OS が開く外部ブラウザは対象外とする。

---

以上を実装の単一ソースとする。実装中に新規の制約が判明した場合は、本設計書の該当節を先に更新してからコードを変更する。
