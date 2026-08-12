# リポジトリ解析ツール

このリポジトリには、ソースツリーの確認と検証を行う3つのツールがあります。

## `git_review`

Gitの変更内容を、秘密情報の値を露出させずに要約します。

コミット前のステージ済み・未ステージ変更の確認に利用できます。

主なオプション：

- `root`: リポジトリのパス
- `include_untracked`: 未追跡ファイルを含める
- `max_diff_chars`: diff出力の最大文字数
- `scan_secrets`: 秘密情報らしいパターンを検出

ステータス、変更ファイル、diff統計、リスクのあるファイル名、テスト候補を返します。

## `security_scan`

リポジトリ内のファイルから、秘密情報らしい文字列やリスクのあるファイル名を検出します。

主なオプション：

- `root`: スキャン対象ディレクトリ
- `include_hidden`: 隠しファイルを含める
- `max_files`: 最大ファイル数
- `max_file_bytes`: 最大ファイルサイズ
- `scan_content`: 内容スキャンを有効にする

秘密情報の値そのものは返しません。検出結果にはファイル、行番号、分類、マスク済みプレビューのみを含めます。

## `coverage_report`

言語別のカバレッジアダプターを使って、プロジェクトのテストを実行します。

対応アダプター：

- `python`: `coverage` と pytest
- `typescript`: `c8` と npm test
- `rust`: `cargo llvm-cov`
- `go`: `go test -coverprofile`
- `java` / `kotlin`: Gradle JaCoCo または Maven JaCoCo
- `dotnet`: `dotnet test --collect:XPlat Code Coverage`
- `cpp`: CMakeのテストターゲット
- `ruby`: Bundler/Rake と SimpleCov
- `php`: PHPUnit Clover XML
- `swift`: `swift test --enable-code-coverage`

主なオプション：

- `language`: `auto`、`python`、`typescript`、`rust`、`go`、`java`、`kotlin`、`dotnet`、`cpp`、`ruby`、`php`、`swift`
- `test_target`: 任意の安全なテスト対象
- `timeout`: 実行タイムアウト（秒）
- `dry_run`: コマンドを表示するだけで実行しない
- `auto_install`: pip、npm、cargoを使って不足しているカバレッジ依存関係を自動インストールする

カバレッジ依存関係は実行時のみインストールされ、dry runではインストールされません。

選択されたアダプター、コマンド、実行結果、出力、取得できる場合はカバレッジ集計値を返します。

## 安全性

3つのツールはいずれも、パスを現在の作業ディレクトリ配下に制限し、秘密情報の値を返さず、出力または実行時間に上限を設けています。
