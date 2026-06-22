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

## 9. Visual Studio (フルIDE) 対応

VS Code 拡張と Visual Studio 拡張は互換性がありません。別途開発が必要です。

### 共通で使い回せる部分

| コンポーネント | 再利用可否 |
|---------------|-----------|
| Python バックエンド（WebSocket サーバ） | そのまま使い回せる |
| チャットUI の HTML/JS（Webview フロントエンド） | そのまま使い回せる |
| uag 本体のツール群 | そのまま使い回せる |

### 書き直しが必要な部分

| 項目 | VS Code (TypeScript) | Visual Studio (C#) |
|------|---------------------|-------------------|
| 拡張マニフェスト | `package.json` | `.vsixmanifest` |
| 拡張API | `@types/vscode` | `EnvDTE`, `IVs*`, `AsyncPackage` |
| エディタ連携 | `TextDocument`, `workspace.fs` | `IVsTextBuffer`, `ITextDocument` |
| コマンド登録 | `commands.registerCommand` | `MenuCommand`, `VSCommandTable` |
| 設定画面 | `contributes.configuration` | `Tools > Options` ページ |
| ツールウィンドウ | `WebviewPanel` | `ToolWindowPane` + WebView2 |
| ソリューションエクスプローラ連携 | `workspace.workspaceFolders` | `IVsSolution`, `DTE.Solution` |

### Visual Studio 拡張の基本構成

```
vs-extension/
├── src/
│   ├── UagPackage.cs            # AsyncPackage (エントリポイント)
│   ├── UagToolWindow.cs         # ToolWindowPane (チャットUI をホスト)
│   ├── UagWebSocketClient.cs    # Python バックエンドとの通信
│   ├── UagCommands.cs           # メニューコマンド
│   └── UagSettings.cs           # 設定ページ
├── UagExtension.vsixmanifest    # マニフェスト
├── UagExtension.csproj          # プロジェクトファイル
└── resources/
    ├── chat.html                # WebView2 で表示するチャットUI (流用)
    └── icon.png
```

### 開発要件

- Visual Studio 2022 (17.x) 以降
- Visual Studio SDK（VS インストーラで「Visual Studio 拡張機能の開発」ワークロード）
- .NET Framework 4.7.2+ または .NET 8+
- WebView2（Edge Chromium ベースの埋め込みブラウザ）

### 開発の優先順位（Visual Studio 版）

| Priority | Task | 工数目安 |
|----------|------|---------|
| P0 | `AsyncPackage` 雛形 + WebSocket 接続 | 2日 |
| P1 | ToolWindow に WebView2 でチャットUI表示 | 2日 |
| P2 | エディタ連携（選択範囲の送信、コード挿入） | 2-3日 |
| P3 | ソリューションエクスプローラ連携（workdir 設定） | 1日 |
| P4 | メニューコマンド登録（右クリック→uag） | 1日 |
| P5 | Marketplace 公開 | 0.5日 |

## 10. 注意点・リスク

- **Python ランタイム必須**: ユーザーは別途 Python + uag のインストールが必要。初回起動時の導線が重要。
- **ポート競合**: 18765 が使用中の場合、フォールバックポートを自動選択するか、ユーザーに通知する。
- **ファイアウォール**: 127.0.0.1 のみ Listen するので外部からのアクセスは不可。セキュリティ問題なし。
- **子プロセスの終了処理**: VSCode 終了時に WebSocket サーバプロセスが orphan にならないよう、`deactivate()` で確実に kill する。
- **Webview のメモリ**: `retainContextWhenHidden: true` によりタブ非表示時も状態維持。ただしメモリ消費が増えるので、長時間使用時は注意。
- **uagw の流用**: 既存の `templates/index.html` は EJS テンプレート。Webview では静的な HTML として書き直す必要あり。
- **テーマ連動**: `body.classList` に `vscode-dark` / `vscode-light` が自動付与されるので、CSS 変数で対応。

### Step 1: 拡張機能の雛形作成

- `yo code` または手動で `vscode-extension/` を作成
- `package.json` に以下を定義:
  - `activationEvents`: `onCommand`, `onView`
  - `contributes.commands`: 全コマンド（`uag.start`, `uag.chat`, `uag.tools` など）
  - `contributes.viewsContainers`: Activity Bar に `uag` アイコン追加
  - `contributes.views`: サイドバーにツリービュー
  - `contributes.configuration`: 設定項目（`uag.provider`, `uag.model` など）

### Step 2: Python バックエンドとの連携方式を決定

uag 本体は Python。VSCode 拡張は TypeScript/JavaScript。連携方法:

| 方式 | メリット | デメリット |
|------|---------|-----------|
| **A) 子プロセス起動** | 簡単、既存の `uag` CLI をそのまま利用 | 起動が遅い、状態管理が複雑 |
| **B) Python の WebSocket/HTTP サーバとして起動** | 常駐、高速応答 | WebSocket サーバの実装が必要 |
| **C) VS Code の Language Server Protocol 拡張** | 標準的 | チャット用途には不向き |
| **D) Python を埋め込み** | 高速 | 複雑、同梱が大変 |

**推奨: B**（Python を WebSocket サーバとして起動し、VSCode 拡張から接続）

### Step 3: Python 側に WebSocket/API サーバを追加

既存の `uagent/` に以下のエンドポイントを持つサーバを追加:

- `/chat` — LLM とのチャット (streaming)
- `/tools` — ツール一覧取得
- `/tool/execute` — ツール実行
- `/files/read` — ファイル読み込み
- `/files/write` — ファイル書き込み
- `/config` — 設定取得/更新
- `/session/list` — セッション一覧
- `/session/load` — セッション読み込み

技術選択肢:
- **FastAPI** + `uvicorn` (推奨: 最もシンプル)
- `websockets` ライブラリ
- `aiohttp`

### Step 4: VSCode 拡張側の実装

#### 4-a: Webview Panel（メインチャット UI）
- 既存の Web UI (`uagw`) のフロントエンドを流用可能
- メッセージの Markdown レンダリング
- コードブロックのシンタックスハイライト
- ファイル参照のクリックで VSCode で開く

#### 4-b: TreeView（ツール一覧/ファイル操作）
- サイドバーにツールカテゴリごとのツリー表示
- `comm` / `file` / `iot` / `devel` など genre 別
- クリックでツール説明表示
- ファイルツリー（作業ディレクトリ）

#### 4-c: エディタ連携
- コード選択 → 右クリック → 「uag に質問」 → 選択範囲をコンテキストとしてチャット送信
- エディタ内のエラーを uag に送信して修正提案
- ファイル作成/編集結果をエディタに反映

#### 4-d: 診断情報プロバイダ
- `DiagnosticCollection` を使って LLM の提案をエディタに表示
- クイックフィックスとしてコード変更を適用

### Step 5: 配布方法

| 方法 | 手順 |
|------|------|
| **VSIX ファイル** | `vsce package` で `.vsix` 作成、手動インストール |
| **VS Code Marketplace** | `vsce publish` → 公開（Azure DevOps アカウント + Personal Access Token が必要） |
| **Open VSX Registry** | Open VSX にも公開（VSCodium 対応） |

### Step 6: Python ランタイムの扱い

ユーザーの環境に Python と uag がインストールされている必要がある:

```json
// package.json
"activationEvents": [
    "onCommand:uag.start"
]
```

- 起動時に `python -c "import uagent"` で確認
- 未インストールの場合: `pip install uag` を促すガイド表示
- Python のパスは設定可能（`uag.pythonPath`）

または拡張機能に同梱:
- `PyInstaller` で uag を単一バイナリ化して同梱（ファイルサイズ増大）
- `pip install --target` で依存関係ごと同梱

## 3. package.json の構成例

```json
{
  "name": "uag-vscode",
  "displayName": "uag - Universal AI Gateway",
  "version": "0.5.20",
  "publisher": "awaku7",
  "engines": { "vscode": "^1.85.0" },
  "categories": ["Chat", "Programming Languages", "Machine Learning"],
  "activationEvents": ["onCommand:uag.chat", "onView:uag.tools"],
  "contributes": {
    "commands": [
      { "command": "uag.chat", "title": "uag: Open Chat" },
      { "command": "uag.explain", "title": "uag: Explain Selection" },
      { "command": "uag.refactor", "title": "uag: Refactor Selection" },
      { "command": "uag.fix", "title": "uag: Fix Error" }
    ],
    "menus": {
      "editor/context": [
        { "command": "uag.explain", "group": "uag" },
        { "command": "uag.refactor", "group": "uag" }
      ]
    },
    "configuration": {
      "title": "uag",
      "properties": {
        "uag.provider": { "type": "string", "default": "openai" },
        "uag.pythonPath": { "type": "string", "default": "python" },
        "uag.port": { "type": "number", "default": 18765 }
      }
    }
  }
}
```

## 4. 必要な依存関係

> **開発時のみ Node.js が必要。エンドユーザーは VSCode 拡張としてインストールするだけでよく、Node.js は不要。**

**TypeScript (VSCode 拡張側) — 開発環境でのみ必要:**
- Node.js (>=18)
- `npm`（Node.js に同梱）
- `@types/vscode`
- `typescript`
- `vsce`（拡張機能のパッケージング/公開ツール）: `npm install -g @vscode/vsce`

VSCode 拡張のビルド手順:
```bash
cd vscode-extension/
npm install          # 依存関係インストール
npm run compile      # TypeScript コンパイル
vsce package         # .vsix ファイル作成（Node.js 不要で配布可能）
vsce publish         # Marketplace 公開
```

**Python 側（新規追加）:**

**TypeScript (VSCode 拡張側):**
- `@types/vscode`
- `typescript`

**Python 側（新規追加）:**
- `websockets` または `fastapi` + `uvicorn`
- `pydantic`

## 5. 開発の優先順位

| Priority | Task | 工数目安 |
|----------|------|---------|
| P0 | Python WebSocket サーバ実装 | 2-3日 |
| P1 | VSCode 拡張雛形 + Webview チャット | 3-5日 |
| P2 | エディタ連携（選択範囲の送信） | 1-2日 |
| P3 | TreeView（ツール一覧） | 1日 |
| P4 | 診断情報プロバイダ | 2日 |
| P5 | Marketplace 公開 | 0.5日 |
| P6 | テスト・CI | 2-3日 |

## 6. Visual Studio (フルIDE) 対応

VS Code 拡張と Visual Studio 拡張は互換性がありません。別途開発が必要です。

### 共通で使い回せる部分

| コンポーネント | 再利用可否 |
|---------------|-----------|
| Python バックエンド（WebSocket サーバ） | そのまま使い回せる |
| チャットUI の HTML/JS（Webview フロントエンド） | そのまま使い回せる |
| uag 本体のツール群 | そのまま使い回せる |

### 書き直しが必要な部分

| 項目 | VS Code (TypeScript) | Visual Studio (C#) |
|------|---------------------|-------------------|
| 拡張マニフェスト | `package.json` | `.vsixmanifest` |
| 拡張API | `@types/vscode` | `EnvDTE`, `IVs*`, `AsyncPackage` |
| エディタ連携 | `TextDocument`, `workspace.fs` | `IVsTextBuffer`, `ITextDocument` |
| コマンド登録 | `commands.registerCommand` | `MenuCommand`, `VSCommandTable` |
| 設定画面 | `contributes.configuration` | `Tools > Options` ページ |
| ツールウィンドウ | `WebviewPanel` | `ToolWindowPane` + WebView2 |
| ソリューションエクスプローラ連携 | `workspace.workspaceFolders` | `IVsSolution`, `DTE.Solution` |

### Visual Studio 拡張の基本構成

```
vs-extension/
├── src/
│   ├── UagPackage.cs            # AsyncPackage (エントリポイント)
│   ├── UagToolWindow.cs         # ToolWindowPane (チャットUI をホスト)
│   ├── UagWebSocketClient.cs    # Python バックエンドとの通信
│   ├── UagCommands.cs           # メニューコマンド
│   └── UagSettings.cs           # 設定ページ
├── UagExtension.vsixmanifest    # マニフェスト
├── UagExtension.csproj          # プロジェクトファイル
└── resources/
    ├── chat.html                # WebView2 で表示するチャットUI
    └── icon.png
```

### 開発要件

- Visual Studio 2022 (17.x) 以降
- Visual Studio SDK（VS インストーラで「Visual Studio 拡張機能の開発」ワークロード）
- .NET Framework 4.7.2+ または .NET 8+
- WebView2（Edge Chromium ベースの埋め込みブラウザ）

### 開発の優先順位（Visual Studio 版）

| Priority | Task | 工数目安 |
|----------|------|---------|
| P0 | `AsyncPackage` 雛形 + WebSocket 接続 | 2日 |
| P1 | ToolWindow に WebView2 でチャットUI表示 | 2日 |
| P2 | エディタ連携（選択範囲の送信、コード挿入） | 2-3日 |
| P3 | ソリューションエクスプローラ連携（workdir 設定） | 1日 |
| P4 | メニューコマンド登録（右クリック→uag） | 1日 |
| P5 | Marketplace 公開 | 0.5日 |

## 7. 注意点

- `uagw`（既存の Web UI）のフロントエンドは流用可能。`templates/index.html` のロジックを参考にすると良い。
- ファイル操作は `ensure_within_workdir()` により VSCode の開いているワークスペースに制限される。VSCode 拡張では `workspace.workspaceFolders` を workdir に設定。
- LLM からのファイル作成要求を VSCode の `workspace.fs` または `TextDocument` で処理すると、エディタ上で変更を可視化できる。
- ストリーミングレスポンスは WebSocket 経由が最も自然。
