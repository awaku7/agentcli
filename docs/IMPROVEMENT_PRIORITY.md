# 改善優先順位と期待効果

この文書は、`uag_improvement_plan.md` に記載された改善項目を、現在の実装状況を踏まえて整理したものです。

## 結論

最優先で実装する順序は次のとおりです。

1. Agent Lifecycle
1. CredentialStore 共通化
1. SQLite TaskStore
1. 構造化 Observability の全境界適用
1. Enterprise Policy Engine

この順番で進めることで、uag は単なる機能集合から、状態を一貫して管理できる Agent Runtime へ発展します。

## 1. Agent Lifecycle

### 概要

Agent の実行状態を、CLI、Web、GUI、A2A、Auto-Pilot で共通化します。

```text
CREATED
  ↓
RUNNING
  ↓
WAITING_TOOL
  ↓
RUNNING
  ↓
COMPLETED
```

異常系として、次の状態も統一的に扱います。

```text
FAILED
CANCELLED
TIMEOUT
PAUSED
```

### 実装対象

- `src/uagent/runtime/lifecycle.py`
- Agent 状態の enum と遷移表
- `start()`、`pause()`、`resume()`、`cancel()`、`wait()`
- cancellation と timeout の統合
- CLI/Web/GUI/A2A の状態通知統合

### 期待効果

- 実行中の Agent を確実にキャンセルできる
- タイムアウトを統一的に扱える
- 各 UI で同じ進捗状態を表示できる
- A2A の状態と実際の処理状態が一致する
- pause / resume の基盤ができる
- Auto-Pilot の継続・停止判定が明確になる

次の不整合を防止します。

```text
Task = CANCELLED
実際のLLM処理 = 継続中
```

## 2. CredentialStore 共通化

### 概要

OAuth token、refresh token、Provider API key、MCP credential、A2A credential、外部 API key を統一的に管理します。

### 推奨インターフェース

```python
class CredentialStore(Protocol):
    def get(self, name: str) -> Credential | None:
        ...

    def set(self, name: str, credential: Credential) -> None:
        ...

    def delete(self, name: str) -> None:
        ...
```

### 保存先の優先順位

```text
OS Secret Store
    ↓
Encrypted Store
    ↓
Environment
```

### 期待効果

- 秘密情報の保存先を統一できる
- Windows Credential Manager、macOS Keychain、Linux Secret Service へ拡張できる
- OAuth token と Provider API key の扱いが一貫する
- ログへの秘密情報漏洩を防ぎやすくなる
- token の期限切れ、refresh、削除を共通化できる
- Provider ごとの認証実装の重複が減る

将来的には、次のような CLI 操作へ拡張できます。

```text
uag credential list
uag credential set openai
uag credential remove github
```

## 3. SQLite TaskStore

### 概要

InMemory 中心の TaskStore を抽象化し、まず SQLite による永続化を追加します。

```text
TaskStore
├── InMemoryTaskStore
└── SQLiteTaskStore
```

Redis は、SQLite の導入後に必要性を確認して検討します。

### 期待効果

- プロセス再起動後もタスク履歴が残る
- 失敗したタスクを確認できる
- A2A の task history を保存できる
- Web で過去の実行履歴を表示できる
- checkpoint / recovery の基盤になる
- 監査ログとして利用できる

将来的には、次のような操作へ拡張できます。

```text
uag task list
uag task show <task-id>
uag task resume <task-id>
```

## 4. 構造化 Observability の全境界適用

### 概要

既存のイベントログを、Agent、Task、LLM、Tool、OAuth、Credential の全境界へ拡張します。

### 共通フィールド

```text
agent_id
session_id
task_id
tool_call_id
event_id
event_code
timestamp
provider
duration_ms
status
error_type
```

### イベント例

```text
agent.created
agent.started
agent.waiting_tool
agent.completed
agent.failed
agent.cancelled
agent.timeout
task.resumed
credential.accessed
oauth.started
oauth.completed
oauth.failed
tool.dispatch
tool.completed
```

### 期待効果

- どの処理で遅延したか分かる
- どのツールが失敗したか分かる
- Provider ごとのエラー率を比較できる
- Web、A2A、CLI の処理を同じ ID で追跡できる
- OAuth や credential 関連の失敗を調査できる
- 再現しにくい問題を解析できる

## 5. Enterprise Policy Engine

### 概要

現在の ToolPolicy を拡張し、Provider、Tool、MCP、Skill、外部ドメイン、Credential、Network、Confirmation を組織単位で制御します。

### ポリシー例

```yaml
tools:
  shell:
    action: deny
  file_delete:
    action: confirm

providers:
  openai:
    action: allow

mcp_servers:
  - https://trusted.example.com

network:
  default: deny
```

### 期待効果

- 組織単位のセキュリティルールを適用できる
- ユーザーごとに権限を変えられる
- 危険な Tool や MCP を一括拒否できる
- 外部送信や IoT 操作に確認を強制できる
- Skill / Plugin の権限管理へ拡張できる
- 監査やコンプライアンスに対応しやすくなる

## 実装ロードマップ

> 凡例: `[x]` はリポジトリ内に実装とテストがある項目です。`[ ]` は未実装、または対象範囲の一部に留まる項目です。

### Phase A: Runtime 安定化

- [x] Agent Lifecycle (`src/uagent/runtime/lifecycle.py`)
- [x] Lifecycle と cancellation の統合 (`src/uagent/runtime/execution.py`)
- [ ] Lifecycle event の追加

### Phase B: 認証・タスク基盤

- [x] CredentialStore Protocol (`src/uagent/auth/credential_store.py`)
- [x] OAuth / Provider / MCP の統合（Provider・MCP OAuth・A2A は共通 CredentialStore を既定利用。環境変数・既存 TokenStore への後方互換フォールバックあり）
- [x] Secret access logging (`credential.accessed` / `credential.stored` / `credential.deleted`)
- [x] TaskStore Protocol (`src/uagent/a2a/task_store.py`)
- [x] SQLiteTaskStore (`src/uagent/a2a/task_store.py`)
- [x] restart recovery (`docs/RESTART_RECOVERY.md`; 実行中タスクを安全に FAILED 化)

### Phase C: 観測性・ポリシー

- [x] structured observability の全境界適用（CLI / Web / GUI / A2A / LLM / OAuth / Tool）
- [x] trace / duration / correlation ID（event_id / correlation_id / duration_ms / tool_call_id）
- [x] Enterprise Policy Engine (`src/uagent/tools/enterprise_policy.py`)
- [x] Skill / Plugin permission (`EnterprisePolicy` + runtime plugin loading)
- [x] MCP / network allowlist (`EnterprisePolicy`)

### Phase D: 高度化

- [x] Checkpoint / Recovery (`TaskStore.save_checkpoint` / `load_checkpoint`)
- [x] DAG-based Tool Scheduler (`src/uagent/runtime/dag_scheduler.py`)
- [x] Distributed A2A (`RemoteAgentRuntime` over A2A)
- [x] Multi-Agent orchestration (`runtime.multi_agent`)
- [x] Remote Agent Runtime (`runtime.remote_agent`)

> 注記: etcd / ZooKeeper 相当の本格的な consensus、ネットワーク分断耐性、OpenTelemetry の完全導入は、外部基盤を必要とする別スコープです。現行実装は共有ファイル lease と A2A の認証済み task / checkpoint / SSE 同期を提供します。

## 現時点で後回しにする項目

次の項目は重要ですが、基盤が固まる前に着手すると再設計が発生しやすいため、後回しにします。

- Redis TaskStore
- OpenTelemetry の本格導入
- Plugin sandbox の完全実装

## 全体的な改善効果

改善後は、各 UI が個別に状態・ログ・認証を管理するのではなく、共通 Agent Runtime を利用します。

```text
CLI
Web
GUI
A2A
  │
  ▼
共通 Agent Runtime
  ├── Lifecycle
  ├── Cancellation
  ├── TaskStore
  ├── CredentialStore
  ├── Policy Engine
  └── Observability
```

その結果、uag は次の能力を持つようになります。

- 入口が増えても挙動がぶれない
- キャンセルや失敗処理が正確になる
- 再起動や復旧に強くなる
- 認証情報を安全に管理できる
- 問題の原因を追跡できる
- 新機能追加時の重複実装が減る
- 企業向けの制御を追加しやすくなる

> **「動く」だけでなく、「止められる・再開できる・追跡できる・安全に制御できる」Agent Runtime にすることが目標です。**

## I18N 注意事項

I18N は表示文言だけでなく、Agent 実行コンテキストの一部として扱います。

- 非同期処理では `contextvars` を使ってロケールを伝播する
- CLI、Web、GUI、A2A の入口でロケールを確定する
- ユーザー向けメッセージを直接ハードコードしない
- ログ・イベントコード・API の状態値はローカライズせず、安定した機械可読値を使用する
- 翻訳キーを追加・変更した場合は、各言語の未翻訳・プレースホルダー不一致を確認する
- 技術用語、Provider 名、Tool 名、イベントコード、API フィールド名は原則として翻訳しない
- 非対話型実行、エラー処理、キャンセル処理でもロケールを失わない
- README や設計文書を更新する場合は、各国語版との同期要否を確認する

## TDD 開発方針

今後の実装は、原則としてテスト駆動開発（TDD）で進めます。

```text
Red    → 失敗するテストを先に追加
Green  → テストを通す最小限の実装
Refactor → 重複・責務・型・可読性を改善
```

### 実装単位ごとの手順

1. 要件と受入条件をテストケースへ分解する
1. まず失敗する単体テストまたは統合テストを追加する
1. 最小限の実装でテストを成功させる
1. I18N、エラー、キャンセル、権限境界を含む回帰テストを追加する
1. リファクタリング後に対象テストと全体テストを実行する
1. `python scripts/acceptance_check.py` が `acceptance: OK` になることを確認する
1. 仕様変更や設計判断を本ドキュメントまたは `ARCHITECTURE.md` に追記する

### TDD の完了条件

- 新しい動作に対応するテストが先に存在する
- 正常系だけでなく、異常系・境界値・キャンセル・ロケールを検証する
- 外部 API や OAuth は実通信に依存しないテストも用意する
- Tool Safety と confirmation の拒否経路を検証する
- 既存テストを壊していない
- import graph、ruff、全体受入チェックが成功する

## 関連文書

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [README_AUTO.md](README_AUTO.md)
