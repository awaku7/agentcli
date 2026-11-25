# 巨大ファイル分割の方針（速度・パフォーマンス重視）（2026-11-25）

- Status: in progress（P0、P1 完了。P2 は未着手）
- Priority: P1
- Source: `UAG_ROUND_LOOP_REVIEW_20261124.md` の RL-06（巨大なファイルと関数の分割）
- 確認基準: `main` = `1ad63ec3a`（PR #465 マージ後）

## 結論

**ファイルを分割するだけでは速くならない。** Python は `.pyc` をキャッシュするので、行数が多くてもモジュール自身の読み込みは数 ms で済む（`uagent_llm` 6 ms、`session_store` 2.5 ms、`tools/__init__` 1.8 ms）。速くなるのは次の 2 つだけ。

1. 使わない処理を読み込まない（遅延読み込み）。
1. import 時に重い処理をしない。

分割は、使用頻度の低い処理を遅延読み込みに回せる境界でだけ行う。ラウンドごとに通るホットパスには、分割によるオーバーヘッドを足さない。

## 計測（分割前、`src/` から実行、ウォームキャッシュ）

| 項目 | 時間 | 内訳 |
|---|---|---|
| **初回のツールアクセス（`_load_plugins`）** | **約 1.77 s（同期）** | ツールモジュール 301 個をすべて import する。遅延読み込みの仕組み（`_LAZY_TOOL_MODULES`）はあるが中身が空 |
| ├ `pwsh_exec_tool` の PowerShell バージョン確認 | 約 0.49 s | import 時に `pwsh` と `powershell` を subprocess で起動 |
| ├ `a2a_poll` / `a2a_send` → `httpx` | 約 0.3 s | |
| ├ `document_extract`（docx / odf / msoffcrypto） | 約 0.15 s | |
| ├ `fetch_url`（bs4） | 約 0.12 s | |
| ├ `qr_reader_ui`（tkinter / numpy） | 約 0.1 s | サブプロセスで起動するスクリプトなのに、ローダーが import していた |
| ├ `screenshot`（pyautogui / pygetwindow） | 約 0.1 s | |
| └ `date_calc`（holidays） | 約 0.08 s | |
| CLI の import | 約 0.37 s | ほとんどが依存の連鎖 |
| `uagent_llm` の import | 約 0.41 s | 自身は 6 ms |
| `tool_catalog` の日本語検索（初回） | 約 0.38 s | janome の初期化 |
| `sandbox_worker` の起動 | 約 0.17 s | サンドボックスのセッションごとに 1 回 |
| `session_store` | — | WAL + `synchronous=NORMAL`。問題なし |

計測は `python scripts/bench_startup.py`（P0-1 で追加）で再現できる。

## 方針と優先順位

### P0: `tools/`（体感に効くのはここだけ）

- **P0-1: import 時の重い処理を取り除く**（低リスク）— 完了、下記参照。
- **P0-2: マニフェストによる遅延読み込み**（効果が最大、中リスク）— 完了、下記参照。
  - `TOOL_SPEC`、`CMD_SPEC` のメタ情報、ポリシーのフラグを、生成したマニフェストから登録する。古くなったことの検出も入れる。
  - モジュールの import はツールの初回実行時まで遅らせる。目標は `_load_plugins` を 0.1 s 前後にすること。
  - 考慮すること: `reload` の扱い、`CMD_SPEC` のハンドラ、`LOAD_DISABLED_REASON`、describer、ロケールごとの spec、外部ツールと Rust ツール。
  - P0-1 で残した `httpx`（MCP の `MCPOAuthHTTPXAuth` が `httpx.Auth` を継承している）、`msoffcrypto`（`excel_ops`）、PIL（`preprocess_image`）もこれで解消する。MCP 系はテストがモジュール属性の `MCPClient` を差し替えているので、個別に直すよりマニフェストで import 自体を遅らせる方が安全。
- **P0-3: `tools/__init__.py` の分割**（P0-2 の後）— 完了、下記参照（ローダーは分けなかった）。
  - ローダー、カタログ検索（CJK トークナイザを含む。`tool_catalog` を呼んだときだけ読み込む）、動的コマンド、トレースに分ける。
  - グローバルな状態と、テストが差し替える名前（`_ensure_loaded`、`run_tool`、`_CONFIRMATION_CALLBACK` など）は `__init__` に残し、状態の持ち主を 1 か所にする。

### P1: `uagent_llm.py`（速度への影響はない。保守性のため）— 完了、下記参照

- ループガード（約 600 行、純粋関数）、Responses の続きと復旧（約 300 行）、registry 経路（約 390 行）、ターン前準備（約 500 行）、Computer Use（約 150 行）に分ける。
- ラウンドごとに呼ぶ関数はモジュールの先頭で import する。めったに通らない経路（Computer Use、リモート復旧）だけを遅延 import にする。
- テストが `uagent_llm.X` を差し替えている約 25 か所は、移動先のモジュールを差し替えるように直す。公開関数は `uagent_llm` から再エクスポートする。

### P2: `session_store.py`（速度への影響はない。優先度は最も低い）

- パッケージにして、`SessionStore` を mixin に分ける（スキーマと移行、メッセージと検索、ツール結果、エージェント状態、サブエージェントの receipt、圧縮記録）。
- 接続とロックは 1 つのまま。import パスは変えない。

### 分割しない: `sandbox_worker.py`

- 1 ファイルのままサンドボックスにコピーされ、`uagent` を import せずに常駐プロセスとして動く。分割すると、セキュリティ境界を越えてコピーするファイルが増える。
- 改善するとしても、`urllib` / `ssl` を遅延 import にして起動ごとに約 50 ms 減らす程度。

## 共通のルール

- 各 PR で `scripts/bench_startup.py` の前後の値をこの文書に記録する。
- 1 PR 1 ステップ。挙動は変えない。

## P0-1 の結果

### 変更内容

| ファイル | 変更 |
|---|---|
| `pwsh_exec_tool.py` | import 時の PowerShell バージョン確認（subprocess 2 回）をやめ、`shutil.which` での有無の確認だけにした。説明文の末尾は `(detected: pwsh <バージョン> / powershell <バージョン>)` から `(detected: pwsh / powershell)` に変わる |
| `a2a_poll_tool.py` / `a2a_send_tool.py` | `A2AClient`（httpx）を `run_tool` の中で import する |
| `document_extract_tool.py` | docx / odf / striprtf / msoffcrypto を、各形式の抽出関数の初回呼び出し時に読み込む（未インストールなら自動インストール） |
| `fetch_url_tool.py` | bs4 を初回使用時に読み込む。`XMLParsedAsHTMLWarning` の抑制もそのときに登録する |
| `date_calc_tool.py` | holidays を祝日判定の初回に読み込む |
| `screenshot_tool.py` | pyautogui / pygetwindow を初回実行時に読み込む。「未試行」は番兵 `_NOT_LOADED`、「使えない」は `None` で区別する（テストが `None` を入れて未インストールを再現しているため） |
| `tools/__init__.py` | `_NON_PLUGIN_MODULES` を追加し、サブプロセス用のスクリプト `qr_reader_ui` をローダーの対象から外した |

挙動の変化: 上記の依存が未インストールのとき、自動インストールが行われるタイミングが「プラグイン読み込み時」から「そのツールの初回実行時」に変わる。インストールの方針（`UAGENT_AUTO_INSTALL`）と許可リストは変わらない。

### 計測（`python scripts/bench_startup.py --runs 5`、中央値）

| 項目 | 前（`main`） | 後 | 差 |
|---|---|---|---|
| `tools: load plugins` | 1773 ms | 767 ms | **−1006 ms（−57%）** |
| `tools: catalog (en)` | 188 ms | 151 ms | −37 ms |
| `tools: catalog (ja, first)` | 377 ms | 347 ms | −30 ms |

`import uagent.cli` と `import uagent.uagent_llm` はこの変更の対象外。`main` は別ドライブ（`%TEMP%`）の worktree で計測したため、この 2 つの前後の差は比較に使わない。

プラグイン読み込み後にまだ読み込まれている重い依存: `httpx`（MCP）、`msoffcrypto`（`excel_ops`）、PIL（`preprocess_image`）。P0-2 で扱う。

### テスト

- `tests/test_tool_plugin_import_cost.py`（新規）: プラグインを読み込んでも遅延対象のライブラリが import されないこと（別プロセスで確認）、`pwsh_exec_tool` が import 時にプロセスを起動しないこと、screenshot の依存が初回に 1 回だけ読み込まれること、import に失敗する導入済みパッケージを再インストールしないこと、document_extract でライブラリがないときのエラー。
- 変更したツールに関係する既存のテストを手元で実行した。テストスイート全体は CI で確認する。

## P0-2 の結果

### 方式

計画では「生成したマニフェスト」としていたが、ビルド時に生成する方式はやめ、**実行時に作るキャッシュ**にした。翻訳済みの説明文や環境で変わる spec をビルド時には確定できないため。

- 新規 `tools/_manifest.py`: 分類、フィンガープリント、保存と読み込み、`ManifestModuleView`。
- キャッシュはユーザーのキャッシュディレクトリの `tool_manifest/<パッケージ位置>-<ロケール>.json`。
- フィンガープリント（どれかが変わると全体を作り直す）: `tools/` 以下のすべての `.py`/`.json`（相対パス、mtime、サイズ）、ロケール、Python のバージョン、プラットフォーム、`UAGENT_*` 環境変数（プロセスごとに変わる 4 つを除く）、`PATH`。走査は約 1 ms。
  - import 時に環境変数を読んで spec を変えるツールがある（`analyze_image`、`semantic_search_files`、`bash_exec` など）。静的に検出するには AST の解析に約 0.7 s かかるため、環境変数をまとめてキーに入れた。キーに余分なものが入ってもキャッシュミスで遅くなるだけで、間違った spec にはならない。
- 遅延登録の対象: すべての spec が起動時に LLM から見えない（`tool_level` が 1 か -1）、`CMD_SPEC(S)`・`is_loadable()`・`LOAD_DISABLED_REASON`・`LAZY_LOAD` がない、spec が JSON そのまま、組み込みモードの除外対象でない、個別に読み込まれていない。それ以外はこれまでどおり import する。
- 遅延ツールには `_LazyRunner` を登録する。`run_tool` は trace と describer の前に本物を import して登録し直す。`get_tool_describer` も必要なら解決する。
- `_find_tool_modules()` は、まだ import していない遅延モジュールに `ManifestModuleView` を返す。キャッシュした `TOOL_SPEC*` と「ないと分かっている属性」はそのまま答え、それ以外の属性を読んだときだけ本物を import する。`tool_catalog`、`enable_single_tool`、`catalog_tool`、grok、`:skills` はこれで変更なしに動く。
- TOOL_SPEC も CMD_SPEC もないヘルパーモジュール（`mcp` パッケージ、`*_shared` など）は、ローダーが import しなくなった。
- 無効化: `UAGENT_TOOL_MANIFEST=off`。GPT-5.4 のネイティブ `tool_search` モードでも使わない（全ツールの spec を送るため）。

### 計測

| 項目 | P0-1 後（`UAGENT_TOOL_MANIFEST=off`） | P0-2（キャッシュあり） |
|---|---|---|
| `tools: load plugins`（`bench_startup.py`、中央値） | 776 ms | **262 ms** |
| CLI の import 後のプラグイン読み込み（実際の起動に近い） | 約 590 ms | **約 90 ms** |
| `tools: catalog (en)` | 151 ms | 160 ms |
| `tools: catalog (ja, first)` | 347 ms | 354 ms |
| プラグイン読み込み後に残る重い依存 | httpx、msoffcrypto、PIL | なし |

- キャッシュがない初回（または作り直し）は、これまでと同じく全モジュールを import する（約 0.8 s）。
- キャッシュありの 262 ms の大半は、import し続けるモジュール（約 40 個）とその依存（`util_tools`、`core` など）。CLI ではこれらは起動時にすでに読み込まれているので、実際の差は上の「CLI の import 後」の行になる。
- 249 個のランナーのうち 222 個が遅延登録。登録されるランナーと LLM に見える spec は、キャッシュなしのときと同じ（テストで確認）。

### テスト

- `tests/test_tool_manifest.py`（新規）: 分類の規則（遅延・スキップ・import し続ける 12 パターン）、フィンガープリントがファイル・ロケール・環境変数で変わること（プロセスごとの値では変わらないこと）、保存と読み込み、壊れたファイルや形式違いの拒否、無効化スイッチ、`ManifestModuleView` が import せずに答えること。別プロセスでの通しの確認: 1 回目でキャッシュを作り、2 回目で同じ登録になること、カタログで見つかっても import されないこと、実行時に import されて結果が正しいこと、`enable_single_tool` で LLM に見えるようになること、無効化で従来の経路に戻ること。
- ローダーの内部を使う既存のテスト 29 ファイルと、全ツールを静的に検査するテスト 16 ファイルを手元で実行した。

## P0-3 の結果

### 方針の変更

計画では、ローダーも分けるとしていた。実際には、ローダー・登録処理・`get_tool_specs`・`run_tool` は `__init__.py` に残した。

- これらは `global` で状態を付け替える（`_TOOL_SPECS_DIRTY`、`_INITIALIZED`、`_TOOL_SPECS_CACHE` など）。テストもパッケージの属性としてこれらを差し替えている（`_ensure_loaded` だけで 17 か所）。
- 別モジュールに移すと、付け替えの対象が移動先のモジュールになり、パッケージ側の差し替えが効かなくなる。状態の持ち主を 1 か所にするという P0-3 の条件を優先した。

### 分けたもの

| モジュール | 行数 | 内容 |
|---|---|---|
| `tools/_catalog.py` | 678 | `get_tool_catalog()` と CJK のクエリ分割（janome / jieba / kiwi / pythainlp）。パッケージの `get_tool_catalog()` が初回の検索時に import する |
| `tools/_trace.py` | 463 | trace 行、翻訳された実行前の説明文、リモートへの進捗通知 |
| `tools/_dynamic_commands.py` | 401 | `CMD_SPEC(S)` のコマンド登録と検索。`_DYNAMIC_COMMANDS` の持ち主 |
| `tools/__init__.py` | 3,340 → 1,943 | ローダー、登録処理、`get_tool_specs`、`run_tool`、並列実行、確認 |

- 移した関数がパッケージの名前（`get_tool_specs`、`_ensure_loaded`、`TOOL_SPECS` など）を使うときは、関数の中で `from . import ...` して呼び出し時に読む。パッケージ側での差し替えがそのまま効く。
- パッケージは移した公開名とテストが使う名前を再エクスポートする。`run_tool` は再エクスポートした `_emit_tool_trace` などをパッケージのグローバルとして呼ぶので、`tools._emit_tool_trace` の差し替えも効く。
- `_trace.py` のメッセージは、これまでどおり `tools/__init__.json` を使う（`make_tool_translator(.../__init__.py)`。`tool_json_i18n_batch.py` の委譲の仕組みで英語の既定値も拾われる）。
- `_register_tool_module` の中にあった `CMD_SPEC(S)` 登録の重複コードは、`_register_dynamic_commands()` の呼び出しにまとめた。
- 速度: `tools: load plugins` 262 ms → 255 ms、カタログ検索は変わらず（`_catalog` は起動時に読み込まれない）。

### テストの変更

移動先のモジュールの内部を差し替える 4 ファイルを、移動先を差し替えるように直した（`test_tool_catalog_korean_terms`、`test_external_web_host`、`test_tool_result_display`、`test_web_command_catalog`）。`test_tools_utilities_i18n` の除外リストに、`__init__.py` から移した 3 モジュールを追加した（同じインフラのコード）。

## P1 の結果

### 分けたもの

| モジュール | 行数 | 内容 |
|---|---|---|
| `llm_loop_guards.py` | 583 | 4 つのループガード、共通の停止処理、会話ごとのガード状態（ContextVar） |
| `llm_turn_context.py` | 529 | ターン前準備（`_prepare_turn_context` と各ステップ）、コンテキスト予算、テレメトリ、エージェント状態、取得したツール情報、ラウンドのコンテキスト計画（`_build_round_context_plan`） |
| `llm_registry_round.py` | 442 | registry 経路（`_try_registry_simple_chat_round`）と、その経路のツール選択 |
| `llm_responses_runtime.py` | 291 | Responses の続きの状態、リモート復旧、registry 経路の終了処理 |
| `llm_computer_use_nav.py` | 152 | Computer Use の URL 直接ナビゲーション |
| `uagent_llm.py` | 3,747 → 1,880 | `run_llm_rounds`、1 ラウンドの 3 段階（前処理・振り分け・後処理）、割り込み、自動アンロードの状態 |

- 分割は AST で行い、関数の中身は変えていない。新しいモジュールは `uagent_llm` を import しない（循環なし）。
- `_build_round_context_plan` は registry 経路と `_record_round_context_plan` の両方が使うので、`llm_turn_context` に置いた。
- `uagent_llm` は、残ったコードが使う名前と、テストや他のモジュールが `uagent_llm` から読む名前を再エクスポートする（`clear_mgmt_load_streak`、`check_*` など）。

### 計画からの変更

- **Computer Use も遅延 import にしなかった。** 有効かどうかの判定を毎ターン呼ぶので、遅延 import にしても読み込みは避けられない。モジュールは 152 行で、import のコストは無視できる。
- **リモート復旧も同様。** `llm_responses_runtime` の一部で、registry 経路から普通に呼ばれる。

### 見つかった問題と修正

- **observability の計装が効かなくなる不具合を防いだ。** `boundary_instrumentation` は、`uagent.uagent_llm.prepare_memory_projection` を計装付きの関数に差し替えていた。この関数の呼び出し元は `llm_turn_context` に移ったので、そのままではメモリ投影のメトリクスが記録されなくなる。差し替え先に `uagent.llm_turn_context` を加え、テストを追加した（修正なしでは失敗することを確認）。
- **差し替えが空振りするテストを直した。** テストが `uagent_llm` 上で差し替えている名前を、実行時に記録して確認した。移動したコードが使う名前を差し替えていたテストは次のとおりで、移動先を差し替えるように直した。
  - `test_registry_generation_options`（`_get_shrink_max_tokens`、`_build_round_context_plan`）
  - `test_round_loop_turn_prep_and_guards`（ターン前準備の各ステップ、`_block_tool_loop` の停止処理）
  - `test_tool_round_limit`（`_resolve_max_tool_rounds` の `env_get`）
  - `test_general_tool_loop`（`check_consecutive_tool_calls` の `env_get`）。このテストは差し替えが効かなくても既定値で偶然通っていた。
  - 修正後に記録した `uagent_llm` 上の差し替え 21 種類は、20 種類が `uagent_llm` に残ったコードが使う名前、残る 1 つは関数ごと差し替える `run_llm_rounds` だった。
- ソースを直接読むテスト 2 つ（Computer Use の直書きの日本語、Memory V2 の境界）は、移動先のファイルも読むようにした。

### 速度

`import uagent.uagent_llm` 337 ms、`import uagent.cli` 316 ms（P0-3 の時点と同じ。`bench_startup.py`、中央値）。

## 補足: 開発環境の注意

`F:\Python314\Lib\site-packages` に、編集可能ではない古い `uagent` が入っていて、`src/` と 177 か所違う。`PYTHONPATH` を指定せずに `python` を実行すると古いコードが読み込まれる。`scripts/bench_startup.py` は常に `src/` を先頭にして計測する。`pip install -e .` で解消できる。

## 更新履歴

- 2026-11-25: 作成。方針を決定し、P0-1 を実施。
- 2026-11-25: P0-2（実行時に作るマニフェストのキャッシュによる遅延読み込み）を実施。
- 2026-11-25: P0-3（`_catalog` / `_trace` / `_dynamic_commands` への分割）を実施。
- 2026-11-25: P1（`uagent_llm.py` を 5 つのモジュールに分割）を実施。
