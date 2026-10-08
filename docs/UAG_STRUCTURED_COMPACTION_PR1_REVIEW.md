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
- [ ] 修正コミットを本書に追記して再レビュー

## 検証状況

初回レビュー時点ではテスト・Black・Ruffを独立実行していなかった。修正後の対象テストと静的チェック結果は、下記の再レビュー記録に記載する。

## 修正・再レビュー記録

| 日付 | コミット | 対応内容 | 検証結果 |
|---|---|---|---|
| 2026-10-08 | `9e926f4b` | 初回レビュー。P1・P2を指摘 | 修正・再検証待ち |
| 2026-10-08 | 作業ツリー（未コミット） | P1: historical base snapshot がない comparison-only を head conflict と区別し、比較不能として拒否。P2: snapshot+revision の同時読み取りを追加し、runtime の更新経路は observed revision を使って保存。revision 省略の legacy 経路には stale-write 制約を明記 | `tests/test_compaction_persistence.py` 17 passed; Python compile 2 passed; Ruff passed; Black `--check` passed |

### 再レビュー所見

- comparison-only は、base revision と現在 revision が一致し、保存済み AgentState snapshot がある場合に限り記録できる。revision が過去の場合は `SessionComparisonUnavailable` を返し、AgentState・revision・checkpoint を変更しない。過去snapshotを復元する機構は追加していない。
- `save_agent_state(..., expected_revision=None)` は互換性のため残しているが、呼び出し元の古いsnapshotを検出できない。複数クライアントが同一セッションを更新する場合は `get_agent_state_snapshot()` で状態とrevisionを一緒に読み、そのrevisionを `expected_revision` に渡す。runtime の `update_agent_state` / `complete_agent_step` はこの経路を使う。
- この環境では修正コミットを作成していないため、コミット単位の再レビューは未実施。
