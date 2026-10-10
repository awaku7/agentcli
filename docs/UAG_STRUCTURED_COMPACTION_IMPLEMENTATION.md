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

- **全体状態:** PR 1 は基礎実装を**条件付き完了**（2026-10-08の最終スコープレビュー）。独立したCI/実行検証と実プロバイダ・全ライフサイクル検証は保留。後続PR機能はPR 1の完了条件に含めない。
- **基準設計:** `docs/UAG_STRUCTURED_COMPACTION_DESIGN.md`
- **現在のフェーズ:** PR 1 条件付き完了 → PR 2 Safe Boundary / Split Turn 完了 → PR 3 Context Runtime Integration 基礎実装・checkpoint境界修正（#202 merged）→ PR 4 Handoff基盤の段階導入中（#204 / #205 merged）
- **設計書の再レビュー:** 明確化事項を設計書へ反映済み（2026-10-08）
- **実装:** immutable record model / typed SourceRef / `session_seq` index、AgentState revision、atomic checkpoint commit、idempotency、Reducer に加え、feature flag `UAGENT_STRUCTURED_COMPACTION=1` で動く structured auto-compaction path の基礎を追加。structured projection と legacy / deterministic fallback を provider context に接続し、Raw History は置換しない。
- **テスト:** PR 1 最終スコープレビューは条件付き完了。PR 2 では Logical Turn parser、parallel tool results を保つ安全境界、oversized turn の assistant 境界 split、split suffix の保持とCheckpoint provenanceを実装し、SessionStore reopen 後のprefix/suffix再構成も検証。Artifact-first tool-result path は既存実装と回帰テストを確認。PR 3 は checkpoint candidate の score / decision / budget、重複抑止、older-page retrieval、session-scoped source rehydration、store failure fallback を追加。PR 3 targeted tests（4 / 18 / 9 passed）と全 pytest suite、全 `src` / `tests` の Ruff・Black check、6ファイルの py_compile、Markdown format、`git diff --check` が成功。実provider matrix / 独立 CI review は未実施。
- **未実装境界:** cross-scope authorization / rehydration の再認可、user confirmation UI と ambiguous-resolution caller、runtime DeterministicDelta の実イベント抽出、PR 4 のhost policy / return適用 / Auto-pilot再開と PR 5 multi-client safety、provider matrix / end-to-end restart review。
- **次の作業:** PR #207で子Sessionの保存済み出力から読み取り専用compact `HandoffRecord` を構築するAPIと回帰テストを追加（PR審査中）。これはMainへの自動配送やAgentState適用を意味しない。次にhost側のtrusted Goal/source選択、Job結果の配送、Main側のrevision競合・root ID重複排除と一括適用を段階的に行う。cross-scope authorization、実provider matrix、process restart後の回復は独立して追跡する。

### PR 1 完了判定（2026-10-08）

**判定: 条件付き完了（基礎実装完了、統合検証保留）。** CompactionRecord、SourceRef/session index、Reducer、revision付き一括永続化、opt-in生成・projection・fallbackの基礎が実装された。実装者の対象テスト・Ruff・Black成功記録はあるが、レビュー担当による独立実行ではない。実プロバイダ接続、実CLIを通したend-to-end再開・長期利用は未検証であり、本番利用可能とは判断しない。feature flagは既定OFFを維持する。

Safe Boundary/Split TurnはPR 2、Active Context・rehydrationはPR 3、handoffはPR 4、複数Clientのsemantic rebaseと認可境界はPR 5に分離する。詳細は [PR 1最終スコープレビュー](./UAG_STRUCTURED_COMPACTION_PR1_REVIEW.md) を参照。

## 4. フェーズ計画

### PR 1 — Structured Compaction Record

この段階では圧縮境界アルゴリズムを大きく変更せず、構造化レコード、状態更新契約、および検証の基礎を実装する。PR 1 は範囲が広いため、以下の小さな順序で実装・テスト・レビューを進める。各段階の完了を確認してから次へ進み、一度に全項目を変更しない。PR 数を機械的に増やす必要はなく、独立した差分としてレビュー可能な単位を優先する。

**PR 1 の実装順序（チェックポイント）**

1. **調査・モデル**：既存コード対応表を確定し、CompactionRecord / GoalDelta と validation の最小モデルを追加。既存の圧縮動作は変えない。
1. **出典・観測情報**：`SourceRef`、`session_seq`、Goal association、DeterministicDelta を追加し、単体テストで契約を固定する。
1. **永続化・Reducer**：Checkpoint / AgentState / revision / operation ID の一括更新（失敗時はすべて取り消す）、競合検出、二重適用防止を実装・検証する。永続化を有効にする前にこの整合性を満たす。
1. **既存経路との接続**：Narrative / legacy summary projection、fallback、最小 telemetry を追加し、回帰テストを通す。

各チェックポイントは必要な最小限のファイルだけ変更し、既存動作を維持できない途中状態を main にマージしない。

- [x] 既存実装とデータフローを調査し、コード対応表を作成
- [x] CompactionRecord / GoalDelta / DecisionRecord / ConstraintRecord / FactRecord のモデルを追加
- [x] Goal association の三状態（既存 Goal、新規 Goal、曖昧）と deterministic `goal_id` 割当契約を実装
- [x] typed / scoped `SourceRef`、session-index との save-time structural validation を実装
- [ ] Runtime の cross-scope authorization resolver と rehydration 時の再認可を接続（現checkpointでは active Session 内の exact source resolver のみ）
- [x] `session_seq` の採番、source range / watermark、legacy ordering backfill policy を実装
- [x] Reducer に ambiguous delta の explicit-authorization gate と resolution lineage の基礎を実装
- [x] DeterministicDelta と dimension ごとの tracking coverage（complete / partial / unavailable）を保存
- [x] SessionStore の Checkpoint 保存、stable operation ID、expected revision guard、AgentState 更新を atomic transaction 化
- [x] comparison-only が AgentState revision を更新しないことを実装
- [ ] Reducer の全 lifecycle invariant / compaction caller 接続 / process-restart idempotency review を完了
- [x] Narrative Continuation を含む AgentState から bounded legacy summary projection を生成
- [x] schema validation failure 時に一度だけrepairし、失敗時は legacy / deterministic fallback を接続
- [x] opt-in structured compaction の success / fallback / latency telemetry を追加
- [x] checkpoint 4 の生成・fallback・raw history 保持テストを追加・実行
- [ ] 設計書の PR 1 範囲および関連 acceptance criteria をレビュー

**完了条件:** AgentState が唯一の authoritative materialized current state であり、CompactionRecord が immutable な delta / evidence として扱われる。失敗時に Raw History が保持される。

### PR 2 — Safe Boundary / Split Turn

- [x] Logical Turn の parser / 表現を実装
- [x] tool call と対応する結果、および parallel tool result をまたがない safe cut point を実装
- [x] 1 turn が budget を超える場合の Split-Turn 処理を実装
- [x] oversized tool result の Artifact-first 処理を実装
- [x] prefix / suffix の復元可能性を検証（SessionStore reopen後、source rangeとfirst_kept_message_idから確認）
- [x] boundary、split、failure fallback のテストを追加・実行

### PR 3 — Context Runtime Integration

- [x] CompactionRecord を ContextCandidate として公開
- [x] Scoring / Decision / Budget と連携
- [x] ActiveContextBuilder および Provider Projection へ接続
- [x] 必要な場合に source refs から retrieval / rehydration（同一 Session の exact / available message refs に限定）
- [x] checkpoint の重複投入を防ぎ、古い checkpoint を再取得可能にする
- [x] runtime 統合テストと provider-neutral な検証を追加・実行

**判定:** 基礎実装完了。source rehydration は session-scoped message refs のみであり、cross-scope authorization、artifact/tool-result adapter、実provider matrix は PR 3 の完了範囲外として保留。

### PR 4 — Sub-Agent / Auto-pilot Handoff

- [x] HandoffRecord と caller-bounded projection を実装（provider-neutralなrecord / projection API）
- [x] trusted dispatch snapshotをSubAgentRunnerへ接続し、専用子Sessionに実出力を保存（#204）
- [x] opt-in host policyからJob workerへのdispatch snapshotの受け渡しを実装（#205）
- [x] 子Sessionの保存済み実出力から読み取り専用compact returnを生成・検証するAPIを実装（#207。Mainへの配送・適用は未実装）
- [x] 結果保存済みの終了Jobからtrusted hostが出典付きcompact returnを取得する読み取り専用APIを実装
- [x] Main側に出典とrevisionを検証する永続compact return受理記録APIを追加（AgentState更新・host接続は対象外）
- [x] trusted Job ownerからMain側の永続受理記録へ結果を明示的に配送するAPIを接続（既存hostは未有効化）
- [x] CLIの終了通知からMain受理記録への自動配送を二段階opt-inで接続（CLI稼働中・同じowner限定、Main状態は非更新）
- [x] CLIのMainに受理記録を未検証・読み取り専用データとして提示するopt-in経路を追加（出典失効時非表示、Goal・Memory非更新）
- [ ] GUI/Web/A2Aの自動配送とMain AgentStateへの安全な適用を接続
- [x] CLIに明示的opt-inのtrusted Goal ID／親Sessionの厳密なmessage SourceRef選択ポリシーを接続（既定は無効、許可リストは空）
- [ ] GUI・Web・A2Aホストのtrusted Goal/source選択ポリシーを安全に有効化
- [x] 受理報告と独立した根拠に基づくtrusted reviewの記録を追加（受理root単位に1件、Mainの状態は非更新）
- [x] trusted host専用のreview済みrootメタデータをMain AgentStateへ一括反映（SQLite単一transactionでrevision照合・root ID重複排除。報告本文やGoalは非更新）
- [ ] review済み報告から独立に検証された個別事実／Goal状態を適用する承認・根拠モデル
- [ ] Main側のrevision検証・root ID重複排除・state適用を一括処理
- [ ] Auto-pilot の checkpoint / resume を実装
- [ ] provider / model handoff の実接続テストを追加・実行

**現在の状態・次の作業（2026-10-09）:** 第一段階として immutable `HandoffRecord` と項目別 provenance、dispatch 時の receiver / revision、root delivery ID、schema / size validation を追加。`HandoffBounds` と Main → Sub-Agent / Sub-Agent → Main の projection API は、許可された Goal / exact SourceRef と送信時の availability / authorization check に限定する。Raw History、Memory、global narrative、provider state、無関係な Goal は投影しない。Checkpoint / Artifact は明示的に選択した参照のみを渡し、全文取得は行わない。#204ではtrusted opt-in dispatchをSubAgentRunnerへ接続し、#205ではhost-owned policyが設定されたJob queueからworkerへそのsnapshotを渡せるようにした。既存hostはpolicy未設定のため、この経路を自動的には利用しない。

**第二段階（opt-in dispatch 接続）:** `runtime/sub_agent_handoff.py` の `capture_sub_agent_dispatch()` は trusted host が指定した receiving Session の AgentState / revision を一緒に取得し、許可 Goal / exact SourceRef に限定した projection を固定する。専用 Sub-Agent Session に dispatch ID / receiver / revision と投影を保存し、`SubAgentRunner.run(..., handoff_dispatch=dispatch)` は送信直前にも availability / authorization callback を再確認する。この経路では legacy の file snippet / shared context / cache を送らず、実際の返却結果を SessionStore の通常の redaction と source index を通して保存する。モデルの tool schema に bounds / dispatch 指定を追加しない。今回、Job manager にhost-owned policyを指定したときの snapshot capture / worker transport を追加したが、既存hostにはまだpolicyを設定していないため、通常のtools / Job / 各hostの opt-in、child 全会話 / tool event の保存、compact HandoffRecord 返却は未実装。

**段階導入の境界:** 第二段階でも Main AgentState の更新、root ID の永続 deduplication、revision conflict / reconciliation の受信処理、Auto-pilot checkpoint / resume、終了判定は変更しない。Job queueはtrusted policyから受けたdispatchをowner scope検証後にworkerへ渡し、structured Jobのshared-store書き込みとlive inbox continuationを拒否する。各hostのGoal/source選択policyは未設定である。次の独立段階では、既に索引化された子Sessionの実出力だけを出典とするcompact returnを先に実装する。子の全会話・tool eventの索引化は別段階とする。#207で保存済み子出力だけのcompact return構築APIを実装した。続いてJob managerに終了Jobの保存確認・owner制限・出典再認可に基づくhost向け取得APIを追加した。各hostによるこのAPIの利用開始とMainへの適用は未実装である。後続でhostごとのtrusted Goal/source policy、Job結果のMainへの配送、受信側のrevision check / root ID uniqueness / state applicationを同じtransactionに実装する。Auto-pilot再開はその基盤の検証後に進める。

**Main側の受理記録（次の限定的な実装段階）:** `receive_compact_sub_agent_return()` はtrusted dispatchと現在のsource認可から `HandoffRecord` を再生成し、受信先Sessionのrevision、子Sessionの同一project/identity/room、dispatchの索引と唯一の出力SourceRefを検証して `sub_agent_receipts` に記録する。受理とroot IDの重複排除はSQLite `BEGIN IMMEDIATE` で一括処理し、同じrootの同内容再試行のみ冪等に成功する。revisionが進んだ未受理の古い結果は拒否する。これは **未検証報告の受理記録** に限り、Main AgentStateのrevision・Goal・Memory・完了判定には変更を加えない。hostへの自動接続とMain状態適用は後続PRの対象とする。

**CLIホストの限定的なopt-in（次の実装）:** 環境設定 `UAGENT_SUB_AGENT_STRUCTURED_HANDOFF=1` を明示したCLI起動時だけ、`SessionStore` に基づく `build_scoped_job_handoff_policy()` をJob managerへ登録する。Goal IDと正確なmessage SourceRefはホスト設定のJSON配列で指定し、初期値はともに空。source accessをSession ID・メッセージID・順序番号・available/exactで都度検証し、選ばれていないGoalや本文履歴を渡さない。Main Sessionの切替、出典失効、無効な設定は暗黙に広い権限へ切り替えない。現時点ではCLIだけがopt-in可能で、Job完了後のMainへの自動配送・AgentStateへの適用は未実装。

**CLIでの通知駆動受理（限定的な自動接続）:** `UAGENT_SUB_AGENT_STRUCTURED_HANDOFF=1` に加え、別の `UAGENT_SUB_AGENT_HANDOFF_AUTO_RECEIPT=1` を指定したCLIでのみ、現在のCLI ownerの `finished` Job通知から #210 の受理APIを呼び出す。終了通知の内容だけを信用せず、Jobの所有者・確定済み子出力・出典索引・Main revisionを改めて検証する。成功・失敗の結果は子本文を含めず構造化ログに記録し、通常のCLI Job通知は変更しない。Session切替後の旧ownerの通知は新Sessionへ配送しない。CLI終了時や再起動跨ぎの未処理通知を再送する仕組みはなく、この自動配送はベストエフォートである。未検証報告をAgentState、Goal、MemoryやAuto-pilotへ適用しない。

**Mainからの安全な参照（次の限定実装）:** 受理済みの `sub_agent_receipts` を、trusted Main Session IDに限定して最大5件まで読み取るAPIを追加する。記録の構造・root ID・受信先の一致を検査し、元の子出力 `SourceRef` が現在もexact/availableであるものだけを表示対象とする。子Sessionの削除や出典利用不可後は、記録自体を消去しなくても報告本文をMainへ再提示しない。CLIの `UAGENT_SUB_AGENT_HANDOFF_CONTEXT=1` 設定が明示的に有効なときだけ、最大3件・4000文字の未検証JSONデータとして次ターンへ渡す。LLMがその本文の指示に従わないように非信頼の注記を付け、AgentState更新の後に追加し、LLM処理の成功・例外終了を問わず元のユーザー本文へ必ず復元することで、報告文のGoal化・会話履歴への残留を避ける。また、一時的な報告を含んだOpenAI Responsesの継続IDは処理終了時に無効化し、Session Storeにも無効化の記録を残す。次のターンや `:load` では古いサーバー側会話へ戻らない。Gemini/Vertexのキャッシュも再構築対象とする。これはMainの参照手段であって、事実認定・Goal完了・Auto-pilot再開ではない。

**Mainの審査済みroot管理（PR #215、限定実装）:** `SessionStore.apply_reviewed_sub_agent_receipt()` は、trusted hostが明示的に指定した既存の `supported` reviewのみを対象に、独立根拠の現在の利用可否・user role・認可、元の子出力の利用可否、Main revisionをSQLite `BEGIN IMMEDIATE` の同一transactionで確認する。初回適用時に `sub_agent_review_registry` へroot ID・確認者・独立根拠SourceRef等のメタデータだけを `reviewed_unverified` として格納し、AgentState revisionを1つ進める。同じrootの再適用は冪等で、状態やGoalは二度更新しない。UAG所有の識別子を付与し、旧バージョンでユーザーが同名の任意データを保存していた場合は `legacy_sub_agent_review_registry*` に退避してから新領域を作る。通常の `save_agent_state()` からUAG所有領域の上書き・消去・偽装を認めず、reducer経由の他の状態更新はその領域を保持する。**これは受理と審査をMain状態に紐付ける処理であり、報告内容の事実認定やGoal完了、自動実行への適用ではない。** CLI/GUI/Web/A2Aホストへの自動接続やAuto-pilot再開は別段階。

**根拠付きreviewの監査記録（新しい限定実装）:** `SessionStore.review_sub_agent_receipt()` は、trusted hostが指定した確認者・判断（`supported` または `rejected`）・独立したMainユーザーメッセージの出典を受け取り、最新のMain revision、元の子出力の出典、別根拠の現在の認可・exact/availableを確認してSQLiteトランザクション内で1件だけ記録する。元の子出力だけを根拠にすることは認めず、別Sessionやassistant出力の流用も拒否する。同じrootと同内容の再試行だけを冪等に認め、別判断による上書きを拒否する。根拠の失効後も監査記録は保持し、参照APIは現在の出典利用可否を返す。これは確認者による審査履歴であり、事実の自動認定、Goal終了判断、AgentStateへの一括適用には相当しない。モデルや一般ツールに書込みAPIを公開しない。

**Job→Mainの明示的な配送（追加の限定実装）:** `SubAgentJobManager.deliver_compact_handoff_to_main(owner, job_id, source_access_check)` は、trusted ownerが取得できる終了Jobのうち構造化された結果を正常保存したものだけを対象とし、Indexed child outputに記録されたJob IDの一致を検証してから#209の `receive_compact_sub_agent_return()` を呼び出す。Main側はSQLiteトランザクション内で出力のJob ID・権限・出典・revision・root IDを再検証し、同じ結果の再配送は受理済みとして返す。キャンセル・未保存・他owner・通常Jobは配送しない。エラー終了の結果も未検証報告として扱い、MainのGoal完了やAgentStateを更新しない。**既存hostは本APIをまだ呼ばず、自動配送とGoal/source選択policyの有効化は別作業。**

**実装済みAPI — 子Session出力のcompact return（#207、Main配送前の段階）:**

1. `SubAgentDispatch.record_result()` が返す子Sessionの正確な `SourceRef` を出典の起点とする。実際に保存されたメッセージ／source indexに存在することを検証し、モデルが返した出典ID・受信先Session・revision・root IDをそのまま信用しない。
1. 既存 `HandoffRecord` と `project_sub_agent_return()` を使い、trusted runtime側がdispatch lineage（受信先Session、base revision、Goal IDs、root ID）を設定する。dispatch時点の `HandoffBounds.source_refs` はMainからの入力専用であり、子出力はまだ存在しない。返却時には同じ受信先・revision・Goal範囲を維持し、索引と現在の認可を検証した子出力 `SourceRef` のみを許可する **別の trusted return-side `HandoffBounds`** を作成する。出力が自由文で構造化された個別の事実を保証できない場合、根拠のないwork_done・decision・state_deltaを捏造せず、受信可能な最小表現または明示的な変換失敗とする。
1. 返却は読み取り専用の提案とし、MainのRaw History、AgentState、Memory、長期profileへ自動書込みしない。全出力・toolイベントの永続化はこの実装単位の前提とせず、今回は保存済みの実出力に出典を限定する。
1. 出典の再認可、参照先不在、サイズ超過、保存時の例外、同一dispatchの再試行・競合、キャンセルと完了の競合を検証する。既存の非構造化Sub-Agent経路と、opt-inしていないhostの動作を維持する。
1. この段階ではMain側のrevision更新、永続root ID重複排除、異なるrunner/processからの復旧、Auto-pilot再開を実装しない。それらは受信側の一括適用と復旧の別差分で扱う。

**受け入れ条件と検証状態:** APIは許可されたGoalと保存済み子出力だけを参照し、失敗してもMainの状態を変更しない。trusted hostからのJob結果取得APIはJob managerのownerと保存確定状態を確認してから返却し、Job状態が未完了または終了しても保存前なら返さない。#207のCI #38005828975ではquality（Ruff/Black/I18N）、full pytest、Python 3.11/3.13/3.14互換性チェックが成功した。Job→Mainの実配送、実provider接続、process restartを含むend-to-end検証は未実施であり、PR4完了とはみなさない。

**第二段階のローカル検証:** 変更した Python ファイルで Black 26.10.0 の整形 / check 成功。dispatch persistence / bounded runner と既存 handoff / compaction / Sub-Agent 回帰 pytest は計 169 passed。Main callback / JSONL / shared store の情報分離、権限復旧後の再試行、並行 duplicate 拒否時の予約不変、循環拒否時の予約解除、provider 例外と append 前後の保存失敗からの回復、および legacy 経路を検証。保存失敗時の結果は同じ runner 内で非公開に保持して再保存し、provider work を再実行しない。保存待ち / 実行中の structured 結果は runner ごとに最大32件に制限し、上限到達時は新規 provider work を始めず予約を解除する。既存の保存待ちは再試行できる。恒久的な権限失効などで再保存を断念する場合は trusted host の `discard_pending_handoff_result(dispatch)` で非公開結果と枠を明示的に解放できる。実行中は破棄を拒否し、破棄した ID は再実行を禁止する。一時的な権限停止では結果を自動破棄しない。初回 dispatch append が失敗した場合は作成直後の未公開 child Session を削除し、再試行による孤立 Session / source index の蓄積を防ぐ。child Session は初回 append 前に親の principal / room を既存 identity binding で引き継ぎ、binding 失敗も未公開 child を削除する。構造化派遣では従来の `provider` / `model` / `response_mode` / 証拠要件を無視し、未登録 role の値をログから伏せる。従来の `response_schema` / `required_fields` を無視して trusted AgentSpec の出力契約を使い、自然言語の会話再開は内部 child を候補から除外し明示 ID も拒否する。構造化派遣は tool permission を `none` に固定し、モデル由来の従来権限で snapshot 外のライブ入力を取得できない。structured 経路は live Job inbox を消費せず、追加入力は新しい authorized dispatch に分ける。SQLite からの profile 再構築では sub-agent Session を message 取得と件数制限の前に除外し、子の objective / generated result が長期 profile 経由で Main に混ざらないようにする。process restart / cross-runner recovery と永続 root ID deduplication は対象外。Ruff module がなくローカル Ruff は実行失敗・未検証。全 suite も実行したが partial source snapshot に `uagent.core` がなく collection error で中断したため未検証。全 `src tests` Black check、実 provider と host / Job end-to-end も未検証。PR CI で full-source の pinned quality / test checks を確認する。

**検証:** Black 26.10.0 の `python -m black` と `python -m black --check` は変更 Python 4 ファイルで成功。`tests/test_handoff_record.py`、`tests/test_handoff_projection.py`、`tests/test_compaction_record.py` は合計 74 passed。通常の clone / pip が実行環境の network 制限で利用できず、対象ブランチの source と Black / pytest の release source を GitHub connector から取得して実行した（外部ツールは repository 外の `/tmp` に配置）。`python -m ruff check src tests` は Ruff module がなく実行失敗し、pinned Ruff のインストールも network 権限の実行待ちで中断されたため **Ruff 未検証**。requirements の全依存関係、全 repository の source、全 pytest suite、全 `src tests` の Black check、実 provider matrix、既存 dispatcher / Auto-pilot 経由の end-to-end は **未検証**。この第一段階を PR 4 全体の完了とは扱わない。

**コード対応表（PR 4 第一段階）:** `src/uagent/runtime/handoff_record.py` に immutable record と deterministic item-level provenance、`src/uagent/runtime/handoff_projection.py` に trusted caller bounds / exact reference checks / UTF-8 byte budget、`tests/test_handoff_record.py` と `tests/test_handoff_projection.py` に round-trip / lineage / scope / disclosure / budget の検証を追加。既存 compression / provider / Auto-pilot path の変更はない。

**検証追記・Codex review 対応（2026-10-09）:** 初回 commit `b6be192` の [CI run 37872054415](https://github.com/awaku7/agentcli/actions/runs/37872054415) で Ruff `check src tests`、Black `--check --diff src tests`、全 pytest suite、Python 3.11 / 3.13 / 3.14 compatibility jobs が成功したことを確認。Codex review の P2「Artifact なしの ExecutionRecord が `artifact_ref: null` で往復できない」を再現し、Handoff の `ProvenancedExecutionRecord.from_dict()` のみに null → optional default の正規化を追加した。入力 dict を変更せず、unknown fields / provenance の validation は維持する。null / omitted artifact の wrapper・Handoff 全体の round-trip と unknown nested field の拒否を追加し、関連 pytest は **77 passed**。修正 Python 2 files の Black 整形・check 成功。修正 commit 前のローカル Ruff は module 不在で実行失敗（**未検証**）、全 suite は未実行。修正後の CI / 再レビュー結果は PR #203 で追跡する。共有 decoder、既存 compression、Auto-pilot は変更しない。

PR 4 追加 review 対応（2026-10-09）: P2「累積 Goal evidence が50件を超えると projection が失敗する」を修正。materialized AgentState の累積件数は invalid とせず、送信時に section ごとの最大50件を選択する。観測は末尾の新しい項目、Decision / Constraint は active / tentative を優先し、非選択件数を `omitted_evidence` に明示する（current constraint / work の完全な一覧とは扱わない）。元の AgentState は変更せず、非選択 source の再認可・本文送信は行わない。75件の累積観測、51件の lifecycle evidence、非選択の古い不可用 source の除外を追加し、関連 pytest は **83 passed**。対象2 Python files の Black整形・check成功。修正commit前のローカルRuffはmodule不在で実行失敗・未検証。修正後CI / Codex再レビューはPR #203で追跡する。

PR 4 aggregate source grant review 対応（2026-10-09）: P2「複数 section 合計の出典許可が50件に制限される」を修正。trusted `HandoffBounds.source_refs` には per-record-section の50件上限を適用せず、SourceRef の型検証・immutable snapshot・exact reference の一致・送信時の認可チェックを維持する。work_done 26件 + findings 25件、およびMainの独立2 sectionから合計51件の出典を送る回帰テストを追加し、関連 pytest は **85 passed**。対象2 Python filesのBlack整形・check成功。commit前ローカルRuffはmodule不在で実行失敗・未検証。最新commitのCI / Codex再レビューはPR #203で追跡する。

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
| AgentState / reducer | `src/uagent/runtime/agent_state.py`: 既存 `AgentState` payload を維持し、`structured_compaction` namespace を authoritative AgentState row 内に materialize。`src/uagent/runtime/compaction_reducer.py`: multi-goal / ambiguous evidence / lifecycle / deterministic-delta reducer。 | 既存・新規 | Structured state は同じ AgentState row に保存。ambiguous Goal は既定で未適用。explicit-authorization を呼び出し側が渡す必要がある。 |
| CompactionRecord / GoalDelta model | `src/uagent/runtime/compaction_record.py`: schema v1 immutable dataclasses、typed / scoped `SourceRef`、item-level provenance、source sequence range、DeterministicDelta tracking coverage、split_turn / first_kept_message_id。 | 新規 | model validation 済み。SessionStore はsession-indexに対する session-scoped SourceRef の存在 / kind / id / availability を保存時検証。cross-scope authorization と rehydration 再認可は未接続。 |
| SessionStore / revision | `src/uagent/runtime/session_store.py`: `session_items` ordering index、`agent_states.revision` / `updated_by_client` migration、append-only `checkpoints`、atomic `commit_compaction_record()`、operation idempotency、`list_indexed_messages()`、`list_compaction_records()`。 | 既存・拡張 | 旧 AgentState table を revision 0 で migrate。`save_agent_state()` は `expected_revision` 指定時に stale update を拒否し、structured namespace を常に Reducer 側から保持する（引数省略は既存互換）。comparison-only は checkpoint のみを保存。`list_compaction_records()` は applied record の新しい順取得と `before_revision` による older-page retrieval を提供。 |
| Structured generator / projection | `src/uagent/runtime/structured_compaction.py`: same-session exact source alignment、bounded generation prompt、one-shot repair、CompactionRecord validation / Reducer preflight、atomic commit、split-turn suffix provenance、AgentState → legacy summary projection、best-effort telemetry。 | 新規 | `UAGENT_STRUCTURED_COMPACTION=1` の opt-in auto-shrink から呼ぶ。SourceRef は選択した message window 内のみ許可。Cross-scope authorization / general rehydration は未接続。 |
| Raw History / rolling summary | `src/uagent/core_impl/history.py`: `compress_history_with_llm()`, `shrink_messages()`, `_fix_tool_call_boundaries()`, `_logical_turn_spans()`, `_safe_assistant_cut_points()`, `_oversized_turn_split_cut()`, `_tool_aware_tail_start()`; `src/uagent/llm_message_helpers.py:_maybe_auto_shrink_messages()`。 | 既存・拡張 | opt-in structured auto-shrink は provider context 用 summary projection を返すが、SQLite Raw History / JSONL を置換しない。Generation / schema 失敗時は既存 rolling summary、これも失敗したら bounded deterministic excerpt fallback。feature flag 既定 OFF の既存経路は変更なし。 |
| Tool call / result / logical turn | `session_store.py`: `record_tool_call()` / `list_tool_calls()`、`record_tool_result()` / `list_tool_results()`。Assistant payload / tool result / tool message の source order を索引化。 | 既存・拡張 | 新規 writes は atomic `exact` order。Legacy message linkage は `legacy_message_order`、関連付け不能な旧 call/result は `legacy_approximate` となり exact-range query は fallback する。 |
| Artifact / bounded retrieval | `src/uagent/runtime/artifact_manager.py`, `tool_result_manager.py`, `tool_result_persistence.py`, `context_retrieval.py`; `src/uagent/runtime/history.py:materialize_large_tool_result()` を `src/uagent/llm_flow_helpers.py` から tool result history へ適用。 | 既存 | oversized results は先に Artifact 化し、登録失敗時は bounded text fallback。`test_tool_result_artifact.py` と `test_responses_tool_result_limit.py` を確認。Tool-result Artifact rehydration はPR 3で未接続。Checkpoint SourceRef は同一 Session の message kind に限って retrieval / rehydration 対応。 |
| ContextCandidate / Decision / Budget | `src/uagent/runtime/active_context.py`, `context_decision.py`, `context_budget.py`, `context_manager.py`。 | 既存 | Applied checkpoint のみを session-scoped candidate 化し、query relevance / importance / recency の scoring、decision、budget を適用。Source range の exact / available 状態を選択後に再確認する。 |
| ActiveContextBuilder / Provider Projection | `src/uagent/runtime/active_context.py` の provider-neutral `ActiveContextBuilder`。 | 既存 | `ContextManager.build_message_context()` から `_run_one_round()` の既存 provider-neutral context hand-off に接続。選択 checkpoint は先行 system prefix の後へ背景情報として投影し、重複 reference は再投入しない。 |
| Sub-Agent / Auto-pilot handoff | `src/uagent/runtime/sub_agent_handoff.py`, `sub_agent_jobs.py`, `tools/sub_agent_tool.py` および関連 coordinator。 | 既存・拡張 | trusted opt-in dispatchとJob workerへのsnapshot transportは#204/#205で実装済み。host policy有効化、compact return / Main側の一括適用、Auto-pilot再開は未接続。 |
| 関連テスト | `tests/test_compaction_record.py`, `test_session_item_index.py`, `test_compaction_persistence.py`, `test_session_store.py`, `test_agent_state_store.py` 等。 | 新規・既存 | checkpoint model / ordered source index / atomic persistence tests と既存 SessionStore / AgentState regressions を個別実行。 |

## 6. 受け入れ条件の追跡

詳細は設計書の「Acceptance Criteria」を参照する。各項目は、該当実装と検証の根拠が確認できた段階で更新する。

| # | 条件の要約 | 状態 | 根拠（コード／テスト／記録） |
|---:|---|---|---|
| 1 | AgentState が唯一の current state 正本である | checkpoint 3 基礎実装 | Structured state は AgentState row 内に materialize。checkpoint は delta/evidence のみ。atomic commit tests。 |
| 2 | 複数 Goal を stable `goal_id` と GoalDelta で追跡し、曖昧な関連付けで不要な分裂を起こさない | 基礎実装 | reducer は operation/delta から stable ID を生成し、ambiguous は unresolved evidence に留める。exact normalized title の new-Goal 重複は拒否。explicit authorization / duplicate-title tests。 |
| 3 | Decision / Constraint の supersede・revert と item-level provenance を保持する | 部分実装 | model / reducer が lifecycle と source refs を保存。再活性化禁止等の完全不変条件は review 未完。 |
| 4 | tool call / result を圧縮境界で破壊しない | 未着手 | safe boundary / split-turn は PR 2。 |
| 5 | ファイル変更と execution metadata を DeterministicDelta として保持する | 基礎実装 | Delta を AgentState の deterministic aggregate に保存。実イベント抽出との接続は未実装。 |
| 6 | Tool Result を authorization-aware に Artifact から再取得できる | 未着手 | Runtime authorization-aware rehydration は未接続。 |
| 7 | Checkpoint を ContextCandidate として扱い、source refs から rehydration できる | PR 3 基礎実装 | `compaction_checkpoint_record()` / `retrieve_checkpoint_candidates()` は applied-only filter、scoring / budget、exact available source range validation を行う。`rehydrate_checkpoint_sources()` は同一 Session の exact / available message refs のみを bounded retrieval する。artifact/tool-result と cross-scope authorization は未接続。 |
| 8 | provider / model を切り替えても provider-neutral checkpoint を利用できる | 基礎実装 | `ContextManager.build_message_context()` の provider-neutral projection を `_run_one_round()` から既存 provider path に接続。Fake/provider-neutral integration tests は実施。実provider matrix は未実施。 |
| 9 | structured compaction 失敗時に Raw History を保持して fallback する | checkpoint 4 基礎実装 | opt-in auto-shrink は Raw History / JSONL を置換しない。構造化生成またはvalidation失敗時はlegacy rolling summary、それも失敗時はbounded deterministic excerptsへfallback。`tests/test_structured_compaction_generation.py`。 |
| 10 | Sub-Agent handoff で provenance / scope semantics を再利用する | 部分実装 | #204/#205でtrusted opt-in dispatchとJob transport、#207で子Session出力のcompact return生成APIを追加。Mainへの配送/一括適用は未実装。 |
| 11 | CLI / GUI / Browser tab を共通の Client Instance model で扱う | 未着手 | PR 5。 |
| 12 | stale `base_revision` を検出し silent overwrite しない | checkpoint 3 基礎実装 | `commit_compaction_record()` の expected revision guard / conflict test。multi-client response は未実装。 |
| 13 | revision conflict 後に最新状態を取得し、安全に再評価できる | 未着手 | reload / semantic rebase は PR 5。 |
| 14 | crash 後に最後の committed revision から二重適用なしで resume できる | atomicity / retry 基礎実装 | checkpoint / AgentState / operation ID を同一 transaction 化し retry test。process-restart integration は未実施。 |
| 15 | retrieval / rehydration 時に現在の authorization を再評価する | 未着手 | Authorization resolver と rehydration は未接続。 |
| 16 | compaction / fallback / client / revision / conflict を telemetry で追跡できる | checkpoint 4 基礎実装 | opt-in generator の outcome / fallback reason / source count / duration を内容を含めず記録。Client-wide / revision-conflict telemetry は未実装。 |

## 7. 検証記録

テストは実行したコマンド、対象、結果を記録する。失敗した場合は失敗内容と対応も残す。

| 日付 | フェーズ | 検証内容／コマンド | 結果 | 備考 |
|---|---|---|---|---|
| 2026-10-08 | PR 1 checkpoint 1 | `pytest -q tests/test_compaction_record.py` | 成功（10 passed） | 新規 schema validation / JSON round-trip |
| 2026-10-08 | PR 1 回帰 | `pytest -q tests/test_agent_state.py`, `test_agent_state_store.py`, `test_session_store.py`, `test_shrink_llm.py`（個別実行） | 成功（3 / 1 / 28 / 22 passed） | 既存 AgentState、SessionStore、rolling shrink に回帰なし |
| 2026-10-08 | PR 1 checkpoint 1 | `python_compile`（新規 module / test）、Ruff check | 成功 | Black `--check` 成功。明示確認を受けて2ファイルを整形済み。 |
| 2026-10-08 | PR 1 checkpoint 2 | `pytest -q tests/test_compaction_record.py`, `pytest -q tests/test_session_item_index.py` | 成功（12 / 6 passed） | typed refs / sequence range / coverage / legacy-order fallback / tombstones |
| 2026-10-08 | PR 1 checkpoint 2 回帰（checkpoint 2 時点） | SessionStore / SQLite command / ToolResult / portability / AgentState / shrink test files（個別実行） | 成功（28 / 10 / 6 / 1 / 4 / 59 / 3 / 1 / 22 passed） | checkpoint 2 時点で合計134件。checkpoint 3 後の最終回帰は別行に記録。 |
| 2026-10-08 | PR 1 checkpoint 3 | `pytest -q tests/test_compaction_persistence.py` | 成功（15 passed） | atomic checkpoint/state commit、revision conflict、comparison-only、idempotency、ambiguous resolution、duplicate-title guard、decision/constraint lineage、legacy migration / source validation |
| 2026-10-08 | PR 1 checkpoint 3 回帰 | `pytest -q tests/test_session_store.py`, `pytest -q tests/test_agent_state_store.py` | 成功（28 / 1 passed） | revised save semantics と既存 SessionStore / AgentState persistence |
| 2026-10-08 | PR 1 checkpoint 1〜3 static | Ruff check、`python_compile`（6 files）、Black `--check`（6 files） | 成功 | 新規・変更Python 6ファイル。 |
| 2026-10-08 | PR 1 checkpoint 4 targeted | `pytest -q tests/test_structured_compaction_generation.py`, `tests/test_shrink_llm.py`, `tests/test_compaction_persistence.py`, `tests/test_session_store.py`, `tests/test_session_item_index.py` | 成功（15 / 22 / 17 / 28 / 6 passed） | Fake OpenAI-compatible client tests cover exact source alignment, repair once, raw-history retention, deterministic fallback, idempotent retry, and revision conflict. `py_compile` 5 files, Ruff, Black `--check`, and Markdown format check passed. Live provider matrix is pending. |
| 2026-10-09 | PR 2 checkpoint 1 | `pytest -q tests/test_shrink_llm.py` | 成功（25 passed） | Logical Turn parser、parallel tool call/result grouping、turn boundary の tail adjustment、turn 単位 chunking を追加。 |
| 2026-10-09 | PR 2 checkpoint 1 回帰 / static | `pytest -q . --durations=30`; Ruff / Black check（変更2 Python files）; `git diff --check` | 成功（全 suite） | Oversized-turn split、Artifact-first、prefix/suffix 復元は未実装。 |
| 2026-10-09 | PR 2 checkpoint 2 targeted / regression | `pytest -q tests/test_shrink_llm.py`, `test_structured_compaction_generation.py`, `test_compaction_record.py`, `test_tool_result_artifact.py`, `test_responses_tool_result_limit.py`（個別実行）; `pytest -q . --durations=30` | 成功（29 / 18 / 12 / 2 / 4 passed; 全 suite 成功） | Safe assistant split、small-message-count token trigger、SessionStore reopen後のsource range / first_kept_message_idによるprefix/suffix再構成、alignment失敗時のfallback、既存Artifact-first/bounded fallbackを検証。Ruff / Black と Markdown format check も成功。 |
| 2026-10-09 | PR 3 targeted / full regression / static | `pytest -q tests/test_context_compaction_candidates.py`（4 passed）, `pytest -q tests/test_compaction_persistence.py`（18 passed）, `pytest -q tests/test_context_manager_pipeline.py`（9 passed）, `pytest -q . --durations=30`; Ruff check `src tests`, Black `--check src tests`, `python_compile`（変更6ファイル）, Markdown format check, `git diff --check` | 成功（targeted 31 passed; 全 suite 成功。全 static checks 成功。） | Applied-only candidate conversion、scoring / decision / budget、duplicate suppression、older checkpoint paging、same-session exact message SourceRef rehydration、store failure fallback を検証。実provider matrix / 独立CI実行は未実施。 |

### Provider Matrix

| Provider | structured generation | validation / fallback | 状態／備考 |
|---|---|---|---|
| OpenAI Responses | 未実施 | 未実施 | |
| Anthropic | 未実施 | 未実施 | |
| Gemini | 未実施 | 未実施 | |
| OpenAI-compatible local provider | Fake client unit path only | Fake client validation / fallback tests | Real provider connectivity / model matrix not verified. |

## 8. 判断・課題ログ

| 日付 | 種別 | 判断／課題 | 根拠・影響 | 状態 |
|---|---|---|---|---|
| 初期記録 | 運用 | 本書を実装計画および継続作業の記録先として作成。設計上の正本は設計書とする。 | 実装進捗と検証根拠を設計仕様から分離して追跡する。 | 採用 |
| 初期記録 | スコープ | 実装を PR 1〜5 に分割し、PR 1 では boundary algorithm を大きく変更しない。 | 設計書の段階導入方針に従い、schema と boundary semantics の変更を同時にしない。 | 採用 |
| 2026-10-08 | 設計判断 | PR 1 に source sequence / typed SourceRef / minimal atomic persistence を含め、PR 5 は multi-client rebase / integration に集中する。 | Checkpoint、AgentState、revision、idempotency の一貫性を基礎 PR で保証する。詳細は設計書 §6.1 / §23 / §26。 | 採用 |
| 2026-10-08 | 設計判断 | ambiguous Goal は自動適用・自動 merge せず、明示的な解決 delta を追記する。 | Goal 分裂・誤統合を防ぎ、元 Checkpoint の immutable lineage を維持する。設計書 §6.2。 | 採用 |
| 2026-10-08 | コード調査（初期時点） | SessionStore / WAL / messages / tool tables は存在する一方、AgentState revision / `session_items` / Checkpoint table は未実装だった。 | checkpoint 2 で source index、checkpoint 3 で revision / Checkpoint table を migration 付きで追加。 | 初期調査記録 |
| 2026-10-08 | 実装判断（checkpoint 1） | provider / storage / compression path に依存しない `compaction_record.py` model / validation から開始。 | 既存動作を変えずに schema 契約を単体テストで固定。後続 checkpoint で typed SourceRef、sequence index、永続化を追加した。 | checkpoint 1 完了 |
| 2026-10-08 | 実装判断（checkpoint 3） | Structured current state は別の current-state table にせず、AgentState JSON 内の `structured_compaction` namespace に materialize する。 | AgentState を唯一の current-state 正本に保ち、legacy save は呼び出し側の指定にかかわらず reducer-owned namespace を維持する。 | 採用 |
| 2026-10-08 | 実装判断（checkpoint 3） | `new` Goal のIDは session / operation / delta ID から deterministic UUID5 で発行し、ambiguous delta は unresolved evidence に留める。 | operation retry の安定性を確保し、類似度だけによる自動 merge / 適用を避ける。既存 Goal と normalized exact-title duplicate は新規作成を拒否する。explicit resolution は trusted caller の authorization IDs を要求する。 | 採用。確認 UI / caller 未接続 |
| 2026-10-08 | 実装判断（checkpoint 3） | SessionStore の commit API で session-scoped SourceRef を ordered index と照合し、Checkpoint row / session item / AgentState revision を一 transaction にする。 | ID / kind / scope / availability の不一致を拒否し、部分 commit と参照先 tombstone 利用を防ぐ。cross-scope authorization resolver は別段階。 | 採用 |
| 2026-10-08 | 実装判断（checkpoint 4） | Structured compaction は `UAGENT_STRUCTURED_COMPACTION=1` の opt-in auto-shrink に限定し、既定は OFF。SourceRef と入力メッセージの厳密な一致が証明できなければ、structured commit を行わず既存 summary path へ fallback。 | Early rollout で従来挙動を保ち、誤った provenance / stale history replacement を防ぐ。structured success と fallback の双方で durable Raw History / JSONL を置換しない。 | 採用（cross-scope rehydration は後続） |
| 2026-10-08 | 検証 | 明示確認後に Black で model / test を整形し、`--check` を再実行。 | 整形が反映され、checkpoint 1 の format gate を通過。 | 解決済み |

## 9. 作業セッション記録

各作業セッションの終了時に、実施内容と次の一手を一行以上追加する。

| 日付 | 実施内容 | 変更ファイル | 検証結果 | 次の作業 |
|---|---|---|---|---|
| 2026-10-09 | Codex review P2 の null artifact デコード失敗を再現・修正。Handoff decoder に限定し、入力不変 / nested validation を検証。初回 CI 全 checks 成功も確認。 | `runtime/handoff_record.py`, `tests/test_handoff_record.py`, implementation docs | 関連 pytest 77 passed、対象 Black 整形・check 成功。修正前ローカル Ruff は実行失敗・未検証。 | 修正 commit の CI と Codex 再レビューを確認する。 |
| 2026-10-09 | PR 4 第一段階として immutable HandoffRecord / item-level provenance / dispatch lineage と caller-bounded Main / return projection API を追加。既存 dispatcher、state application、Auto-pilot 再開への接続は未実装。 | `runtime/handoff_record.py`, `runtime/handoff_projection.py`, 対応する2 test files、implementation / DEVELOP docs | 対象 Black 26.10.0 整形・check、関連 pytest 74件、syntax / whitespace check 成功。Ruff・全 suite・実 provider / end-to-end は未検証。詳細は PR 4 節。 | CIで未検証 checks を再実行し、dispatch snapshot / source index 接続から段階的に進める。 |
| 2026-10-09 | Job manager に host-owned structured dispatch policy とsnapshotのworker transportを追加。構造化Jobはshared store / live inboxを拒否し、module-level Sub-Agent tool entrypointはdispatchを非公開runtime引数としてRunnerへ渡す。既存hostはpolicy未設定のため従来動作を維持。 | `runtime/sub_agent_jobs.py`, `tools/spawn_sub_agent_tool.py`, `tools/sub_agent_tool.py`, Job / handoff tests, DEVELOP docs | Black 26.10.0整形・check、py_compile成功。関連pytest **61 passed**。3ケースは部分ソースに欠落する`uagent.core` / Job plugin依存のため除外。Ruffはmodule不在、pinned installは長時間待ち後に中断され未検証。全suite / CI未確認。 | CLI/Web/GUI/A2Aの各trusted Goal/source policyを別段階で設定し、child source index / compact returnを実装する。 |
| 初期記録 | 設計書を基に、本実装計画・進捗記録を作成。実装コードの調査・変更・テストは未実施。 | `docs/UAG_STRUCTURED_COMPACTION_IMPLEMENTATION.md` | 未実施 | 既存コードを調査し、PR 1 のコード対応表と最小スコープを確定する。 |
| 2026-10-08 | PR 1 の実装順序を4チェックポイントに分け、無関係な Markdown 整形を避ける運用を追記。実装コードは変更せず。 | `docs/UAG_STRUCTURED_COMPACTION_IMPLEMENTATION.md` | 文書更新のみ。テスト未実施。 | PR 1 のコード対応表を埋め、最初のチェックポイントから着手する。 |
| 2026-10-08 | 設計書を再レビューし、8項目の仕様境界を明確化して設計書・実装記録を更新。 | `docs/UAG_STRUCTURED_COMPACTION_DESIGN.md`, `docs/UAG_STRUCTURED_COMPACTION_IMPLEMENTATION.md` | ドキュメントレビュー・編集のみ。コード調査とテストは未実施。 | PR 1 のコード調査で既存 SessionStore / DB schema / revision API / schema version を照合する。 |
| 2026-10-08 | PR 1 checkpoint 1 として provider-neutral な record dataclasses / validation と単体テストを追加。AgentState / SessionStore / history compression は変更なし。 | `src/uagent/runtime/compaction_record.py`, `tests/test_compaction_record.py`, `docs/UAG_STRUCTURED_COMPACTION_IMPLEMENTATION.md` | 初回10 tests、checkpoint 2 後12 tests。関連 regression tests 成功。 | checkpoint 1 を完了し、typed SourceRef / session_seq の設計実装へ進む。 |
| 2026-10-08 | PR 1 checkpoint 2 として typed SourceRef / tracking coverage / session_items / watermark / legacy backfill / tombstone を追加。圧縮・AgentState 更新には未接続。 | `src/uagent/runtime/compaction_record.py`, `src/uagent/runtime/session_store.py`, `tests/test_compaction_record.py`, `tests/test_session_item_index.py`, design / implementation docs | checkpoint tests 18 passed、checkpoint 2 時点の related regression tests 134 passed、Ruff / py_compile 成功。 | checkpoint 2 完了後、checkpoint 3 の atomic persistence / revision / Reducer を実装。 |
| 2026-10-08 | PR 1 checkpoint 3 として revision migration、Checkpoint table、session-scoped SourceRef の index validation、atomic commit / reducer / idempotency を追加。 | `src/uagent/runtime/session_store.py`, `src/uagent/runtime/compaction_reducer.py`, `tests/test_compaction_persistence.py`, implementation docs | 新規 tests 15、SessionStore / AgentState regression 29 passed。source index regressions を含む既存関連 regression 134 passed。Ruff / py_compile / Black --check 成功。最終 diff review は継続。 | checkpoint 3 の diff review と broader regressions 後、checkpoint 4 の LLM / legacy summary path 接続へ進む。 |
| 2026-10-08 | PR 1 checkpoint 4 の基礎接続。Opt-in structured generation / provenance validation / one-shot repair / reducer + atomic commit / bounded summary projection / legacy and deterministic fallback / metadata-only telemetry を auto-shrink に接続。Strict source alignment できない時は structured record を commit せず fallback。成功・fallbackとも SQLite Raw History と JSONL を置換しない。 | `src/uagent/runtime/structured_compaction.py`, `src/uagent/runtime/session_store.py`, `src/uagent/core_impl/history.py`, `src/uagent/llm_message_helpers.py`, `tests/test_structured_compaction_generation.py`, implementation docs | structured generation 16, shrink 22, persistence 17, SessionStore 28, session index 6 passed; `py_compile` passed 5 files; Ruff, Black `--check`, and Markdown format check passed. Live provider matrix and cross-scope authorization/re-hydration review remain pending. | PR 1 は条件付き完了として扱い、未検証事項は別途追跡。PR 2 Safe Boundary / Split Turn を独立差分で開始する。 |
| 2026-10-09 | PR 2 checkpoint 1 として Logical Turn の範囲解析、parallel tool results を含む turn の不可分な chunking、tail boundary の turn-aware adjustment を追加。oversized turn split / Artifact-first は未実装。 | `src/uagent/core_impl/history.py`, `tests/test_shrink_llm.py`, implementation docs | 対象25 tests と全 pytest suite 成功。変更Pythonファイル Ruff / Black check 成功、`git diff --check` 成功。 | oversized tool result の Artifact-first 処理、assistant 境界での oversized-turn split、復元可能性・failure fallback tests を続ける。 |
| 2026-10-09 | PR 2 checkpoint 2 として oversized logical turn を安全な assistant boundary で prefix/suffix に分割し、structured Checkpoint に `split_turn` と `first_kept_message_id` を記録。Oversized tool result の Artifact-first 経路は既存実装を確認。 | `src/uagent/core_impl/history.py`, `src/uagent/llm_message_helpers.py`, `src/uagent/runtime/structured_compaction.py`, `src/uagent/runtime/compaction_record.py`, `tests/test_shrink_llm.py`, `tests/test_structured_compaction_generation.py`, implementation docs | 対象テストは 29 / 18 / 12 / 2 / 4 passed（個別実行）、全 pytest suite 成功。Ruff / Black fix+check、Markdown format check、`git diff --check` 成功。 | PR 2 基礎実装を完了として扱い、PR 3 ContextCandidate と ActiveContextBuilder の接続を調査・設計する。 |
| 2026-10-09 | PR 3 基礎実装として applied CompactionRecord の ContextCandidate adapter、scoring / decision / budget integration、SessionStore page retrieval、duplicate suppression、same-session exact message SourceRef rehydration、および `_run_one_round()` provider-neutral context connection を追加。 | `src/uagent/runtime/session_store.py`, `src/uagent/runtime/context_retrieval.py`, `src/uagent/runtime/context_manager.py`, `src/uagent/uagent_llm.py`, `tests/test_compaction_persistence.py`, `tests/test_context_compaction_candidates.py`, implementation docs | targeted tests 4 / 18 / 9 passed、全 `pytest -q . --durations=30` 成功。Ruff check `src tests`、Black `--check src tests`、6-file py_compile、Markdown format、`git diff --check` 成功。実provider matrix / 独立CI reviewは未実施。 | PR 3 基礎実装を完了として扱い、次に PR 4 Sub-Agent / Auto-pilot Handoff を開始する。cross-scope authorization は PR 5、artifact/tool-result rehydration と実provider matrix は別途追跡する。 |

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
1. **既存 SessionStore 前提 — 初期コード調査時点。** `sessions`、`messages`、`tool_calls`、`tool_results`、`agent_states`、`context_decisions` と SQLite WAL / busy_timeout を確認。当時は `agent_states` に revision がなく、保存は unconditional UPSERT、global `session_seq` / checkpoint table も未実装だった。現在は checkpoint 2 / 3 で該当 schema / API を追加済み。設計書 §23.2.1。
1. **schema version — 初期 v1 採用。** src 内に Structured Compaction record の既存 schema version は見つからず、新しい payload schema v1 とする。SQLite migration version とは分離し、unknown version を model message にしない契約を設計書 §6.1 / §23.9 に反映済み。

### 初回レビュー時点の結論（checkpoint 1 開始時の履歴スナップショット）

以下は初回設計レビュー直後の記録であり、現在の実装状態を表すものではない。最新状態は「3. 現在の状態」および「7. 検証記録」を参照する。

- **設計:** 明確化事項を `UAG_STRUCTURED_COMPACTION_DESIGN.md` に反映済み。設計全体の再作成は不要。
- **当時の実装:** PR 1 checkpoint 1 の in-memory model のみ。SessionStore / compaction path への接続は未実施だった。
- **当時の検証:** checkpoint 1 の unit / regression tests は成功。以後、Black gate は通過し、SessionStore checkpoint 2 / 3 を追加した。

## 11. 更新履歴

| 日付 | 変更 |
|---|---|
| 初期記録 | 実装計画、フェーズチェックリスト、受け入れ条件追跡、検証・判断・セッション記録欄を作成。 |
| 2026-10-08 | PR 1 を小さな実装チェックポイントに分け、不要な Markdown 整形を避ける方針を追加。 |
| 2026-10-08 | 設計書の再レビュー論点を確定し、設計書と PR チェックリストへ反映。 |
| 2026-10-08 | PR 1 checkpoint 1 の provider-neutral model / validation / tests を追加し、Black 整形。 |
| 2026-10-08 | PR 1 checkpoint 2 / 3 の session item index、AgentState revision、atomic Checkpoint commit / Reducer を実装し、テスト記録と未実装境界を更新。 |
| 2026-10-09 | PR 3 Context Runtime Integration の checkpoint candidates / source retrieval / ActiveContext connection を実装・検証し、PR3 checklist、コード対応表、検証記録を更新。 |
