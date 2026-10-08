# PR 2 最終スコープレビュー（2026-10-09）

## 対象

- 基準: `docs/UAG_STRUCTURED_COMPACTION_DESIGN.md` / `docs/UAG_STRUCTURED_COMPACTION_IMPLEMENTATION.md`
- 実装: `9fabde86`（Logical Turn）、`9cf404b5`（Safe Split）、`79c95516`（SessionStore reopen 回帰）
- 読み取りレビューのみ。レビュー担当者によるローカル pytest / Ruff / Black / 実プロバイダ実行は未実施。

## 判定

**PR 2 基礎実装: 条件付き完了（PR 3 に進行可）。** 現時点でPR 2を差し戻す明確な重大欠陥は確認していない。ただし実CLIのresume/debug経路そのものを動かした統合検証と実プロバイダでの長大履歴検証は完了扱いにしない。

## 確認事項

1. `_logical_turn_spans()` がuser境界とpending tool callを考慮し、parallel tool resultsを同一圧縮単位に保つ。
2. `_safe_assistant_cut_points()` と `_oversized_turn_split_cut()` が未完了のtool call/resultを跨ぐcutを避け、token budget内のprefixだけを圧縮対象にする。
3. `CompactionRecord` に `split_turn` / `first_kept_message_id` を追加し、split時にsource windowとsuffixの索引整合性が確認できなければcommitせずfallbackする。
4. Raw Historyはstructured projectionによって置換しない。Artifact-firstは既存のtool result経路を再利用し、既存回帰テストで確認している。
5. `test_split_turn_record_reconstructs_prefix_and_suffix_after_store_reopen` がDB再オープン後のsource sequence range、suffix ID、Raw History、AgentState summaryを検証する。

## 残留リスク・後続確認

- **統合テスト範囲:** reopenテストは永続データを読み、テスト内でprefix/suffixを再構成している。実際のCLI resume/debug callerが同じmetadataを消費して再構成することまでは証明していない。実CLIライフサイクル検証で確認する。
- **長大/異常tool履歴:** 未対応のprovider固有tool message形式、call ID欠損・孤立結果、実トークナイザとの差異は実provider matrixと異常系テストで確認する。既存の安全側fallbackを維持する。
- **PR 3/5との境界:** CheckpointのContextCandidate/ActiveContextBuilder接続とrehydration認可はPR 3/5で扱う。PR 2の完了をもってcross-scope authorizationやmulti-client semantic rebase完了とはしない。
- **検証記録:** 実装計画には対象テスト（29/18/12/2/4）・全pytest suite・Ruff/Black成功と記録されているが、レビュー担当者は独立実行していない。

## 引き継ぎ

PR 3はContextCandidateの公開・重複排除・scoring/budget/provider projectionに限定して段階的に進める。上記統合検証は別途追跡し、問題が確認された場合のみPR 2の修正に戻す。
