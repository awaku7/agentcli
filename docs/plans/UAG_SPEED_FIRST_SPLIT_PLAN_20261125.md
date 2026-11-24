# 巨大ファイル分割の方針（速度・パフォーマンス重視）（2026-11-25）

- Status: in progress（P0-1 完了）
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
- **P0-2: マニフェストによる遅延読み込み**（効果が最大、中リスク）
  - `TOOL_SPEC`、`CMD_SPEC` のメタ情報、ポリシーのフラグを、生成したマニフェストから登録する。古くなったことの検出も入れる。
  - モジュールの import はツールの初回実行時まで遅らせる。目標は `_load_plugins` を 0.1 s 前後にすること。
  - 考慮すること: `reload` の扱い、`CMD_SPEC` のハンドラ、`LOAD_DISABLED_REASON`、describer、ロケールごとの spec、外部ツールと Rust ツール。
  - P0-1 で残した `httpx`（MCP の `MCPOAuthHTTPXAuth` が `httpx.Auth` を継承している）、`msoffcrypto`（`excel_ops`）、PIL（`preprocess_image`）もこれで解消する。MCP 系はテストがモジュール属性の `MCPClient` を差し替えているので、個別に直すよりマニフェストで import 自体を遅らせる方が安全。
- **P0-3: `tools/__init__.py` の分割**（P0-2 の後）
  - ローダー、カタログ検索（CJK トークナイザを含む。`tool_catalog` を呼んだときだけ読み込む）、動的コマンド、トレースに分ける。
  - グローバルな状態と、テストが差し替える名前（`_ensure_loaded`、`run_tool`、`_CONFIRMATION_CALLBACK` など）は `__init__` に残し、状態の持ち主を 1 か所にする。

### P1: `uagent_llm.py`（速度への影響はない。保守性のため）

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

## 補足: 開発環境の注意

`F:\Python314\Lib\site-packages` に、編集可能ではない古い `uagent` が入っていて、`src/` と 177 か所違う。`PYTHONPATH` を指定せずに `python` を実行すると古いコードが読み込まれる。`scripts/bench_startup.py` は常に `src/` を先頭にして計測する。`pip install -e .` で解消できる。

## 更新履歴

- 2026-11-25: 作成。方針を決定し、P0-1 を実施。
