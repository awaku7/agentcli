# UAG 新アーキテクチャ

## 目的

他のエージェントの有用な設計を UAG に取り入れる。ただし、UAG に既に存在するスキル、メモリ、サブエージェント、MCP、タイマー、シークレット、コード解析、テスト機能は再実装しない。

本設計の優先順位は次のとおり。

Session Storeは現在、SQLiteを既定として有効化する。従来動作が必要な場合は環境変数でJSONLまたはdualへ切り替える。

```env
UAGENT_SESSION_STORE=1
UAGENT_SESSION_BACKEND=sqlite
# Unset: user state directory/sessions/sessions.sqlite3
UAGENT_SESSION_STORE_PATH=
UAGENT_MEMORY_BACKEND=sqlite
UAGENT_MEMORY_DB=
```

`UAGENT_SESSION_STORE` は未設定時も有効で、`0`/`false` で無効化できる。`UAGENT_SESSION_BACKEND` の既定値は `sqlite`、保存先未指定時はユーザー状態ディレクトリ配下を使用する。

1. 既存機能を統合する
1. 権限と安全性を一貫させる
1. セッションと成果物を再利用可能にする
1. 必要な機能だけを段階的に追加する

## 現状の再利用マップ

| 概念 | UAG の既存機能 | 方針 |
| --- | --- | --- |
| スキル | `skills_*`, `plugin_manage` | Skill Manager の下位実装として再利用 |
| 長期記憶 | `add_long_memory`, `get_long_memory` | 長期層として再利用 |
| サブエージェント | `run_sub_agent`, `run_sub_agent_chain` | Orchestrator として再利用 |
| MCP | `mcp_*`, `handle_mcp_v2` | MCP Adapter として再利用 |
| タイマー | `set_timer` | 永続 Scheduler へ拡張 |
| バッチ | `batch_state` | Task/Artifact 状態管理へ統合 |
| 認証情報 | `secrets`, `get_env` | Credential Manager として再利用 |
| 品質・安全性 | `security_scan`, `run_tests`, `lint_format` | Skill/Plugin の検査フックとして再利用 |
| コード解析 | `code_map`, 各種 `*2idx` | 開発タスクの標準ツールとして再利用 |

## 目標アーキテクチャ

```text
Entry Points: CLI / GUI / Web / A2A
                    |
              Conversation Manager
                    |
       +------------+-------------+
       |                          |
   Session Store              Policy Engine
       |                          |
 Memory Manager             Tool Router
       |                          |
 Skill Manager       Sub-Agent Orchestrator
       |                          |
 Provider Registry          MCP Adapter
       |
 Scheduler / Task Queue
       |
 Artifact & Workspace Manager
```

全エントリーポイントは同じ Conversation Manager、Policy Engine、Session Store を共有する。CLI 専用の実装を GUI/Web/A2A に複製しない。

## 追加コンポーネント

### 1. Session Store

長期記憶とは別に、会話と実行履歴を保存する。

最初の実装は SQLite + FTS5 とする。

```text
sessions
messages
turns
 tool_calls
artifacts
session_summaries
```

最低限の API：

```text
create_session(project, entry_point)
append_message(session_id, role, content)
record_tool_call(session_id, tool, args_hash, result_ref, status)
search_sessions(query, project=None, limit=20)
get_session_summary(session_id)
```

保存対象は、会話本文、ツール名、実行状態、成果物参照、要約とする。秘密情報や完全な認証情報は保存しない。

### 2. Memory Manager

記憶を3層に分ける。

```text
短期: 現在の LLM コンテキスト
セッション: 今回の作業、判断、失敗、成果物
長期: ユーザー設定、プロジェクト方針、再利用知識
```

既存の長期メモリ API は長期層として維持する。セッション終了時に、候補だけを抽出し、長期保存は承認または高信頼ルールを通す。

### 3. Skill Lifecycle

既存の Skill 機能を次の状態モデルで包む。

```text
draft -> reviewed -> enabled -> improved -> deprecated
```

スキルのメタデータ：

- 使用回数
- 成功/失敗回数
- 最終使用時刻
- 必要ツールと権限
- 依存関係
- セキュリティ検査結果
- 対象プロジェクト

自動生成スキルは即時有効化しない。まず `draft` に保存し、`security_scan` と人間またはポリシーによるレビューを通す。

### 4. Policy Engine

全ツール呼び出しを、入口にかかわらず同じポリシーで判定する。

```text
none
read_only
propose_only
write
admin
```

ルール：

- 子エージェントは親の権限を超えられない
- スキルは宣言した権限だけを要求する
- 危険操作は明示確認を必要とする
- 作業ディレクトリを越えるファイル操作を拒否する
- ネットワーク、シークレット、外部送信を個別に制御する
- すべての判定結果を Session Store に記録する

既存ツールの確認処理を置き換えるのではなく、Policy Engine を共通の前段に置く。

### 5. Provider Registry

既存の UAG プロバイダー実装を登録型に整理する。

```text
provider
model
capabilities
credential_source
cost_hint
context_limit
routing_policy
```

認証情報は次の2つを区別する。

```text
他のエージェントに明示設定済み
環境に偶然存在するだけ
```

後者を自動利用・自動課金対象にしない。モデル選択画面にも明示設定済みのプロバイダーを優先表示する。

### 6. Durable Scheduler

既存の `set_timer` を置き換えず、永続ジョブを追加する。

```text
Scheduler -> Task Queue -> Worker -> Result Store -> Notification
```

必要な属性：

- cron/interval
- timezone
- retry policy
- timeout
- target entry point
- notification destination
- last run / next run
- idempotency key

UAG が停止しても登録を失わない。重複実行防止と失敗時の状態保存を必須とする。

### 7. Artifact & Workspace Manager

バッチ、サブエージェント、コード変更の成果物をセッションから参照可能にする。

成果物の例：

- パッチ
- レポート
- テスト結果
- スクリーンショット
- 生成ファイル
- Git worktree の参照

Git worktree は後期フェーズで追加し、まずは既存の作業ディレクトリ制御と成果物参照を実装する。

## 採用しないもの

初期段階では以下を導入しない。

- 他のエージェント の巨大な CLI/TUI の移植
- デスクトップUIの再実装
- すべてのメッセージングサービス
- すべての外部実行バックエンド
- trajectory 生成・学習パイプライン
- オプション依存関係の一括インストール

## 段階的実装計画

### Phase 0: 境界の確認

- 既存のメモリ、スキル、タイマー、サブエージェントの API を棚卸し
- 入口別の重複処理を確認
- Session Store の保存禁止項目を定義

### Phase 1: Session Store

- SQLite スキーマ
- セッション開始/終了
- メッセージ・ツール実行記録
- FTS5 検索
- 既存エントリーポイントへの読み取り専用統合

### Phase 2: Policy Engine

- 統一権限モデル
- ツール単位の判定
- 子エージェントへの権限継承
- 監査ログ

### Phase 3: Skill Lifecycle

- スキル状態とメタデータ
- 実行結果の収集
- draft 生成
- 検査・承認フロー

### Phase 4: Provider Registry

- 既存プロバイダーの能力情報
- 明示設定判定
- モデルルーティング

### Phase 5: Durable Scheduler

- 永続ジョブ
- リトライ、タイムアウト、重複防止
- 実行結果と通知

### Phase 6: Artifact/Workspace

- 成果物参照
- worktree連携
- 複数タスクの隔離

## 非機能要件

- 既存の CLI/GUI/Web/A2A の挙動を壊さない
- オフラインでも Session Store を利用できる
- SQLite のロック競合に備える
- 認証情報・トークン・Cookieを会話履歴に保存しない
- すべての新機能を無効化できる設定を持つ
- 既存テストに加え、権限境界と再起動復旧をテストする

## 最初の実装単位

最初に実装するのは `SessionStore` だけとする。理由は、メモリ、スキル、スケジューラー、サブエージェント、成果物のすべてが共通して利用でき、他機能との重複を最も減らせるためである。

候補パス：

```text
src/uagent/runtime/session_store.py
src/uagent/runtime/session_schema.sql
src/uagent/runtime/session_redaction.py
tests/test_session_store.py
```

実装後に、CLIからのセッション開始・メッセージ保存・ツール記録・検索を対象にした小さな統合テストを追加する。

## TDD 実装方針

新規コンポーネントは、原則として Red -> Green -> Refactor の順で実装する。機能を先に作ってからテストを追加する方式は採用しない。

### TDD の基本サイクル

1. 失敗する最小テストを書く
1. テストを実行し、失敗理由を確認する
1. テストを通す最小限の実装を行う
1. 関連テストを含めて実行する
1. 重複・責務・命名を整理する
1. リグレッションテストを追加して次のケースへ進む

### Phase 1 のテスト先行項目

`SessionStore` では、実装前に以下をテストとして定義する。

プロジェクト識別子は、長い絶対パスではなく作業ディレクトリ名を使用する。たとえば `F:\KAIHATSU\agentcli` は `agentcli` として記録する。

- セッションを作成できる
- セッションIDが一意である
- メッセージを順序どおり保存・取得できる
- ツール呼び出しを成功・失敗・タイムアウト付きで記録できる
- 同じ記録を二重登録しても壊れない
- セッションを再起動後に読み出せる
- FTS5で本文と要約を検索できる
- プロジェクト単位で検索結果を絞り込める
- 認証情報、トークン、Cookieが保存結果から除去される
- SQLiteの一時的なロックに対して安全に扱える
- 不正なセッションIDや破損データを適切に拒否する

### テスト層

```text
Unit tests
  └── redaction, schema, repository, search
Integration tests
  └── SessionStore + SQLite + runtime lifecycle
Entry-point tests
  └── CLI / GUI / Web / A2A の共通記録
Regression tests
  └── 発見した不具合を再発防止ケースとして固定
```

### 以降のコンポーネントも同じ順序で実装する

- Policy Engine：拒否・確認・許可の境界を先にテストする
- Skill Lifecycle：状態遷移と不正遷移を先にテストする
- Provider Registry：明示設定と環境変数だけの状態を区別するテストを書く
- Durable Scheduler：再起動、重複実行、リトライ、タイムアウトを先にテストする
- Artifact Manager：パス境界、成果物参照、削除・隔離を先にテストする

### TDD の完了条件

各機能は、次を満たしてから次のPhaseへ進む。

- 正常系・異常系・境界値のテストがある
- セキュリティ境界のテストがある
- 既存UAGのテストがすべて通る
- CLI/GUI/Web/A2Aの共通動作に差異がない
- テストが実装詳細ではなく公開APIと観測可能な挙動を検証している
- 失敗テストを再現できるリグレッションケースが残っている

### 実行コマンド

```bash
pytest -q tests/test_session_store.py
pytest -q tests/test_session_store.py tests/test_runtime_*.py
python -m py_compile src/uagent/
python -m ruff check src tests
```
