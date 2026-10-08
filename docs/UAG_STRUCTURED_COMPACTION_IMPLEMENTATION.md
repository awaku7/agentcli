# UAG Structured Compaction 実装計画・作業記録

## 1. 目的

[`UAG_STRUCTURED_COMPACTION_DESIGN.md`](./UAG_STRUCTURED_COMPACTION_DESIGN.md) の設計を、実装可能な PR 単位に分け、進捗・判断・変更箇所・検証結果を継続して記録する。

この文書は設計書の代替ではない。設計上の契約・用語・受け入れ条件は設計書を正本とし、本書には実装計画と実施した作業の事実を記録する。設計変更が必要になった場合は、根拠と影響を本書に記録したうえで設計書も更新する。

## 2. 運用ルール

- 実装前に対象コード、既存データモデル、永続化方式、テスト構成を調査し、実ファイルへの対応を「コード対応表」に記入する。
- 完了チェックは、コード変更だけでなく必要なテスト・レビューが終わった後に付ける。
- 実施していないテストや未確認の挙動は「未実施」「未確認」と明記する。
- 実装上の判断、設計との差異、既知の制約は「判断・課題ログ」に日付とともに追記する。
- 各作業セッションの終了時に「現在の状態・次の作業」を更新し、別セッションから再開できるようにする。
- 設計・実装変更と無関係な Markdown の整形（区切り線、コードフェンス、リスト番号など）を同じコミットに混ぜない。必要な整形は別コミットに分け、レビュー対象の差分を小さく保つ。

## 3. 現在の状態

- **全体状態:** 実装着手前
- **基準設計:** `docs/UAG_STRUCTURED_COMPACTION_DESIGN.md`
- **現在のフェーズ:** PR 1 のコード調査・スコープ確定
- **設計書の再レビュー:** 明確化事項を設計書へ反映済み（2026-10-08）
- **コード調査:** 未実施
- **実装:** 未実施
- **テスト:** 未実施
- **次の作業:** 既存の AgentState、SessionStore、会話圧縮、Artifact、Context Runtime の実装箇所とテストを調査し、コード対応表を埋める。

## 4. フェーズ計画

### PR 1 — Structured Compaction Record

この段階では圧縮境界アルゴリズムを大きく変更せず、構造化レコード、状態更新契約、および検証の基礎を実装する。PR 1 は範囲が広いため、以下の小さな順序で実装・テスト・レビューを進める。各段階の完了を確認してから次へ進み、一度に全項目を変更しない。PR 数を機械的に増やす必要はなく、独立した差分としてレビュー可能な単位を優先する。

**PR 1 の実装順序（チェックポイント）**

1. **調査・モデル**：既存コード対応表を確定し、CompactionRecord / GoalDelta と validation の最小モデルを追加。既存の圧縮動作は変えない。
2. **出典・観測情報**：`SourceRef`、`session_seq`、Goal association、DeterministicDelta を追加し、単体テストで契約を固定する。
3. **永続化・Reducer**：Checkpoint / AgentState / revision / operation ID の一括更新（失敗時はすべて取り消す）、競合検出、二重適用防止を実装・検証する。永続化を有効にする前にこの整合性を満たす。
4. **既存経路との接続**：Narrative / legacy summary projection、fallback、最小 telemetry を追加し、回帰テストを通す。

各チェックポイントは必要な最小限のファイルだけ変更し、既存動作を維持できない途中状態を main にマージしない。

- [ ] 既存実装とデータフローを調査し、コード対応表を作成
- [ ] CompactionRecord / GoalDelta / DecisionRecord / ConstraintRecord / FactRecord のモデルを追加
- [ ] Goal association の三状態（既存 Goal、新規 Goal、曖昧）と stable `goal_id` の割当契約を実装
- [ ] typed / scoped `SourceRef` と保存時・再取得時の認可検証を実装
- [ ] `session_seq` の採番、source range / watermark、legacy ordering backfill policy を実装
- [ ] Goal association 解決を明示的根拠に制限し、ambiguous delta の resolution lineage を実装
- [ ] DeterministicDelta と dimension ごとの tracking coverage（complete / partial / unavailable）を実装
- [ ] SessionStore の Checkpoint 保存、stable operation ID、expected revision guard、AgentState 更新を atomic transaction 化
- [ ] comparison-only が AgentState revision を更新しないことを実装
- [ ] AgentState Reducer の不変条件、再適用防止、idempotency を実装
- [ ] Narrative Continuation と legacy summary の互換 projection を実装
- [ ] schema validation と失敗時 fallback を実装
- [ ] 基本 telemetry を追加
- [ ] 単体テストを追加・実行し、結果を検証記録に記載
- [ ] 設計書の PR 1 範囲および関連 acceptance criteria をレビュー

**完了条件:** AgentState が唯一の authoritative materialized current state であり、CompactionRecord が immutable な delta / evidence として扱われる。失敗時に Raw History が保持される。

### PR 2 — Safe Boundary / Split Turn

- [ ] Logical Turn の parser / 表現を実装
- [ ] tool call と対応する結果、および parallel tool result をまたがない safe cut point を実装
- [ ] 1 turn が budget を超える場合の Split-Turn 処理を実装
- [ ] oversized tool result の Artifact-first 処理を実装
- [ ] prefix / suffix の復元可能性を検証
- [ ] boundary、split、failure fallback のテストを追加・実行

### PR 3 — Context Runtime Integration

- [ ] CompactionRecord を ContextCandidate として公開
- [ ] Scoring / Decision / Budget と連携
- [ ] ActiveContextBuilder および Provider Projection へ接続
- [ ] 必要な場合に source refs から retrieval / rehydration
- [ ] checkpoint の重複投入を防ぎ、古い checkpoint を再取得可能にする
- [ ] runtime 統合テストと provider-neutral な検証を追加・実行

### PR 4 — Sub-Agent / Auto-pilot Handoff

- [ ] HandoffRecord と caller-bounded projection を実装
- [ ] Main → Sub-Agent の最小権限 context projection
- [ ] Sub-Agent → Main の compact return と provenance
- [ ] Auto-pilot の checkpoint / resume を実装
- [ ] provider / model handoff のテストを追加・実行

### PR 5 — Client / Session Revision Safety

- [ ] principal / workspace / client_instance / session の scope を確認・実装
- [ ] immutable checkpoint lineage と Client Instance provenance を検証
- [ ] PR 1 の revision guard に対する複数 Client の conflict classification / response を統合
- [ ] stale request の latest AgentState / history reload と semantic rebase を実装・検証
- [ ] PR 1 の atomic transaction / idempotency 基盤を使った process restart / retry recovery を end-to-end 検証
- [ ] authorization-aware retrieval / rehydration と schema capability negotiation を検証
- [ ] CLI と GUI 等、複数 Client が同一 Session を更新する統合テストを追加・実行

## 5. コード対応表

コード調査後に、設計概念と実際のモジュール・型・テストを対応づける。未確認の欄を推測で埋めない。

| 設計上の責務 | 実装ファイル／型／関数 | 既存・新規 | 状態／メモ |
|---|---|---|---|
| AgentState / reducer | 未調査 | 未確認 | |
| SessionStore / revision | 未調査 | 未確認 | |
| Raw History / rolling summary | 未調査 | 未確認 | |
| Tool call / result / logical turn | 未調査 | 未確認 | |
| Artifact / bounded retrieval | 未調査 | 未確認 | |
| ContextCandidate / Decision / Budget | 未調査 | 未確認 | |
| ActiveContextBuilder / Provider Projection | 未調査 | 未確認 | |
| Sub-Agent / Auto-pilot handoff | 未調査 | 未確認 | |
| 関連テスト | 未調査 | 未確認 | |

## 6. 受け入れ条件の追跡

詳細は設計書の「Acceptance Criteria」を参照する。各項目は、該当実装と検証の根拠が確認できた段階で更新する。

| # | 条件の要約 | 状態 | 根拠（コード／テスト／記録） |
|---:|---|---|---|
| 1 | AgentState が唯一の current state 正本である | 未着手 | |
| 2 | 複数 Goal を stable `goal_id` と GoalDelta で追跡し、曖昧な関連付けで不要な分裂を起こさない | 未着手 | |
| 3 | Decision / Constraint の supersede・revert と item-level provenance を保持する | 未着手 | |
| 4 | tool call / result を圧縮境界で破壊しない | 未着手 | |
| 5 | ファイル変更と execution metadata を DeterministicDelta として保持する | 未着手 | |
| 6 | Tool Result を authorization-aware に Artifact から再取得できる | 未着手 | |
| 7 | Checkpoint を ContextCandidate として扱い、source refs から rehydration できる | 未着手 | |
| 8 | provider / model を切り替えても provider-neutral checkpoint を利用できる | 未着手 | |
| 9 | structured compaction 失敗時に Raw History を保持して fallback する | 未着手 | |
| 10 | Sub-Agent handoff で provenance / scope semantics を再利用する | 未着手 | |
| 11 | CLI / GUI / Browser tab を共通の Client Instance model で扱う | 未着手 | |
| 12 | stale `base_revision` を検出し silent overwrite しない | 未着手 | |
| 13 | revision conflict 後に最新状態を取得し、安全に再評価できる | 未着手 | |
| 14 | crash 後に最後の committed revision から二重適用なしで resume できる | 未着手 | |
| 15 | retrieval / rehydration 時に現在の authorization を再評価する | 未着手 | |
| 16 | compaction / fallback / client / revision / conflict を telemetry で追跡できる | 未着手 | |

## 7. 検証記録

テストは実行したコマンド、対象、結果を記録する。失敗した場合は失敗内容と対応も残す。

| 日付 | フェーズ | 検証内容／コマンド | 結果 | 備考 |
|---|---|---|---|---|
| 未実施 | — | — | 未実施 | 実装着手前 |

### Provider Matrix

| Provider | structured generation | validation / fallback | 状態／備考 |
|---|---|---|---|
| OpenAI Responses | 未実施 | 未実施 | |
| Anthropic | 未実施 | 未実施 | |
| Gemini | 未実施 | 未実施 | |
| OpenAI-compatible local provider | 未実施 | 未実施 | |

## 8. 判断・課題ログ

| 日付 | 種別 | 判断／課題 | 根拠・影響 | 状態 |
|---|---|---|---|---|
| 初期記録 | 運用 | 本書を実装計画および継続作業の記録先として作成。設計上の正本は設計書とする。 | 実装進捗と検証根拠を設計仕様から分離して追跡する。 | 採用 |
| 初期記録 | スコープ | 実装を PR 1〜5 に分割し、PR 1 では boundary algorithm を大きく変更しない。 | 設計書の段階導入方針に従い、schema と boundary semantics の変更を同時にしない。 | 採用 |
| 2026-10-08 | 設計判断 | PR 1 に source sequence / typed SourceRef / minimal atomic persistence を含め、PR 5 は multi-client rebase / integration に集中する。 | Checkpoint、AgentState、revision、idempotency の一貫性を基礎 PR で保証する。詳細は設計書 §6.1 / §23 / §26。 | 採用 |
| 2026-10-08 | 設計判断 | ambiguous Goal は自動適用・自動 merge せず、明示的な解決 delta を追記する。 | Goal 分裂・誤統合を防ぎ、元 Checkpoint の immutable lineage を維持する。設計書 §6.2。 | 採用 |
| 未記録 | 課題 | 既存コード上の実装位置、migration 方針、テスト実行方法。 | コード調査後に追記する。 | 未調査 |

## 9. 作業セッション記録

各作業セッションの終了時に、実施内容と次の一手を一行以上追加する。

| 日付 | 実施内容 | 変更ファイル | 検証結果 | 次の作業 |
|---|---|---|---|---|
| 初期記録 | 設計書を基に、本実装計画・進捗記録を作成。実装コードの調査・変更・テストは未実施。 | `docs/UAG_STRUCTURED_COMPACTION_IMPLEMENTATION.md` | 未実施 | 既存コードを調査し、PR 1 のコード対応表と最小スコープを確定する。 |
| 2026-10-08 | PR 1 の実装順序を4チェックポイントに分け、無関係な Markdown 整形を避ける運用を追記。実装コードは変更せず。 | `docs/UAG_STRUCTURED_COMPACTION_IMPLEMENTATION.md` | 文書更新のみ。テスト未実施。 | PR 1 のコード対応表を埋め、最初のチェックポイントから着手する。 |
| 2026-10-08 | 設計書を再レビューし、8項目の仕様境界を明確化して設計書・実装記録を更新。 | `docs/UAG_STRUCTURED_COMPACTION_DESIGN.md`, `docs/UAG_STRUCTURED_COMPACTION_IMPLEMENTATION.md` | ドキュメントレビュー・編集のみ。コード調査とテストは未実施。 | PR 1 のコード調査で既存 SessionStore / DB schema / revision API / schema version を照合する。 |

## 10. 設計書の明確化・再レビュー（2026-10-08）

### 総評

設計の基本方針は一貫しており、実装可能。AgentState を唯一の materialized current state とし、CompactionRecord を immutable delta / evidence とすること、決定論的情報と LLM による意味抽出を分離すること、失敗時に Raw History を保護することを維持する。

### 再レビュー論点と処置

1. **PR 1 / PR 5 の責務境界 — 設計反映済み。** PR 1 に SessionStore の atomic commit、stable operation ID、expected revision guard を含め、PR 5 は複数 Client の識別、conflict response、semantic rebase、end-to-end recovery を統合する。設計書 §23.2.1 / §26。
1. **Goal association — 設計反映済み。** ambiguity は候補 Goal に適用せず、タイトル類似度だけでは解決しない。明示確認等で解決する際は元 Checkpoint を変更せず、新しい resolution delta と provenance を追記する。自動 Goal merge は初期版では行わない。設計書 §6.2。
1. **source refs / source range — 設計反映済み。** typed / scoped な `SourceRef`、Runtime による ID 発行と authorization 検証、Session 単調増加 `session_seq`、inclusive source range / end watermark を規定した。設計書 §6.1 / §6.3 / §23.2.1。
1. **DeterministicDelta の観測範囲 — 設計反映済み。** 実際に観測した操作のみを記録し、空リストを「操作なし」と扱わない。coverage を complete / partial / unavailable で区別する。設計書 §6.4 / §11.1。
1. **retention / redaction — 設計反映済み。** 永久保存を約束せず、retention policy と明示的削除を優先し、redaction tombstone と派生 checkpoint の無効化 / purge を規定した。設計書 §3.1 / §23.8。
1. **transaction lifecycle — 設計反映済み。** `application_status` は applied / comparison_only のみ。draft は非永続で、DB rollback なら record も state update も見えない。設計書 §6.1 / §23.4。
1. **既存 SessionStore 前提 — 実装前確認として残る。** 設計書は target architecture として SQLite / SessionStore を指定した。実際の tables、transaction API、WAL、revision、Artifact/event persistence は PR 1 のコード調査で確認する。設計書 §23.2.1。
1. **schema version — 設計反映済み（コード照合待ち）。** payload schema と DB migration version を分離し、structured record v1 を提案した。既存コードで version が既に割当済みなら実装前に調整する。未知 version は model message にせず、安全側で read-only / write refusal とする。設計書 §6.1 / §23.9。

### 現時点の結論

- **設計:** 明確化事項を `UAG_STRUCTURED_COMPACTION_DESIGN.md` に反映済み。設計全体の再作成は不要。
- **実装:** まだ未着手。PR 1 のコード調査を開始できるが、SQLite / SessionStore の設計前提と schema version はコード・DB と照合して確定する。
- **テスト:** 未実施。今回の作業はドキュメント編集のみ。

## 11. 更新履歴

| 日付 | 変更 |
|---|---|
| 初期記録 | 実装計画、フェーズチェックリスト、受け入れ条件追跡、検証・判断・セッション記録欄を作成。 |
| 2026-10-08 | PR 1 を小さな実装チェックポイントに分け、不要な Markdown 整形を避ける方針を追加。 |
| 2026-10-08 | 設計書の再レビュー論点を確定し、設計書と PR チェックリストへ反映。 |
