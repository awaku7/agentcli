# UAG Memory / Session検索の正確性・診断改善計画（2026-10-26）

- **状態:** MR-01〜05はマージ済み。MR-06の保守的prefilterはPR #282でレビュー中。Windows全体pytest、Ruff、Blackは通過。評価は合成データのみで、実データ測定は未実施。
- **計画時の確認基準:** `main` = `1a13e12e1def7c27336cf74d41a5d4be77820177`（2026-10-26 JST）
- **実装時の作業基準:** `main` = `214a9b0`（2026-10-26 JST）。計画時の確認基準とは異なるため、差分をレビュー時に考慮する。
- **目的:** 既存のMemory V2/V3・SessionStore・FTS5・日本語検索・Structured Compactionを維持し、根拠を確認した不具合と評価の弱点を小さなPRで改善する。
- **原則:** 正確性・安全性を先に修正し、性能変更は結果同値性と実測を確認してから採用する。

## 1. 現行実装の確認

### FTS5は導入済み

`src/uagent/runtime/session_store.py` の `_initialize()` に `message_search USING fts5(content, session_id UNINDEXED, message_id UNINDEXED)` がある（約L549）。`_append_message_unlocked()` がメッセージ・FTS5索引・SessionItemを更新し、`append_message()` が同一トランザクションで確定する（約L1270–1360）。セッション削除・メッセージ置換時にも検索行を除去する。

`:sessions search` → `SessionCommandService.search()` → `SessionStore.search()` はFTS5 `MATCH` と `m.content LIKE` / `m.payload_json LIKE` を併用する（約L3630–3659）。**FTS5が未実装という前提で修正を計画しない。**

### 長期記憶の投影は別の経路

`uagent_llm.run_llm_rounds()` → `prepare_memory_projection()`（`runtime/memory_projection.py`）→ `shadow_retrieve_memories()`（`runtime/memory_retrieval.py`）。

長期MemoryはSQLite `MemoryStore.records()` または認可付き `ScopedMemoryStore.records()` から取得され、完全一致・単語照合・日本語等の文字n-gram・候補相対順位付けで選択される。ここではFTS5を直接呼ばない。`shadow_retrieve_memories()` は名前に反して本番の自動Memory投影でも使用される。

V3ではOwner / Project / Room / audience / revision-bound grantを検索前に認可し、Profileの継続制約は検索一致に依存しない専用枠に投影する。これらの既存境界を維持する。

### 対象外

- FTS5、長期Memory、認証・共有モデル、Structured Compactionの全面作り直し。
- Embedding、ベクトルDB、Dream Agentの無条件導入。
- 未検証の記憶内容の自動上書き、誤ったscopeへの共有昇格。
- Raw Historyの削除、未認可・期限切れ記憶の再利用。
- 計測せずに索引方式を変更すること。

## 2. 確実な正確性・可観測性の改善

### MR-01 [P1] セッション検索の20メッセージ上限による取りこぼし

**根拠:** `SessionStore.search(query, project=None, limit=20)` はメッセージ単位に `ORDER BY m.message_id LIMIT ?` を適用する。その後 `SessionCommandService.search()`（`runtime/session_command_service.py` 約L217–290）がセッション別に集約する。例えばSession Aが30hit、Session Bが1hitの場合、最初の20hitをAが占めBが検索結果から漏れ得る。

**修正:** `:sessions search` 専用のセッション集約検索を追加し、一致件数・代表hit・日時をSQL側で確定した後、**セッション数**に上限を適用する。既存 `SessionStore.search()` の「メッセージ単位検索」契約は変更しない。既存の `--sort date|matches|date,matches`、`--project`、`:sessions load <index>` を維持する。`system` の派生文脈は**集約前に**除外する。

**受入条件:** A=30hit・B=1hitでも双方が表示される。21セッション以上の一致で上限がセッション数へ適用される。代表hit、件数、日時、並べ替え、project境界、削除・置換後の整合性に回帰がない。

### MR-02 [P1] LIKEワイルドカードによる誤一致

**根拠:** `session_store.py` 約L3635の `query_like = f"%{query}%"` は `%` と `_` を文字としてエスケープしない。ユーザーがそれらを文字として探すと無関係な本文がヒットし得る。

**修正:** LIKE用に `!`、`%`、`_` をエスケープし、SQLに `ESCAPE '!'` を指定する。SQLパラメータ化と既存FTS5のクォート処理は維持する。

**受入条件:** `%`、`_`、`!`、`a_b`、`100%`、`new-1`、引用符、日本語短語、SQL風の入力で誤一致・例外がない。既存FTS5と部分一致検索は維持される。

### MR-03 [P1] Memory読み込み障害が空件数に化ける

**根拠:** `tools/long_memory.py` の `load_long_memory_records()`（約L290–327）はSQLite読込例外で `[]` を返す。JSONL側も読込例外を一部握りつぶす。`prepare_memory_projection()` には正常な空DBと障害の区別が届かない。

**修正:** 全呼出元を確認し、型付き結果・明示的例外・診断経路のいずれかで「正常0件」と「取得失敗」を区別する。失敗時は当該Memoryを投影しないfail-closed動作を維持し、秘密やMemory本文をログに出さずエラー種別だけを記録する。

**受入条件:** 空DBは正常0件、破損・権限不足・SQLite `OperationalError` は診断可能。local CLI/GUI/Web/A2A、既存 `get_long_memory`、V3認可に回帰がない。

### MR-04 [P2] 日本語n-gram識別スコアの重複計算

**根拠:** `runtime/memory_retrieval.py` の `_discriminative_relevance()`（約L161–186）は候補ごとに全候補のn-gram集合と各n-gramの出現頻度を再計算する（約L413–433）。

**修正:** 検索1回の候補集合・document frequencyを一度だけ計算し、各候補へ再利用する。既存スコア、閾値、除外理由、tie-break、候補順序を変えない。

**受入条件:** 日本語・中国語・タイ語・英語・短語・句読点・重複noteを含むfixtureで候補ID順・score・diagnosticsが変更前と一致する。キャッシュ構築は候補ごとでなく検索単位。速度向上率は測定結果で報告し、未測定の倍率を保証しない。

### MR-05 [P2] scope違反評価の検出能力不足

**根拠:** `runtime/memory_evaluation.py`（約L117–134）の `scope_violation_count` は `action == "candidate"` かつ `scope_status in {"mismatch", "scope_unknown"}` を数える。しかし現Retrieverは不一致を `exclude` とし、未知scopeを `legacy_unknown` と表現する。このカウンタが0であっても、返却候補が独立に認可検証されたことにはならない。

**修正:** fixtureの正本recordと返却候補のprovenanceを照合する独立した評価を追加。Owner / Project / Scopeに加え、V3のPrivate・Room・Direct grantを認可済み出力から検証する。既存診断値の文字列を合わせるだけで完了としない。

**受入条件:** テストで意図的に越境候補を返した場合に検出・失敗する。正常ケースは違反0。unknown scopeのstrict扱いを守り、診断に他人のMemory本文を複製しない。

## 3. 効果を測定して判断する最適化

### MR-06 [P2 / measurement-first] 長期Memoryの全件取得

`MemoryStore.records()` / `ScopedMemoryStore.records()` は許可済みrecordを読み、`prepare_memory_projection()` がPython側で候補を選ぶ。`UAGENT_MEMORY_PROJECTION_MAX_CANDIDATES=20` は最終候補の上限であり、DB読み出し数の制限ではない。

100 / 1,000 / 10,000 / 50,000件について、DB読み込み・認可・候補生成・投影の時間、ピークメモリ、recall、無関係注入率を計測する。日本語短語、ファイルパス、英数字、別Project、Direct grant、言い換えを含む。

検索品質・スコープ安全性を維持し、実測で改善する案だけ採用する。Sessionの既存FTS5をそのまま長期Memoryに使う判断はしない。標準FTS5は日本語部分一致を保証しない。Embeddingも現行方式との比較後に判断する。

#### 初回合成データ測定（2026-10-26）

Python 3.14.6 / SQLite 3.50.4、Windows上でSQLite DBに合成recordを一括投入して測定。時間はDB読込・認可が各1回、retrievalが3回の中央値、projectionが5回の中央値。ピークメモリは各処理を別途 `tracemalloc` で1回計測（Python割当量であり、プロセスRSSではない）。query実行時間の計測中はtracemallocを無効化した。

| DB record数 | 認可後record数 | raw read ms / MiB | scoped read+auth ms / MiB | retrieval ms（5つの完全一致ケースの範囲） | projection ms（1候補） |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 83 | 1.4 / 0.11 | 1.0 / 0.10 | 1.8–4.0 | 0.08–0.11 |
| 1,000 | 831 | 5.1 / 1.06 | 6.5 / 1.03 | 19.0–36.6 | 0.09–0.11 |
| 10,000 | 8,314 | 57.9 / 10.63 | 65.8 / 10.30 | 178.6–375.6 | 0.09–0.10 |
| 50,000 | 41,573 | 374.6 / 53.31 | 504.8 / 51.63 | 973.2–2,322.9 | 0.08–0.10 |

完全一致の日本語・英語・ファイルパス・英数字・Direct grantケースはrecall 1.0、無関係注入率0。言い換えケースはrecall 0で、別の完全一致候補が1件返った。合成fixture上でも言い換え検索の弱さが確認された。各ケースの候補は1件なのでprojection時間を大量候補時へ外挿しない。

**判断:** baselineでは50,000件時の候補検索・rankingが約0.97–2.32秒/queryで、DB read/authの約0.4–0.5秒とprojection（約0.1ms）を上回った。後続の統合prefilter比較では合成fixture上でspeedupが観測された。ただし単一環境・合成分布に限られるため、本番性能やrecallの保証ではない。実データ測定は未実施。

#### 保守的な候補prefilterの実装・差分測定（2026-10-26）

検証中branchでは、Owner / Project / Scope / empty-noteの既存判定をすべて通過したrecordに対してのみ、query phrase / token substring / script n-gram substringの保守的なprefilterを追加した。prefilterがfalseを返すのは完全一致・token一致・対象scriptのn-gram一致があり得ない場合だけとし、false-positiveは従来の `_relevance()` に渡す。除外diagnosticは従来どおり `no_query_match` / relevance `0.0` として生成する。認可前の候補検索・scope境界の変更はない。

decoy入り同一合成fixtureで、prefilter有効時と無効時（query prefilter preparation/skippingを無効化）を各3回計測した。retrieval時間は中央値。全6 query caseについてcandidate出力、score、順序、item ID/reference、全diagnosticsが完全一致した。

| DB record数 | speedup範囲（6 cases） | prefilter通過件数範囲 / 認可済みrecord | baselineとの結果 |
| ---: | ---: | ---: | --- |
| 100 | 1.57–4.42× | 1–3 / 84 | 完全一致 |
| 1,000 | 1.14–3.35× | 1–12 / 842 | 完全一致 |
| 10,000 | 1.68–3.10× | 1–102 / 8,429 | 完全一致 |
| 50,000 | 1.54–3.02× | 1–502 / 42,148 | 完全一致 |

50,000件のspeedup中央値は約1.89×。この実装は合成fixtureでは改善したが、プロパティテストは有限の例集合であり、速度・recallを実データ分布で保証するものではない。merge前に中国語・タイ語・punctuation・short query・重複note・strict unknown・scope除外を含む回帰/property testsと全体pytestを再実行する。最終採用判断は実データ評価後に行う。

### MR-07 [別計画] Structured Compactionとの統合

元メッセージ / Artifact / Tool Resultの再取得、複数クライアントのrevision競合、再起動後の実LLM検証は `docs/UAG_STRUCTURED_COMPACTION_IMPLEMENTATION.md` に継続記録する。本書から重複開発を指示しない。

## 4. 実装PRの分割

| 単位 | 内容 | 主なテスト |
| --- | --- | --- |
| PR A | MR-01・MR-02：Session検索の正確性 | `tests/test_session_store.py`, `tests/test_session_command_service.py`, `tests/test_memory_history_boundary.py` |
| PR B | MR-03：Memory読み出し障害の明示 | `tests/test_memory_backend_consistency.py`, `tests/test_memory_projection.py`, `tests/test_memory_v3_projection.py` |
| PR C | MR-04：n-gram計算の共有 | `tests/test_memory_shadow_retrieval.py`, `tests/test_memory_evaluation_runner.py` |
| PR D | MR-05：評価オラクルと故意の越境候補テスト | `tests/test_memory_evaluation_runner.py`, `tests/test_memory_access.py`, `tests/test_memory_v3_projection.py` |
| 測定後 | MR-06：必要な場合だけ最適化 | ベンチマーク＋既存のMemory回帰suite |

上表は独立した修正範囲であり、固定PR数の強制ではない。最初に各問題の再現テストを追加し、最小修正を行う。CI・第三者レビュー・Codexレビューを確認してからマージ判断する。変更によって新たな設計課題が見つかった場合は本書へ記録する。

## 5. 回帰チェックリスト

1. `SessionStore.search` のメッセージ単位APIと `:sessions search` のセッション単位表示を混同しない。
1. 日本語・中国語・タイ語・英語、短語、英数字、ファイルパス、記号、引用符を含める。
1. 20件を超えるメッセージ・複数セッション・日付/一致数sort・削除/置換・再起動を含める。
1. Owner / Project / Room / audience / grant / revision / revoke / stale snapshotの境界を守る。
1. `UAGENT_MEMORY_STRICT_SCOPE`、Profile guidance、Personal / Sharedの区別を維持する。
1. Memory投影は1 turn内の凍結snapshotを再利用し、生会話の永続履歴に混ぜない。
1. リポジトリの `AGENTS.md` に従い、変更したPythonをBlack整形後、Ruff / Black / pytestを実行する。最終コード改訂に対しフル回帰を実施する。
1. 各PRに実際の実行コマンド、CI run、レビュー指摘と対処、未実施項目を残す。実LLMや本番環境の未検証事項を「成功」と記載しない。

```bash
python -m pytest -q tests/test_session_store.py tests/test_session_command_service.py tests/test_memory_history_boundary.py
python -m pytest -q tests/test_memory_shadow_retrieval.py tests/test_memory_evaluation_runner.py tests/test_memory_projection.py tests/test_memory_v3_projection.py tests/test_memory_access.py tests/test_memory_backend_consistency.py
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q . --durations=30
```

## 6. 記録

| 日付 | 作業 | 状態 |
| --- | --- | --- |
| 2026-10-26 | mainのSessionStore、SessionCommandService、MemoryStore、Memory Projection、Memory Retriever、評価コードと関連テストを読取照合 | 完了（ソース調査） |
| 2026-10-26 | FTS5導入箇所と `:sessions search`、長期Memoryの異なる検索経路を確認 | 完了（ソース調査） |
| 2026-10-26 | 本計画を作成 | 初稿時は文書のみ。後続の実装記録を以下に追加 |
| 2026-10-26 | MR-01〜05を実装。MR-01/02はセッション集約検索・LIKEエスケープ、MR-03は読み込み障害の明示とfail-closed診断、MR-04は候補集合単位のn-gram頻度共有、MR-05は正本record／認可済みmemory ID・revisionとの照合を追加 | マージ済み。MR-06 prefilterは検証中branchで未マージ。実LLM・本番データ測定は未実施 |
| 2026-10-26 | SessionStore、SessionCommandService、Memory backend、retrieval、evaluation、projection、V3 projection/access、history boundary、utilities i18nの対象テストを個別実行 | すべて通過。`tests/test_rpg2idx_tool.py` と `tests/test_office_to_markdown_tool.py` も適切な外部 `--basetemp` で通過 |
| 2026-10-26 | `python -m pytest -q . --basetemp=C:/Users/Gk40000498/AppData/Local/Temp/pytest-full-outside --tb=short --durations=30` | 初回は `tests/test_mxc_macos_scope.py` で8件失敗。Windowsに `os.killpg` と `signal.SIGKILL` がないことを確認し、製品コードではなく単体テスト内にPOSIX APIの安全なshimを追加。 |
| 2026-10-26 | `python -m pytest -q tests/test_mxc_macos_scope.py --basetemp=C:/Users/Gk40000498/AppData/Local/Temp/pytest-mxc-shim --tb=short` | 11 passed, 1 skipped |
| 2026-10-26 | `python -m pytest -q . --basetemp=C:/Users/Gk40000498/AppData/Local/Temp/pytest-full-final --tb=short --durations=30` | 全体pytest通過（Windows）。POSIX実シグナル意味論の検証はLinux/macOS CIで別途必要 |
| 2026-10-26 | Windows単体テスト用のPOSIX API shimを `tests/test_mxc_macos_scope.py` に追加 | `os.killpg` と `signal.SIGKILL` のみ補い、テスト内のkill/killpgはspyに置換。製品コードは変更せず |
| 2026-10-26 | `python -m ruff check src tests`、`python -m black --check src tests`、`git diff --check` | すべて通過 |
| 2026-10-26 | MR-06合成データbaseline測定（100 / 1,000 / 10,000 / 50,000件、MemoryStore/ScopedMemoryStore、6 query cases） | 結果と測定条件をMR-06節に記録。50,000件時retrievalは約0.97–2.32秒/query、projectionは約0.08–0.10ms/1候補 |
| 2026-10-26 | 認可済みrecordに対する保守的なprefilterをretrieval内へ実装し、prefilter無効baselineと比較 | 6 query casesでcandidate/diagnostics完全一致。50,000件で1.54–3.02×（中央値約1.89×）。合成fixtureのみ |
| 2026-10-26 | MR-06 prefilterの回帰/propertyテストと全体pytestを実行 | `tests/test_memory_shadow_retrieval.py` 14件通過。最終 `python -m pytest -q . --basetemp=... --tb=short --durations=30` 全体通過（Windows） |
| 2026-10-26 | MR-06をPR #282 (`c38b158`) としてpush | CI result tracked on PR; production corpus measurement not run |

## 7. 関連資料

- [MemoryとProfile](../MEMORY.ja.md)
- [Memory V2の検索とFTS5の判断履歴](../archive/UAG_MEMORY_ARCHITECTURE_V2.md)
- [Memory V3設計](../UAG_MEMORY_ARCHITECTURE_V3.md)
- [Memory V3 security hardening](../UAG_MEMORY_V3_SECURITY_HARDENING.md)
- [Structured Compaction実装記録](../UAG_STRUCTURED_COMPACTION_IMPLEMENTATION.md)
- [Memory V2 acceptance](../MEMORY_V2_ACCEPTANCE.md)
- [実装ロードマップ](./IMPLEMENTATION_ROADMAP.md)
