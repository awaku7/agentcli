# Plugin System (Developer Guide)

uagent は Claude Code 互換のプラグインシステムを実装しています。
プラグインは `.claude-plugin/plugin.json` マニフェストを持つ自己完結型のディレクトリです。

## Quick Start

```
:plugin init my-plugin          # スキャフォールド生成
:plugin install ./my-plugin     # ローカルからインストール
:plugin install genshijin       # bare name（登録 marketplace を自動検索）
:plugin install genshijin@claude-plugins-official  # marketplace 明示
:plugin list                    # 一覧
:plugin enable my-plugin        # 有効化
:plugin disable my-plugin       # 無効化
:plugin remove my-plugin        # アンインストール
:plugin info my-plugin          # 詳細
```

## Plugin ディレクトリ構造

```
<plugin-name>/
├── .claude-plugin/
│   └── plugin.json              # マニフェスト（必須: name）
├── skills/                      # Agent Skills（SKILL.md）
├── commands/                    # ":" コマンド（プラグイン名で名前空間化）
│   ├── <plugin>.toml            # :plugin [args]
│   └── <plugin>-foo.toml        # :plugin foo / :plugin-foo / :plugin:foo
├── agents/                      # サブエージェント定義
├── hooks/
│   └── hooks.json               # ライフサイクルフック
├── monitors/
│   └── monitors.json
├── output-styles/               # 出力スタイル定義
├── themes/
├── bin/                         # PATH 追加バイナリ
├── .mcp.json                    # MCP サーバー定義
├── .lsp.json                    # LSP サーバー定義
├── settings.json                # デフォルト設定
└── SKILL.md                     # 単一スキル（skills/ がない場合）
```

## マニフェスト（plugin.json）

必須フィールドは `name` のみ。Claude Code と完全互換。

```json
{
  "$schema": "https://json.schemastore.org/claude-code-plugin-manifest.json",
  "name": "my-plugin",
  "displayName": "My Plugin",
  "version": "0.1.0",
  "description": "Does something useful",
  "defaultEnabled": true,
  "author": { "name": "Author" },
  "skills": "./skills",
  "commands": ["./commands/deploy.md"],
  "agents": ["./agents/reviewer.md"],
  "hooks": "./hooks/hooks.json",
  "mcpServers": "./.mcp.json",
  "lspServers": "./.lsp.json",
  "outputStyles": "./output-styles/",
  "userConfig": { ... },
  "dependencies": ["base-lib", {"name": "lib2", "version": "~1.0"}],
  "settings": {}
}
```

## スキル（Skills）

- `<plugin>/skills/<name>/SKILL.md` → `:skills list` で自動検出
- `skills/` がない場合、ルート直下の `SKILL.md` を単一スキルとしてロード
- スキル名: `<plugin-name>:<skill-name>`（Claude Code 互換の名前空間）

## MCP サーバー

- `<plugin>/.mcp.json` の内容が `mcp_servers.json` に自動マージ
- サーバー名: `<plugin-name>:<server-name>`
- プラグイン無効化/削除時に自動クリーンアップ

## エージェント（Sub-agents）

- `<plugin>/agents/*.md` → `~/.uag/subagent_roles/` に JSON 変換して配置
- YAML frontmatter 対応（name, description, model, effort, maxTurns 等）
- ファイル名: `<plugin-name>@<agent-name>.json`（Windows では `@`、Unix では `:`）

## Hooks

- `<plugin>/hooks/hooks.json` の定義を `~/.uag/hooks/plugin_hooks.json` に登録
- 対応イベント: SessionStart, Setup, UserPromptSubmit, PreToolUse, PostToolUse, PostToolUseFailure, PostToolBatch, SubagentStart, SubagentStop, Stop, StopFailure, SessionEnd
- 対応タイプ: command（subprocess）, http（POST/PUT/PATCH）, mcp_tool（MCP tool call）
- PreToolUse は正規表現マッチャー対応（`"matcher": "Write|Edit"`）
- コマンド内の `${CLAUDE_PLUGIN_ROOT}` / `${UAGENT_PLUGIN_ROOT}` は当該プラグインのインストールディレクトリに展開（Claude Code 互換）。`${UAGENT_PROJECT_DIR}` はプロジェクトルート。
- レジストリ `plugin_roots` にプラグイン名→パスを記録し、フック実行時に `CLAUDE_PLUGIN_ROOT` 環境変数も付与する
- **stdout → 会話コンテキスト注入**（Claude Code の additionalContext 相当・後方互換）:
  - フックが成功し stdout に意味のある本文があるとき、`[HOOK] event=<EventName>` 付き system メッセージとして会話へ追加する
  - プレーンテキスト stdout（例: genshijin SessionStart）をそのまま注入
  - JSON の `hookSpecificOutput.additionalContext` またはトップレベル `additionalContext` のみ採用（decision/block のみの JSON は注入しない）
  - `ok` / `done` / `{}` 等のトリビアル出力は無視（既存フックに影響なし）
  - CLI: SessionStart / Setup / UserPromptSubmit を直接注入。UserPromptSubmit はターンごとに同一 event を置換
  - Web: サーバ起動時 SessionStart を stash → ルーム初期化（`build_initial_messages` 後）で注入
  - GUI: ウィンドウ表示後の SessionStart 結果を `win.messages` へ注入
  - ログ再読込時は `[SKILL] ` と同様に `[HOOK] ` system を保持
  - 未対応（安全のため後回し）: UserPromptSubmit への stdin JSON 供給、decision=block UI

## Hooks 実行エンジン

```python
from uagent.hooks_engine import (
    load_hooks_registry,    # レジストリ読み込み
    fire_event,             # イベント発火
    fire_tool_event,        # ツールイベント発火（マッチャー対応）
    fire_session_start,     # SessionStart（stdout を pending stash）
    fire_stop,              # Stop
    fire_stop_failure,      # StopFailure
    get_active_hook_count,  # アクティブフック数
    execute_hook,           # 単一フック実行
    parse_hook_stdout_context,           # stdout → 注入テキスト
    inject_hook_context,                 # results → messages へ [HOOK] 注入
    inject_pending_session_hook_context, # Web 等: stash 済み SessionStart を注入
)
```

## userConfig

- `plugin.json` の `userConfig` フィールドを `settings.json` の `pluginConfigs[].options` に保存
- `${user_config.KEY}` プレースホルダを MCP/Hook コマンドで解決
- デフォルト値とのマージ対応

## 依存関係（Dependencies）

```json
{
  "dependencies": ["base-lib", {"name": "secrets-vault", "version": "~2.1.0"}]
}
```

- `parse_plugin_dependencies()`: マニフェストから依存関係をパース
- `resolve_dependencies()`: DFS トポロジカルソートで依存順序を解決
- 循環依存検出対応

## マーケットプレイス

```
:plugin marketplace add <url>       # 登録
:plugin marketplace remove <name>   # 削除
:plugin marketplace list            # 一覧
:plugin marketplace update <name>   # 更新
:plugin install <name>@<marketplace> # インストール
```

- `marketplace.json` スキーマ（Claude Code 互換）をパース
- プラグインソースのパス解決
- レジストリ管理（`~/.uag/marketplaces.json`）

## チャンネル（Channels）

```json
{
  "channels": [{"server": "telegram", "userConfig": {...}}]
}
```

- チャンネル設定の保存・取得・一覧・削除
- 各チャンネルは MCP サーバーに紐付け

## アーキテクチャ

### ファイル構成

| ファイル | 責務 |
|---|---|
| `src/uagent/plugin_shared.py` | 共有ユーティリティ（パース/検証/検出/管理） |
| `src/uagent/tools/plugin_manage_tool.py` | LLM ツール + CLI コマンド |
| `src/uagent/runtime/runtime_plugins.py` | Startup ローダー |
| `src/uagent/hooks_engine.py` | Hooks 実行エンジン |

### Plugin 検出順序

1. `.uag/plugins/<name>/`（プロジェクト）
2. `.claude/plugins/<name>/`（Claude Code 互換）
3. `~/.uag/plugins/<name>/`（ユーザー）
4. `~/.claude/plugins/<name>/`（Claude Code 互換）

同名の場合は先に見つかった方が優先。

### Skills-directory プラグイン

`~/.uag/skills/<name>/.claude-plugin/plugin.json` がある場合、
そのディレクトリはスキル兼プラグインとして自動検出される（`:plugin install` 不要）。

### ユニットテスト

```
pytest tests/test_plugin_system.py       # 基本管理（97 tests）
pytest tests/test_hooks_engine.py         # Hooks エンジン（stdout 注入含む）
pytest tests/test_hooks_all_events.py     # 全フックイベント（18 tests）
pytest tests/test_plugin_userconfig.py    # userConfig（9 tests）
pytest tests/test_plugin_marketplace.py   # マーケットプレイス（17 tests）
pytest tests/test_plugin_channels.py      # チャンネル（8 tests）
pytest tests/test_plugin_outputstyles.py  # OutputStyles（7 tests）
```

全 171 tests がパスすること。

## プラグインコマンド（`:`）

Claude Code の `/plugin`・`/plugin:cmd` に相当する機能を、uag では **`:` 名前空間**で提供する。

| ファイル | 登録されるコマンド |
|---|---|
| `commands/<plugin>.toml` | `:<plugin> [args]` |
| `commands/<plugin>-foo.toml` | `:<plugin> foo` / `:<plugin>-foo` / `:<plugin>:foo` |

ルール:

- トップレベル名は **プラグイン名**（コア予約語 `help`/`tools`/`cd` 等は拒否）
- 有効化時に登録、無効化・削除時に解除
- 実行時はまず `UserPromptSubmit` フックへ ` /<stem> ...` を流す（既存 genshijin hook 互換）
- `prompt` は `{{args}}` を展開。タスク系は LLM へ渡す

