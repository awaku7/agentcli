# uag WebSocket Server — 概要・起動・API リファレンス

VSCode 拡張などの外部クライアントから uag のツール群にアクセスするための
WebSocket サーバです。

---

## 起動方法

### 基本

```bash
python -m uagent.ws_server
```

デフォルトで `127.0.0.1:18765` にサーバが起動します。

### オプション

```bash
python -m uagent.ws_server --port 18765 --log-level DEBUG
```

| オプション | 既定値 | 説明 |
|-----------|--------|------|
| `--port` | `18765` | ポート番号 |
| `--log-level` | `INFO` | ログレベル (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

### シグナル

サーバが起動し接続可能になると、標準出力に以下の行が出力されます:

```
UAG_WS_READY:18765
```

VSCode 拡張はこの行を監視して接続開始のタイミングを判断します。

### 終了

- `Ctrl+C` で graceful shutdown
- `SIGTERM` / `SIGINT` 対応 (Unix)

---

## 動作確認 (手動テスト)

```bash
# ターミナル1: サーバ起動
python -m uagent.ws_server --port 18765
```

```bash
# ターミナル2: WebSocket で接続テスト (websocat が必要な場合)
# pip install websockets で代用可能
python -c "
import asyncio, json, websockets

async def test():
    async with websockets.connect('ws://127.0.0.1:18765') as ws:
        # Ping
        await ws.send(json.dumps({'id':'1','method':'ping','params':{}}))
        print(await ws.recv())
        
        # Tools list
        await ws.send(json.dumps({'id':'2','method':'tools/list','params':{}}))
        print(await ws.recv())

asyncio.run(test())
"
```

---

## プロトコル仕様

### メッセージ形式

すべての通信は JSON テキストフレームです。

#### リクエスト (Client → Server)

```json
{
  "id": "req_001",
  "method": "ping",
  "params": {}
}
```

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `id` | string | yes | リクエストID。レスポンスと対応付けるために使用 |
| `method` | string | yes | 呼び出すメソッド名 |
| `params` | object | yes | メソッドに渡すパラメータ |

#### レスポンス (Server → Client)

```json
{
  "id": "req_001",
  "ok": true,
  "result": { "pong": true }
}
```

成功時:

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `id` | string | リクエストID |
| `ok` | boolean | `true` |
| `result` | object | メソッドの戻り値 |

エラー時:

```json
{
  "id": "req_001",
  "ok": false,
  "error": {
    "code": "METHOD_NOT_FOUND",
    "message": "Unknown method: hoge"
  }
}
```

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `ok` | boolean | `false` |
| `error.code` | string | 機械可読エラーコード |
| `error.message` | string | 人間可読エラーメッセージ |

---

## API リファレンス

### ping

ヘルスチェック。

```json
// Request
{ "id": "1", "method": "ping", "params": {} }

// Response
{ "id": "1", "ok": true, "result": { "pong": true, "timestamp": 1234567890.123 } }
```

---

### tools/list

利用可能な全ツールの一覧を取得。

```json
// Request
{ "id": "1", "method": "tools/list", "params": {} }

// Response
{
  "id": "1",
  "ok": true,
  "result": {
    "tools": [
      {
        "name": "tool_catalog",
        "description": "Return a JSON catalog of available tools...",
        "genre": "",
        "parallel_safe": true,
        "parameters": ["query", "all"]
      },
      ...
    ]
  }
}
```

---

### tools/get

特定ツールの詳細情報を取得。

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `name` | string | yes | ツール名 |

```json
// Request
{ "id": "1", "method": "tools/get", "params": { "name": "search_web" } }

// Response
{ "id": "1", "ok": true, "result": { "spec": { ... } } }
```

---

### tool/execute

ツールを実行。

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `name` | string | yes | ツール名 |
| `args` | object | yes | ツールに渡す引数 |

```json
// Request
{ "id": "1", "method": "tool/execute", "params": { "name": "fetch_url", "args": { "url": "https://example.com" } } }

// Response
{ "id": "1", "ok": true, "result": { "result": { "ok": true, ... } } }
```

---

### config/get

設定値を取得。

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `key` | string | no | 特定のキー。省略時は全設定を返す |

```json
// Request (全設定)
{ "id": "1", "method": "config/get", "params": {} }

// Request (特定キー)
{ "id": "1", "method": "config/get", "params": { "key": "provider" } }
```

設定の優先順位:

1. VSCode 拡張から `config/set` で設定された値 (セッション内のみ有効)
2. 環境変数 (`UAGENT_PROVIDER` など)
3. `.env` ファイル

---

### config/set

設定値を変更 (セッション内のみ。環境変数は書き換えない)。

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `key` | string | yes | 設定キー |
| `value` | string | yes | 設定値 |

```json
// Request
{ "id": "1", "method": "config/set", "params": { "key": "provider", "value": "openai" } }

// Response
{ "id": "1", "ok": true, "result": { "ok": true } }
```

---

### session/new

新規セッションを作成。

```json
// Request
{ "id": "1", "method": "session/new", "params": {} }

// Response
{ "id": "1", "ok": true, "result": { "id": "a1b2c3d4e5f6" } }
```

セッションは `get_state_dir()/sessions/` に JSON ファイルとして保存され、
通常の uag CLI セッションと互換性があります。

---

### session/list

保存済みセッションの一覧 (新しい順)。

```json
// Request
{ "id": "1", "method": "session/list", "params": {} }

// Response
{
  "id": "1",
  "ok": true,
  "result": {
    "sessions": [
      {
        "id": "a1b2c3d4e5f6",
        "created": "2026-06-25T10:30:00+00:00",
        "message_count": 5,
        "preview": "最後のメッセージ内容..."
      }
    ]
  }
}
```

---

### session/load

セッションを読み込み (0 = 最新)。

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `index` | integer | no | インデックス (0始まり、既定: 0) |

```json
// Request
{ "id": "1", "method": "session/load", "params": { "index": 0 } }

// Response
{ "id": "1", "ok": true, "result": { "session": { "id": "...", "messages": [...], ... } } }
```

---

### session/delete

セッションを削除。

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `id` | string | yes | セッションID |

```json
// Request
{ "id": "1", "method": "session/delete", "params": { "id": "a1b2c3d4e5f6" } }

// Response
{ "id": "1", "ok": true, "result": { "deleted": true } }
```

---

### files/read

作業ディレクトリ内のファイルを読み込み。

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `path` | string | yes | ファイルパス (workdir からの相対パス) |

```json
// Request
{ "id": "1", "method": "files/read", "params": { "path": "pyproject.toml" } }

// Response
{
  "id": "1",
  "ok": true,
  "result": {
    "content": "[project]\nname = \"uag\"\n...",
    "language": "toml",
    "size": 3912
  }
}
```

---

### workdir/get / workdir/set

作業ディレクトリの取得/設定。

```json
// Get
{ "id": "1", "method": "workdir/get", "params": {} }
// Response: { "ok": true, "result": { "path": "/home/user/project" } }

// Set
{ "id": "1", "method": "workdir/set", "params": { "path": "/home/user/project" } }
// Response: { "ok": true, "result": { "ok": true, "path": "/home/user/project" } }
```

---

### system/specs

システム情報を取得。

```json
// Request
{ "id": "1", "method": "system/specs", "params": {} }

// Response
{
  "id": "1",
  "ok": true,
  "result": {
    "platform": "Windows",
    "release": "10",
    "python_version": "3.14.5",
    "hostname": "MY-PC"
  }
}
```

---

## エラーコード一覧

| コード | 意味 |
|--------|------|
| `METHOD_NOT_FOUND` | 存在しないメソッドが呼ばれた |
| `INVALID_JSON` | JSON のパースに失敗 |
| `INVALID_PARAMS` | パラメータが不足または不正 |
| `FILE_NOT_FOUND` | ファイルが存在しない |
| `PERMISSION_DENIED` | 権限エラー |
| `INTERNAL_ERROR` | その他の内部エラー |

---

## ファイル構成

```
src/uagent/
├── ws_server.py      # WebSocket サーバ (エントリポイント)
├── ws_handler.py     # メッセージディスパッチ + 全ハンドラ
├── ws_session.py     # セッション管理 (uag CLI と互換)
└── ws_config.py      # 設定管理 (VSCode設定 > 環境変数)
```

---

## 依存関係

- `websockets>=16.0` — requirements.txt に既に含まれています
- その他は uag の既存依存関係のみ (`pip install uag` で全て揃う)
