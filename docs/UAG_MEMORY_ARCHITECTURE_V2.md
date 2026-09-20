# UAG Memory Architecture v2 — 再レビュー版

## 調査範囲と位置づけ

対象は awaku7/agentcli、v0.7.11、commit `18c70a4cae6cb3ff5564dfdf8d6038c595050b83`。2026-09-20に取得した固定スナップショットの再レビューであり、本書の現状分析はこのcommitを基準とする。

コミット準備時に`git fetch origin`を実施し、`origin/main`がこのcommitと一致することを確認した。以後の実装着手時にも基準を再確認する。

本書は前版を置き換える。実装変更・PR作成は行っていない。ChatGPT内部実装を模倣する設計ではなく、UAGで確認できた動作と不足に基づく提案である。前の会話で説明したChatGPTの階層的記憶、検索方式、Composerの存在は内部仕様として検証できていない。

### 既存設計との関係

- [UAG Context Management Design](UAG_CONTEXT_MANAGEMENT_DESIGN.md)：Historyと投影の分離、Stable/Active/Persistent Contextの原則を継承する。
- [Brain Memory設計書](BRAIN_MEMORY_DESIGN.md)：特に20〜26節の正本、承認、引用、競合、忘却の契約を継承する。本書はBrainの代替でも、同設計が実装済みだという宣言でもない。
- 本書：既存Personal/Profile/Sessionの不具合修正、評価、ContextPlanへの選択投影を先行させる具体的な実装順序を扱う。

Brainは整理・探索のための派生レイヤー、SessionStoreは会話の正本、既存Memoryは正式なメモの保持先、AgentStateは作業状態の正本とする。BrainのMarkdownとSQLiteに同じ事実の更新権限を二重に持たせない。将来Brainを検索元へ追加する場合も、同じsource参照・scope・承認契約へ接続する。

旧recordに承認の証拠がない場合、実在しない承認履歴を補完しない。既存の利用を維持しつつprovenanceはlegacy/unknownとし、自動共有・自動昇格には用いない。

## 1. 前版で訂正する判断

| 前版の判断 | 再レビュー後 |
|---|---|
| 記憶の自動抽出が弱い・未整備 | Profileには既にLLM抽出、マージ、重複排除がある。発火条件・初回反映・出典管理を分けて評価する |
| 汎用Retrieval/Decisionは主にTool Resultで稼働 | 自動Tool Result取得も直接search→format→注入であり、汎用候補Decision経路を通らない |
| 全メモリを検索で選べば改善 | 適用対象の明示的制約は検索一致に依存させない。常時適用枠と検索枠を分離する |
| FTS5を接続するP0は低リスク | 日本語検索、無関連候補除外、会話書換え、予算、再開時の整合性が未解決 |
| 0.35等の重みを推奨 | 実測根拠がないため撤回。評価データで比較する実験パラメータとする |
| 一致するsubject/predicateは新しい値で置換 | 複数PC・プロジェクト・期間の併存を表せず危険。明示訂正と適用範囲の一致を要求する |
| 大型MemoryRecordとProfile統合を早期導入 | 保存互換性を維持し、小さな契約と読み取り専用評価から始める |

## 2. 確認した実経路

### 2.1 Personal / Shared Memory

`add_long_memory_tool.run_tool` → `long_memory.append_long_memory` → SQLite/JSONL。

SQLiteのMemoryStoreはid・created_at・noteを保持する。起動側は `append_long_memory_system_messages` → `MemoryManager.records_for_prompt` → `build_long_memory_system_message` でsystem message化する。PersonalとSharedは別々に整形され、それぞれ約4,000文字で打ち切られる。Profileも別枠である。4,000文字は全記憶の総予算ではない。

`MemoryManager`はpersonal/shared/profile/sessionのFacadeだが、起動時の利用は主にpersonal/shared。profileは別処理、session候補にはstoreとsession IDの指定が必要であり、4種類を自動的に統合検索しているわけではない。

### 2.2 Profile

デフォルトで有効。`profile_manager`にはLLM抽出、制約・好みのマージ、重複排除がある。確認できた非同期発火点は履歴のLLM圧縮とskill終了。通常の全ターン終了へ一律接続されているとは確認できない。過去ログからの明示的な再構築経路もある。

環境の値は更新される。好み・制約は類似判定、件数制限、LLM整理を使うため、「更新処理が存在しない」は誤り。ただし、出典単位で検証可能な訂正・競合管理ではない。

### 2.3 Tool ResultとContext Runtime

`run_llm_rounds` → `_inject_retrieved_tool_context` → coreにattachされた`retrieve_tool_context` → 当該sessionの`search_tool_results` → `ContextResultManager.format_retrieved_context` → 最新user messageの本文へ前置。

その後にコンテキスト予算処理がある。したがって、完全に予算外ではない。一方、`retrieve_candidates` → `ContextDecisionEngine`による候補選別をこの自動取得経路は通らない。

`build_active_context_from_records`は利用可能な部品だが、src内での検索では外側の本番呼出元を確認できない。候補版`build_active_context`にはbenchmarkの呼出しがある。APIと単体テストの存在を、稼働経路への統合と同一視しない。

### 2.4 既存の作業状態

`AgentState`はgoal、completed_steps、current_step、files、errors、next_action等を既に保持する。WorkingStateを新しいMemory表へ二重管理しない。会話中の進捗の正本はAgentState、過去の根拠はSessionStore、将来も再利用する明示的知識はMemoryとする。

## 3. 実行で確認した問題

外部APIを呼ばないPython直接検証を実施。pytestは未導入で、対象テストスイートは未実行。次は既存関数またはSQLiteを直接呼んだ結果である。

| 検証 | 観測 | 設計上の意味 |
|---|---|---|
| 無関連候補をquery付きで取得・判定 | relevance=0、score=0.25、無制限予算ではKEEP | exclude条件が0.25未満なので無関連でも境界上で残る。単に接続してもprecisionは保証されない |
| note/tsの生recordを汎用Retrieverへ渡す | contentが空、sourceはtool_result | Memory専用Adapterが必須 |
| noteを通常formatterへ渡す | scope/note/tsを含むJSONが本文へ出る | noteを優先取得していない。ID等のmetadataで予算を浪費する |
| Profileのsystem messageがない状態で更新 | 初回system messageは追加されない | 初回学習が当該live messagesへ反映されない |
| 長い古いnoteの後ろに新しいnote | 新しいnoteは出力されず、本文長は4,048文字 | 古い順のprefix保持と、打切りmarkerによる上限超過 |
| 標準FTS5で「コードは必ず全体を表示する」を保存し「全体」を検索 | 0件 | FTS5採用だけでは日本語検索を解決しない |

静的に追加確認した事項:

- `append_long_memory`は例外を握りつぶすが、toolはsavedを返す。失敗を成功として通知する経路がある。
- SQLite更新は全件replaceでIDを再採番し得る。現IDをそのまま恒久的出典IDに転用できない。
- Profileの非同期処理はlive messagesを変更する。将来のMemory処理は背景workerによる会話直接変更を避ける。
- 既定ContextBudgetは無制限。Memoryの予算を全体既定値だけに依存させない。
- `ContextCandidate`には前版が前提にした任意metadata fieldはない。専用Adapterまたは明示的な契約変更が必要。

これらは「体感が悪い唯一の原因」を証明しない。ユーザーの実ログで想起の成功・失敗を比較する評価が必要である。

## 4. 改訂する設計

### 4.1 三つの入力枠

| 枠 | 内容 | 取得・適用 |
|---|---|---|
| Applicable constraints / preferences | 対象ユーザー・プロジェクトに有効な明示的制約、安定した好み | 語句の検索一致に依存させず小さな専用枠に置く |
| Working context | AgentStateと直近の会話 | session/taskを明確にして既存経路を利用 |
| Retrieved evidence | 過去会話、決定、関連メモ、成果物の参照 | 必要時に検索。無関係なら0件を許容 |

適用範囲は必須。C# 7.3という制約をPythonの依頼に適用しない。現在のユーザーの明示的変更が、同じ適用範囲の過去設定より優先される。ユーザーの好みはシステムの安全・権限方針を上書きしない。

### 4.2 Turn単位の読み取り専用Memory Context

元のuser messageを変更しない。原文と現在のAgentStateからqueryを作り、取得結果を一時的なprojectionとしてContextPlan生成前に合成する。

同一turnのtool loop/retryでは同じsnapshotを再利用し、必要な追加検索だけ明示的に更新する。cancel後やsession切替後に古い背景処理の結果を混ぜない。投影済み記憶を履歴の原文として再学習しない。

Responses継続やprovider cacheに残った古い文脈は、ローカル削除だけでは消えない場合がある。訂正・忘却時の継続リセット/再投影を契約として検証する。「Providerへ固有の抽出ロジックを入れない」と「既存provider経路の検証不要」は別である。

### 4.3 最小の記憶契約

初期に必要な属性は、安定ID、所有者/適用scope、project参照、kind、本文、source参照、record revision、status、作成・更新日時。

出典にはuser statement / assistant proposal / tool observation / imported legacyを区別する。assistantの提案をユーザーの採用決定に昇格させない。旧noteの出典不明は不明のまま移行する。

subject/predicate/valueの正規化、数値confidence、アクセス回数、embeddingは必須にしない。推定confidenceは権限や真偽の保証ではない。

### 4.4 検索と選択

所有者・共有権限・projectのfilterはスコアではなく検索前の境界とする。個人からsharedへの自動昇格を禁止する。

候補生成はFTS5に限定しない。日本語の文字n-gram/利用可能なtokenizer/限定的substring検索などを評価し、短語や英数字・パスもテストする。Embeddingは後から比較する。

まず無関連候補を除外し、その後に重要度・鮮度等で順位を付ける。importanceやrecencyだけで無関連候補を救済しない。relevanceが0.25等の単一閾値へ暗黙変換される設計は避ける。

通常取得と「以前の決定を探して」のepisodic取得は分ける。後者はSessionStoreの候補からsource messageを必要な範囲だけ展開し、結論の根拠を確認する。「続き」だけでは語句検索にならないため、直近のユーザー発言とtask/project状態から補う。

### 4.5 ComposerとBudget

初期Composerは決定論的formatterとし、毎ターンLLMで再要約しない。短い関連項目とsource IDを保持し、不確実・過去時点の情報を明示する。

Memory専用の有限予算と全体の残予算の両方を守る。適用制約の枠を先に確保し、項目の途中切断で否定や例外を落とさない。収まらない制約は無言で捨てず診断対象にする。token計測は既存estimatorを利用し、推定値であることを記録する。

ContextPlanは既にmessages等からfingerprintを生成する。新しいglobal memory revisionを直ちに全identityへ足す必要はない。snapshot revisionはまず診断情報とし、実際の投影変更・忘却で既存の継続不変条件が成立するか検証する。

### 4.6 更新・訂正・忘却

背景抽出は候補を作るだけとし、確定更新は単一writer/transaction、expected revision、source IDによる冪等性で管理する。全会話を反復抽出しない。

新しい値だけで旧値を廃止しない。同一対象・適用範囲の明示訂正を確認したときだけsupersede。環境の併存は別record、曖昧な競合は両立/未解決として扱う。現在の文脈から矛盾が解けなければ確認する。

forgetは単なるstatus変更と区別する。検索index、cache、派生summary、継続contextからの除去、および元履歴からの再抽出防止を設計する。監査ログへ削除対象の本文を残さない。元会話も削除するかは利用者の指定と保持方針に分ける。

### 4.7 セキュリティ

取得した履歴・tool outputは証拠であり、新しい実行指示ではない。secret除去は抽出前と保存前に行う。秘密を含み得る本文をtelemetryへ出さず、ID・理由・件数を記録する。共有記憶の記述が個人の権限やtool許可を上書きしない。

## 5. 実装順序を変更する

### PR 1: 現行の信頼性修正と評価ケース

noteの整形、保存失敗の返却、初回Profile反映の再現テストを追加する。noteの整形と保存失敗の返却を先に修正し、4,000文字のmarker込み境界をテストする。Profileの初回反映修正は背景workerでappendする暫定対処を避け、PR 3の安全なturn境界への適用と一緒に行う。PR 1時点で初回反映が解決したとは報告しない。

同時に小さなgolden casesを追加する。起動時記憶、C#の制約、古い/新しい設定、別PC、別project、無関連、短い日本語、初回学習、保存失敗を含める。検索の本番切替はしない。

### PR 2: Memory Adapterとshadow retrieval

既存storeを保持し、ID/出典の互換Adapter、適用scope、無関連filter、日本語候補生成、診断理由を実装する。shadowではモデル入力を変えず、現行方式と候補・予算だけ比較する。記憶本文を診断ログに複製しない。

### PR 3: 明示opt-inのturn projection

適用制約枠を維持したまま、検索証拠をContextPlanへ統合する。原文不変、snapshot冪等性、二重注入防止、有限Memory Budgetを保証する。CLI/GUI/Web/A2Aの所有者・session設定を個別に検証する。「共通関数だから同じ」とはみなさない。

rollbackはprojection flagで可能にする。元データの削除・一括変換をこの段階では行わない。

### PR 4: 構造化更新と明示的訂正・忘却

stable ID、transaction、version、source、supersede、削除制御を追加する。旧storeのmigrationはbackup、schema version、件数照合、再実行の冪等性を保証する。全件replaceをなくしてからIDを外部参照へ使う。

### PR 5以降: Curator拡張とsemantic検索

既存Profile抽出をAdapterとして活用し、必要ならturn差分抽出へ拡張する。Profile storeの廃止は同等性確認後の別変更とする。EmbeddingやLLM rerankerは日本語・言い換えの実測改善がある場合に追加する。

## 6. 評価基準

評価は最後ではなくPR 1から行う。最低限、必要記憶のRecall、無関連注入率、制約保持率、古い情報の誤適用率、別project混入率、訂正反映、忘却後再出現、Memory token量、遅延・追加LLM回数を測る。

決定論的なfixtureテストと、固定シナリオに対する実モデルの複数回評価を分離する。LLM judgeだけで正解を決めず、sourceと明示的な期待結果を持つ。

安全条件は、別所有者・権限外情報の混入ゼロ、原文書換えゼロ、保存失敗の成功通知ゼロ。品質閾値と遅延目標はbaseline測定後に決め、裏付けのない数値を推奨しない。

## 7. 再レビューの結論

「MemoryとContext Runtimeの連携を改善する」は維持する。ただし、接続だけで自然な記憶になるとは言えない。優先順位は、既存機構の信頼性、適用制約の保持、出典とscope、評価、選択注入、構造化更新の順である。

巨大なCuratorを新設する前に、今ある記憶が確実に保存され、正しく初回反映され、関連時だけ根拠付きで再利用されることを保証する。

## 8. 実作業の手順と完了ゲート

### 8.1 毎回の開始手順

1. fetch後に基準commit、作業ツリー、既存PRを確認する。未コミット変更を混ぜず、実装は目的別branchへ分ける。
2. 変更対象の入口、保存先、caller、host、provider境界を表にする。名称やテストの存在だけで本番接続済みと判断しない。
3. 問題の再現テストを先に作り、現行失敗と期待結果を記録する。外部APIは原則fake/mock、保存先は一時領域へ隔離する。
4. 最小変更で対象テストを通し、関連範囲、lint、全体CI相当へ広げる。未実行・既知失敗・今回の退行を区別する。
5. diffをレビューし、変更対象だけをstageする。テスト結果と未解決事項を記した単一目的のcommitを作る。
6. push後にremote commitを確認し、CI結果を確認する。push成功とCI成功は別々に報告する。

今回のcommitは設計文書だけであり、以下の実装PRを実施したことにはしない。

### 8.2 PRごとの具体的な範囲

| PR | 主な対象 | 完了条件 | このPRでは行わないこと |
|---|---|---|---|
| 1: 信頼性 | util_message、long_memory、add/get tool、Web/CLIのcaller、関連tests | 保存失敗をtool/Webが成功扱いしない。note本文の整形と上限を確認。初回Profile未反映を再現 | 検索の有効化、schema移行、背景処理の全面改造 |
| 2: shadow | MemoryManagerの読取Adapter、候補生成、診断、テストfixture | user/project scopeを守る。無関連0件、日本語、旧recordを評価。モデルへ送る内容は変更しない | 自動記憶更新、承認の追加取得、provider継続の変更 |
| 3: opt-in投影 | runtime_memory、ContextManager、round入口、Profile結果引渡し、host adapter | 原文不変、制約保持、初回Profile反映、有限予算、同turn再試行時の重複なし。全hostと継続APIを確認 | store廃止、全履歴移行、Dream有効化 |
| 4: 明示更新 | MemoryStore、既存承認policyとの接続、source管理、migration、forget | transaction/冪等性/競合停止、更新と削除の反映、移行の再実行安全性 | 推測による無条件上書き、権限拡大、shared自動書込 |
| 5以降: 拡張 | 既存Profile extractor、Brain adapter、任意semantic検索 | baseline比の改善とコストを測定し、採用/不採用を記録 | 効果未測定での既定ON、第二の正本・承認系の追加 |

PR 2の前提としてMemory IDを再採番する既存replaceの問題を回避する。shadow段階ではbackendのrevisionとrecord位置を含む一時参照を使い、更新後に無効化する。この参照を恒久IDと呼ばない。PR 3も読取snapshot限定とし、永続的なsource linkや忘却の保証にはPR 4のstable IDを要求する。

legacy noteのproject/ownerが不明なら、勝手に推定して他scopeへ配置しない。shadowの入力範囲は現在の認可済みstoreに限定し、未分類として可視化する。Brainのpath filterをACLの代用にしない。

### 8.3 先に固定する契約

- 保存結果：成功/失敗を明示する。例外伝播または型付き結果のどちらかに統一し、tool、Web、CLIをすべて追う。
- 適用制約：検索不要の枠へ何を入れるかを明示する。自由文の旧noteを無条件に恒久的制約へ昇格させない。
- 読取snapshot：owner、project、session、turn、source revision、選択理由、使用予算を保持する。
- 非同期Profile：workerは候補と対象revisionを返し、turn境界の所有者が反映する。古いsessionの結果は破棄する。
- 承認：新しい推測・競合解消・本番知識更新はBrain設計と既存policyに従う。既存データを読むopt-inと、新しい永続書込の許可は別に扱う。
- エラー時：追加検索の失敗は「記憶なし」と識別し、適用制約を消さない。scope不明や権限失敗では別storeへ迂回しない。

### 8.4 検証マトリクス

| 軸 | 必須ケース |
|---|---|
| 保存 | SQLite/JSONL、空入力、書込不可、DB lock、失敗時のtool/Web応答 |
| 検索 | 日本語短語、英数字/パス、無関連、重複、別project、未分類legacy |
| Profile | 初回、訂正、背景処理完了前の次turn、cancel、session切替 |
| 予算 | 境界値、長い単項目、否定/例外保持、marker込み上限、全体残予算 |
| host | CLI/GUI/Web/A2Aで同じ明示scopeなら同じ結果、異なるscopeなら隔離 |
| provider | stateless chat、Responses継続、利用可能なcache経路、retry/recovery |
| 更新 | source revision競合、二重適用、クラッシュ再開、forget後の再抽出防止 |

依存関係と外部APIなしで回せるfixtureを先に揃える。host/provider統合は実装段階ごとに追加し、未導入経路を完了扱いしない。実モデル品質評価は機能テストと分離し、呼出費用と入力データの取り扱いを確認して実行する。

### 8.5 展開・停止・ロールバック

順序は現行baseline → shadow → 明示opt-in → 評価 → 既定値の変更判断。モード設定は既存の設定系へ合わせ、CLI指定を優先し全hostで意味を統一する。具体的なflag名は実装時に既存設定と照合する。

権限外混入、制約欠落、忘却済み情報の再出現、原文変更、保存失敗の成功通知が1件でもあれば段階を進めない。無関連率・遅延・token量はbaseline比較を記録する。

PR 2/3は入力projectionの切替で戻せる。ただし訂正・忘却が発生した後は旧snapshotへ戻して情報を復活させない。PR 4のschema rollbackは別手順とし、backup復元で新しい記憶やtombstoneを失わないか確認する。新schemaを旧binaryが安全に読めないなら無条件downgradeを許可しない。

### 8.6 直近の着手点

次の実装はPR 1に限定する。最初に保存失敗、note整形、初回Profile未反映の再現fixtureを作り、保存成功の判定と整形を修正する。その結果を見てPR 2へ進む。現時点ではBrain/Dream、新しいDB、Embedding、全面的なProfile移行は着手対象にしない。

## 主な根拠ファイル

以下はすべて上記固定commitに対する相対パス。

- src/uagent/runtime/memory_manager.py
- src/uagent/runtime/memory_store.py
- src/uagent/runtime/runtime_memory.py
- src/uagent/tools/long_memory.py
- src/uagent/tools/add_long_memory_tool.py
- src/uagent/util_message.py
- src/uagent/profile_manager.py
- src/uagent/core_impl/history.py
- src/uagent/tools/skill_history.py
- src/uagent/runtime/session_store.py
- src/uagent/runtime/context_manager.py
- src/uagent/runtime/context_retrieval.py
- src/uagent/runtime/context_decision.py
- src/uagent/runtime/active_context.py
- src/uagent/runtime/context_policy.py
- src/uagent/runtime/context_plan_builder.py
- src/uagent/runtime/agent_state.py
- src/uagent/providers/responses_runtime.py
- src/uagent/uagent_llm.py

既存テストはtest_memory_manager、test_memory_backend_consistency、test_context_retrievalを静的確認。直接検証は第3節の6ケース。pytestは未実行であり、全host・全providerのE2E確認済みとは主張しない。
