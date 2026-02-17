# uag（ローカルツール実行エージェント）

uag は、ローカルPC上で **コマンド実行**・**ファイル操作**・**各種データ読取** などを行う対話型エージェントです。

- CUI（CLI）: `uag` / `python -m uagent`
- GUI: `uagg` / `python -m uagent.gui`
- Web: `uagw` / `python -m uagent.web`

---

## ドキュメント（`uag docs`）

wheel（whl）でインストールした環境でも、同梱ドキュメントを `uag docs` で参照できます。

```bash
uag docs
uag docs webinspect
uag docs develop
uag docs --path webinspect
uag docs --open webinspect
```

---

## インストール（配布版: whl）

配布された whl を pip でインストールする手順は **`QUICKSTART.md`** を参照してください。

- 配布先: GitHub の **Releases** ページ（Assets の `.whl`）
- whl 例: `uag-<VERSION>-py3-none-any.whl`
- インストール例:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ./uag-<VERSION>-py3-none-any.whl
```

補足:
- `uag` は **Python 3.11+** が必要です。
- リポジトリを開発用途で使う場合は、`python -m pip install -e .`（Web UIも使うなら `python -m pip install -e ".[web]"`）を推奨します。

---

## 使い方（最低限）

### 起動

```bash
uag
# または
python -m uagent
```

#### workdir（作業ディレクトリ）指定

通常は指定の必要はありません。

- CLI: `uag -C ./work`
- GUI: `uag gui -C ./work`（または `python -m uagent.gui -C ./work`）
- Web: `UAGENT_WORKDIR=./work uag web`（Web は環境変数で指定）

終了:

- `:exit`

---

## Provider（OpenAI互換の扱い）

`uag` は複数のLLMプロバイダを切り替えて利用できます。

- `UAGENT_PROVIDER=openai` は **OpenAI互換**（OpenAI API互換のエンドポイントを含む）として扱います。
  - 必須: `UAGENT_OPENAI_API_KEY`
  - 任意: `UAGENT_OPENAI_BASE_URL`（既定: `https://api.openai.com/v1`）
  - 任意: `UAGENT_OPENAI_DEPNAME`

- `UAGENT_PROVIDER=azure` は **Azure OpenAI** を利用します。
  - 必須: `UAGENT_AZURE_BASE_URL`
  - 必須: `UAGENT_AZURE_API_KEY`
  - 必須: `UAGENT_AZURE_API_VERSION`
  - 任意: `UAGENT_AZURE_DEPNAME`

- `UAGENT_PROVIDER=openrouter` は **OpenRouter**（OpenAI互換の統一API）を利用します。
  - 必須: `UAGENT_OPENROUTER_API_KEY`
  - 任意: `UAGENT_OPENROUTER_BASE_URL`（既定: `https://openrouter.ai/api/v1`）
  - 任意: `UAGENT_OPENROUTER_DEPNAME`
  - 任意: OpenRouter のモデルフォールバック（OpenRouter独自拡張）
    - 条件: `UAGENT_OPENROUTER_DEPNAME="openrouter/auto"` のときのみ有効（他プロバイダ・他モデル指定には影響しません）
    - `UAGENT_OPENROUTER_FALLBACK_MODELS`（カンマ区切り）を設定すると、Chat Completions リクエストに `models=[...]` を付与します
      - 例: `UAGENT_OPENROUTER_FALLBACK_MODELS="anthropic/claude-4.5-sonnet,openai/gpt-4o,mistral/mistral-x"`

- `UAGENT_PROVIDER=nvidia` は **NVIDIA（OpenAI互換）** を利用します。
  - 必須: `UAGENT_NVIDIA_API_KEY`
  - 任意: `UAGENT_NVIDIA_BASE_URL`（既定: `https://integrate.api.nvidia.com/v1`）
    - `/v1` を指定してください（`/v1/chat/completions` まで含める指定は推奨しません）
  - 任意: `UAGENT_NVIDIA_DEPNAME`

- `UAGENT_PROVIDER=grok` は **xAI Grok（OpenAI互換）** を利用します。
  - 必須: `UAGENT_GROK_API_KEY`
  - 任意: `UAGENT_GROK_BASE_URL`（既定: `https://api.x.ai/v1`）
  - 任意: `UAGENT_GROK_DEPNAME`

- `UAGENT_PROVIDER=gemini` は **Google Gemini（google-genai）** を利用します。
  - 必須: `UAGENT_GEMINI_API_KEY`
  - 任意: `UAGENT_GEMINI_DEPNAME`

- `UAGENT_PROVIDER=claude` は **Anthropic Claude** を利用します。
  - 必須: `UAGENT_CLAUDE_API_KEY`
  - 任意: `UAGENT_CLAUDE_DEPNAME`

※プロバイダやキーの設定例は `env.sample.*` を参照してください。

---

## 更新情報

- CUIの確認入力（confirm）で、稀に `[REPLY] >` が二重に表示される問題を修正しました。

---

## 開発者向け

開発者向けの情報は `src/uagent/docs/DEVELOP.md` を参照してください。

追加ドキュメント:
- `src/uagent/docs/RUNTIME_INIT.md`（起動時初期化: workdir/banner/長期記憶）
- `src/uagent/docs/WEB_UI_LOGGING.md`（Web UI のログ/メッセージ経路）

---

## Web Inspector（playwright_inspector）

Playwright Inspector を使って、手動操作の流れ（URL遷移/DOM/スクリーンショット/イベントログ）を保存できます。

前提:
- `playwright` がインストールされていること
- ブラウザのセットアップが済んでいること（例: `python -m playwright install`）

ドキュメント:
- `src/uagent/docs/WEBINSPECTER.md`
- `uag docs webinspect`（wheel環境でも参照可能）
