```
██╗   ██╗ █████╗  ██████╗ ███████╗███╗   ██╗████████╗ ██████╗██╗     ██╗
██║   ██║██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██╔════╝██║     ██║
██║   ██║███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ██║     ██║     ██║
██║   ██║██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ██║     ██║     ██║
╚██████╔╝██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ╚██████╗███████╗██║
 ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝╚══════╝╚═╝
```

# uag（ローカルAIエージェント）

uag は、ローカルPC上で **コマンド実行**・**ファイル操作**・**各種データ読取** などを行う対話型エージェントです。CLI / GUI / Web の 3 つのインターフェースを提供します。

## インストール

`uag` は pip でインストールできます。

```bash
pip install uag
```

インストール後、初回起動時に環境変数を設定するための **対話型セットアップウィザード** が自動的に起動します。環境変数の詳細や暗号化については、**[ENVIRONMENT.ja.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.ja.md)** を参照してください。

## 主な特長

- **実用的なツール群**: ローカル環境で即座に実行可能な、ファイル操作、ウェブ検索、データ抽出（PDF/PPTX/Excel）、画像生成・解析等のツールを搭載。
- **マルチプロバイダ対応**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Claude / Grok / NVIDIA をサポート。
- **柔軟なインターフェース**: 
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
- **MCP (Model Context Protocol)**: 外部 MCP ツールサーバーとの連携が可能。
- **セッション継続**: プロバイダやモデルを切り替えても会話の文脈を保持。
- **Web Inspector**: `playwright_inspector` を使用して、ブラウザ操作の遷移、DOM、スクリーンショットを自動保存。
- **ドキュメント参照**: `uag docs` コマンドで、内蔵されている詳細ドキュメントを即座に参照可能。

## 使い方

### 起動と終了
ターミナルから `uag` を実行して開始します。終了するには `:exit` を入力します。

### A2A（Agent2Agent）サーバー
既存のインターフェースとは別に、A2A 互換の HTTP サーバーを起動できます。
```bash
uaga
# または python -m uagent.a2a.server
```

### 便利な Tips（会話の継続と制御）
- `:tools`: ロード済みツール一覧を表示。
- `:logs [n]`: セッションログを表示（`n` で件数指定）。
- `:load <index>`: 過去のセッションを読み込んで会話を再開。
- `:skills`: Agent Skills（追加の役割や指示）を選択してロード。
- `:shrink [n]`: 会話履歴を末尾 `n` 件に整理してトークンを節約。

## 設定と詳細情報

### 環境変数とセットアップ
詳細な設定（プロバイダの API キー、表示言語 `UAGENT_LANG`、履歴圧縮設定など）については、**[ENVIRONMENT.ja.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.ja.md)** を参照してください。
- **セットアップ**: `python -m uagent.setup_cli` で対話的に設定。
- **暗号化**: `uag_envsec` ツールで `.env` ファイルを安全に暗号化可能。

### 開発者・多言語対応
- **開発者ドキュメント**: `src/uagent/docs/DEVELOP.md`
- **ロケールの追加**: `src/uagent/docs/ADD_LOCALE.md`
- **他言語の README**: [English](https://github.com/awaku7/agentcli/blob/main/README.md) / [Deutsch](https://github.com/awaku7/agentcli/blob/main/README.de.md) / [Français](https://github.com/awaku7/agentcli/blob/main/README.fr.md) / [한국어](https://github.com/awaku7/agentcli/blob/main/README.ko.md) / [简体中文](https://github.com/awaku7/agentcli/blob/main/README.zh_CN.md) / [繁體中文](https://github.com/awaku7/agentcli/blob/main/README.zh_TW.md)
