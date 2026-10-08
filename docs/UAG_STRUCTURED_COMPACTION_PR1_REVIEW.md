# UAG Structured Compaction — PR 1 初回実装レビュー

- 対象コミット: [`9e926f4b`](https://github.com/awaku7/agentcli/commit/9e926f4b30e1f28a0b5643d283ae4c9c1ad6d2df)
- 記録日: 2026-10-08
- 対象: PR 1 チェックポイント 1〜3（モデル、履歴順序、永続化、Reducer）
- 状態: **指摘対応済み・対象テスト／静的チェック済み**
- 関連: [Issue #200](https://github.com/awaku7/agentcli/issues/200)

## 総評

構造化レコード、session-scoped な順序インデックス、Checkpoint と AgentState の一括保存は、設計に沿った基礎実装となっている。ただし、下記2点はチェックポイント4に進む前に確認・対処する。広範囲のリファクタリングや、PR 5 に予定している semantic rebase の先行実装は求めない。

## P1 — comparison_only が過去 revision の比較を拒否する

**場所:** [`src/uagent/runtime/session_store.py` — `commit_compaction_record()`](https://github.com/awaku7/agentcli/blob/9e926f4b30e1f28a0b5643d283ae4c9c1ad6d2df/src/uagent/runtime/session_store.py#L1760-L1805)

**観察:** `record.base_revision != current_revision` の判定が `applied` と `comparison_only` に共通している。このため、セッションが進んだ後、過去のsource rangeを過去のbase revisionで比較専用に再圧縮すると競合になる。一方、設計では comparison-only は**過去の base snapshot** に対する比較であり、現在の AgentState を更新しない。現実装の `current_row is not None` は過去 snapshot の存在確認にもなっていない。

**対処案:** `applied` の現在head一致検証と `comparison_only` の過去snapshot検証を分離する。過去snapshotを保持していない場合は比較不能を明示して返す。過去状態を復元する新しい大規模機構は、この修正のためだけに導入しない。

**追加テスト:** 現在headが進んだ状態で、過去base revisionを指定する comparison-only が誤って「現在headとの競合」にならないこと。過去snapshotがない場合は明示的に比較不能となり、AgentState と revision は不変であること。

## P2 — legacy AgentState 保存で stale write を検出できない

**場所:** [`src/uagent/runtime/session_store.py` — `save_agent_state()`](https://github.com/awaku7/agentcli/blob/9e926f4b30e1f28a0b5643d283ae4c9c1ad6d2df/src/uagent/runtime/session_store.py#L1525-L1605)

**観察:** `expected_revision=None` の場合、トランザクション内で最新revisionを読み、そのrevisionを条件にして、呼び出し元の古い `state` を保存できる。SQLの `WHERE revision = current_revision` だけでは、呼び出し元が古いsnapshotを持っていたことを検出できない。`structured_compaction` 名前空間の保護は有効だが、それ以外の AgentState 項目の上書きは残る。既存 runtime adapter にrevisionを渡さない呼び出しがある。

**対処案:** PR 1 では、少なくともこの互換経路の制約を明記する。複数クライアントから同一セッションを更新し得る呼び出しには、読み取り時に観測したrevisionを渡す。完全な競合後再評価はPR 5の責務とし、ここでは無理に実装しない。

**追加テスト:** 2つの呼び出し元が同じrevisionを読み、一方が先に保存した後、他方の古い状態の保存が競合として拒否されること（revisionを渡す経路）。互換経路の制約もテストまたは文書に明示する。

## 確認項目

- [x] P1の比較専用・過去snapshotの扱いを修正または仕様上の制約として明確化
- [x] P1の回帰テストを追加
- [x] P2のlegacy保存の競合制約を明記し、必要な呼び出し経路でrevisionを渡す
- [x] P2の2クライアント競合テストを追加
- [x] 対象テストと関連回帰テストを実行
- [x] Black `--check` とRuffを確認
- [x] 修正コミットを本書に追記して再レビュー

## 検証状況

初回レビュー時点ではテスト・Black・Ruffを独立実行していなかった。修正後の対象テストと静的チェック結果は、下記の再レビュー記録に記載する。

## 修正・再レビュー記録

| 日付 | コミット | 対応内容 | 検証結果 |
|---|---|---|---|
| 2026-10-08 | `9e926f4b` | 初回レビュー。P1・P2を指摘 | 修正・再検証待ち |
| 2026-10-08 | `1aaad9d2` | P1: historical base snapshot がない comparison-only を head conflict と区別し、比較不能として拒否。P2: snapshot+revision の同時読み取りを追加し、runtime の更新経路は observed revision を使って保存。revision 省略の legacy 経路には stale-write 制約を明記 | `tests/test_compaction_persistence.py` 17 passed; `tests/test_session_store.py` 28 passed; Python compile 2 passed; Ruff passed; Black `--check` passed |

### 再レビュー所見

- comparison-only は、base revision と現在 revision が一致し、保存済み AgentState snapshot がある場合に限り記録できる。revision が過去の場合は `SessionComparisonUnavailable` を返し、AgentState・revision・checkpoint を変更しない。過去snapshotを復元する機構は追加していない。
- `save_agent_state(..., expected_revision=None)` は互換性のため残しているが、呼び出し元の古いsnapshotを検出できない。複数クライアントが同一セッションを更新する場合は `get_agent_state_snapshot()` で状態とrevisionを一緒に読み、そのrevisionを `expected_revision` に渡す。runtime の `update_agent_state` / `complete_agent_step` はこの経路を使う。
- 修正は `1aaad9d2` にコミットし、対象テストと静的チェックの通過を確認した。

## チェックポイント4レビュー（2026-10-08）

- 対象: [`1b6f1872`](https://github.com/awaku7/agentcli/commit/1b6f18722415378f011a6309b464bc013c3265b6)、[`eccceb7f`](https://github.com/awaku7/agentcli/commit/eccceb7f01025c9c145996ec3b7134d7b666945d)
- 判定: **基礎接続は妥当。PR 1 全体の完了判定は保留。** 以下はレビューで確認した制約・残作業。新たな確定的P1/P2バグの指摘ではない。

### 確認できた点

- `UAGENT_STRUCTURED_COMPACTION=1` の opt-in に限定し、従来経路を既定で維持している。
- `_resolve_source_window()` はセッション内のメッセージとの一意な一致・順序・可用性を検証し、一致できないときは構造化commitを行わない。
- 生成JSONの検証、一度だけの修復、Reducer事前検証、revision付きcommit、失敗時の従来要約／決定的抜粋へのfallbackがある。
- 成功・fallback時とも、opt-in経路ではSQLiteのRaw HistoryおよびJSONLを置換しない。
- process restart後の同一operation再試行、auto-shrink統合、Telemetryに原文を含めないテストが追加された。

### PR 1 完了前の確認事項

1. **実プロバイダ検証:** OpenAI Responses / Anthropic / Gemini / OpenAI-compatible等の実接続を未検証と明記。Fake clientの成功をprovider matrix完了と見なさない。
1. **出典の認可境界:** 現実装は同一sessionのexact message windowに限定。cross-scope authorizationおよびrehydration時の再認可は未接続。現時点で対応済みと記載しない。PR 3担当との境界を設計書に照合する。
1. **投影の欠落（対応済み）:** `project_agent_state()` に簡潔なbudget allocationを追加。共有情報を先に確保し、新規作成Goalを優先、項目を短くboundedにして、複数Goal時に後方Goal・共有制約・narrativeが一括して末尾切り捨てされないようにした。8 Goalの回帰テストで確認。大規模な優先順位機構は追加していない。
1. **安全なfallback（対象ケース確認済み）:** source alignment失敗、構造化生成・repair失敗、revision競合、legacy要約失敗の各経路をテスト。Raw HistoryのavailabilityとAgentState/revision/checkpointの非更新を確認。既存テストに含まれるものは重複追加しない。
1. **範囲管理:** PR 2のsplit-turn/boundary、PR 3のActive Context候補化、PR 5のsemantic rebaseをこの段階に混ぜない。

### 検証について

実装者の記録ではcheckpoint 4対象テスト15件、既存shrink22件、persistence17件、SessionStore28件、session index6件、Black/Ruffが成功。**このレビューではテストを独立実行していない。**

| 日付 | コミット | 対応内容 | 検証結果 |
|---|---|---|---|
| 2026-10-08 | `1b6f1872`, `eccceb7f` | チェックポイント4のコード・追加テストをレビュー。基礎接続を確認し、完了前の制約と確認事項を記録 | コード確認のみ。独立テスト未実施 |

## 実装者への次の作業指示（2026-10-08）

本節をチェックポイント4の対応依頼として扱う。レビューで挙げた事項をすべて新機能として実装する必要はない。**既存のテスト・設計で満たされているかを先に確認し、不足だけを最小限修正する。**

1. **複数Goalの投影:** `project_agent_state()` が長い複数Goalを扱うとき、後方Goal、shared constraints、narrative continuationが文字数上限で失われる挙動を検証する。重要情報の脱落が確認できた場合のみ、簡潔な優先順・上限配分など最小限の改善と回帰テストを追加する。複雑なスコアリング機構は導入しない。
1. **失敗時の不変条件:** source alignment失敗、生成失敗、revision競合、legacy要約失敗を既存テストと照合する。不足ケースだけ追加し、Raw History / AgentState / checkpoint / revisionが意図せず更新されないことを確認する。
1. **実プロバイダ:** 利用可能な範囲で実接続を検証する。実行できないproviderは未検証としてprovider matrixに明記し、Fake clientテストと区別する。認証情報や実環境がないことを理由にテスト成功を推測しない。
1. **後続PRとの境界:** cross-scope authorization / rehydration、Active Context統合、split-turn、semantic rebaseは該当後続PRの責務を確認し、PR 1の未対応事項として正確に記録する。必要以上に先行実装しない。
1. **品質確認:** 対象pytestと関連回帰、Ruff、Black `--check` を実行する。失敗した場合は成功と記録しない。修正コード・テスト・実装記録・本レビューMDを一緒にコミットし、SHAと結果を追記する。

**完了報告の形式:** 対応した項目／仕様上の制約として残した項目／後続PRへ送った項目／実行したテストと結果／コミットSHAを簡潔に記載する。プッシュ後、別レビュー担当が差分を再確認してPR 1の完了可否を判断する。

## チェックポイント4 対応結果（2026-10-08）

- **投影の欠落:** `project_agent_state()` をbounded allocationに変更。共有制約・共有事実・critical context・narrative continuationに予算を確保し、新規作成順のGoalを優先。長い項目を制限し、省略時はAgentStateに完全情報が残る旨を表示する。複数Goalと共有情報を含むテストを追加。
- **失敗時の不変条件:** exact source alignment失敗、構造化JSON/修復失敗、revision conflict、legacy summary失敗からのdeterministic fallbackをテスト。structured success/fallbackともRaw Historyのsession item availabilityを維持し、SQLite message rowsを置換しないことを確認。SQLite再オープン後のoperation retryも検証。
- **統合経路:** opt-in auto-shrinkからgenerator・保存・projectionまでfake OpenAI-compatible clientで通す回帰テストを追加。feature flag OFF時はlegacy経路を通る。
- **認可境界:** SourceRef解決は同一sessionのexact message windowに限定。cross-scope authorizationとrehydration時の再認可は未接続で、対応済みとは扱わない。PR3との責務境界を設計書に照合する。
- **プロバイダー:** fake OpenAI-compatible client以外の実接続は未検証。OpenAI Responses / Anthropic / Geminiの検証完了とは扱わない。
- **判定:** 投影偏りと失敗時のRaw History不変条件への基礎対応は完了。PR1全体の完了判定はprovider matrix、cross-scope authorization / rehydration、full lifecycle review後まで保留。
- **最終検証:** `test_structured_compaction_generation.py` 16件、`test_shrink_llm.py` 22件、`test_compaction_persistence.py` 17件、`test_session_store.py` 28件、`test_session_item_index.py` 6件成功。Ruff / Black `--check` / py_compile（5 files）/ Markdown format check成功。実provider検証は未実施。
- **追加修正コミット:** `0780b5bf` (`fix: preserve multi-goal context in bounded projection`)。

## PR 1 最終スコープレビュー（2026-10-08）

**判定: 条件付きで PR 1 の実装スコープは完了と扱える。ただし本レビューは静的コード・差分・既存テスト記録の確認であり、独立した実行検証・実provider検証は未完了。** feature flagは既定OFFのまま維持する。PR 1を「全機能完成」「本番投入検証済み」とは表現しない。

### PR 1 内で満たした基礎契約

- provider-neutralなCompactionRecord / GoalDelta / typed SourceRef、session sequenceとwatermark、ReducerとAgentStateのcurrent-state正本を追加。
- checkpoint / AgentState / revision / operation IDを一括更新（失敗時はすべて取り消す）。revision競合と再試行の二重適用防止を実装。
- 同一session内のexact source windowに限定した構造化生成、出典検証、一度だけのrepair、bounded summary projection、legacy / deterministic fallbackをopt-inで接続。
- Raw History / JSONLを置換しない方針をコードと対象テストで確認。複数Goalの投影偏りを改善（`0780b5bf`）。
- 実装者の記録: structured generation 16、shrink 22、persistence 17、SessionStore 28、session index 6件成功。Ruff、Black --check、py_compile、Markdown format check成功。レビュー担当は独立実行していない。

### PR 1 の完了条件と区別すべき未検証事項

1. **実provider接続: 未検証。** Fake OpenAI-compatible clientによるテストは実API互換性の証明ではない。PR 1のprovider-neutral保存契約とは分離し、provider matrix実行時に結果を追記する。実接続を試さず「対応完了」と書かない。
2. **end-to-end全ライフサイクル: 部分検証。** SQLite再オープン後のoperation retryはテスト済み。実CLI/実providerを通した再開、並行操作、長期利用は未検証。後続の統合検証で確認する。
3. **SourceRefの権限: 現段階は同一session限定。** cross-scope retrieval/rehydration時の再認可は未実装。PR 3のretrieval接続およびPR 5のclient/principal権限モデルに合わせて実装・検証する。認可を伴うcross-scope参照をPR 1から有効化しない。
4. **Safe Boundary / Split Turn: PR 2。** 既存auto-shrinkへの接続はあるが、tool call/resultをまたがない切断点とoversized turnはPR 2の責務。
5. **ContextCandidate / ActiveContextBuilder / provider projection: PR 3。** PR 1のlegacy summary projectionと混同しない。
6. **Sub-Agent / Auto-pilot handoff: PR 4。**
7. **複数Clientのsemantic rebase・client scope: PR 5。** revisionを省略するlegacy保存APIの制約も引き続き残る。

### 注意しておく設計上の制約

- `project_agent_state()` はbounded text projectionであり、Goalが多い場合は省略され得る。AgentState自体は保持されるが、モデルへの投影が全Goalを網羅する保証はない。優先度の高度な判断はPR 3のContext Runtime設計と整合させる。
- `comparison_only` は過去revisionのsnapshotが保存されていない場合に比較不能を返す。履歴snapshot再生はPR 1に追加しない。
- 既存の圧縮挙動を変えないため、`UAGENT_STRUCTURED_COMPACTION` は既定OFFを維持する。

### 最終判断と次の作業

**レビュー上の結論:** PR 1で実装すると決めた「構造化レコード＋一括永続化＋既存経路へのopt-in基礎接続」は概ね揃っている。未実装の後続PR機能をPR 1のブロッカーとして扱わない。独立したCI/実行結果が得られるまでは「条件付き完了」とし、本番利用可能とは判断しない。

**次の作業:** 実装者は実装計画MDのPR 1状態を「基礎実装完了・統合検証保留」に更新し、PR 2のSafe Boundary / Split Turnを別の差分として開始する。PR 2ではcheckpoint 1〜4のコードを無関係にリファクタリングしない。実provider matrixは別途実施し、結果を本書に追記する。

| 日付 | 対象 | レビュー担当による確認 | 結果 |
|---|---|---|---|
| 2026-10-08 | `0780b5bf`, `1eab3dc5` とPR 1の実装計画・コード | GitHub上の差分・設計境界・実装記録を照合。独立pytest/CI実行なし | PR 1基礎実装は条件付き完了、実provider・全ライフサイクル検証は保留 |
