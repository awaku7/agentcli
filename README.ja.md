<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag（ローカルAIエージェント）

uag は、ローカルPC上で **コマンド実行**・**ファイル操作**・**PDF/PPTX/Excel などのデータ読取** を行う対話型エージェントです。CLI / GUI / Web の 3 つのインターフェースを提供します。

GitHub: https://github.com/awaku7/agentcli

## インストール

PyPI から pip でインストールできます。

```bash
pip install uag
```

仮想環境を使う場合は、先に有効化してから実行してください。

初回起動時には、必要なプロバイダ設定が不足している場合に限り、環境変数を設定するためのセットアップウィザードが自動的に起動します。設定の詳細は [ENVIRONMENT.ja.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.ja.md) を参照してください。

## 主な特長

- **実用的なツール群**: ファイル操作、ウェブ検索、PDF/PPTX/Excel 抽出、画像生成、画像解析。
- **マルチプロバイダ対応**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA。
- **3つのインターフェース**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **A2A サーバー**: `uaga` / `python -m uagent.a2a.server`
- **MCP 対応**: 外部 MCP ツールサーバーへ接続可能。
- **セッション継続**: モデルやプロバイダを切り替えても会話文脈を維持。
- **Web Inspector**: `playwright_inspector` でブラウザ遷移、DOM、スクリーンショットを保存。
- **組み込みドキュメント**: `uag docs` で同梱ドキュメントを参照可能。

## 使い方

### 起動と終了
ターミナルで `uag` を実行して開始します。終了するには `:exit` を入力します。

### A2A サーバー
Agent2Agent 互換の HTTP サーバーを起動します。

```bash
uaga
```

認証、ホスト、ポート、再読み込み、公開ベース URL、同時実行数、エンジンなどの `UAGENT_A2A_*` 設定は [ENVIRONMENT.ja.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.ja.md) を参照してください。

### 便利なコマンド
- `:tools`: ロード済みツール一覧を表示
- `:logs [n]`: 直近のセッションログを表示
- `:load <index>`: 過去セッションを読み込む
- `:skills`: Agent Skills を選択してロード
- `:shrink [n]`: 履歴を要約して末尾 `n` 件を残す

## 設定と詳細

### 環境変数とセットアップ
API キー、表示言語 `UAGENT_LANG`、履歴圧縮設定などの詳細は [ENVIRONMENT.ja.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.ja.md) を参照してください。

- **セットアップウィザード**: `python -m uagent.setup_cli`
- **暗号化済み環境**: `uag_envsec` で `.env` を `.env.sec` として暗号化可能
- **暗号化ファイルの更新**: `uag_envsec add --file .env.sec --key NAME --value VALUE`

### Responses API の注意
`UAGENT_RESPONSES=1` を設定した場合、Responses API は OpenAI / Azure / Bedrock / OpenRouter / Ollama で使用されます。
Gemini / Claude / Vertex AI はネイティブ API 経路を使い、Responses API の対象外です。
それ以外のプロバイダでは、プロバイダ固有の経路または ChatCompletions にフォールバックします。

### 開発者向けドキュメント / 多言語
- **開発者ドキュメント**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **ロケール追加**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **他言語の README**: [English](https://github.com/awaku7/agentcli/blob/main/README.md) / [日本語](https://github.com/awaku7/agentcli/blob/main/README.ja.md) / [Deutsch](https://github.com/awaku7/agentcli/blob/main/README.de.md) / [Español](https://github.com/awaku7/agentcli/blob/main/README.es.md) / [Français](https://github.com/awaku7/agentcli/blob/main/README.fr.md) / [Italiano](https://github.com/awaku7/agentcli/blob/main/README.it.md) / [한국어](https://github.com/awaku7/agentcli/blob/main/README.ko.md) / [Português](https://github.com/awaku7/agentcli/blob/main/README.pt_BR.md) / [Русский](https://github.com/awaku7/agentcli/blob/main/README.ru.md) / [ไทย](https://github.com/awaku7/agentcli/blob/main/README.th.md) / [简体中文](https://github.com/awaku7/agentcli/blob/main/README.zh_CN.md) / [繁體中文](https://github.com/awaku7/agentcli/blob/main/README.zh_TW.md) / [Polski](https://github.com/awaku7/agentcli/blob/main/README.pl.md) / [Tiếng Việt](https://github.com/awaku7/agentcli/blob/main/README.vi.md) / [Bahasa Indonesia](https://github.com/awaku7/agentcli/blob/main/README.id.md) / [العربية](https://github.com/awaku7/agentcli/blob/main/README.ar.md) / [हिन्दी](https://github.com/awaku7/agentcli/blob/main/README.hi.md) / [Português](https://github.com/awaku7/agentcli/blob/main/README.pt.md) / [Svenska](https://github.com/awaku7/agentcli/blob/main/README.sv.md) / [Norsk bokmål](https://github.com/awaku7/agentcli/blob/main/README.nb.md) / [フィンランド語](https://github.com/awaku7/agentcli/blob/main/README.fi.md) / [オランダ語](https://github.com/awaku7/agentcli/blob/main/README.nl.md)

`UAGENT_RESPONSES=1` を設定した場合、Responses API は OpenAI / Azure / Bedrock / OpenRouter / Ollama で使用されます。
Gemini / Claude / Vertex AI use their native API paths and are not covered by Responses API.
For other providers, uag falls back to the provider-specific or chat-completions path.
