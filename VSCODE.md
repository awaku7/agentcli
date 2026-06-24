# uag VS Code Extension

uag の機能を VS Code 内で直接利用できる拡張機能です。

## インストール

### 前提条件

- Python 3.11+
- uag パッケージ: `pip install uag`

### ビルド

```bash
cd vscode-extension
npm install
npm run compile
```

### インストール方法

1. `vsce package` で `.vsix` ファイルを生成
2. VS Code の拡張機能ビューから「...」→「VSIX からのインストール」で選択

または VS Code マーケットプレイスで "uag" を検索してインストール（公開後）。

## 機能

### Chat Panel（チャットパネル）

| 項目 | 説明 |
|---|---|
| 起動コマンド | `uag: Open Chat` |
| ショートカット | `Ctrl+Shift+U`（Win/Linux）/ `Cmd+Shift+U`（Mac） |
| 説明 | uag と直接チャットできる Webview パネルを開きます。コードの質問、ファイル操作、Web 検索など、uag の全ツールをチャット経由で利用できます。 |

- パネル内のテキストエリアにメッセージを入力して Send または `Ctrl+Enter`/`Cmd+Enter`
- チャットの応答はストリーミング表示されます
- `+ New Session` ボタンで新しいセッションを開始

### Explain Selection（選択範囲の説明）

| 項目 | 説明 |
|---|---|
| 起動コマンド | `uag: Explain Selection` |
| ショートカット | `Ctrl+Shift+E`（Win/Linux）/ `Cmd+Shift+E`（Mac） |
| コンテキストメニュー | エディタ右クリック → `uag: Explain Selection` |
| 条件 | テキストが選択されていること |

エディタで選択したコードを uag が説明します。ファイルパスと言語が自動的に付加され、チャットパネルに送信されます。

### Refactor Selection（選択範囲のリファクタリング）

| 項目 | 説明 |
|---|---|
| 起動コマンド | `uag: Refactor Selection` |
| ショートカット | `Ctrl+Shift+R`（Win/Linux）/ `Cmd+Shift+R`（Mac） |
| コンテキストメニュー | エディタ右クリック → `uag: Refactor Selection` |
| 条件 | テキストが選択されていること |

選択したコードのリファクタリング案を uag が提案します。レスポンスにコードブロックが含まれている場合、以下のオプションが表示されます：

- **Show Diff**: リファクタリング結果をエディタに適用（差分表示なし）
- **Apply**: リファクタリング結果を直接適用

### Fix Error（エラー修正）

| 項目 | 説明 |
|---|---|
| 起動コマンド | `uag: Fix Error at Cursor` |
| ショートカット | `Ctrl+Shift+.`（Win/Linux）/ `Cmd+Shift+.`（Mac） |
| コンテキストメニュー | エディタ右クリック → `uag: Fix Error at Cursor` |
| 条件 | カーソル位置に診断エラーがあること |

カーソル位置のエラー（VS Code の diagnostics）を uag が分析し、修正案を提案します。レスポンスにコードブロックが含まれている場合、Show Diff / Apply のオプションが表示されます。

### Tools Tree View（ツール一覧ビュー）

アクティビティバーの uag アイコンからツール一覧を参照できます。ジャンルごとに分類されたツールの一覧が表示され、各ツールの名前と説明を確認できます。

- 接続中は自動的にツール一覧を更新
- 手動更新: `uag: Refresh Tools` コマンドまたはツリービューの更新ボタン

### New Session（新規セッション）

| 項目 | 説明 |
|---|---|
| 起動コマンド | `uag: New Session` |
| 説明 | 新しいチャットセッションを開始します。 |

### Status Bar（ステータスバー）

ステータスバーに uag の接続状態が表示されます：

| 状態 | 表示 |
|---|---|
| 起動中 | `$(hubot) uag: starting...` |
| Python 未インストール | `$(warning) uag: Python not found` |
| uag 未インストール | `$(warning) uag: not installed` |
| サーバ起動中 | `$(hubot) uag: starting server...` |
| サーバ起動失敗 | `$(error) uag: server failed` |
| 接続済み | `$(hubot) uag: connected` |
| 切断 | `$(warning) uag: disconnected` |
| 接続失敗 | `$(error) uag: connection failed` |

ステータスバーをクリックすると Chat Panel が開きます。

## 設定

| 設定キー | 型 | デフォルト | 説明 |
|---|---|---|---|
| `uag.pythonPath` | string | `python` | Python 実行ファイルのパス |
| `uag.port` | number | `18765` | WebSocket サーバのポート番号 |
| `uag.autoFix` | boolean | `false` | エラー自動修正の提案を有効にする |

## 動作の仕組み

1. 拡張機能のアクティベーション時に、指定された Python と uag パッケージの有無を確認
2. `python -m uagent.ws_server --port <port>` で WebSocket サーバを起動
3. サーバの stdout に `UAG_WS_READY` が出力されるのを待って接続
4. 接続後、ワークスペースルートを作業ディレクトリとして設定
5. 各コマンドは WebSocket 経由でサーバと通信

### 再接続

- 最大10回の自動再接続を試行（指数バックオフ、最大30秒間隔）
- 30秒ごとにハートビート（`ping`）を送信
- ハートビートのタイムアウトは5秒（LLMの長時間処理中はタイムアウトしても切断しない）

## 開発

```bash
cd vscode-extension
npm install
npm run compile    # TypeScript のコンパイル
npm run watch      # ウォッチモード
npm run package    # .vsix パッケージの生成
```

デバッグには VS Code の `Extension Development Host`（F5）を使用します。
`.vscode/launch.json` と `.vscode/tasks.json` が予め設定されています。

### ファイル構成

```
vscode-extension/
├── src/
│   ├── extension.ts          # メインエントリポイント
│   ├── wsClient.ts           # WebSocket クライアント
│   ├── panel.ts              # チャットパネル（Webview）
│   ├── editorIntegration.ts  # エディタ統合（Explain/Refactor/Fix）
│   └── treeProvider.ts       # ツリー表示プロバイダ
├── package.json              # 拡張機能のマニフェスト
├── tsconfig.json             # TypeScript 設定
└── .vscode/
    ├── launch.json           # 起動設定
    └── tasks.json            # タスク設定
```

## 既知の制限

- サーバは拡張機能ごとに1プロセス起動され、拡張機能を閉じると終了します
- 初回起動時に Python / uag のインストール確認を行うため、環境によっては数秒の遅延があります
- `uag.autoFix` は現在未実装（将来対応予定）
