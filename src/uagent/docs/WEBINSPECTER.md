# WEBINSPECTER（playwright_inspector）

`uag` の `playwright_inspector` ツールは、Playwright を用いて **手動ブラウザ操作の流れ**を記録し、
あとから（主に LLM で）解析・デバッグに使える形で成果物を保存します。

> 注意
> - 本ツールは Playwright を利用します。事前に Playwright のインストールとブラウザのセットアップが必要です。
> - ログには URL やリクエスト情報、画面の HTML が含まれます。機密情報・個人情報の取り扱いに注意してください。

---

## 1. 何ができるか（用途）

- ログインなど **人間が手で操作しないと進めない手順**を踏んだあとに、
  - ページ遷移（URL 変化）ごとの DOM（HTML）
  - ページ遷移ごとのスクリーンショット
  - 遷移・ネットワーク・console・pageerror のイベントログ
  を保存し、あとから問題解析に使えます。

典型的な利用シーン:
- 認証付き画面の DOM を採取したい
- 画面遷移の途中でどの URL に飛んだか、どの API が失敗したかを追いたい
- コンソールエラーやページエラーを証跡として残したい

---

## 2. 使い方

ツール呼び出し（例）:

- URL を開いて Inspector を起動します
- 画面を手操作して、Inspector の **Resume(▷)** を押すと記録を確定して終了します

### 2.1 ツール引数

- `url`:
  - 最初に開くURL（既定: `about:blank`）
- `prefix`:
  - 保存先ディレクトリ名に使う接頭辞（既定: `debug_capture`）

---

## 3. 生成物（保存先）

> 補足（workdir）
> - 保存先は「現在の workdir」配下に作成されます。
> - workdir は `--workdir/-C`（CLI）、`UAGENT_WORKDIR`（Web/GUI含む）、または自動で決定されます。
> - どこに保存されたか分からない場合は、起動時の `[INFO] workdir = ...` を確認してください。

保存先は **`webinspect/{prefix}/`** です（`prefix` は安全なファイル名にサニタイズされます）。

- `webinspect/{prefix}/final.html`
  - 最終状態の DOM（`page.content()`）
- `webinspect/{prefix}/final.png`
  - 最終状態のスクリーンショット
- `webinspect/{prefix}/flow.jsonl`
  - イベントログ（JSON Lines）
- `webinspect/{prefix}/snapshots/`
  - URL 遷移（メインフレーム `framenavigated`）ごとの DOM/スクショ
  - 例: `0001_navigated_<sanitized>.html` / `0001_navigated_<sanitized>.png`

---

## 4. flow.jsonl（イベントログ）の見方

`flow.jsonl` は 1行1JSON の形式です。

代表的な `type`:
- `goto`: 初回 `page.goto()`
- `navigated`: メインフレームの URL 遷移
- `snapshot`: 自動保存したスナップショット（index/URL/ファイル名など）
- `request`: リクエスト（method/url/resource_type）
- `response`: レスポンス（url/status/ok）
- `console`: ブラウザ console の出力
- `pageerror`: ページエラー
- `final`: 最終成果物の出力情報

LLM に渡すときのコツ:
- まず `flow.jsonl` を時系列に読ませ、どの URL に遷移したか、どの response が失敗したかを抽出させる
- 問題が起きた直前/直後の `snapshots/*.html` を追加で読ませて DOM を解析させる

---

## 5. LLM での解析例（プロンプト例）

以下のファイルを添付（または貼り付け）して依頼します。

- `webinspect/{prefix}/flow.jsonl`
- `webinspect/{prefix}/snapshots/000X_*.html`（必要な箇所だけ）
- `webinspect/{prefix}/final.html`

プロンプト例:

- 「flow.jsonl を時系列に解析して、どの URL 遷移のあとにエラーが出たか特定して」
- 「navigated の直後に response.status が 4xx/5xx になっている箇所を列挙して」
- 「該当の snapshot HTML を読んで、フォーム要素の name/id を抽出して」

---

## 6. wheel（whl）インストール後にドキュメントを読ませる導線案

「インストール後でも確実に読める」導線として、次が実用的です。

### 6.1 README から案内（最小）
- README に「詳細は `WEBINSPECTER.md`」と明記

### 6.2 パッケージに同梱して参照できるようにする（推奨）
- `WEBINSPECTER.md` をパッケージデータとして wheel に含める
- `importlib.resources` で取り出せるようにする

例（概念）:
- `python -c "import importlib.resources as r; print(r.files('uagent').joinpath('WEBINSPECTER.md').read_text())"`

### 6.3 CLI で表示するコマンドを用意する（推奨）
- 例: `uag docs webinspect` で内容を表示、またはパスを表示
- 例: `uag docs --open webinspect`（環境次第でブラウザ/エディタ起動）

### 6.4 PyPI / project_urls にリンクを載せる
- `pyproject.toml` の `project.urls` に GitHub 上の `WEBINSPECTER.md` を登録

---
