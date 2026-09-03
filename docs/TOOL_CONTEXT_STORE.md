# ツール単位コンテキストストア設計

## 目的

ツールがモジュールグローバル変数へ状態を保存する代わりに、uagent 本体がツールごとのコンテキスト辞書を管理し、必要なツールへ渡せるようにする。

コンテキストの識別キーはツール名とする。

```text
tool_name -> context dictionary
```

例:

```text
file_grep -> {"last_pattern": "...", "recent_files": [...]}
```

## 基本方針

- コンテキストの所有者は uagent 本体とする
- ツール側は `ToolCallbacks` 経由でコンテキストへアクセスする
- ツール呼び出しの通常引数 `args` にはコンテキストを混在させない
- ツール名をキーとして使用する
- 既存ツールは変更なしで動作できるよう後方互換にする
- `system_reload` でツールモジュールを再読み込みしても、本体側の状態は維持する
- 機密情報や巨大なデータを無制限に保存しない

## 本体側の管理

本体側にツールコンテキストストアを用意する。

```python
class ToolContextStore:
    def __init__(self) -> None:
        self._contexts: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    def get(self, tool_name: str) -> dict[str, Any]:
        with self._lock:
            return self._contexts.setdefault(tool_name, {})

    def clear(self, tool_name: str | None = None) -> None:
        with self._lock:
            if tool_name is None:
                self._contexts.clear()
            else:
                self._contexts.pop(tool_name, None)
```

実際の導入では、辞書を直接公開せず、必要に応じて `get`、`set`、`delete`、`clear` などの操作を提供する。

## ToolCallbacks への追加

既存のコールバックを壊さないよう、任意のフィールドとして追加する。

```python
@dataclass
class ToolCallbacks:
    # 既存フィールド
    set_status: Optional[Callable[[bool, str], None]] = None
    ...

    # 新規フィールド
    get_tool_context: Optional[
        Callable[[str], dict[str, Any]]
    ] = None
```

本体の初期化時にストアのアクセサを注入する。

```python
store = ToolContextStore()

init_callbacks(
    ToolCallbacks(
        ...,
        get_tool_context=store.get,
    )
)
```

## ツール側の利用方法

コンテキストを必要とする新規ツールだけが利用する。

```python
from .context import get_callbacks


def run_tool(args: dict[str, Any]) -> str:
    callbacks = get_callbacks()
    context = (
        callbacks.get_tool_context("my_tool")
        if callbacks.get_tool_context is not None
        else {}
    )

    context["last_value"] = args.get("value")
    return "ok"
```

コンテキストが未注入の環境でも空の辞書で動作するため、単体テストや旧ホストとの互換性を保てる。

## 従来のツールへの影響

従来のツールは変更せず、そのまま動作させる。

- `run_tool(args)` のシグネチャは変更しない
- `TOOL_SPEC` の変更は不要
- 既存のモジュールグローバル状態も直ちには削除しない
- 新しい状態を保存する場合だけコンテキストストアを利用する
- 既存ツールのグローバル状態は、必要なものから段階的に移行する

これにより、全ツールを一括変更する必要はない。

## 並列実行

`parallel` から同じツールが同時に呼ばれる可能性があるため、ストアの取得・削除はロックで保護する。

ただし、取得した辞書を使った複数操作は別途保護が必要である。

```python
with store.lock_for("my_tool"):
    context = store.get("my_tool")
    context["count"] = context.get("count", 0) + 1
```

単純な読み取り専用データや、呼び出し単位で上書きする値については、ツール側で追加ロックを避けられる設計にする。

## セッションとの分離

ツール単位だけでなくセッション単位の状態が必要になった場合は、次の構造へ拡張できる。

```text
session_id -> tool_name -> context dictionary
```

ただし、セッションをまたいで共有する必要がない状態は、セッション終了時に削除する。

## メモリ管理

コンテキストは常駐状態になるため、以下を守る。

- 大きなレスポンス、画像、音声、ファイル本体を保存しない
- 保存する場合はパス、ID、要約、ハッシュなどに置き換える
- エントリ数や文字数に上限を設ける
- セッション終了時・ツール無効化時に削除する
- `clear(tool_name)` と全消去手段を用意する
- TTL が必要な状態には有効期限を付ける

## セキュリティ

APIキー、アクセストークン、パスワードなどの秘密情報は保存しない。必要な場合は、既存の credential store や OS キーリングを参照する。

コンテキストをログ、LLMプロンプト、ツール引数へ自動的に含めてはならない。

## 移行手順

1. 本体に `ToolContextStore` を追加
1. `ToolCallbacks` に任意のアクセサを追加
1. CLI、GUI、Web、A2A の各初期化箇所から同じストアを注入
1. 新規ツールからコンテキストストアを使用
1. 必要性の高い既存ツールのモジュールグローバル状態を段階的に移行
1. `system_reload`、並列実行、セッション終了時のテストを追加

## 採用しない方法

### `args` への隠しフィールド注入

```python
args["_uagent_context"] = context
```

この方法は既存ツールの引数処理、ログ、スキーマ、外部ツールとの互換性を壊す可能性があるため採用しない。

### ツールモジュールのグローバル辞書

```python
_CONTEXT = {}
```

ホットリロード、複数セッション、並列実行で状態の所有範囲が不明確になるため、新しい実装では使用しない。

## 実装済み補足

現在の画像ツール連携では、Meta Model APIのResponses APIで取得した `response_id` を `generate_image` のツールコンテキストへ保存する。後続の `img2img` は通常のツール引数へIDを注入せず、同コンテキストからIDを取得して `previous_response_id` として利用する。

- 画像本体やBase64データはコンテキストへ保存しない
- `response_id` はセッションストアへ永続化できる
- `system_reload` 後も本体側のコンテキストを維持する
- Metaの経路診断ログは `UAGENT_IMG_GENERATE_DEBUG=1` の場合のみ出力する

## まとめ

本方式では、本体が次の辞書を管理する。

```python
contexts[tool_name] -> dict[str, Any]
```

既存ツールはそのまま動作し、新しいツールや移行済みツールだけが `ToolCallbacks.get_tool_context` を通じて状態を利用できる。これにより、ツール単位の状態管理、ホットリロード耐性、並列実行対応、段階的な移行を両立できる。
