# code_map リファクタリング検査報告・実行指示書

## 0. この文書の目的

この文書は、`code_map` ツールを別のLLMが新規に読んでも、仕様を推測せずに安全にリファクタリングできるようにするための検査報告兼実行指示書である。

実装者は、この文書だけで判断できない仕様を勝手に追加せず、既存コード・`AGENTS.md`・`TOOL_SPEC`を確認すること。

______________________________________________________________________

## 1. 対象

### 変更対象

- `src/uagent/tools/code_map_tool.py`（公開Facade）
- `src/uagent/tools/code_map_impl/`（内部実装）
  - `language_detection.py`
  - `symbols.py`
  - `relations.py`
  - `resolvers.py`
  - `manifests.py`
  - `lockfiles.py`
  - `caches.py`
  - `cmake.py`
  - `conflicts.py`
  - `renderers.py`

### 仕様確認対象

- `src/uagent/tools/code_map_tool.json`
- `AGENTS.md`
- `src/uagent/docs/`配下の関連文書

### テスト対象

- 既存の`tests/`配下
- 必要に応じて追加する`code_map`専用テスト

### 原則として変更しないもの

- `src/uagent/tools/code_map_tool.json`の公開パラメータ名・型・enum
- 他ツールの実装
- 既存の出力形式。ただしバグ修正に必要な追加フィールドは、後方互換性を保てる場合に限る
- `.org`、`.org1`、`.org2`などのバックアップファイル

______________________________________________________________________

## 2. 現在の公開仕様

`code_map`は、指定ディレクトリを解析し、以下を出力する。

- ソースファイル一覧
- ファイルごとの言語
- 任意のシンボル定義
- 任意のimport/require関係
- JSON形式
- Mermaid形式
- JSON-LD ontology形式
- 指定時の出力ファイル保存
- 指定時のMermaid PNGレンダリング

現在の主なパラメータは以下のとおり。

- `path`
- `depth`
- `include_symbols`
- `project_only`
- `format`: `json` / `mermaid` / `ontology`
- `output_dir`
- `render_image`
- `include_relations`

`include_relations`を省略した場合、`format == "ontology"`のときだけ既定値を`True`とする既存挙動を維持する。

______________________________________________________________________

## 3. 検査結果

### 重大度：高

#### 3.1 Python相対インポートの解決漏れ

対象:

- `_extract_imports_python()`
- `_resolve_python_module()`

問題:

- `ast.ImportFrom.level`を保持していない。
- `from . import x`で`module`が空になり、関係抽出から除外される。
- `from ..pkg import x`の相対階層が失われる。

必須改善:

- import情報に`level`を保持する。
- 相対importの基準ディレクトリを`level`に基づいて計算する。
- `from . import x`では`names`も解決候補として利用する。

#### 3.2 `project_only=True`の動作と説明が不一致

対象:

- `run_tool()`

問題:

- プロジェクトを検出しても、`sources`が空の場合は通常の全体スキャンへフォールバックする。
- 説明文の「プロジェクトファイルで参照されるファイルのみ」と一致しない。

必須改善:

- `project_only=True`では、検出したプロジェクト情報を優先する。
- プロジェクトが検出されたが対象ソースがない場合、全体スキャンへ黙ってフォールバックしない。
- 既存のJSON出力を壊さない形で、空結果または明示的な警告を返す。

#### 3.3 出力ファイルの衝突と無確認上書き

対象:

- `run_tool()`内の`_save_file()`

問題:

- 秒単位のタイムスタンプだけでファイル名を作成する。
- 同一秒の複数実行で衝突する。
- `open(..., "w")`により既存ファイルを無条件に上書きする。

必須改善:

- 既存ファイルを上書きしない。
- `O_EXCL`、高精度時刻、連番などで衝突を回避する。
- 保存失敗時は理由をJSONで返す。
- 既存の保存レスポンス形式をできるだけ維持する。

#### 3.4 最初に検出したプロジェクト種別だけを処理する

対象:

- `_find_project_files()`

問題:

- `.sln`、`package.json`、`Cargo.toml`などが混在していても、最初の種別で`return`する。
- モノレポや複合プロジェクトで他のソースが無視される。

必須改善:

- プロジェクト形式ごとの検出処理を独立した小さな関数へ分割する。
- 全形式の結果を統合する。
- 重複するプロジェクトファイル・ソースファイルを除去する。
- 既存の`project.type`文字列を壊す場合は、互換性を検討してから変更する。

______________________________________________________________________

### 重要度：中

#### 3.5 正規表現ベースのシンボル抽出

対象:

- `_extract_symbols()`
- `SYMBOL_PATTERNS`

問題:

- コメントや文字列中の宣言を誤検出する可能性がある。
- 同じ名前を`seen`で一つにまとめ、オーバーロードや別スコープの定義を失う。
- `template`など宣言本体でないものを検出するパターンがある。

改善方針:

- PythonはASTベースの抽出を優先する。
- 他言語は現行の正規表現を維持しつつ、変更範囲を限定する。
- 同名シンボルを無条件に削除しない。ただし出力互換性を壊す場合はテストと仕様確認を先に行う。
- 一度に全言語の抽出方式を変更しない。

#### 3.6 TypeScript/JavaScriptのimport抽出

対象:

- `_extract_imports_typescript()`

問題:

- コメントや文字列内の`import`/`require`を誤認識する可能性がある。
- dynamic importとrequireの分類が粗い。

改善方針:

- 外部パッケージを必須化しない。
- 軽量なコメント・文字列除外を導入する場合は、通常の文字列・テンプレート文字列・正規表現リテラルを壊さないテストを追加する。
- `type`の変更は既存利用者への影響を確認する。

#### 3.7 Go内部依存の解決

対象:

- `_build_relations()`
- `_resolve_go_module()`

問題:

- `str(root_path) in module`は通常のGo module import pathと一致しにくい。
- `go.mod`のmodule宣言を利用していない。
- import情報に行番号がない。

改善方針:

- `go.mod`のmodule名を読み取る。
- module prefixをローカルディレクトリへ変換する。
- import情報に行番号を追加する。
- 外部依存は引き続き関係グラフの対象外とする。

#### 3.8 Pythonの`src/`レイアウト

対象:

- `_resolve_python_module()`

問題:

- root直下中心の探索で、`root/src/package/...`を解決できない可能性がある。

改善方針:

- rootとroot/srcを探索候補にする。
- 解決結果は解析対象ファイル集合でフィルタする。
- `pyproject.toml`の詳細なpackage設定の解釈は、今回の最小変更範囲を超える場合は行わない。

#### 3.9 Rustのmodule解決

対象:

- `_extract_imports_rust()`
- `_resolve_rs_internal()`

問題:

- `use crate::{a, b};`などのグループ指定に弱い。
- ネストしたmodule、相対解決、重複候補の処理が不十分。

改善方針:

- `mod.rs`と`<name>.rs`の規則を共通化する。
- 解決結果は集合で重複排除する。
- 複雑なRust構文を完全なパーサーなしで完全対応しようとしない。

#### 3.10 Mermaidラベルのエスケープ

対象:

- `_tree_to_mermaid()`

問題:

- `|`、`<`、`&`、改行などを含むファイル名・ディレクトリ名で構文エラーや表示崩れが起きる可能性がある。

必須改善:

- Mermaidラベル用のエスケープ関数を独立させる。
- ノードIDと表示ラベルを分離する。
- 特殊文字のテストを追加する。

______________________________________________________________________

## 4. 保守性・性能上の課題

- `_find_project_files()`にプロジェクト種別ごとの重複処理が多い。
- `skip_dirs`が`run_tool()`内に固定されている。
- `project_info["sources"]`をリスト検索しており、大規模リポジトリで非効率。
- シンボル抽出とrelation抽出でファイルを複数回読み込む。
- `_render_mermaid_to_image()`が失敗理由を握りつぶす。
- Mermaidレンダリング時に自動pipインストールを試行し、実行時副作用とネットワーク依存がある。

改善優先度:

1. 正確性と安全性
1. 後方互換性
1. テスト可能性
1. 性能
1. 大規模な抽象化

______________________________________________________________________

## 5. 実装手順

実装者は以下の順番で進めること。各段階で構文チェックと差分確認を行う。

### Step 1: 現状を記録

- `git status --short`
- `git diff -- src/uagent/tools/code_map_tool.py src/uagent/tools/code_map_tool.json`
- 既存テストの有無を確認
- `python -m py_compile src/uagent/tools/code_map_tool.py`
- `python -m ruff check src/uagent/tools/code_map_tool.py`

### Step 2: 入力検証と共通定数を整理

- `run_tool()`から`skip_dirs`をモジュール定数へ移す。
- `format`、`depth`、`path`などの入力値を明示的に検証する。
- 不正入力では既存形式に合わせた`{"ok": false, "error": ...}`を返す。
- 未対応の入力仕様を勝手に追加しない。

### Step 3: ファイル収集を分離

以下の責務を別関数に分ける。

- プロジェクト検出
- プロジェクトソース収集
- 通常のファイル収集
- パスの正規化
- 重複除去

推奨関数名の例:

- `_collect_source_files(root, skip_dirs)`
- `_deduplicate_paths(paths)`
- `_normalize_file_path(path)`

既存の外部から呼ばれる関数がないか確認し、内部関数の変更に留める。

### Step 4: プロジェクト検出を統合方式へ変更

- 種別ごとの処理を小関数に分割する。
- すべてのプロジェクト形式を走査する。
- 結果を統合し、パスを正規化・重複排除する。
- 既存の`project`出力を維持する。
- 複数種別を表現できない場合は、互換性を優先した値を選び、追加情報は新規フィールドとして慎重に検討する。

### Step 5: Python相対importを修正

- `_extract_imports_python()`で`ImportFrom.level`を保存する。
- `from . import x`で`names`を解決候補にする。
- `from ..pkg import x`で親階層を正しく計算する。
- 絶対importではrootとroot/srcを探索する。
- 解決された候補は解析対象ファイル集合で絞り込む。

### Step 6: GoとRustの関係解決を改善

- Goは`go.mod`のmodule名を利用する。
- Go importに行番号を付与する。
- Rustの候補パスは集合で管理する。
- 外部依存を内部relationとして誤登録しない。

### Step 7: Mermaidラベルを安全化

- エスケープ関数を追加する。
- ファイル名・ディレクトリ名に対する特殊文字テストを追加する。
- ノードIDは内部生成値を使い、表示名をIDに使わない。

### Step 8: 出力保存を安全化

- 出力ディレクトリは必要に応じて作成する。
- 既存ファイルを上書きしない。
- 同名候補があれば連番または高精度時刻で回避する。
- 保存エラーを握りつぶさない。
- 保存処理の変更後、JSON・Mermaid・Ontologyそれぞれを確認する。

### Step 9: レンダリングの副作用を確認

- 通常のJSON/Mermaid/Ontology解析でネットワークアクセスやpipインストールを発生させない。
- `render_image=True`の場合のみ、既存仕様に従ってレンダリングを試行する。
- 失敗時は原因をレスポンスに含める。

### Step 10: テストと検証

後述のテストケースを実行する。

______________________________________________________________________

## 6. 必須テストケース

一時ディレクトリを使い、テスト後に作業ツリーへ生成物を残さないこと。

### 6.1 Python相対import

以下の構成でrelationが生成されること。

```text
project/
  pkg/
    __init__.py
    a.py              # from . import b
    b.py
    sub/
      __init__.py
      c.py            # from .. import b
```

確認事項:

- `a.py`から`b.py`が解決される。
- `c.py`から`pkg/b.py`または仕様上妥当な候補が解決される。
- `source_line`が正しい。

### 6.2 Python `src/`レイアウト

```text
project/
  src/
    pkg/
      __init__.py
      a.py
      b.py
```

`a.py`の`import pkg.b`または相当するimportが`b.py`へ解決されること。

### 6.3 `project_only=True`

- プロジェクトファイルとソースファイルを作成する。
- プロジェクトに含まれるファイルだけが結果に入ることを確認する。
- プロジェクトが存在するが対象ソースがない場合、全体スキャンへ黙って切り替わらないことを確認する。

### 6.4 複合プロジェクト

同一rootに複数のプロジェクト形式を置き、各形式のソースが取り込まれることを確認する。

### 6.5 出力衝突

- 同一`output_dir`へ短時間に2回保存する。
- 2つのファイルが生成され、既存ファイルが上書きされないことを確認する。

### 6.6 Mermaid特殊文字

次の文字を含むファイル名・ディレクトリ名でMermaid出力が壊れないことを確認する。

- `"`
- `(`、`)`
- `[`、`]`
- `{`、`}`
- `|`
- `&`
- `<`、`>`
- 改行相当の入力

### 6.7 既存出力形式

最低限、以下を確認する。

- JSONが有効なJSONである。
- Ontologyが有効なJSON-LDである。
- Mermaidが`graph TD`で始まる。
- `include_relations`省略時のOntology既定値が維持される。
- `include_symbols=False`でsymbolsが意図どおり処理される。
- 空ディレクトリ、存在しないディレクトリ、不正なdepthを処理できる。

______________________________________________________________________

## 7. 合格基準

以下をすべて満たすこと。

- `python -m py_compile src/uagent/tools/code_map_tool.py`が成功する。
- `python -m ruff check src/uagent/tools/code_map_tool.py`が成功する。
- 関連テストが成功する。
- 新規テストがある場合、そのテスト自身が一時ファイルを後始末する。
- 既存の公開パラメータ名・型・enumを変更していない。
- JSON、Mermaid、Ontologyの既存出力形式を不必要に変更していない。
- 既存ファイルを無確認で上書きしない。
- 通常解析でネットワークアクセスや自動pipインストールを行わない。
- `git diff`で変更内容を説明できる。
- `git status --short`で意図しない生成物がない。

mypyは環境依存のNumPy stubエラーがあるため、実行した場合は対象コードの結果と環境エラーを分けて報告すること。エラーを勝手に無視して合格扱いにしない。

______________________________________________________________________

## 8. 禁止事項

- ユーザー確認なしに無関係なファイルを削除しない。
- 既存ファイルを無確認で上書きしない。
- 外部パッケージを必須依存にしない。
- 通常解析で外部ネットワークへ接続しない。
- 未確認の言語仕様を推測して実装しない。
- すべての言語解析を一度に全面書き換えない。
- `.org`等のバックアップファイルを編集しない。
- 仕様変更を行ったのにドキュメント・テストを更新しない。
- 既存の失敗を握りつぶして成功レスポンスにしない。

______________________________________________________________________

## 9. 推奨コミット単位

可能なら以下の単位で分ける。

1. 検査報告・実行指示書
1. ファイル収集とプロジェクト検出の整理
1. Python/Go/Rust relation修正
1. Mermaidと出力保存の安全化
1. テスト追加
1. ドキュメント更新

各コミット前に、対象範囲の`git diff`と検証結果を確認する。

______________________________________________________________________

## 10. 完了報告形式

実装者は完了時に、以下を日本語で簡潔に報告する。

```text
## 実施内容
- 変更したファイル:
- 主な変更:

## 検証
- python -m py_compile:
- ruff check:
- テスト:
- その他:

## 未解決事項
- なし、または具体的な内容

## Git
- git status:
- commit:
```

コミットやプッシュは、明示的なユーザー依頼がある場合にのみ実行する。

______________________________________________________________________

## 11. 検査時点の検証状況

- `python -m py_compile src/uagent/tools/code_map_tool.py`: 成功
- Ruff: 成功
- mypy: NumPy stubと実行中Pythonバージョンの互換エラーで対象コードの解析前に停止
- `code_map`専用テスト: 検査時点では確認できず
- サブエージェント検査: 使用モデルが`temperature=0.2`を受け付けず実行不能
- 検査報告作成時点のGit作業ツリー: 実装変更なし

## 現在の実装状態（2026-08-07）

### 内部構成

`code_map_tool.py`は公開Facadeとして維持し、TOOL_SPEC、run_tool、I18Nカタログの参照先を変えない。実装は`code_map_impl/`へ分割している。

### 依存関係解析

以下を静的に解析する。

- Python、TypeScript/JavaScript、Go、Rust
- Java/Kotlin/Scala、C/C++、C#
- PHP、Ruby、Swift、Dart、Lua、R
- COBOLのCOPY/CALL
- Objective-C/Objective-C++の#import/#include
- manifest、lockfile、ローカルキャッシュ
- dependency_edges、transitive_dependencies、resolved_paths、classpath_paths
- バージョン競合、TFM、Maven scope/optional/exclusions
- CMakeの保守的なif/elseif/else、NOT/AND/OR、変数展開

### I18N

公開I18Nカタログは`src/uagent/tools/code_map_tool.json`に集約する。内部モジュールに個別の翻訳カタログを作らない。全ロケールの説明と検索語をカタログへ反映する。

### 検証

- `tests/test_code_map_tool.py`
- 全体pytest
- 内部モジュールのpython_compile
- `system_reload`

を変更後に実行する。
