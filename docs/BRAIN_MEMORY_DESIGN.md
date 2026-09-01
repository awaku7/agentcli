# uag Brain Memory 設計書

## 1. 目的

本設計書は、`uag` に長期記憶・知識Wiki型の外部メモリ機構（仮称 **Brain Memory**）を追加するための設計を定義する。

目的は、過去のセッション、ユーザーの好み、プロジェクト情報、意思決定、外部ソースを、エージェントが必要な範囲と深さで探索できる形に整理することである。

単なる会話ログ保存やベクトル検索だけではなく、以下を満たす知識環境を構築する。

- エージェントが通常のファイル操作で探索できる
- 知識同士の関係をたどれる
- 主張の根拠を確認できる
- 古い情報を更新・削除できる
- 更新内容をステージングして検証できる
- Git履歴で変更を監査できる
- 複数のエージェントやセッションから安全に利用できる
- 記憶を使うほど検索性・正確性が改善する

> 本設計は、Perplexityが公開した「Brain: Agentic Memory as a Knowledge Wiki」の考え方を参考にしつつ、`uag`のローカルファースト、明示的な書き込み確認、セッション永続化、ツール実行モデルに合わせて設計する。

## 2. 設計原則

### 2.1 ファイルシステムを第一のインターフェースにする

記憶は特殊な専用APIだけでなく、エージェントが既に使えるファイル操作で扱えるようにする。

- `read_file`
- `file_grep`
- `search_files`
- `diff_files`
- `git_ops`
- `code_map`

これにより、モデル専用の新しい操作体系を最小化し、既存ツールとの組み合わせを可能にする。

### 2.2 検索と検証を分離する

検索で得た情報を、そのまま事実として扱わない。

- 知識ページへのリンク：関連情報を探索するためのエッジ
- 引用リンク：主張の根拠を検証するためのエッジ

情報の「見つけやすさ」と「正しさの確認」を別の操作として扱う。

### 2.3 段階的探索を行う

全記憶を毎回プロンプトへ投入しない。

1. コンパクトなインデックスを提示
1. 質問に関連するページを検索
1. 必要な関連ページをリンクから探索
1. 重要な主張だけ引用元を確認
1. 足りない場合のみ意味検索を実行

これにより、コンテキスト消費と検索コストを抑える。

### 2.4 変更は提案・検証・同期の順に行う

記憶の更新を直接本番領域へ書き込まない。

```text
観察・セッション
      ↓
更新候補の生成
      ↓
staging領域への書き込み
      ↓
構文・参照・意味の検証
      ↓
ユーザーまたはポリシーによる承認
      ↓
本番領域へ同期
      ↓
Git履歴へ記録
```

### 2.5 重要度と鮮度を明示する

すべての情報を同じ重みで扱わない。

- 重要度：低・通常・高・決定的
- 鮮度：作成日時、最終確認日時、失効日時
- 信頼度：根拠の数、根拠の信頼性、意味検証結果
- 状態：active、superseded、deleted、disputed

## 3. 対象範囲

### 3.1 初期リリースの対象

- セッションの要約保存
- ユーザー設定・好みの保存
- プロジェクト・エンティティ・意思決定の知識ページ
- Wikiリンク（`[[...]]`）
- 引用（`[cite:...]`）
- コンパクトなインデックス
- キーワード検索
- オプションの意味検索
- ステージング更新
- 決定的検証
- Git差分・履歴による監査

### 3.2 初期リリースの対象外

- 無制限の自律的な外部サービス書き込み
- 根拠のない自動削除
- 完全自動の事実保証
- すべての過去会話を常時コンテキストへ投入すること
- ベクトルDBへの依存を必須にすること
- 複数ユーザー間での記憶共有
- 個人情報を含む記憶の無制限な外部同期

## 4. ディレクトリ構成

```text
memory/
├── README.md
├── knowledge/
│   ├── index.md
│   ├── entities/
│   │   ├── users/
│   │   ├── people/
│   │   ├── organizations/
│   │   └── systems/
│   ├── projects/
│   ├── preferences/
│   ├── decisions/
│   ├── concepts/
│   └── topics/
├── notes/
│   ├── by-topic/
│   └── inbox/
├── sessions/
│   ├── index/
│   ├── summaries/
│   ├── transcripts/
│   └── evidence/
├── retrieval/
│   ├── manifest.json
│   └── cache/
├── staging/
│   ├── runs/
│   └── current/
├── validation/
│   ├── reports/
│   └── schemas/
├── deletions.md
└── .gitignore
```

### 4.1 `knowledge/`

長期的に利用する統合済み知識を配置する。各ページは原則として1つの対象・概念・プロジェクトを表す。

### 4.2 `notes/`

セッションから抽出した短いメモを配置する。まだWikiページへ昇格していない情報や、一時的な補助情報に使用する。

### 4.3 `sessions/`

原記録とその要約を配置する。知識ページの根拠は、可能な限りここまたは許可済みコネクターを参照する。

### 4.4 `staging/`

Dream相当の更新エージェントが提案する変更を配置する。本番の`knowledge/`を直接変更しない。

## 5. ファイル形式

## 5.1 知識ページ

```markdown
---
id: project:example-project
kind: project
title: Example Project
status: active
importance: high
confidence: 0.86
created_at: 2026-09-01T10:00:00+09:00
updated_at: 2026-09-01T12:00:00+09:00
last_verified_at: 2026-09-01T12:00:00+09:00
owners:
  - person:user
sources:
  - cite:session-20260901-001
  - cite:file-docs/spec.md
tags:
  - example
  - project
---

# Example Project

## 概要

このページはExample Projectの現在の状態を表す。

## 関係

- 所有者：[[entities/people/user]]
- 関連システム：[[entities/systems/example-system]]
- 意思決定：[[decisions/2026-09-01-example-decision]]

## 現在の事実

- 現在の責任者はユーザーである。[cite:session-20260901-001]
- 次回レビューは2026年9月15日を予定している。[cite:file-docs/spec.md]

## 更新履歴

- 2026-09-01：初版作成。[cite:session-20260901-001]
```

## 5.2 セッション要約

```markdown
---
id: session:20260901-001
kind: session_summary
session_id: 20260901-001
started_at: 2026-09-01T09:00:00+09:00
ended_at: 2026-09-01T10:30:00+09:00
summary_version: 1
privacy: private
---

# Session 20260901-001

## 目的

ユーザーのプロジェクト構成を整理する。

## 決定事項

- Example Projectを継続する。[cite:turn-12]

## 抽出候補

- ユーザーはMarkdownを優先する。[cite:turn-18]
- レポートはPDFではなくMarkdownで受け取りたい。[cite:turn-19]

## 未確定事項

- 次回レビュー日の最終確定は未確認。
```

## 5.3 短いノート

```markdown
---
id: note:20260901-004
kind: note
topic: preferences
status: candidate
confidence: 0.72
created_at: 2026-09-01T10:30:00+09:00
source: cite:session-20260901-001
---

ユーザーは、生成した図をPNGよりPDFで受け取ることを好む。[cite:session-20260901-001]
```

## 5.4 削除ログ

削除は物理削除だけに依存せず、論理的な削除記録を残す。

```markdown
# Deletion Log

- `knowledge/preferences/output-format.md`
  - deleted_at: 2026-09-01T13:00:00+09:00
  - reason: ユーザーの明示的な削除依頼
  - requested_by: user
  - replacement: `knowledge/preferences/artifact-format.md`
```

削除ログにより、過去の古い記憶がDream処理で再生成されることを防止する。

## 6. リンクと引用

### 6.1 Wikiリンク

```markdown
[[projects/example-project]]
[[entities/people/user]]
[[preferences/output-format]]
```

Wikiリンクは、知識グラフ上のコンテキストエッジである。

### 6.2 引用

```markdown
[cite:session-20260901-001]
[cite:file-docs/spec.md]
[cite:connector-google-calendar:event-123]
```

引用は、主張が依存する証拠エッジである。引用先は次の形式をサポートする。

- `session-*`：会話セッション
- `file-*`：ローカルファイル
- `connector-*`：許可済み外部コネクター
- `tool-*`：ツール結果
- `decision-*`：過去の意思決定

### 6.3 引用の要件

重要度が高い主張には、少なくとも1つの引用を要求する。

| 重要度 | 引用要件 |
|---|---|
| low | 任意。ただし推測であることを明記 |
| normal | 可能な限り1件以上 |
| high | 1件以上必須 |
| critical | 独立した根拠を2件以上、またはユーザー確認必須 |

## 7. エージェント構成

```text
┌──────────────────────────┐
│ Foreground Agent         │
│ ユーザー要求への応答      │
└────────────┬─────────────┘
             │ index / read / grep / cite
             ▼
┌──────────────────────────┐
│ Local Materialized Set   │
│ 現セッションで利用可能な  │
│ knowledge / notes /       │
│ sessions                  │
└────────────┬─────────────┘
             │ 不足時
             ▼
┌──────────────────────────┐
│ Memory Retrieval Agent   │
│ キーワード・意味検索      │
│ 関連ファイルの取得         │
└────────────┬─────────────┘
             │ 更新候補
             ▼
┌──────────────────────────┐
│ Dream Agent              │
│ セッション要約・知識統合   │
└────────────┬─────────────┘
             ▼
┌──────────────────────────┐
│ Validator / Synchronizer │
│ 検証・承認・Git同期        │
└──────────────────────────┘
```

### 7.1 Foreground Agent

通常のユーザー要求を処理するエージェント。初期コンテキストにBrainのインデックスを受け取り、必要に応じて探索する。

Foreground Agentは、以下を行ってよい。

- 記憶の読み取り
- キーワード検索
- Wikiリンクの追跡
- 引用元の読み取り
- Memory Retrieval Agentの呼び出し
- 更新候補の作成

本番記憶への直接書き込みは、ポリシーで明示的に許可された場合を除き禁止する。

### 7.2 Memory Retrieval Agent

大量の記憶本体を直接Foreground Agentへ投入せず、必要なファイルを検索・取得するサブエージェント。

入力例：

```text
「ユーザーが過去に希望した図の出力形式と、その根拠を探してください。
knowledge、notes、sessionsを横断し、関連ファイルをmaterializeしてください。」
```

出力には次を含める。

- 検索概要
- 取得ファイル一覧
- 重要な候補事実
- 引用
- 信頼度
- 未解決の矛盾

### 7.3 Dream Agent

オフラインまたはスケジュール実行で記憶を整理するバックグラウンドエージェント。

Dream Agentは毎回、既存のBrainを読み取り、差分更新を作成する。ゼロから全記憶を再構築しない。

## 8. Dream処理フロー

### Phase 1: Orient

1. Brainのルートインデックスを読む
1. メモリの対象範囲を確認する
1. 常設指示を確認する
1. 削除ログを確認する
1. 前回実行時刻と処理済みセッションを確認する
1. 停止条件を確認する

### Phase 2: Summarize sessions

1. 前回実行以降に作成・更新されたセッションを列挙
1. 各セッションから目的、決定、好み、重要な事実、未確定事項を抽出
1. セッション要約を作成または更新
1. 個人情報・秘密情報の取り扱いポリシーを適用

### Phase 3: Attach facts to subjects

1. 各候補事実の対象を特定
1. 対象Wikiページを検索
1. 既存記述との重複・矛盾を確認
1. 適切なページへ引用付きで追加
1. 新しい対象なら新規ページ候補を作成

### Phase 4: Update knowledge wiki

1. 変更候補を`staging/runs/<run-id>/`へ出力
1. 変更対象、理由、引用、信頼度を記録
1. 決定的検証を実行
1. 意味検証を実行
1. 承認条件を満たした場合だけ同期
1. Git差分と実行レポートを保存

## 9. ステージングと同期

### 9.1 実行ディレクトリ

```text
staging/runs/20260901T130000Z-abc123/
├── manifest.json
├── proposed/
│   └── knowledge/
├── deleted/
├── validation.json
├── semantic_review.md
└── diff.patch
```

### 9.2 `manifest.json`

```json
{
  "run_id": "20260901T130000Z-abc123",
  "agent": "dream-agent",
  "started_at": "2026-09-01T13:00:00Z",
  "base_revision": "34505c68",
  "source_sessions": ["session-20260901-001"],
  "changes": [
    {
      "path": "knowledge/preferences/output-format.md",
      "operation": "update",
      "reason": "新しいユーザー選好を反映",
      "citations": ["cite:session-20260901-001"],
      "confidence": 0.91
    }
  ],
  "requires_user_confirmation": false
}
```

### 9.3 同期条件

次のいずれかに該当する場合、ユーザー確認を必須とする。

- `critical`情報の追加・変更
- 個人情報の新規追加
- 既存事実との矛盾解消
- 削除または失効
- 複数ユーザーに影響する変更
- 外部コネクター由来の情報
- 信頼度が閾値未満の変更

## 10. 検索設計

### 10.1 初期インデックス

各セッション開始時に、全ページ本文ではなく、次の情報だけを提示する。

- ページパス
- タイトル
- kind
- 重要度
- 更新日時
- タグ
- 主要リンク
- 検索ヒント

例：

```markdown
# Brain Index

- [[projects/example-project]] — active, high, updated 2026-09-01
- [[preferences/output-format]] — active, normal, updated 2026-08-30
- [[decisions/2026-09-01-example-decision]] — active, high

## Search hints

- プロジェクト：`projects/`
- 好み：`preferences/`
- 根拠：`sessions/` と `[cite:]`
```

### 10.2 キーワード検索

最初の検索手段はファイル検索とする。

```text
file_grep("PDF", memory/knowledge memory/notes memory/sessions)
```

### 10.3 意味検索

キーワード検索で候補が不足する場合のみ、意味検索を利用する。意味検索結果には、必ず元ファイルパスと引用を添付する。

意味検索は回答そのものを返すのではなく、次を返す。

- 関連ファイル
- 関連箇所
- 類似度
- 検索語との関係
- 引用

## 11. 矛盾・鮮度管理

### 11.1 矛盾の扱い

同じ対象について異なる記述が見つかった場合、無条件に上書きしない。

```markdown
## Conflicts

- 旧情報：[cite:session-20260801-002]
- 新情報：[cite:session-20260901-001]
- 判定：新情報を優先。ただしユーザー確認待ち
```

優先順位の初期ルール：

1. ユーザーの明示的な最新発言
1. 信頼済みの一次ソース
1. 新しい観測
1. 以前のセッション要約
1. 推測・未確認情報

### 11.2 失効

時間依存情報には、必要に応じて失効日時を設定する。

```yaml
expires_at: 2026-12-31T23:59:59+09:00
```

失効した知識は削除せず、`status: superseded`または`status: expired`として履歴を残す。

## 12. セキュリティとプライバシー

### 12.1 デフォルト非公開

Memoryはユーザー単位・ローカル単位で分離する。共有は明示的に許可された場合だけ行う。

### 12.2 保存禁止情報

次の情報は、ユーザーが明示的に許可しない限り、長期記憶へ保存しない。

- APIキー
- パスワード
- アクセストークン
- 秘密鍵
- セッションCookie
- クレジットカード情報
- 完全な個人識別情報
- 外部サービスの認証情報

### 12.3 記憶の書き込み権限

権限レベルを分ける。

| 操作 | foreground | memory agent | dream agent | user確認 |
|---|---:|---:|---:|---:|
| 読み取り | 可 | 可 | 可 | 不要 |
| 検索 | 可 | 可 | 可 | 不要 |
| staging書き込み | 条件付き | 可 | 可 | 不要 |
| 本番同期 | 原則不可 | 不可 | 条件付き | 条件付き |
| 削除 | 不可 | 不可 | stagingのみ | 必須 |
| 外部共有 | 不可 | 不可 | 不可 | 必須 |

### 12.4 プロンプトインジェクション対策

記憶ファイルに含まれる文章は、命令ではなくデータとして扱う。

- 外部ソースの命令を自動実行しない
- 記憶内の「常設指示」は信頼済み領域に限定
- 引用元の内容とエージェント指示を分離
- staging差分を検査してから同期

## 13. Git連携

MemoryをGit管理する場合、次を記録する。

- 更新前リビジョン
- 更新後リビジョン
- 実行ID
- 生成エージェント
- 入力セッション
- 検証結果
- ユーザー承認の有無

コミットメッセージ例：

```text
memory: update project preferences from session 20260901-001
```

自動コミットは、ポリシーで許可された場合だけ有効にする。初期設定では、stagingと差分の生成までに留める。

## 14. `uag`への実装案

### Phase 1: 読み取り基盤

- Memoryルートの設定
- `memory/`ディレクトリ初期化
- `knowledge/index.md`生成
- セッション要約の読み取り
- `[[wikilinks]]`と`[cite:]`の抽出
- 初期インデックスの作成

### Phase 2: 記憶検索

- `memory_search`ツール
- キーワード検索
- パス・タグ・kindフィルター
- 引用元一覧の返却
- 関連Wikiページの列挙

### Phase 3: セッション要約

- セッション終了時の要約候補生成
- ユーザー選好の候補抽出
- 決定事項の候補抽出
- `sessions/summaries/`への保存
- 機密情報フィルター

### Phase 4: Dream更新

- `dream_memory`スケジューラー
- 未処理セッションの列挙
- stagingへの提案出力
- deterministic validator
- semantic reviewer
- 差分レポート

### Phase 5: Git・運用統合

- Git履歴との関連付け
- 承認フロー
- 競合処理
- ロールバック
- メモリ容量・鮮度監視

## 15. 想定ツール

初期実装では、既存ツールを再利用する。

| 目的 | 利用ツール |
|---|---|
| ファイル読み取り | `read_file` |
| キーワード検索 | `file_grep`, `search_files` |
| 差分確認 | `diff_files`, `git_ops diff` |
| 構文確認 | `mdformat_check` |
| Git確認 | `git_ops`, `git_review` |
| スケジュール | `set_timer` |
| サブエージェント | `run_sub_agent`, `run_sub_agent_chain` |
| バッチ状態 | `batch_state` |
| 秘密情報検査 | `security_scan` |

新規ツールを追加する場合の候補：

- `memory_init`
- `memory_search`
- `memory_index`
- `memory_validate`
- `memory_stage_update`
- `memory_sync`
- `memory_forget`

## 16. 検証仕様

### 16.1 決定的検証

- YAML frontmatterが正しい
- `id`が重複していない
- `kind`が許可値である
- リンク先が存在する、または外部リンクとして明示されている
- 引用形式が正しい
- 削除済みページを参照していない
- Markdownとして解析可能である
- ファイルパスが許可されたMemoryルート内にある
- staging外から本番を直接変更していない

### 16.2 意味検証

- 主張に根拠がある
- 根拠の内容と記述が一致している
- 古い情報を最新情報として扱っていない
- 既存ページとの矛盾が解消または明示されている
- 不要な重複ページを作成していない
- 個人情報や秘密情報を不必要に保存していない

### 16.3 テストケース

1. 新規セッションから要約を生成できる
1. 要約からユーザー選好候補を抽出できる
1. Wikiリンクをたどって関連ページを取得できる
1. 引用からセッションへ戻れる
1. 古い事実と新しい事実を同時に保持できる
1. 削除ログにより削除済み情報の再生成を防げる
1. staging差分が本番へ意図せず反映されない
1. 低信頼度の変更が自動同期されない
1. 機密情報が長期記憶へ保存されない
1. Git差分から変更理由を追跡できる

## 17. 運用・監視

最低限、以下を定期的に確認する。

- 記憶ファイル数
- セッション未処理数
- staging未承認数
- 引用切れ数
- 孤立ページ数
- 古いページ数
- 矛盾状態のページ数
- 平均検索深度
- Memory Retrieval Agentの呼び出し回数
- ユーザーによる記憶訂正・削除回数

## 18. 成功指標

Brain Memoryの有効性は、「保存したファイル数」ではなく、実際の回答品質と運用コストで評価する。

### 品質

- 過去情報に関する回答正解率
- 根拠再現率
- 最新情報の採用率
- 矛盾回答率
- ユーザーによる訂正率

### 効率

- 回答あたりの入力トークン数
- Memory Retrieval Agent呼び出し回数
- 検索から回答までの時間
- 不要なファイル読み取り数

### 安全性

- 根拠なし主張の割合
- 秘密情報の保存件数
- 承認なし本番変更件数
- 削除要求の反映漏れ

## 19. まとめ

Brain Memoryは、会話ログを保存する機能ではなく、エージェントが探索・検証・更新できる知識環境として設計する。

中核となる構成は次のとおりである。

```text
Markdown filesystem
+ knowledge wiki
+ wikilinks
+ citations
+ local materialization
+ retrieval agent
+ Dream background agent
+ staged updates
+ deterministic validation
+ semantic validation
+ Git audit trail
```

`uag`では、まず読み取り・検索・引用追跡を実装し、その後にセッション要約、Dream更新、staging検証、Git同期を段階的に追加する。自律性を高める場合も、ユーザーの記憶を勝手に変更・削除・共有しないことを最優先とする。

## 20. 既存uag基盤との統合契約

### 20.1 配置スコープ

Brain Memoryは、プロジェクト固有データとユーザー共通状態を分離する。

- プロジェクト固有Memory：現在のworkspaceまたはproject root配下の`memory/`
- ユーザー共通状態：`~/.uag/`配下の既存ユーザー状態領域
- セッション正本：既存のSessionStoreおよびセッションDB
- 成果物・派生物：既存のArtifactManagerが管理するworkdir内のartifact領域
- 一時処理：`staging/`および実行単位の一時ディレクトリ

`~/.uag/`はユーザー横断の設定、承認履歴、共通の長期記憶、ジョブ状態などに使用する。一方、プロジェクトの知識やプロジェクト固有の意思決定は、プロジェクト配下のMemoryへ保存する。

Memoryの論理パスは、現在のカレントディレクトリを暗黙に指すのではなく、uagが解決したworkspace/project rootを基準にする。解決後の絶対パスが許可されたルート配下にあることを必ず検証し、`~/.uag`のユーザー状態をプロジェクトMemoryから相対パスで参照しない。

### 20.2 ArtifactManagerとの統合

Brainが生成する要約、検索結果、materialized set、Dream実行レポート、検証結果、差分パッチ、承認パッケージは、原則としてArtifactManagerを介して管理する。

各派生成果物には、可能な限り次のメタデータを付与する。

```yaml
artifact_id: 9f2e...
session_id: session-20260901-001
run_id: 20260901T130000Z-abc123
scope: project
privacy: private
content_hash: sha256:...
created_at: 2026-09-01T13:00:00Z
expires_at: null
```

永続的な知識ページの正本と、一時的なmaterialized setを混同しない。ArtifactManagerの登録に失敗した場合は、本番同期を行わず、再試行可能なエラーとして記録する。

### 20.3 セッション・既存メモリとの関係

会話記録の正本は既存のSessionStoreとする。Brainはセッション全文を無秩序に複製せず、次の派生情報を保持する。

- `sessions/summaries/`：セッション要約
- `sessions/index/`：検索用インデックス
- `sessions/evidence/`：引用解決に必要なメタデータ
- `notes/`：知識ページへの昇格前の候補

各要約には、少なくとも次を保持する。

- `session_id`
- 正本の参照先または`artifact_id`
- workspace/projectスコープ
- 要約バージョン
- 生成モデルまたは実行ID
- 対象となった入力範囲
- privacy分類
- 作成日時と更新日時

既存の長期記憶はユーザーが承認した正式な記憶として扱い、Brainはその整理された知識ビューとして利用する。Brainが候補を発見しても、既存の承認フローを経ずに正式な長期記憶へ昇格させない。

### 20.4 承認フロー

Memoryの承認にはuagの既存承認モデルを再利用し、Brain独自の並行した承認状態を作らない。

承認パッケージには以下を含める。

- 変更対象と差分
- 根拠と引用
- 変更理由
- リスクと影響範囲
- `run_id`
- `base_revision`
- 作成者または生成エージェント
- 有効期限
- ポリシー判定

承認状態は最低限、次をサポートする。

```text
pending → approved → applied
pending → rejected
pending → expired
approved → superseded
```

承認後にbase revision、差分、根拠、ポリシー判定が変わった場合、承認を無効化して再承認する。同期直前にも、競合検査、秘密情報検査、権限検査を再実行する。

## 21. スキーマ契約と引用の再現性

### 21.1 必須frontmatter

知識ページと要約ページでは、次の共通フィールドを必須とする。

```yaml
schema_version: 1
id: project:example-project
kind: project
status: active
scope: project
privacy: private
created_at: 2026-09-01T00:00:00Z
updated_at: 2026-09-01T00:00:00Z
provenance:
  run_id: 20260901T130000Z-abc123
  agent: dream-agent
```

許可される`kind`、`status`、`scope`、`privacy`の値はスキーマで固定する。未知フィールドは読み取り時に保持し、同期時に暗黙に破棄しない。

日時は保存時にはUTCのISO 8601を基本とし、表示時のみユーザーのローカルタイムへ変換する。ID、ファイル名、Wikiリンクの正規化規則もvalidatorで検査する。

### 21.2 再現可能な引用

引用は単なる文字列ではなく、次の情報を持つ証拠メタデータとして扱う。

```yaml
source_id: session-20260901-001
locator: turn-18
retrieved_at: 2026-09-01T13:00:00Z
content_hash: sha256:...
source_scope: session
state: available
```

`locator`には、セッションのturn ID、ファイルの行範囲、JSON Pointer、外部イベントIDなどを指定する。引用元が変更・削除・アクセス不能になった場合は、`stale`または`unavailable`として表示し、主張を自動的に最新情報へ置き換えない。

## 22. 同時実行・競合・リカバリ

各Memory更新は、`run_id`と`base_revision`を持つ独立したトランザクションとして扱う。

同期前に以下を再確認する。

- 対象ファイルのcontent hash
- GitまたはMemoryのbase revision
- 承認パッケージとの一致
- 他の未完了runの有無
- 現在のポリシー判定

同一scopeへの同期は排他制御する。base revisionやファイルハッシュが変化していた場合は、自動上書きせず競合として停止する。

処理途中の状態はmanifestへ記録し、クラッシュ後に次のいずれかを選べるようにする。

- 未完了runを再開
- stagingを破棄
- 差分を手動確認

`run_id`または変更ハッシュを冪等性キーとして利用し、同じ提案が二重適用されないようにする。

## 23. 忘却・削除の伝播

忘却要求は、対象IDをキーに以下の保持先を列挙する。

```text
SessionStore
長期記憶
knowledge
notes
sessions/summaries
sessions/evidence
retrieval/cache
staging
ArtifactManager成果物
Git履歴・バックアップ
```

`deletions.md`は、削除済み情報の再生成を防ぐtombstoneであり、削除対象本文の代替ではない。削除処理は各保持先について、`requested`、`completed`、`unavailable`、`requires_manual_action`を記録する。

Git履歴やバックアップに機密情報が残る場合があるため、次を運用ポリシーとして定義する。

- 履歴を保持する期間
- 履歴書換えまたはリポジトリ再作成の要否
- バックアップの削除方法
- キャッシュの無効化方法
- 削除完了をユーザーへ報告する範囲

## 24. 品質管理上の注意

記憶の蓄積は、品質向上を自動的には保証しない。情報量が増えると、ノイズ、重複、古い記述、誤った一般化、検索コストも増える可能性がある。

したがって、Brainの品質は次の指標で継続的に評価する。

- 根拠付き回答の正解率
- 引用の再現率
- 最新情報の採用率
- 矛盾回答率
- ユーザー訂正率
- 不要な記憶読み取り数
- 検索深度と回答遅延

意味検索の類似度を事実の信頼度と混同しない。類似度は候補発見の指標であり、回答採用には引用、鮮度、スコープ、意味検証を必要とする。

## 25. 実装優先順位の見直し

実装は次の順序を推奨する。

1. 既存SessionStoreと既存長期記憶を正本として明文化
1. Memoryルートと`~/.uag`のスコープ分離
1. 知識ページのfrontmatterと引用スキーマを固定
1. 読み取り、インデックス、キーワード検索を実装
1. セッション要約と候補抽出を実装
1. ArtifactManagerとのメタデータ連携を実装
1. staging、決定的validator、意味検証を実装
1. 競合・クラッシュリカバリを実装
1. Dreamの定期更新を有効化
1. 必要に応じてローカルGit監査を追加

Gitは初期導入の必須条件ではない。最初はローカルファイル、ハッシュ、staging、検証レポートで安全性を確保し、Git連携は監査・ロールバックの追加機能として導入する。

## 26. レビュー時点での決定事項

- Brainは既存の記憶機構を置き換えない
- セッション原文は既存SessionStoreを正本とする
- Brainは整理・探索・引用のための派生知識レイヤーとする
- プロジェクトMemoryとユーザー共通状態を物理的・論理的に分離する
- 一時成果物と正本をArtifactManagerのメタデータで区別する
- 本番knowledgeの更新はstagingと承認を経由する
- 削除は派生物・キャッシュ・履歴への伝播を考慮する
- Git連携は後段でよく、ローカルファイル基盤を先行する
- 自動化の強化よりも、根拠・鮮度・スコープ・監査性を優先する
