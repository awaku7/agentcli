# Tool Sending Flow

## 概要

LLM にツールを送る方式はプロバイダとモードによって異なります。

## 方式一覧

### A. Chat Completions API（DeepSeek 等、Responses API 未使用）

```
req_tools = tools.get_tool_specs() if send_tools_this_round else None
```

- `tools.get_tool_specs()` は `TOOL_SPECS` から全ツールを返す
- `TOOL_SPECS` への登録は `tool_level` / `tool_genre` / genre mask で制御される
- デフォルトでは基本ツールのみ登録され、その他は `tool_catalog` → `tool_load` で動的ロード
- `UAGENT_GPT54_TOOL_SEARCH` の影響は受けない

### B. Responses API + OpenAI/Azure + GPT-5.4+（デフォルト = native mode）

```python
responses_tool_specs = None  # → build_responses_request 内で get_tool_specs()
```

- 全ツールをサーバに送信し、サーバ側 tool_search が narrow
- 管理ツール（tool_catalog / tool_load / unload_tool）も含まれる
- auto-unload: スキップ（`_is_gpt54_tool_search_target` が True）
- compaction: 自動適用（`_get_shrink_max_tokens` の閾値）

### C. Responses API + OpenAI/Azure + GPT-5.4+ + `UAGENT_GPT54_TOOL_SEARCH=legacy`

```python
responses_tool_specs = _select_tool_specs_legacy(call_messages)
```

- 初期は `tool_catalog` / `tool_load` / `unload_tool` / `human_ask` のみ
- LLM が `tool_catalog` で目的のツールを検索 → `tool_load` で動的ロード
- `_select_tool_specs_legacy()` はユーザーメッセージに基づいてツールを絞り込む

### D. Responses API + OpenAI/Azure + GPT-5.4+ + `UAGENT_GPT54_TOOL_SEARCH=native`

- A と同じく全ツール送信
- ただし管理ツール（tool_catalog / tool_load / unload_tool）は除外される（サーバ側 tool_search に任せる）
- `_should_preload_lazy_specs()` が True になり、genre フィルタをバイパスして全ツールが強制登録される

## モード判定

| モード | `_get_gpt54_tool_search_mode()` | `_should_preload_lazy_specs()` | 備考 |
|---|---|---|---|
| デフォルト（A / B） | `"native"` | `False` | view 3, 4 参照 |
| legacy（C） | `"legacy"` | `False` | 明示設定が必要 |
| native（D） | `"native"` | `True` | `UAGENT_GPT54_TOOL_SEARCH=native` が必要 |

## auto-unload スキップ条件

```python
if not (_should_preload_lazy_specs()
        or _is_gpt54_tool_search_target(...)
        or bool(core.responses_state.get("previous_response_id"))):
    # auto-unload 実行
```

以下のいずれかに該当する場合はスキップ:
1. `_should_preload_lazy_specs()` が True（native mode 明示）
2. `_is_gpt54_tool_search_target()` が True（OpenAI/Azure + GPT-5.4+ の Responses API）
3. `previous_response_id` が設定されている（全プロバイダの Responses API）

## tool_catalog による動的ツールロード

LLM に最初から全ツールを送るのではなく、必要に応じてツールを動的にロードする仕組みです。

### 動作の流れ

1. 初期状態では `tool_catalog` / `tool_load` / `unload_tool` / `human_ask` のみが LLM に送られる
2. LLM が `tool_catalog` を呼び出すと、利用可能な全ツールの一覧が返る  
   → クエリ（`query`）指定時は、先頭（最高スコア）の未ロードツールが自動的にロードされる  
   → レスポンスの `auto_loaded` フィールドに自動ロードされたツール名が格納され、該当ツールの `loaded` が `true` に更新される
3. 上記以外で必要なツールは `tool_load(tool_name)` で動的ロードする
4. ロードされたツールは次ラウンド以降のツールリストに追加される
5. `unload_tool(tool_name)` で明示的にアンロードできる
6. 一定ラウンド使われなかったツールは auto-unload される（`UAGENT_AUTO_UNLOAD_ROUNDS`、デフォルト `10`）  
   → 自動ロードされたツールもこの対象となる（`_LOADED_SINGLE_TOOLS` に登録されるため）

### 適用されるケース

| ケース | tool_catalog が使われるか |
|---|---|
| Chat Completions API（DeepSeek 等） | はい（genre mask で絞られた残りを動的ロード） |
| Responses API + GPT-5.4+（デフォルト） | いいえ（全ツール送信、サーバ側 tool_search） |
| Responses API + GPT-5.4+ + `legacy` | はい（`_select_tool_specs_legacy` で明示的に使用） |
| Responses API + GPT-5.4+ + `native` | いいえ（tool_catalog 自体が除外される） |

### 実装

- `tool_catalog` / `tool_load` / `unload_tool` は `tools/catalog_tool.py` に実装
- これらは `tool_genre: "devel"` に属し、`tool_level=0`（常時有効）
- `_select_tool_specs_legacy()` はユーザーメッセージを解析し、関連ツールを初期セットに追加する

## 環境変数

| 変数 | デフォルト | 説明 |
|---|---|---|
| `UAGENT_GPT54_TOOL_SEARCH` | (未設定 = native) | `native` / `legacy` / `off` |
| `UAGENT_RESPONSES` | (自動) | `1` で強制有効化 |
| `UAGENT_AUTO_UNLOAD_ROUNDS` | `10` | 未使用ツールをアンロードするラウンド数 |
