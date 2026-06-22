# VSCode Extension 化計画

uag（Universal AI Gateway）を VSCode 拡張機能として統合するためのタスク一覧。

---

## 1. プロジェクト構成

```
agentcli/
├── .vscode/                     # VSCode 拡張の設定
│   ├── launch.json
│   └── tasks.json
├── vscode-extension/            # 拡張機能本体
│   ├── package.json             # 拡張機能マニフェスト
│   ├── src/
│   │   ├── extension.ts         # エントリポイント（activate/deactivate）
│   │   ├── panel.ts             # Webview Panel（チャットUI）
│   │   ├── treeProvider.ts      # TreeView（ツール一覧など）
│   │   ├── commands.ts          # コマンド登録
│   │   ├── config.ts            # 設定管理
│   │   ├── providerManager.ts   # LLMプロバイダ管理
│   │   └── utils.ts
│   ├── media/
│   │   └── main.js              # Webview のフロントエンド
│   ├── test/
│   └── tsconfig.json
└── src/                         # 既存の Python コード（そのまま利用）
```

## 2. 実装ステップ

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

## 6. 注意点

- `uagw`（既存の Web UI）のフロントエンドは流用可能。`templates/index.html` のロジックを参考にすると良い。
- ファイル操作は `ensure_within_workdir()` により VSCode の開いているワークスペースに制限される。VSCode 拡張では `workspace.workspaceFolders` を workdir に設定。
- LLM からのファイル作成要求を VSCode の `workspace.fs` または `TextDocument` で処理すると、エディタ上で変更を可視化できる。
- ストリーミングレスポンスは WebSocket 経由が最も自然。
