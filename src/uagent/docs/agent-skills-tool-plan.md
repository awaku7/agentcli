# Agent Skills（https://agentskills.io/specification）対応ツール 追加方針（案）

## 目的
本リポジトリ（`./src/uagent/tools` に既存ツール群がある構成）に、Agent Skills 仕様（`SKILL.md` + 任意ディレクトリ）を扱うためのツールを追加し、
- スキルディレクトリの走査
- `SKILL.md` frontmatter の解析
- 仕様に沿った検証
- 必要時の本文/参照ファイルの読み出し
をエージェントから呼び出し可能にする。

本方針書は「まず動く最小構成（MVP）」を定義し、次に拡張（検索、インデックス、allowed-tools連携等）を段階的に行う。

---

## 前提（リポジトリ側）
- 既存ツール実装は `./src/uagent/tools` 配下にある。
- 既存ドキュメントは `./src/uagent/docs` 配下にある。
- 今回追加するツールも同じ流儀（モジュール配置、登録方法、命名規則、I/O形式、エラーハンドリング）に合わせる。
  - ※具体の登録方式（ツールの自動検出/明示登録）や I/O スキーマは、既存コードを確認して合わせる。

---

## Agent Skills 仕様（実装に反映すべき要点）
参照: https://agentskills.io/specification

### 1) ディレクトリ構造
- スキルはディレクトリ。
- 必須ファイル: `SKILL.md`
- 任意ディレクトリ: `scripts/`, `references/`, `assets/`

### 2) SKILL.md フォーマット
- YAML frontmatter（必須） + Markdown body
- frontmatter 必須フィールド
  - `name`
  - `description`
- frontmatter 任意フィールド
  - `license`
  - `compatibility`
  - `metadata`（string->string のマップ）
  - `allowed-tools`（スペース区切り。実験的）

### 3) `name` フィールド制約（検証必須）
- 1〜64文字
- `a-z`（小文字英字）/ 数字 / `-` のみ
- 先頭/末尾が `-` でない
- `--`（連続ハイフン）を含まない
- 親ディレクトリ名と一致

### 4) progressive disclosure（運用方針）
- 起動/一覧時はメタ情報（主に `name`, `description`）のみ軽量にロード
- 実際にスキル使用時のみ `SKILL.md` 本文をロード
- references 等は必要時に個別ロード（相対パス参照）

---

## 追加するツール群（MVP）

### Tool 1: skills_list
**目的**: 指定ルート配下のスキル候補を走査し、`SKILL.md` の frontmatter を読み、一覧を返す。

- 入力
  - `root_dir`: スキルディレクトリ群を格納するルートディレクトリ
  - `recursive`: 再帰探索するか（将来オプション。MVPは true/false どちらか固定でもよい）
- 出力（例）
  - `[{"path": ".../pdf-processing", "name": "pdf-processing", "description": "...", "license": "...", "compatibility": "...", "metadata": {...}, "allowed_tools": "..."}, ...]`
- 期待動作
  - `SKILL.md` が存在するディレクトリのみ列挙
  - YAML frontmatter の parse 失敗は「一覧に含めるが error を付与」or「除外」いずれか（要統一）


### Tool 2: skills_load
**目的**: 指定スキルの `SKILL.md` を読み、frontmatter と body を返す。

- 入力
  - `skill_dir`: スキルディレクトリ
- 出力（例）
  - `{"path": "...", "frontmatter": {...}, "body_markdown": "..."}`


### Tool 3: skills_validate
**目的**: Agent Skills 仕様に沿ってスキルを検証し、エラー/警告を返す。

- 入力
  - `skill_dir`
  - `strict`: 警告を失敗扱いにするか
- 出力（例）
  - `{"ok": true/false, "errors": ["..."], "warnings": ["..."]}`

- MVP検証項目
  - `SKILL.md` の存在
  - frontmatter の存在（`---` ... `---`）
  - `name` の必須性・制約（上記）
  - `description` の必須性・長さ（1〜1024）
  - `compatibility` の長さ（<=500）※存在時
  - `metadata` が mapping であること、key/value が string であること（可能なら）


### Tool 4: skills_read_file
**目的**: スキル配下の参照ファイルを相対パスで読み出す（progressive disclosure用）。

- 入力
  - `skill_dir`
  - `relative_path`（例: `references/REFERENCE.md`）
- 出力
  - `{"path": "...", "content": "..."}`

- セキュリティ要件
  - `..` によるディレクトリトラバーサルを禁止
  - `skill_dir` 外への脱出を禁止（realpathチェック）

---

## 追加するツール群（拡張案）

### Tool 5: skills_search
- `skills_list` の結果（name/description）に対してキーワード検索
- 返却: マッチした skills とスコア（単純一致でよい）

### Tool 6: skills_index
- 大量スキルを扱う場合に、キャッシュ（sqlite/json）を作って高速化
- ただしMVPでは不要

### allowed-tools の統合（将来）
- `allowed-tools` を、このリポジトリのツール許可制御（もし存在するなら）と接続
- 例: `allowed-tools: Bash(git:*) Read` のような記述を
  - 実行前チェック
  - 実行計画生成
 などに利用

---

## 実装方針（コード構造）

### 配置
- `./src/uagent/tools/` 配下に `agent_skills/` あるいは `skills/` のようなサブパッケージを新設し、
  - パーサ
  - バリデータ
  - 各ツールエントリポイント
  を分離する。

例:
- `src/uagent/tools/agent_skills/parser.py`
- `src/uagent/tools/agent_skills/validator.py`
- `src/uagent/tools/agent_skills/tools.py`（tool定義）

### YAML frontmatter のパース
- `SKILL.md` 先頭の `---` から次の `---` までを YAML として扱う。
- それ以降を Markdown body とする。
- パース結果は
  - `frontmatter: dict`
  - `body: str`
 で保持。

### エラー設計
- ツール実行エラー（入出力不正/ファイル無し/パース不能）と
- 検証エラー（仕様違反）
を区別し、
- 実行エラーは例外 or `ok=false` で返す
- 検証は `skills_validate` で詳細を返す
のように一貫性を持たせる。

---

## ドキュメント追加方針
- `./src/uagent/docs` に
  - Agent Skills 対応の概要
  - 各ツールの引数/返却/例
  - セキュリティ注意（skills_read_file のパス制約等）
を追記する。

---

## 受け入れ条件（MVP）
- `skills_list` が `SKILL.md` を持つディレクトリを列挙できる
- `skills_load` が frontmatter/body を正しく分離できる
- `skills_validate` が name/description 等の仕様違反を検出できる
- `skills_read_file` がスキル外へ脱出できない

---

## 次に行う作業（この方針確定後）
1. 既存 `./src/uagent/tools` のツール登録方式・I/O形式を調査
2. 既存の YAML/Markdown 依存（PyYAML等）の有無を確認
3. MVP 4ツールを実装
4. `./src/uagent/docs` に使い方を追記
5. 最低限のテスト（ユニット or スモーク）を追加
