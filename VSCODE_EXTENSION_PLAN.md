# VSCode Extension 化 — 詳細仕様書

uag（Universal AI Gateway）を VSCode 拡張機能として統合するための詳細設計。

---

## 1. システムアーキテクチャ

```
┌─────────────────────────────────────────────────┐
│                 VSCode 拡張 (TypeScript)          │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │Webview   │  │TreeView  │  │Commands       │  │
│  │Panel     │  │(tools)   │  │(editor ctx)   │  │
│  └────┬─────┘  └──────────┘  └───────┬───────┘  │
│       │                               │          │
│  ┌────▼───────────────────────────────▼───────┐  │
│  │         WebSocket Client (wsライブラリ)      │  │
│  └────────────────────┬───────────────────────┘  │
│                       │ ws://localhost:18765     │
├───────────────────────┼─────────────────────────┤
│                 Python バックエンド               │
│  ┌────────────────────▼───────────────────────┐  │
│  │   WebSocket Server (asyncio + websockets)  │  │
│  │   Port: 18765 (固定, configで変更可)         │  │
│  └────┬───────────────────────────────────────┘  │
│       │                                          │
│  ┌────▼───────────────────────────────────────┐  │
│  │   uag 本体 (uagent.core / tools / llm)     │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

**起動シーケンス:**

```
VSCode 起動 → activate() 発火
  → Python の存在確認 (python -c "import uagent")
    → NG: 「pip install uag」を促す通知を表示
  → uag の WebSocket サーバを子プロセス起動
    → python -m uagent.ws_server --port 18765
  → WebSocket 接続確立を待機 (最大10秒, 200ms間隔でpoll)
  → 接続成功 → サイドパネル有効化 + ステータスバーに "uag: connected" 表示
  → 接続失敗 → エラー通知 + リトライボタン表示
```

## 2. WebSocket プロトコル仕様

### 2-a. メッセージフォーマット

すべての通信は JSON テキストフレーム。1リクエスト＝1レスポンス（ストリーミング除く）。

```typescript
// リクエスト (TypeScript → Python)
{
  "id": "req_001",              // リクエストID (UUID, 必須)
  "method": "chat",             // メソッド名 (必須)
  "params": {                   // パラメータ (メソッド依存)
    "message": "Hello",
    "stream": true
  }
}

// レスポンス (Python → TypeScript)
{
  "id": "req_001",              // リクエストID (対応付け用)
  "ok": true,                   // 成功/失敗
  "result": { ... },            // 成功時データ
  "error": "error message"      // 失敗時のみ
}

// ストリーミングチャンク (stream=true 時)
{"id": "req_001", "type": "chunk", "data": "Hello"}
{"id": "req_001", "type": "chunk", "data": " world"}
{"id": "req_001", "type": "tool_call", "tool": "search_web", "args": {"q": "..."}}
{"id": "req_001", "type": "tool_result", "tool": "search_web", "result": "..."}
{"id": "req_001", "type": "done", "result": "final answer"}

// サーバ → クライアント (通知系)
{"id": null, "type": "status", "data": "LLM processing..."}
{"id": null, "type": "error", "data": "Connection lost..."}
```

### 2-b. メソッド一覧

| method | params | result | 説明 |
|--------|--------|--------|------|
| `ping` | `{}` | `{"pong": true}` | 死活監視 (30秒間隔) |
| `chat` | `{message, stream?, history?, context?}` | ストリーム or `{reply}` | LLM チャット |
| `tools/list` | `{}` | `{tools: [...]}` | 全ツール一覧 |
| `tools/get` | `{name}` | `{spec: {...}}` | 特定ツールの詳細 |
| `tool/execute` | `{name, args}` | `{result: ...}` | ツール実行 |
| `config/get` | `{key?}` | `{config: {...}}` | 設定取得 |
| `config/set` | `{key, value}` | `{ok: true}` | 設定更新 |
| `session/list` | `{}` | `{sessions: [...]}` | セッション一覧 |
| `session/load` | `{index}` | `{session: {...}}` | セッション復元 |
| `session/new` | `{}` | `{id: "..."}` | 新規セッション |
| `files/read` | `{path}` | `{content, language}` | ファイル読み込み |
| `files/write` | `{path, content}` | `{ok: true}` | ファイル書き込み |
| `workdir/get` | `{}` | `{path: "..."}` | 作業ディレクトリ取得 |
| `workdir/set` | `{path}` | `{ok: true}` | 作業ディレクトリ設定 |

### 2-c. エラーコード

```typescript
{
  "ok": false,
  "error": {
    "code": "PYTHON_NOT_FOUND",      // 機械可読コード
    "message": "Python not found",    // 人間可読メッセージ
    "detail": "...",                  // 追加情報 (スタックトレース等)
  }
}
```

| code | 意味 |
|------|------|
| `PYTHON_NOT_FOUND` | Python 実行ファイルが見つからない |
| `UAG_NOT_INSTALLED` | uag パッケージがインストールされていない |
| `WS_SERVER_FAILED` | WebSocket サーバの起動に失敗 |
| `WS_TIMEOUT` | 接続タイムアウト (10秒) |
| `TOOL_NOT_FOUND` | ツール名が存在しない |
| `TOOL_EXEC_FAILED` | ツール実行エラー |
| `INVALID_PARAMS` | パラメータ不正 |
| `SESSION_NOT_FOUND` | セッションが見つからない |
| `FILE_NOT_FOUND` | ファイルが存在しない |
| `FILE_READ_ERROR` | ファイル読み込みエラー |
| `WORKDIR_INVALID` | 作業ディレクトリが不正 |
| `INTERNAL_ERROR` | その他内部エラー |

## 3. Python バックエンド実装

### 3-a. 新規ファイル構成

```
src/uagent/
├── ws_server.py              # WebSocket サーバエントリポイント
├── ws_handler.py             # メッセージディスパッチ
├── ws_session.py             # セッション管理
└── ws_config.py              # 設定管理 (環境変数 + VSCode設定の統合)
```

### 3-b. ws_server.py (概略)

```python
"""WebSocket server for VSCode extension integration."""
import asyncio, json, os, sys
from uagent.ws_handler import handle_message

async def handler(websocket):
    """接続ごとのハンドラ"""
    async for raw in websocket:
        msg = json.loads(raw)
        response = await handle_message(msg)
        await websocket.send(json.dumps(response))

async def main():
    port = int(os.environ.get("UAG_WS_PORT", "18765"))
    async with websockets.serve(handler, "127.0.0.1", port):
        await asyncio.Future()  # 永続待機

if __name__ == "__main__":
    asyncio.run(main())
```

### 3-c. セッション管理

既存の `uagent/core.py` のセッション機構を WebSocket 向けにラップ:

```python
class WSSessionManager:
    """WebSocket 用セッション管理。通常の uag セッションと互換性あり。"""
    
    def __init__(self):
        self.sessions: dict[str, Session] = {}
        self.current: str | None = None
    
    def create(self) -> str:
        # uagent.core.create_session() を呼ぶ
        ...
    
    def load(self, index: int) -> str:
        # uagent.core.load_session(index) を呼ぶ
        ...
```

セッションの保存先は `get_state_dir()` で既存の uag と共有。これにより CLI で使っていたセッションを VSCode 拡張でも読み込める。

### 3-d. 設定の優先順位

```
1. VSCode 設定 (uag.provider など)    ← 最優先 (拡張から送信)
2. 環境変数 (UAGENT_PROVIDER など)    ← フォールバック
3. .env ファイル                       ← フォールバック
```

VSCode 拡張から `config/set` で送られた値は、そのセッション内でのみ有効（環境変数は書き換えない）。

## 4. VSCode 拡張 (TypeScript) 詳細

### 4-a. ファイル構成

```
vscode-extension/
├── package.json
├── tsconfig.json
├── .vscode/
│   ├── launch.json         # F5 デバッグ設定
│   └── tasks.json          # ビルドタスク
├── src/
│   ├── extension.ts        # activate / deactivate
│   ├── wsClient.ts         # WebSocket 接続管理 + 全メソッドのラッパー
│   ├── panel.ts            # WebviewPanel (チャットUI)
│   ├── treeProvider.ts     # TreeDataProvider (ツール一覧)
│   ├── statusBar.ts        # ステータスバー表示
│   ├── config.ts           # VS Code 設定 ↔ Python 設定の橋渡し
│   ├── editorIntegration.ts # エディタ連携 (選択/診断/クイックフィックス)
│   └── utils.ts            # ユーティリティ
├── media/
│   ├── chat.html           # Webview HTML (インライン)
│   ├── chat.js             # Webview フロントエンド
│   └── chat.css            # Webview スタイル
└── test/
    └── suite/
        ├── extension.test.ts
        └── wsClient.test.ts
```

### 4-b. extension.ts

```typescript
import * as vscode from 'vscode';
import { WsClient } from './wsClient';
import { ChatPanel } from './panel';
import { ToolTreeProvider } from './treeProvider';
import { StatusBarManager } from './statusBar';
import { ConfigBridge } from './config';
import { EditorIntegration } from './editorIntegration';

let wsClient: WsClient;

export async function activate(context: vscode.ExtensionContext) {
    // 1. Python/uag の存在確認
    const pythonPath = vscode.workspace.getConfiguration('uag').get('pythonPath', 'python');
    const installed = await checkUagInstalled(pythonPath);
    if (!installed) {
        vscode.window.showErrorMessage(
            'uag: Python package not found. Run: pip install uag',
            'Install Guide'
        ).then(selection => {
            if (selection === 'Install Guide') {
                vscode.env.openExternal(vscode.Uri.parse('https://pypi.org/project/uag/'));
            }
        });
        return; // activate 失敗
    }

    // 2. WebSocket サーバ起動 (子プロセス)
    wsClient = new WsClient();
    const serverProcess = startWsServer(pythonPath);
    
    // 3. 接続待機 (最大10秒)
    await wsClient.connect('ws://127.0.0.1:18765', 10000);
    
    // 4. workdir 設定 (VS Code の開いてるフォルダ)
    const folders = vscode.workspace.workspaceFolders;
    if (folders) {
        await wsClient.call('workdir/set', { path: folders[0].uri.fsPath });
    }

    // 5. UI コンポーネント登録
    context.subscriptions.push(
        vscode.commands.registerCommand('uag.chat', () => ChatPanel.createOrShow(context, wsClient)),
        vscode.window.registerTreeDataProvider('uag.tools', new ToolTreeProvider(wsClient)),
        new StatusBarManager(wsClient),
        new EditorIntegration(wsClient),
        new ConfigBridge(wsClient)
    );
}

export function deactivate() {
    wsClient?.close();
    // 子プロセスは自動終了 (VSCode 終了時に強制kill)
}
```

### 4-c. WebSocket Client (wsClient.ts) — 詳細

```typescript
import * as vscode from 'vscode';

type MessageCallback = (data: any) => void;

export class WsClient {
    private ws: WebSocket | null = null;
    private pending = new Map<string, { resolve, reject, timer }>();
    private listeners = new Map<string, MessageCallback[]>();
    private seq = 0;
    private reconnectTimer: NodeJS.Timer | null = null;

    async connect(url: string, timeoutMs = 10000): Promise<void> {
        return new Promise((resolve, reject) => {
            this.ws = new WebSocket(url);
            this.ws.onopen = () => {
                this.startHeartbeat();
                resolve();
            };
            this.ws.onmessage = (event) => this.onMessage(event);
            this.ws.onclose = () => this.onDisconnect();
            this.ws.onerror = () => reject(new Error('WebSocket connection failed'));
            setTimeout(() => reject(new Error('Connection timeout')), timeoutMs);
        });
    }

    // 全メソッドの呼び出し口
    async call(method: string, params: any = {}): Promise<any> {
        const id = `req_${++this.seq}`;
        return new Promise((resolve, reject) => {
            const timer = setTimeout(() => {
                this.pending.delete(id);
                reject(new Error(`Timeout: ${method}`));
            }, 30000);  // 30秒タイムアウト
            this.pending.set(id, { resolve, reject, timer });
            this.ws!.send(JSON.stringify({ id, method, params }));
        });
    }

    // ラップ済みAPI
    chat(message: string, options?: { stream?, history?, context? }) { ... }
    listTools(): Promise<ToolSpec[]> { ... }
    executeTool(name: string, args: any): Promise<any> { ... }
    readFile(path: string): Promise<string> { ... }

    private startHeartbeat() {
        setInterval(() => this.call('ping').catch(() => {}), 30000);
    }

    private onDisconnect() {
        // 自動リコネクト (3秒後)
        this.reconnectTimer = setTimeout(() => {
            this.connect('ws://127.0.0.1:18765');
        }, 3000);
        vscode.window.showWarningMessage('uag: Connection lost. Reconnecting...');
    }
}
```

### 4-d. Webview Panel (panel.ts) — チャットUI

```typescript
export class ChatPanel {
    public static currentPanel: ChatPanel | undefined;
    private panel: vscode.WebviewPanel;

    static createOrShow(context: vscode.ExtensionContext, ws: WsClient) {
        const panel = vscode.window.createWebviewPanel(
            'uag.chat',
            'uag Chat',
            { viewColumn: vscode.ViewColumn.Beside, preserveFocus: true },
            {
                enableScripts: true,
                retainContextWhenHidden: true,  // タブ切り替えで状態維持
                localResourceRoots: [
                    vscode.Uri.joinPath(context.extensionUri, 'media')
                ]
            }
        );
        
        // HTML をインラインで埋め込み vs ファイル参照
        panel.webview.html = getChatHtml(panel.webview, context);
        
        // Webview ←→ Extension 間通信
        panel.webview.onDidReceiveMessage(async (msg) => {
            switch (msg.type) {
                case 'chat':
                    // ユーザー入力を LLM に送信
                    await handleChatMessage(panel, ws, msg.text);
                    break;
                case 'openFile':
                    // ファイル参照クリック → VSCode で開く
                    vscode.commands.executeCommand(
                        'vscode.open',
                        vscode.Uri.file(msg.path)
                    );
                    break;
                case 'applyDiff':
                    // LLM のコード提案をエディタに適用
                    applyDiffToEditor(msg.diff);
                    break;
            }
        });
    }
}

// Webview → Extension メッセージプロトコル
interface WebviewMessage {
    type: 'chat' | 'openFile' | 'applyDiff' | 'cancel' | 'resize';
    text?: string;
    path?: string;
    diff?: string;
}

// Extension → Webview メッセージプロトコル
interface ExtensionMessage {
    type: 'chunk' | 'tool_call' | 'tool_result' | 'done' | 'error' | 'history';
    data?: any;
    tool?: string;
    args?: any;
    result?: any;
}
```

### 4-e. TreeView (treeProvider.ts) — ツール一覧

```typescript
class ToolTreeProvider implements vscode.TreeDataProvider<ToolItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<ToolItem | undefined>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    async getChildren(element?: ToolItem): Promise<ToolItem[]> {
        if (!element) {
            // ルート: genre 一覧
            return [
                new ToolItem('File', 'file', vscode.TreeItemCollapsibleState.Collapsed),
                new ToolItem('Communication', 'comm', vscode.TreeItemCollapsibleState.Collapsed),
                new ToolItem('IoT', 'iot', vscode.TreeItemCollapsibleState.Collapsed),
                new ToolItem('Development', 'devel', vscode.TreeItemCollapsibleState.Collapsed),
            ];
        }
        // 子ノード: ツール一覧 (ws.listTools() で取得)
        const tools = await this.ws.listTools();
        return tools
            .filter(t => t.genre === element.genre)
            .map(t => new ToolItem(t.name, t.genre, vscode.TreeItemCollapsibleState.None, t));
    }
}
```

### 4-f. エディタ連携 (editorIntegration.ts)

```typescript
export class EditorIntegration {
    constructor(private ws: WsClient) {
        // 選択範囲を uag に送信
        vscode.commands.registerCommand('uag.explain', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            const selection = editor.document.getText(editor.selection);
            const filePath = editor.document.uri.fsPath;
            
            // チャットパネルに送信 (コンテキスト付き)
            const panel = ChatPanel.currentPanel;
            if (panel) {
                panel.sendMessage({
                    type: 'context',
                    code: selection,
                    file: filePath,
                    language: editor.document.languageId
                });
            }
        });

        // 診断情報 (エラー) を検出 → uag に送信
        vscode.languages.onDidChangeDiagnostics((e) => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            const diagnostics = vscode.languages.getDiagnostics(editor.document.uri);
            const errors = diagnostics.filter(d => d.severity === vscode.DiagnosticSeverity.Error);
            if (errors.length > 0) {
                // 自動提案 (設定で無効化可)
                if (vscode.workspace.getConfiguration('uag').get('autoFix', false)) {
                    this.suggestFix(editor, errors);
                }
            }
        });
    }

    // クイックフィックスとしてコード変更を提案
    async suggestFix(editor: vscode.TextEditor, errors: vscode.Diagnostic[]) {
        const code = editor.document.getText();
        const result = await this.ws.call('chat', {
            message: `Fix these errors:
${errors.map(e => e.message).join('
')}`,
            context: { code, file: editor.document.uri.fsPath }
        });
        
        // コードブロックを検出 → diff 表示 → ユーザー承認で適用
        const fix = extractCodeBlock(result.reply);
        if (fix) {
            const action = await vscode.window.showInformationMessage(
                'uag: Suggested fix available',
                'Show Diff', 'Apply'
            );
            if (action === 'Apply') {
                const edit = new vscode.WorkspaceEdit();
                // 全文置換 or 部分置換 (diffベース)
                const fullRange = new vscode.Range(
                    editor.document.positionAt(0),
                    editor.document.positionAt(editor.document.getText().length)
                );
                edit.replace(editor.document.uri, fullRange, fix);
                await vscode.workspace.applyEdit(edit);
            }
        }
    }
}
```

## 5. フロントエンド (Webview) 仕様

### 5-a. チャットHTML構成

```
┌─────────────────────────────────┐
│  uag Chat               [−][□][×]│  ← タイトルバー
├─────────────────────────────────┤
│  ┌───────────────────────────┐  │
│  │ ユーザーメッセージ         │  │  ← Markdown レンダリング
│  ├───────────────────────────┤  │
│  │ LLM 応答 (ストリーミング)  │  │  ← コードブロックはシンタハイ
│  │ ```python                 │  │
│  │ def hello():              │  │
│  │     print("world")        │  │
│  │ ```                       │  │
│  ├───────────────────────────┤  │
│  │ 🔍 search_web("...")      │  │  ← ツール呼び出しインジケータ
│  │ ⏳ 処理中...              │  │
│  └───────────────────────────┘  │
├─────────────────────────────────┤
│  [📎 ファイル参照] [📋 コード]  │  ← クイックアクション
├─────────────────────────────────┤
│  ┌───────────────────────────┐  │
│  │ メッセージ入力...    [送信]│  │  ← 入力欄 + Ctrl+Enter 送信
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

### 5-b. Webview 内の状態管理

```javascript
// chat.js (Webview 内)
const vscode = acquireVsCodeApi();
let state = {
    messages: [],       // メッセージ履歴 [{role, content, tools}]
    streaming: false,   // ストリーミング中フラグ
    abortController: null,
    theme: 'dark',      // VS Code テーマ連動
};

// VS Code のテーマ変更を検出
function updateTheme() {
    const body = document.body;
    body.classList.remove('vscode-dark', 'vscode-light', 'vscode-high-contrast');
    body.classList.add(document.body.className);
}

// メッセージ受信
window.addEventListener('message', event => {
    const msg = event.data;
    switch (msg.type) {
        case 'chunk':
            appendToLastMessage(msg.data);
            break;
        case 'tool_call':
            showToolIndicator(msg.tool, msg.args);
            break;
        case 'tool_result':
            updateToolResult(msg.tool, msg.result);
            break;
        case 'done':
            finalizeMessage(msg.result);
            break;
        case 'history':
            state.messages = msg.data;
            renderMessages();
            break;
    }
});
```

### 5-c. シンタックスハイライト

Webview 内のコードブロックは **highlight.js**（CDN 読み込み）でシンタックスハイライト。VS Code のテーマカラーに合わせる:

```html
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
```

### 5-d. ファイル参照のハイパーリンク

LLM が `path/to/file.py:42` のようにファイル参照を出力した場合、Webview 内でクリッカブルなリンクにする:

```javascript
function renderMessage(text) {
    // ファイルパスパターン: path/to/file.ext:line を検出
    return text.replace(
        /(\S+?\.[a-zA-Z]+):(\d+)/g,
        (match, file, line) => 
            `<a href="#" onclick="openFile('${file}', ${line})">${match}</a>`
    );
}

function openFile(path, line) {
    vscode.postMessage({ type: 'openFile', path, line });
}
```

## 6. プロジェクト構成 (最終形)

```
agentcli/
├── .vscode/
│   ├── launch.json              # 拡張デバッグ設定
│   └── tasks.json               # ビルドタスク
├── vscode-extension/            # 拡張機能本体
│   ├── package.json
│   ├── tsconfig.json
│   ├── src/
│   │   ├── extension.ts
│   │   ├── wsClient.ts
│   │   ├── panel.ts
│   │   ├── treeProvider.ts
│   │   ├── statusBar.ts
│   │   ├── config.ts
│   │   ├── editorIntegration.ts
│   │   └── utils.ts
│   ├── media/
│   │   ├── chat.html
│   │   ├── chat.js
│   │   └── chat.css
│   └── test/
├── src/
│   ├── uagent/
│   │   ├── ...
│   │   ├── ws_server.py         # ← NEW: WebSocket サーバ
│   │   ├── ws_handler.py        # ← NEW: メッセージハンドラ
│   │   ├── ws_session.py        # ← NEW: セッション管理
│   │   └── ws_config.py         # ← NEW: 設定管理
│   └── ...
└── VSCODE_EXTENSION_PLAN.md     # 本ドキュメント
```

## 7. 実装ステップ (詳細版)

### Phase 0: Python WebSocket サーバ (2-3日)

| # | タスク | ファイル | 備考 |
|---|--------|---------|------|
| 0.1 | `ws_server.py` 雛形 | `src/uagent/ws_server.py` | `asyncio` + `websockets` で127.0.0.1:18765 にサーバ |
| 0.2 | メッセージディスパッチャ | `src/uagent/ws_handler.py` | method → ハンドラ関数のマッピング |
| 0.3 | chat ハンドラ (ストリーミング) | `ws_handler.py` | `uagent/core.py` のチャットループを WebSocket 対応 |
| 0.4 | ツール一覧/実行ハンドラ | `ws_handler.py` | `get_tool_catalog()` + `run_tool()` をラップ |
| 0.5 | セッション管理 | `src/uagent/ws_session.py` | 既存セッション機構との互換 |
| 0.6 | 設定管理 | `src/uagent/ws_config.py` | 環境変数 + VSCode設定の統合 |
| 0.7 | ファイルI/O | `ws_handler.py` | `safe_file_ops.py` の読み取り専用ラッパー |
| 0.8 | テスト | `test_ws_server.py` | 各メソッドの単体テスト |

### Phase 1: VSCode 拡張 雛形 + Webview チャット (3-5日)

| # | タスク | ファイル | 備考 |
|---|--------|---------|------|
| 1.1 | `package.json` 作成 | `vscode-extension/package.json` | activationEvents, commands, views, config |
| 1.2 | `extension.ts` activate/deactivate | `src/extension.ts` | Python 確認 → サーバ起動 → 接続 |
| 1.3 | `wsClient.ts` WebSocket 通信 | `src/wsClient.ts` | コネクション管理 + call() ラッパー |
| 1.4 | `panel.ts` WebviewPanel | `src/panel.ts` | Webview 作成 + メッセージ仲介 |
| 1.5 | `chat.html` / `chat.js` / `chat.css` | `media/` | Markdown 表示、コードハイライト、ストリーミング |
| 1.6 | `statusBar.ts` | `src/statusBar.ts` | 接続状態表示 |

### Phase 2: エディタ連携 (1-2日)

| # | タスク | ファイル | 備考 |
|---|--------|---------|------|
| 2.1 | 選択範囲送信 | `src/editorIntegration.ts` | 「uag: Explain/Refactor」コマンド |
| 2.2 | ファイル参照クリック → エディタで開く | `media/chat.js` | `vscode.open` の呼び出し |
| 2.3 | diff 適用 | `media/chat.js` + `panel.ts` | LLM提案 → WorkspaceEdit |

### Phase 3: TreeView + 診断 (2-3日)

| # | タスク | ファイル | 備考 |
|---|--------|---------|------|
| 3.1 | `treeProvider.ts` ツリー表示 | `src/treeProvider.ts` | genre 別ツール一覧 |
| 3.2 | クイックフィックス | `src/editorIntegration.ts` | エラー検出 → LLM提案 → 自動修正 |
| 3.3 | 診断情報プロバイダ | `src/editorIntegration.ts` | DiagnosticCollection 連携 |

### Phase 4: 配布・運用 (1日)

| # | タスク | 備考 |
|---|--------|------|
| 4.1 | `vsce package` で VSIX 作成 | CI に組み込む |
| 4.2 | Marketplace 公開 | Azure DevOps PAT 取得 |
| 4.3 | Open VSX 公開 | VSCodium 対応 |
| 4.4 | GitHub Releases に VSIX 同梱 | タグリリース時自動ビルド |

## 8. package.json 完全版

```json
{
  "name": "uag-vscode",
  "displayName": "uag - Universal AI Gateway",
  "description": "AI-powered file operations, web search, image generation, IoT control, and more - 116+ tools.",
  "version": "0.5.20",
  "publisher": "awaku7",
  "icon": "icon.png",
  "engines": { "vscode": "^1.85.0" },
  "categories": ["Chat", "Programming Languages", "Machine Learning", "Other"],
  "activationEvents": [
    "onCommand:uag.chat",
    "onView:uag.tools",
    "onLanguage:python",
    "onLanguage:typescript",
    "onLanguage:javascript"
  ],
  "main": "./out/extension.js",
  "contributes": {
    "commands": [
      { "command": "uag.chat", "title": "uag: Open Chat" },
      { "command": "uag.explain", "title": "uag: Explain Selection" },
      { "command": "uag.refactor", "title": "uag: Refactor Selection" },
      { "command": "uag.fix", "title": "uag: Fix Error at Cursor" },
      { "command": "uag.tools", "title": "uag: Show Tools" },
      { "command": "uag.newSession", "title": "uag: New Session" }
    ],
    "menus": {
      "editor/context": [
        { "command": "uag.explain", "group": "uag@1", "when": "editorHasSelection" },
        { "command": "uag.refactor", "group": "uag@2", "when": "editorHasSelection" },
        { "command": "uag.fix", "group": "uag@3", "when": "editorHasDiagnostics" }
      ],
      "editor/title/context": [
        { "command": "uag.explain", "group": "uag" }
      ]
    },
    "viewsContainers": {
      "activitybar": [
        { "id": "uag", "title": "uag", "icon": "icon.svg" }
      ]
    },
    "views": {
      "uag": [
        { "id": "uag.tools", "name": "Tools" },
        { "id": "uag.sessions", "name": "Sessions" }
      ]
    },
    "configuration": {
      "title": "uag",
      "properties": {
        "uag.pythonPath": {
          "type": "string",
          "default": "python",
          "description": "Path to Python executable"
        },
        "uag.port": {
          "type": "number",
          "default": 18765,
          "description": "WebSocket server port"
        },
        "uag.autoFix": {
          "type": "boolean",
          "default": false,
          "description": "Automatically suggest fixes for errors"
        },
        "uag.provider": {
          "type": "string",
          "default": "",
          "description": "LLM provider (overrides UAGENT_PROVIDER)"
        },
        "uag.model": {
          "type": "string",
          "default": "",
          "description": "Model deployment name (overrides UAGENT_DEPNAME)"
        }
      }
    }
  },
  "scripts": {
    "compile": "tsc -p ./",
    "watch": "tsc -watch -p ./",
    "package": "vsce package",
    "publish": "vsce publish"
  },
  "devDependencies": {
    "@types/vscode": "^1.85.0",
    "typescript": "^5.3.0",
    "@vscode/vsce": "^2.22.0"
  }
}
```

## 9. 詳細実装補足

### 9-a. Python WebSocket Server 完全実装

#### ws_server.py

```python
"""WebSocket server for VSCode extension integration.
Entry point: python -m uagent.ws_server --port 18765
"""
import asyncio
import argparse
import json
import logging
import os
import signal
import sys
from pathlib import Path

# uag の既存モジュールをインポート
from uagent.ws_handler import WsHandler
from uagent.ws_session import WsSessionManager
from uagent.ws_config import WsConfigManager

logger = logging.getLogger("uag.ws_server")

class UagWebSocketServer:
    """WebSocket サーバ。127.0.0.1 のみ Listen する。"""

    def __init__(self, port: int = 18765):
        self.port = port
        self.handler = WsHandler()
        self.session_mgr = WsSessionManager()
        self.config_mgr = WsConfigManager()
        self._server = None
        self._tasks: set[asyncio.Task] = set()

    async def start(self):
        import websockets
        self._server = await websockets.serve(
            self.on_connect,
            host="127.0.0.1",
            port=self.port,
            ping_interval=20,       # 20秒ごとに ping
            ping_timeout=10,        # ping 応答10秒で切断
            max_size=10 * 1024 * 1024,  # 最大メッセージサイズ 10MB
            compression=None,       # 圧縮オフ (低レイテンシ優先)
        )
        logger.info(f"WebSocket server started on 127.0.0.1:{self.port}")
        await asyncio.Future()  # 永続待機

    async def on_connect(self, websocket):
        """クライアント接続ごとに呼ばれる"""
        remote = websocket.remote_address
        logger.info(f"Client connected: {remote}")
        try:
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                    response = await self.dispatch(msg)
                    await websocket.send(json.dumps(response))
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "id": None, "ok": False,
                        "error": {"code": "INVALID_JSON", "message": "Invalid JSON"}
                    }))
                except Exception as e:
                    logger.exception("Handler error")
                    await websocket.send(json.dumps({
                        "id": msg.get("id") if isinstance(msg, dict) else None,
                        "ok": False,
                        "error": {"code": "INTERNAL_ERROR", "message": str(e)}
                    }))
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            logger.info(f"Client disconnected: {remote}")

    async def dispatch(self, msg: dict) -> dict:
        """メッセージを対応するハンドラに振り分ける"""
        method = msg.get("method", "")
        params = msg.get("params", {})
        req_id = msg.get("id")

        handlers = {
            "ping":         self.handle_ping,
            "chat":         self.handle_chat,
            "tools/list":   self.handle_tools_list,
            "tools/get":    self.handle_tools_get,
            "tool/execute": self.handle_tool_execute,
            "config/get":   self.handle_config_get,
            "config/set":   self.handle_config_set,
            "session/list": self.handle_session_list,
            "session/load": self.handle_session_load,
            "session/new":  self.handle_session_new,
            "files/read":   self.handle_files_read,
            "files/write":  self.handle_files_write,
            "workdir/get":  self.handle_workdir_get,
            "workdir/set":  self.handle_workdir_set,
        }
        handler = handlers.get(method)
        if not handler:
            return {
                "id": req_id, "ok": False,
                "error": {"code": "METHOD_NOT_FOUND", "message": f"Unknown method: {method}"}
            }
        try:
            result = await handler(params)
            return {"id": req_id, "ok": True, "result": result}
        except Exception as e:
            return {
                "id": req_id, "ok": False,
                "error": {"code": type(e).__name__.upper(), "message": str(e)}
            }

    async def handle_ping(self, params):
        return {"pong": True, "timestamp": asyncio.get_event_loop().time()}

    async def handle_chat(self, params):
        """LLM チャット。stream=True の場合はストリーミング。
        本実装では通常の応答を返す。
        実際のストリーミングは別途、チャンク分割が必要。
        """
        from uagent.core import process_message
        message = params.get("message", "")
        stream = params.get("stream", False)
        context = params.get("context")
        # process_message は既存の uag チャットループ
        reply = await process_message(message, context=context)
        return {"reply": reply}

    async def handle_tools_list(self, params):
        from uagent.tools import get_tool_catalog
        catalog = get_tool_catalog()
        # 必要なフィールドだけ抽出
        tools = []
        for t in catalog.get("tools", []):
            fn = t.get("function", {})
            tools.append({
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "genre": t.get("tool_genre", "unknown"),
                "parallel_safe": t.get("x_parallel_safe", False),
                "parameters": fn.get("parameters", {}),
            })
        return {"tools": tools}

    async def handle_tools_get(self, params):
        name = params.get("name", "")
        catalog = await self.handle_tools_list({})
        for t in catalog["tools"]:
            if t["name"] == name:
                return {"spec": t}
        raise ValueError(f"Tool '{name}' not found")

    async def handle_tool_execute(self, params):
        from uagent.tools import run_tool
        name = params.get("name", "")
        args = params.get("args", {})
        result = run_tool(name, args)
        return {"result": json.loads(result)}

    async def handle_config_get(self, params):
        key = params.get("key")
        if key:
            return {"config": {key: self.config_mgr.get(key)}}
        return {"config": self.config_mgr.get_all()}

    async def handle_config_set(self, params):
        key = params.get("key")
        value = params.get("value")
        self.config_mgr.set(key, value)
        return {"ok": True}

    async def handle_session_list(self, params):
        sessions = self.session_mgr.list_sessions()
        return {"sessions": sessions}

    async def handle_session_load(self, params):
        index = params.get("index", 0)
        session = self.session_mgr.load(index)
        return {"session": session}

    async def handle_session_new(self, params):
        session_id = self.session_mgr.create()
        return {"id": session_id}

    async def handle_files_read(self, params):
        from uagent.tools.safe_file_ops_extras import ensure_within_workdir
        path = params.get("path", "")
        safe_path = ensure_within_workdir(path)
        if not os.path.isfile(safe_path):
            raise FileNotFoundError(f"File not found: {safe_path}")
        with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        ext = Path(safe_path).suffix.lower()
        lang_map = {
            ".py": "python", ".ts": "typescript", ".js": "javascript",
            ".html": "html", ".css": "css", ".json": "json",
            ".md": "markdown", ".yml": "yaml", ".yaml": "yaml",
            ".rs": "rust", ".go": "go", ".java": "java",
            ".cs": "csharp", ".cpp": "cpp", ".c": "c",
        }
        language = lang_map.get(ext, "text")
        return {"content": content, "language": language, "size": len(content)}

    async def handle_files_write(self, params):
        from uagent.tools.safe_file_ops_extras import ensure_within_workdir
        path = params.get("path", "")
        content = params.get("content", "")
        safe_path = ensure_within_workdir(path)
        os.makedirs(os.path.dirname(safe_path) or ".", exist_ok=True)
        with open(safe_path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        return {"ok": True, "path": safe_path, "size": len(content)}

    async def handle_workdir_get(self, params):
        from uagent.tools.context import get_callbacks
        cb = get_callbacks()
        return {"path": str(cb.get_workdir())}

    async def handle_workdir_set(self, params):
        from uagent.tools.safe_file_ops_extras import ensure_within_workdir
        path = params.get("path", "")
        safe_path = ensure_within_workdir(path)
        from uagent.tools.context import get_callbacks
        cb = get_callbacks()
        cb.set_workdir(safe_path)
        logger.info(f"Workdir set to: {safe_path}")
        return {"ok": True, "path": safe_path}


def main():
    parser = argparse.ArgumentParser(description="uag WebSocket Server")
    parser.add_argument("--port", type=int, default=18765, help="WebSocket port")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    server = UagWebSocketServer(port=args.port)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except OSError as e:
        logger.error(f"Failed to start server on port {args.port}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

#### ws_session.py

```python
"""セッション管理。既存の uag セッションと互換性あり。"""
import os
import json
from pathlib import Path
from uagent.utils.paths import get_state_dir

class WsSessionManager:
    """WebSocket 用のセッション管理ラッパー。"""

    def __init__(self):
        self.sessions_dir = get_state_dir() / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def create(self) -> str:
        """新規セッション作成。状態IDを返す。"""
        import uuid
        session_id = str(uuid.uuid4())[:8]
        session_path = self.sessions_dir / f"{session_id}.json"
        session_data = {
            "id": session_id,
            "created": str(__import__("datetime").datetime.now()),
            "messages": [],
            "context": {},
        }
        with open(session_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False)
        return session_id

    def list_sessions(self) -> list[dict]:
        """セッション一覧。新しい順。"""
        sessions = []
        for f in sorted(self.sessions_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                sessions.append({
                    "id": data["id"],
                    "created": data["created"],
                    "message_count": len(data.get("messages", [])),
                    "preview": (data.get("messages", []) or [{}])[-1].get("content", "")[:80],
                })
            except (json.JSONDecodeError, KeyError):
                continue
        return sessions

    def load(self, index: int = 0) -> dict | None:
        """セッション読み込み。index は list_sessions のインデックス。"""
        sessions = self.list_sessions()
        if 0 <= index < len(sessions):
            path = self.sessions_dir / f"{sessions[index]['id']}.json"
            return json.loads(path.read_text(encoding="utf-8"))
        return None
```

### 9-b. ストリーミングチャットの実装

LLM からのストリーミング応答を WebSocket で転送する方式。

```python
# ws_handler.py 内のストリーミング処理
async def handle_chat_stream(self, websocket, params: dict, req_id: str):
    """ストリーミングチャット。逐次 websocket.send() でチャンクを送信。"""
    message = params.get("message", "")
    context = params.get("context")

    # uag のチャットループを非同期で実行
    from uagent.core import stream_process_message

    async for chunk in stream_process_message(message, context=context):
        if chunk["type"] == "text":
            # テキストチャンク
            await websocket.send(json.dumps({
                "id": req_id, "type": "chunk", "data": chunk["data"]
            }))
        elif chunk["type"] == "tool_call":
            # ツール呼び出し通知
            await websocket.send(json.dumps({
                "id": req_id, "type": "tool_call",
                "tool": chunk["tool"], "args": chunk["args"]
            }))
        elif chunk["type"] == "tool_result":
            # ツール実行結果
            await websocket.send(json.dumps({
                "id": req_id, "type": "tool_result",
                "tool": chunk["tool"], "result": chunk["result"]
            }))

    # 完了通知
    await websocket.send(json.dumps({
        "id": req_id, "type": "done"
    }))
```

**重要:** ストリーミングモードでは `dispatch()` の通常の request/response フローを使わず、`handle_chat` 内で直接 websocket.send() を呼ぶ。TypeScript 側では `pending` map の Promise を使わず、`listeners` 経由でイベント駆動で処理する。

### 9-c. セキュリティ

| 項目 | 対策 |
|------|------|
| ポート露出 | `127.0.0.1` のみ Listen。外部からの接続不可 |
| WebSocket 認証 | 不要（ローカル専用）。必要な場合はトークンハンドシェイク方式を追加可能 |
| ファイルアクセス制限 | `ensure_within_workdir()` により作業ディレクトリ外への読み書き禁止 |
| XSS (Webview) | `Content-Security-Policy` ヘッダで CDN のみ許可。`innerHTML` は sanitize |
| トークン漏洩 | 環境変数は VSCode の `SecretStorage` には保存せず、`.env` / `.env.sec` に保持 |
| Python 子プロセス | `subprocess.Popen` で起動。`CREATE_NO_WINDOW` フラグでコンソール非表示 |

```typescript
// Webview の Content-Security-Policy
const csp = [
    "default-src 'self';",
    "script-src 'self' https://cdnjs.cloudflare.com;",
    "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com;",
    "img-src 'self' data:;",
    "connect-src 'self' ws://127.0.0.1:*;",
].join(' ');
panel.webview.html = `<html><head><meta http-equiv="Content-Security-Policy" content="${csp}">...`;
```

### 9-d. Webview テーマ連動 (CSS変数)

VS Code のテーマ変更を検出し、Webview の見た目を自動追従:

```typescript
// extension.ts
context.subscriptions.push(
    vscode.window.onDidChangeActiveColorTheme((theme) => {
        ChatPanel.currentPanel?.postMessage({
            type: 'themeChanged',
            theme: theme.kind === vscode.ColorThemeKind.Dark ? 'dark' 
                 : theme.kind === vscode.ColorThemeKind.HighContrast ? 'high-contrast'
                 : 'light'
        });
    })
);
```

```css
/* chat.css — VS Code のCSS変数でテーマ対応 */
:root {
    --bg-primary: var(--vscode-editor-background, #1e1e1e);
    --bg-secondary: var(--vscode-sideBar-background, #252526);
    --text-primary: var(--vscode-editor-foreground, #d4d4d4);
    --text-secondary: var(--vscode-descriptionForeground, #9d9d9d);
    --border-color: var(--vscode-panel-border, #3c3c3c);
    --accent-color: var(--vscode-textLink-foreground, #3794ff);
    --code-bg: var(--vscode-textCodeBlock-background, #2d2d2d);
    --danger-color: var(--vscode-errorForeground, #f48771);
    --success-color: #4ec9b0;
    --font-mono: var(--vscode-editor-font-family, 'Consolas', 'Courier New', monospace);
    --font-size: var(--vscode-editor-font-size, 14px);
}

body {
    background-color: var(--bg-primary);
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: var(--font-size);
    margin: 0;
    padding: 8px;
}

.message-user {
    background-color: var(--bg-secondary);
    border-left: 3px solid var(--accent-color);
    padding: 8px 12px;
    margin: 8px 0;
    border-radius: 0 4px 4px 0;
}

.message-assistant {
    padding: 8px 12px;
    margin: 8px 0;
}

pre code {
    background-color: var(--code-bg);
    border-radius: 4px;
    padding: 12px;
    display: block;
    overflow-x: auto;
}

.tool-indicator {
    color: var(--text-secondary);
    font-size: 0.9em;
    padding: 4px 8px;
}

.error-text {
    color: var(--danger-color);
}
```

### 9-e. エラーリカバリ完全実装

```typescript
// wsClient.ts — 完全版
export class WsClient extends EventEmitter {
    private ws: WebSocket | null = null;
    private pendingCalls = new Map<string, { resolve, reject, timer }>();
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 10;
    private reconnectDelay = 1000;  // 初回1秒
    private heartbeatInterval: NodeJS.Timeout | null = null;
    private isConnected = false;

    async connect(url: string, timeoutMs = 10000): Promise<void> {
        return new Promise((resolve, reject) => {
            try {
                this.ws = new WebSocket(url);
            } catch (e) {
                reject(e);
                return;
            }
            const timer = setTimeout(() => {
                this.ws?.close();
                reject(new Error('Connection timeout'));
            }, timeoutMs);

            this.ws.onopen = () => {
                clearTimeout(timer);
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.startHeartbeat();
                this.emit('connected');
                resolve();
            };

            this.ws.onclose = (event) => {
                this.isConnected = false;
                this.stopHeartbeat();
                this.rejectAllPending('Connection closed');
                this.emit('disconnected', event.code, event.reason);
                this.scheduleReconnect(url);
            };

            this.ws.onerror = () => {
                clearTimeout(timer);
                // onclose も続けて呼ばれるので、ここでは何もしない
            };

            this.ws.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    this.handleMessage(msg);
                } catch (e) {
                    console.error('Failed to parse message:', e);
                }
            };
        });
    }

    private handleMessage(msg: any) {
        if (msg.id && this.pendingCalls.has(msg.id)) {
            const pending = this.pendingCalls.get(msg.id)!;
            clearTimeout(pending.timer);
            this.pendingCalls.delete(msg.id);
            if (msg.ok) {
                pending.resolve(msg.result);
            } else {
                pending.reject(new Error(msg.error?.message || msg.error));
            }
        } else if (msg.type) {
            // ストリーミングチャンク or 通知
            this.emit(msg.type, msg);
        }
    }

    async call(method: string, params: any = {}, timeoutMs = 30000): Promise<any> {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            throw new Error('Not connected');
        }
        const id = `req_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
        return new Promise((resolve, reject) => {
            const timer = setTimeout(() => {
                this.pendingCalls.delete(id);
                reject(new Error(`Timeout: ${method} (${timeoutMs}ms)`));
            }, timeoutMs);
            this.pendingCalls.set(id, { resolve, reject, timer });
            this.ws!.send(JSON.stringify({ id, method, params }));
        });
    }

    private scheduleReconnect(url: string) {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            this.emit('reconnectFailed');
            return;
        }
        const delay = Math.min(
            this.reconnectDelay * Math.pow(2, this.reconnectAttempts),
            30000  // 最大30秒
        );
        this.reconnectAttempts++;
        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
        setTimeout(() => {
            this.connect(url).catch(() => {
                // 接続失敗は onclose で再度 scheduleReconnect が呼ばれる
            });
        }, delay);
    }

    private startHeartbeat() {
        this.heartbeatInterval = setInterval(async () => {
            try {
                await this.call('ping', {}, 5000);
            } catch {
                // ping 失敗 → 自動リコネクト (onclose で処理)
                this.ws?.close();
            }
        }, 30000);
    }

    private stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }

    private rejectAllPending(reason: string) {
        for (const [id, pending] of this.pendingCalls) {
            clearTimeout(pending.timer);
            pending.reject(new Error(reason));
        }
        this.pendingCalls.clear();
    }

    async close() {
        this.stopHeartbeat();
        this.reconnectAttempts = this.maxReconnectAttempts;  // リコネクト抑制
        this.ws?.close();
    }
}
```

### 9-f. ロギング戦略

| コンポーネント | ログ出力先 | レベル |
|---------------|-----------|--------|
| Python サーバ | 標準出力 (VSCode の `debug console` に表示) | INFO (通常時), DEBUG (開発時) |
| TypeScript 拡張 | `console.log` → VSCode の `Output` パネル (`uag` チャンネル) | 全レベル |
| Webview | `console.log` → VSCode デベロッパーツールコンソール | 全レベル |

```typescript
// extension.ts — ログチャンネル作成
const outputChannel = vscode.window.createOutputChannel('uag');
outputChannel.appendLine('uag extension activated');

// 各モジュールで使用
function log(level: string, message: string, ...args: any[]) {
    const timestamp = new Date().toISOString().slice(11, 23);
    outputChannel.appendLine(`[${timestamp}][${level}] ${message}`);
    if (args.length) outputChannel.appendLine(JSON.stringify(args, null, 2));
}

// エラー時は自動表示
function logError(error: Error) {
    log('ERROR', error.message);
    outputChannel.show(true);  // フォーカスは奪わない
}
```

### 9-g. テスト戦略

```typescript
// test/suite/wsClient.test.ts
import * as assert from 'assert';
import { WsClient } from '../../src/wsClient';

suite('WsClient', () => {
    test('connect timeout', async () => {
        const client = new WsClient();
        try {
            await client.connect('ws://127.0.0.1:1', 100);
            assert.fail('Should have thrown');
        } catch (e: any) {
            assert.ok(e.message.includes('Connection timeout') || 
                      e.message.includes('failed'));
        }
    });

    test('call with no connection', async () => {
        const client = new WsClient();
        try {
            await client.call('ping');
            assert.fail('Should have thrown');
        } catch (e: any) {
            assert.ok(e.message.includes('Not connected'));
        }
    });
});

// Python 側テスト
// test_ws_server.py
import pytest
import json
from uagent.ws_handler import WsHandler

@pytest.mark.asyncio
async def test_handle_ping():
    handler = WsHandler()
    result = await handler.handle_ping({})
    assert result["pong"] is True

@pytest.mark.asyncio
async def test_handle_tools_list():
    handler = WsHandler()
    result = await handler.handle_tools_list({})
    assert "tools" in result
    assert len(result["tools"]) > 0
```

### 9-h. Webview レイアウト詳細

```html
<!-- chat.html — Webview 完全版 -->
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Security-Policy" 
          content="default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com; 
                   style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; 
                   img-src 'self' data:;">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
    <link rel="stylesheet" href="${webview.cspSource}/chat.css">
</head>
<body>
    <div id="message-list">
        <!-- メッセージが動的に追加される -->
    </div>
    
    <div id="input-area">
        <div id="toolbar">
            <button id="btn-file" title="Attach file">📎</button>
            <button id="btn-code" title="Attach editor code">📋</button>
            <button id="btn-clear" title="Clear chat">🗑️</button>
            <button id="btn-new-session" title="New session">➕</button>
        </div>
        <textarea id="input" 
                  placeholder="Ask anything... (Ctrl+Enter to send)" 
                  rows="3"></textarea>
        <button id="btn-send" disabled>Send</button>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
    <script src="${webview.cspSource}/chat.js"></script>
</body>
</html>
```

```css
/* chat.css — レイアウト */
html, body {
    height: 100%;
    margin: 0;
    display: flex;
    flex-direction: column;
}

#message-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
}

#input-area {
    border-top: 1px solid var(--border-color);
    padding: 8px;
    background: var(--bg-primary);
}

#toolbar {
    display: flex;
    gap: 4px;
    margin-bottom: 4px;
}

#toolbar button {
    background: none;
    border: 1px solid var(--border-color);
    color: var(--text-secondary);
    cursor: pointer;
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 14px;
}

#toolbar button:hover {
    background: var(--bg-secondary);
}

#input {
    width: 100%;
    box-sizing: border-box;
    background: var(--bg-secondary);
    color: var(--text-primary);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    padding: 8px;
    font-family: var(--font-mono);
    font-size: var(--font-size);
    resize: vertical;
}

#input:focus {
    outline: none;
    border-color: var(--accent-color);
}

#btn-send {
    float: right;
    margin-top: 4px;
    padding: 4px 16px;
    background: var(--accent-color);
    color: white;
    border: none;
    border-radius: 3px;
    cursor: pointer;
}

#btn-send:disabled {
    opacity: 0.5;
    cursor: default;
}

/* ツール呼び出しインジケータ */
.tool-call {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--text-secondary);
    font-size: 0.9em;
    padding: 4px 8px;
}

.tool-call .spinner {
    width: 12px;
    height: 12px;
    border: 2px solid var(--border-color);
    border-top-color: var(--accent-color);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

.tool-result {
    background: var(--code-bg);
    border-radius: 4px;
    padding: 8px;
    margin: 4px 0;
    font-size: 0.85em;
    white-space: pre-wrap;
    max-height: 200px;
    overflow-y: auto;
}
```

```javascript
// chat.js — 完全版
(function() {
    const vscode = acquireVsCodeApi();
    const state = vscode.getState() || { messages: [] };

    const messageList = document.getElementById('message-list');
    const input = document.getElementById('input');
    const sendBtn = document.getElementById('btn-send');

    // 状態復元
    if (state.messages.length > 0) {
        state.messages.forEach(msg => renderMessage(msg));
        messageList.scrollTop = messageList.scrollHeight;
    }

    // 入力処理
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            sendMessage();
        }
        // Shift+Enter は改行
    });

    input.addEventListener('input', () => {
        sendBtn.disabled = !input.value.trim();
        // 高さ自動調整
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 200) + 'px';
    });

    sendBtn.addEventListener('click', sendMessage);

    function sendMessage() {
        const text = input.value.trim();
        if (!text) return;
        input.value = '';
        sendBtn.disabled = true;
        input.style.height = 'auto';

        // ユーザーメッセージを表示
        const userMsg = { role: 'user', content: text };
        state.messages.push(userMsg);
        renderMessage(userMsg);

        // LLM に送信
        vscode.postMessage({ type: 'chat', text });
    }

    function renderMessage(msg) {
        const div = document.createElement('div');
        div.className = `message-${msg.role || 'system'}`;
        if (msg.role === 'assistant' && msg.content === undefined) {
            // ストリーミング中
            div.innerHTML = '<span class="cursor-blink">▊</span>';
            div.id = 'streaming-message';
        } else if (msg.content) {
            div.innerHTML = marked.parse(escapeHtml(msg.content));
            div.querySelectorAll('pre code').forEach(block => {
                hljs.highlightElement(block);
                // コピーボタンを追加
                addCopyButton(block.parentElement);
            });
            // ファイル参照をリンクに
            div.querySelectorAll('a').forEach(a => {
                const match = a.textContent.match(/(\S+?\.\w+):(\d+)/);
                if (match) {
                    a.href = '#';
                    a.addEventListener('click', (e) => {
                        e.preventDefault();
                        vscode.postMessage({ type: 'openFile', path: match[1], line: parseInt(match[2]) });
                    });
                }
            });
        }
        messageList.appendChild(div);
        messageList.scrollTop = messageList.scrollHeight;
    }

    function escapeHtml(text) {
        const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
        return text.replace(/[&<>"']/g, c => map[c]);
    }

    // コピーボタン
    function addCopyButton(preElement) {
        const btn = document.createElement('button');
        btn.className = 'copy-btn';
        btn.textContent = 'Copy';
        btn.addEventListener('click', () => {
            const code = preElement.querySelector('code')?.textContent || '';
            navigator.clipboard.writeText(code).then(() => {
                btn.textContent = 'Copied!';
                setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
            });
        });
        preElement.style.position = 'relative';
        preElement.appendChild(btn);
    }

    // VS Code からのメッセージ受信
    window.addEventListener('message', event => {
        const msg = event.data;
        switch (msg.type) {
            case 'chunk':
                appendChunk(msg.data);
                break;
            case 'tool_call':
                showToolCall(msg.tool, msg.args);
                break;
            case 'tool_result':
                showToolResult(msg.tool, msg.result);
                break;
            case 'done':
                finalizeMessage();
                break;
            case 'error':
                showError(msg.data);
                break;
            case 'themeChanged':
                document.body.className = `theme-${msg.theme}`;
                break;
            case 'context':
                appendContext(msg);
                break;
        }
    });

    function appendChunk(text) {
        let streamingEl = document.getElementById('streaming-message');
        if (!streamingEl) {
            const msg = { role: 'assistant' };
            state.messages.push(msg);
            renderMessage(msg);
            streamingEl = document.getElementById('streaming-message');
        }
        streamingEl.textContent += text;
        messageList.scrollTop = messageList.scrollHeight;
    }

    function showToolCall(tool, args) {
        const div = document.createElement('div');
        div.className = 'tool-call';
        div.innerHTML = `<span class="spinner"></span> 🔍 ${tool}(${JSON.stringify(args).slice(0, 100)})`;
        messageList.appendChild(div);
        messageList.scrollTop = messageList.scrollHeight;
    }

    function showToolResult(tool, result) {
        const lastTool = messageList.lastElementChild;
        if (lastTool?.className === 'tool-call' && lastTool.textContent.includes(tool)) {
            const resultDiv = document.createElement('div');
            resultDiv.className = 'tool-result';
            resultDiv.textContent = typeof result === 'string' ? result.slice(0, 500) : JSON.stringify(result).slice(0, 500);
            lastTool.after(resultDiv);
        }
    }

    function finalizeMessage() {
        const streamingEl = document.getElementById('streaming-message');
        if (streamingEl) {
            streamingEl.id = '';
            const lastMsg = state.messages[state.messages.length - 1];
            if (lastMsg) lastMsg.content = streamingEl.textContent;
        }
        input.focus();
        // 状態保存
        vscode.setState({ messages: state.messages });
    }

    function showError(error) {
        const div = document.createElement('div');
        div.className = 'error-text';
        div.textContent = `Error: ${error}`;
        messageList.appendChild(div);
    }

    function appendContext(ctx) {
        const div = document.createElement('div');
        div.className = 'context-info';
        div.textContent = `[Context: ${ctx.file}:${ctx.code.slice(0, 50)}...]`;
        messageList.appendChild(div);
    }
})();
```

### 9-i. キーボードショートカット

```json
// package.json に追加
"contributes": {
    "keybindings": [
        {
            "command": "uag.chat",
            "key": "ctrl+shift+u",
            "mac": "cmd+shift+u",
            "when": "editorFocus"
        },
        {
            "command": "uag.explain",
            "key": "ctrl+shift+e",
            "mac": "cmd+shift+e",
            "when": "editorHasSelection"
        },
        {
            "command": "uag.refactor",
            "key": "ctrl+shift+r",
            "mac": "cmd+shift+r",
            "when": "editorHasSelection"
        },
        {
            "command": "uag.fix",
            "key": "ctrl+shift+.",
            "mac": "cmd+shift+.",
            "when": "editorHasDiagnostics"
        }
    ]
}
```

### 9-j. CI/CD パイプライン

```yaml
# .github/workflows/extension.yml
name: Build and Publish VSCode Extension

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          
      - name: Install dependencies
        run: |
          cd vscode-extension
          npm ci
          
      - name: Compile TypeScript
        run: |
          cd vscode-extension
          npm run compile
          
      - name: Run tests
        run: |
          cd vscode-extension
          npm test -- --no-coverage
          
      - name: Package VSIX
        run: |
          cd vscode-extension
          npx vsce package
          
      - name: Upload VSIX to Release
        uses: actions/upload-release-asset@v1
        env:
          GITHUB_TOKEN: \${{ secrets.GITHUB_TOKEN }}
        with:
          upload_url: \${{ github.event.release.upload_url }}
          asset_path: ./vscode-extension/uag-vscode-*.vsix
          asset_name: uag-vscode-\${{ github.ref_name }}.vsix
          asset_content_type: application/octet-stream
          
      - name: Publish to Marketplace
        run: |
          cd vscode-extension
          npx vsce publish -p \${{ secrets.VSCE_PAT }}
```

### 9-k. パフォーマンス考慮点

| 項目 | 対策 | 根拠 |
|------|------|------|
| WebSocket メッセージサイズ | 最大10MB (`max_size`) | ツール実行結果が大きい場合を考慮 |
| ストリーミングレイテンシ | 1チャンク最大1024文字 | 高頻度の send() を避けるため |
| Webview メモリ | メッセージ100件で古いものを間引き | `state.messages.length > 100` で slice |
| Python 子プロセスメモリ | 1セッションあたり最大500MB想定 | `resource.setrlimit` で制限可能 |
| 並列リクエスト | `call()` のタイムアウト30秒 | ツール実行のタイムアウトと一致 |
| Webview HTML サイズ | インライン化で初期表示高速化 | 外部ファイル参照より `webview.html` に直接埋め込み |

```typescript
// メッセージ間引き
function trimHistory() {
    const MAX_MESSAGES = 100;
    if (state.messages.length > MAX_MESSAGES) {
        const removeCount = state.messages.length - MAX_MESSAGES;
        state.messages.splice(0, removeCount);
        // DOM からも削除
        const children = messageList.children;
        for (let i = 0; i < removeCount && i < children.length; i++) {
            children[i].remove();
        }
    }
}
```

## 10. Visual Studio (フルIDE) 対応

VS Code 拡張と Visual Studio 拡張は互換性がありません。別途開発が必要です。
