# UAG Context Result Projection / SessionStore 修正指示書

- **対象リポジトリ:** [`awaku7/agentcli`](https://github.com/awaku7/agentcli)
- **作業対象:** `main` の最新コミットを取得したうえで実施
- **検証基準点:** `9be785b6787e1016c54af259ca9f57612f69758d`（2026-10-12、PR #246 マージ時）
- **根拠資料:** `UAG_CONTEXT_RESULT_PROJECTION_VERIFICATION.md`（別途提供された検証レポート）
- **関連設計:** `docs/UAG_CONTEXT_MANAGEMENT_DESIGN.md` §32、§33.2–33.5、`docs/plans/IMPLEMENTATION_ROADMAP.md`
- **作業方針:** **2件の独立PR**。先に永続化の保護を修正し、マージ後にLLM向けProjectionを統合する。
- **禁止事項:** 大規模リファクタ、無関係な機能追加、根拠のない「全Provider検証済み」宣言、CI未確認のマージ、作業者による無断マージ

## 0. 作業依頼

検証レポートに記録された2件の問題を、既存のTool実行経路・Agent State・外部コンテンツ保護を壊さず、段階的に修正してください。

1. **PR 1 — SessionStore Tool Result専用レコードの機密値・サイズ保護**
1. **PR 2 — LLM向けResult Projectionの正しい接続と縮小処理の整理**

両PRは**別ブランチ・別レビュー・別マージ**にしてください。PR 1を完成させたらレビューとCIを確認し、**ユーザーによるマージを待ってから**PR 2を最新の`main`から作成してください。PR 1にPR 2の変更を混ぜないこと。

### 作業開始時の確認

- `AGENTS.md`を読み、現行コードとCI設定を確認する。
- `origin/main`を取得し、検証レポートの基準点から何が変わったかを確認する。レポートの行番号は基準点のものであり、最新`main`にそのまま適用しない。
- PR #246による **`success` / `failed` / `timeout` / `cancelled` の記録、`failed_steps`、再試行・復元処理**は修正済みと扱い、理由なく変更しない。
- **作業途中の試作ブランチ** `fix/context-result-llm-projection-20261012` が存在する。こちらには `8b9843`（限定的なLLM投影切替）と `c18767`（試作テスト）があるが、**検証レポートが警告するデータ準備・Artifact化の一元性を十分に保証しない**。このブランチをそのままPR化・マージ・無条件でcherry-pickしない。必要なテストや知見だけ再評価して採用する。ユーザー確認なく既存ブランチを削除・強制更新しない。
- 既存の未マージPRが生じていたら重複作業を避ける。

## 1. 確認済みの事実とリスク

### 1.1 LLM向けProjectionの未接続

検証基準点では、`src/uagent/llm_flow_helpers.py` の `_execute_tool_calls()` が次の処理を並行して行っている。

- Tool結果から表示・LLM用文字列を準備し、Binary除去・外部コンテンツ境界・`materialize_large_tool_result()`を適用する。
- `ContextManager.process_result()`で `ToolResultRecord` と `llm_context` / `ui_remote` / `persistent_history` / `ui_display` を生成する。
- **実際のTool message本文は `materialized_result` を使用し、`projections.llm_context` は適用されない。**

既存の切り詰め・Artifact化は機能しているので「巨大結果がLLMへ無制限に送られる」と断定しない。ただしResult Managerの要約・構造化previewと実際のLLM入力は一致していない。

**重要:** `tool_msg["content"] = projections.llm_context` に単純置換することは禁止する。Managerの入力が、Binary除去・外部境界付与**前**のJSONを含む場合、元の機密データ・Base64を再導入する危険がある。

### 1.2 SessionStore永続化の機密値・サイズ保護不足

検証基準点では、`src/uagent/runtime/session_store.py` の `record_tool_result()`が `tool_results.persistent_json` に値を保存する。`sanitize_binary_payload()` によるBinary形状の除去はあるが、**通常テキスト／JSON中の資格情報等の一般的なマスキングと、1件あたりの明確な保存サイズ制限が不十分**である。

- Session messageに適用される安全処理とTool Result専用レコードの保存経路を区別する。
- `persistent_json`だけでなく、`summary`・`metadata_json`・表示・検索・再取得経路への機密データの混入も検証する。
- 保存後の行数制限（既定500件）は**1件の巨大データのサイズ制限にはならない**。
- レポートは既存データの全件漏洩を立証したものではない。**保存し得る経路がある**という実装上の問題である。

**Artifact経路も別に確認すること:** 検証基準点では `_execute_tool_calls()` が `record_tool_result()` より前に `materialize_large_tool_result()` を呼び、閾値を超えるTool結果を既存Artifactストアへ登録する。現行の `artifact_helpers.register_tool_result()` は `redact_sensitive()` を通してから保存するため、Artifactが無加工だとは決めつけない。一方、そのredactionは限定的なパターンベースであり、今回求める構造化key・ネスト値等の保護をすべて満たすとは限らない。したがってSQLite保存境界だけの変更で完了とせず、Artifact実ファイルに適用済みの処理を確認し、新しい保存ポリシーの対象になる値が残らないかを検証すること。

### 1.3 UI / Agent State

- `ui_display` はオプトイン時に使われる。`ui_remote` は共通UI経路への接続が未確認だが、**表示欠落は立証されていない**。今回、新しいUI機構を作らない。
- PR #246のTool実行状態判定とSessionStore Agent State更新は、レポートが確認した範囲で正常。今回の変更では維持する。

## 2. PR 1：SessionStore Tool Result保存保護（先行）

### 目的

Tool Result専用永続レコードへ、機密情報や際限のない巨大本文が保存されるのを防ぐ。**保存直前の境界にも防御を置く**こと。呼び出し元のProjectionだけに依存しない。

### 主な対象

- `src/uagent/runtime/session_store.py` — `record_tool_result()` / Tool Result検索・再取得
- `src/uagent/runtime/tool_result_persistence.py` — Binary形状を保護する現行処理
- `src/uagent/runtime/tool_result_manager.py` — `summary`、`metadata`、`persistent_history`の扱い
- `src/uagent/utils/secret_mask.py` — 共通のsecret key・inline value masking
- `src/uagent/runtime/history.py` / `artifact_helpers.py` / `artifact_manager.py` — **現行Tool経路でArtifactが先に作成されるため、永続化保護に必要な場合に限り対象へ含める。** Artifact書き込みを調査せず、SQLite側だけの対策で完了としない。
- 既存のredaction / mask共通関数 — **重複実装しない**
- テスト: `tests/test_tool_result_store.py`、`tests/test_tool_result_persistence.py`、`tests/test_tool_result_artifact.py`、`tests/test_session_store.py`、`tests/test_secret_mask.py`、必要なら小さな専用テストを追加

### 実装指示

1. 現行の `redact_sensitive()`、`_sanitize_text()`、`_sanitize_value()`、`_mask_inline_secrets()` 等の実装と責任範囲を確認し、**共通化可能な安全な処理を再利用**する。機密値の辞書キー、ネスト構造、通常テキストの`key=value` / HTTP header等を考慮する。
1. `persistent_json`・`summary`・`metadata_json`に、**保存直前で確実に**必要な安全処理を適用する。加工はコピーに対して行い、実行中のTool戻り値・UI添付を破壊しない。
1. 1レコードの保存上限を**UTF-8バイト単位**で定め、既存設定との関係を文書化する。JSONとして有効な構造、既存の結果ID・Session参照、`artifact_ref`、`status`などの必要情報を維持する。
1. 大きな結果は、必要性に応じて**既存の権限制御付きArtifact参照**へ分離する。ただし、**資格情報を含む全文を無検証のArtifactへ複製してはならない**。SessionStoreへの保存より前にArtifactを書き込む経路も含め、どの値が実際にファイルへ保存されるか確認する。既存Artifactのアクセス境界・保存形式・cleanupを先に点検し、安全に保管できない場合は、永続化側で機密値をマスキングしたbounded表現へ縮小する。永続化用Artifactをマスキングする場合は、LLM/UIへ渡す表示・previewとArtifactの内容・参照との整合性を明示し、未加工payloadが別の保存先へ残らないことをテストする。
1. Artifact保存失敗時、redaction失敗時、JSON変換失敗時も、**未加工の全文を永続化するfallbackは禁止**する。実行を壊さず安全な縮約・エラー記録へ移る方針を明記する。
1. `list_tool_results()` / `get_tool_result()` / `search_tool_results()` とSession復元、検索・再注入の既存契約を確認する。既存DBの読み取りを壊さない。**既存の保存済み秘密データが修正によって自動削除されるとは主張しない**。
1. Binaryフィールドとプロトコル用途のBase64を区別し、署名・認証・暗号化処理に使う**不透明な文字列を一律削除しない**。ただし永続化してよいかはセキュリティ境界で別途判断する。
1. Agent State・`ToolExecutionText`の成功／失敗判定には手を加えない。

### PR 1受け入れ条件・テスト

- [ ] 通常テキスト／JSON／ネスト辞書／metadata／summary内の**ダミー資格情報**が、`tool_results`のDB列に平文で残らない。
- [ ] Binary形状と`data:*;base64,`の保存保護が維持される。
- [ ] 保存する各レコードが決めたbyte上限を守る。日本語等のマルチバイト、上限境界、無効設定を検証する。
- [ ] 大きな値の保存・Artifact失敗・DB再取得・検索・Session復元が安全に動く。
- [ ] `_execute_tool_calls()`を通じてArtifact閾値を超えるダミー資格情報入り結果を処理し、**SQLiteの各関連列だけでなく、登録されたArtifactの実ファイル内容**にも平文が残らないことを確認する。Artifactの参照・preview・復元結果も、決めたredaction/size policyと一致する。
- [ ] 結果ID、Session境界、`artifact_ref`、実行状態metadataが破損しない。
- [ ] LLM向けTool message・UI表示は、このPRでは意図せず変更されない。
- [ ] 古いレコードの読み取りと、既存テストが成功する。
- [ ] 新たな秘密値の混入・平文保存をSQLiteファイルまたは直接SQLからも検証する（返却値だけの検査で終わらせない）。

**PR 1の非対象:** `projections.llm_context`への切替、Context Budget全面刷新、UI機能追加、過去DBの一括破壊的移行。

## 3. PR 2：LLM Result Projection統合（PR 1マージ後）

### 目的

Tool ResultのLLM入力経路が、Result Managerの**安全な、サイズ制限されたProjection**と一致するよう整理する。既存のArtifact登録・外部コンテンツ保護・UI・履歴・Responses互換を守る。

### 主な対象

- `src/uagent/llm_flow_helpers.py` — `_execute_tool_calls()`
- `src/uagent/runtime/history.py` — `materialize_large_tool_result()` / truncate / Artifact
- `src/uagent/runtime/tool_result_manager.py` と `context_manager.py`
- テスト: `tests/test_tool_result_manager.py`、`tests/test_tool_result_artifact.py`、`tests/test_tool_result_context_limit.py`、`tests/test_responses_tool_result_limit.py`、`tests/test_agent_state_failure_flow.py`
- 試作テスト `tests/test_tool_result_projection_flow.py` は参考にしてよいが、**試作の前提をそのまま採用しない**。

### 実装指示

1. 現状の **raw Tool result → JSON解析 → 外部データ境界 / Binary除去 / 添付情報抽出 → Artifact登録 → Result Record・Projection → 実際のLLM Tool message / UI / History** を実行順序付きで整理する。
1. **LLM投入前に保護済みのデータ**をResult ManagerのLLM投影に渡す設計に統一する。元の `parsed_tool_result` をそのまま再表示してBinary・未信頼テキストを復活させない。
1. **Artifact化とLLM向け縮小の責任を一元化**し、同じ結果の二重登録、二重truncate、`artifact_ref`の欠落、RecordとLLM表示の参照不一致を防ぐ。
1. smallの通常テキスト・JSONの既存意味、`tool_call_id`、順序、providerへのTool message形式を維持する。大きな構造化結果は要約・head/tail・referenceを必要に応じて適用する。
1. 外部データの`---BEGIN_UAGENT_EXTERNAL_CONTENT---` / `---END_UAGENT_EXTERNAL_CONTENT---`境界が**LLMに届く最終文字列にも残る**ことを保証する。出力縮小時に開始だけ／終了だけ残る状態を許容しない。
1. Binary Base64、スクリーンショット、生成画像・音声、`attachments`、`saved_files`、`saved_path`、Responses継続用のデータを壊さず分離する。
1. `projections.ui_display`、UI向け添付、`persistent_history`を誤ってLLMへ混ぜない。UI契約が未確定な`ui_remote`の新規接続は行わない。
1. **PR #246の実行状態は独立情報として引き続き判定**する。文字列本文に`Error:`、`timeout`、`{"status":"blocked"}`が現れても、正常なTool実行を誤って失敗にしない。
1. 縮小設定（現行の既定最大12,000文字、Artifact閾値100,000文字、値`0`を含む特別な設定）の意味を確認し、既存の許可された設定が意図せず変わらないようにする。上限無効時の実際のProvider制限もテストする。
1. Result ID、Artifact ID / `artifact_ref`、Summary、LLM表示、専用永続レコードが相互に追跡できることを確認する。

### PR 2受け入れ条件・テスト

- [ ] `_execute_tool_calls()`の**最終Tool message**を検証する（Manager単体のProjection生成テストだけで完了扱いしない）。
- [ ] small / large / huge の文字列、長いJSON / 行配列、構造化preview、summaryを確認する。
- [ ] 100k文字前後とArtifact登録成功・失敗、参照ID一致を確認する。
- [ ] 外部テキストの引用境界を保持し、Binary・Base64をLLMへ再混入させない。
- [ ] LLM / UI / Historyの内容が混線せず、必要な添付が保持される。
- [ ] 既存のChat Completions / Responses API Tool messageの形式・サイズ制限テストが成功する。
- [ ] 明示的Tool実行status、Agent State `failed_steps`、成功再試行が維持される。
- [ ] CLI/Web/GUI/A2Aは、共通コード確認だけで実機動作済みと断定しない。実機未検証範囲はPR説明に残す。

**PR 2の非対象:** SessionStoreの再設計、Embedding検索、任意LLM要約の追加、すべてのProvider Adapter改造、Context Budget全面刷新。

## 4. テスト・レビュー・作業品質

### 最低限確認する既存テスト

検証レポートは以下12ファイルについて **54 passed / 0 failed** を報告（Windows / Python 3.14.7）。これは**修正前の基準**であり、修正後の保証ではない。

```text
tests/test_tool_result_manager.py
tests/test_tool_result_artifact.py
tests/test_tool_result_context_limit.py
tests/test_tool_result_display.py
tests/test_tool_result_persistence.py
tests/test_tool_result_retention.py
tests/test_context_manager_pipeline.py
tests/test_agent_state_failure_flow.py
tests/test_tool_result_store.py
tests/test_tool_result_unicode.py
tests/test_responses_tool_result_limit.py
tests/test_agent_state_integration.py
```

### 実行手順

1. **変更前に再現テスト**を作り、基準`main`で問題を確認する。

1. 実装は**必要な境界だけ**を変更し、関連テストを実行する。

1. コミット前に以下を実行する。Python・Black/RuffのバージョンはリポジトリのCIに合わせる。

   ```bash
   python -m black --check src/uagent tests
   python -m ruff check src/uagent tests
   python -m pytest -q tests/test_tool_result_manager.py tests/test_tool_result_artifact.py tests/test_tool_result_context_limit.py tests/test_tool_result_display.py tests/test_tool_result_persistence.py tests/test_tool_result_retention.py tests/test_context_manager_pipeline.py tests/test_agent_state_failure_flow.py tests/test_tool_result_store.py tests/test_tool_result_unicode.py tests/test_responses_tool_result_limit.py tests/test_agent_state_integration.py
   ```

1. 可能なら対象の全テストを実行し、**GitHub ActionsのBlack、Ruff、Python各バージョン、full-testsを確認**する。テストが一部未実施なら必ず明示する。

1. PR本文に「変更箇所」「設計上の保護境界」「テスト結果」「実機未検証項目」「非対象」「既存データへの影響」を記載する。

1. CIが通ってからCodexレビューを依頼。指摘を再現・評価し、**妥当なものだけ最小範囲で修正**。各コメントへ原因と修正・テスト根拠を返信し、必要時に再レビューを依頼する。

1. Black失敗はCIログで**差分を正確に確認して修正**。整形修正を口実に無関係な変更を広げない。

1. 設計書`docs/UAG_CONTEXT_MANAGEMENT_DESIGN.md` §32.3/§32.4、および `docs/plans/IMPLEMENTATION_ROADMAP.md`を、**実装・検証できた範囲だけ**更新する。PR #246で実装済みの`failed_steps`を未実装のまま残さない。ただし`important_facts`、process restart中のAgent Loop復旧などを一括完了扱いにしない。

1. **ユーザーは自分でマージする。** 作業エージェントはPRをマージせず、URL・最新コミット・CI状況・Codexレビュー状況・未解決事項を報告する。無限のレビュー反復にならないよう、新規指摘ごとに原因が共通するか先に判断する。

## 5. 注意すべき境界条件

- **Toolの成否とToolが返す文字列は別。** 正常な `python_exec` / `pwsh_exec` / 画像解析等の出力に `Error:` や失敗らしいJSONが含まれても、実行状態を変えない。
- **User/Tool由来の未信頼テキストをsystem指示へ昇格しない。** 外部コンテンツ引用境界を守る。
- **Agent State / SessionStore** と **実行中のAgent Loop再開**を混同しない。
- 保存前のredactionは**安全性確保**、Artifact参照は**容量・復元性**の問題であり、Artifact化だけで機密性は保証されない。
- DBの過去データには既に機密値が存在する可能性がある。今回は新規保存の予防と既存形式の読み取り互換を優先し、必要な過去データの対処は別途文書化する。
- 個別ProviderやGUI等の実機試験を未実施なら、CI成功だけで完了したと書かない。

## 6. 完了報告の形式

各PRの完了時に、次の情報を簡潔に報告してください。

```text
対象: PR 1（またはPR 2）
PR URL:
HEAD:
修正した根本原因:
変更ファイル:
追加・変更した回帰テスト:
ローカルテスト:
CI（Black/Ruff/pytest）:
Codexレビュー:
未検証事項 / 残る懸念:
マージ可否: （判断根拠を添える。マージ操作は行わない）
```

## 7. 参照先

- 検証レポート: `UAG_CONTEXT_RESULT_PROJECTION_VERIFICATION.md`（本指示書と併せて渡す）
- [PR #246 — Tool実行状態とAgent State修正](https://github.com/awaku7/agentcli/pull/246)
- [実装ロードマップ](https://github.com/awaku7/agentcli/blob/main/docs/plans/IMPLEMENTATION_ROADMAP.md)
- [Context Management設計](https://github.com/awaku7/agentcli/blob/main/docs/UAG_CONTEXT_MANAGEMENT_DESIGN.md)
- [Tool Result Manager](https://github.com/awaku7/agentcli/blob/main/src/uagent/runtime/tool_result_manager.py)
- [LLM Tool実行共通経路](https://github.com/awaku7/agentcli/blob/main/src/uagent/llm_flow_helpers.py)
- [SessionStore](https://github.com/awaku7/agentcli/blob/main/src/uagent/runtime/session_store.py)

______________________________________________________________________

**重要:** 対応の完了条件は「既存のテストが成功した」だけではなく、**DBへの永続化データと実際にLLMへ届くTool messageを検証できたこと**。実機未検証の部分は必ず切り分ける。
