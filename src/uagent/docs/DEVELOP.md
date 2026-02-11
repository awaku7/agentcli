# DEVELOP（開発者向け）

このドキュメントは **uag（ローカル ツール実行エージェント）** の開発者向けメモです。

## 動作環境

- Python 3.11 以上（`pyproject.toml` の `requires-python` 準拠）
- Git（バージョン管理および一部ツールで必須）
  - Windows: [公式サイト](https://git-scm.com/download/win) からダウンロード
  - macOS: Homebrew (`brew install git`) または Xcode Command Line Tools (`xcode-select --install`)
  - Linux: `sudo apt install git` (Ubuntu/Debian) または `sudo yum install git` (CentOS/RHEL)
- Windows / macOS / Linux

### エントリポイント

- **CUI**: `src/uagent/cli.py`（実行時は `uag` / `python -m uagent`）
- **GUI**: `src/uagent/gui.py`（実行時は `uagg` / `python -m uagent.gui`）
- **Web**: `src/uagent/web.py`（実行時は `uvgw` / `python -m uagent.web`）

※ ルート直下の `uag.py`, `scheckgui.py`（旧GUIラッパ）, `scheckweb.py`（旧Webラッパ） は、パッケージングされていない環境でも手軽に実行できるようにするためのラッパースクリプトです。

### 主要コンポーネント

- **Core**: `src/uagent/core.py` (会話履歴、ログ、ステータス、Summarization)
- **LLM Logic**: `src/uagent/uagent_llm.py` (対話ループ、ツール実行制御、リトライ制御)
- **Providers**:
  - `src/uagent/llm_openai_responses.py` (OpenAI/Azure Responses API 対応)
  - `src/uagent/llm_gemini.py` (Google Gemini API / `google-genai` 対応)
  - `src/uagent/llm_claude.py` (Anthropic Claude API 対応)
  - `src/uagent/llm_errors.py` (エラーハンドリング、Rate Limit リトライ計算)
- **Utilities**:
  - `src/uagent/util_providers.py` (クライアント生成)
  - `src/uagent/util_tools.py` (ツール共通処理: tools callbacks/コマンド処理/初期メッセージ構築など)
  - `src/uagent/runtime_init.py` (起動時初期化の共通化: workdir決定・banner生成・長期記憶挿入)
- **Tools**: `src/uagent/tools/` (プラグイン群)
- **Prompts**: `src/uagent/prompts/` (YAML定義 + テンプレート)

---

## 1. 文字コード（Windows）

### 1.1 背景

Windows 環境では、外部コマンド（特に `git diff` など）の出力が UTF-8 を含むことがあり、cp932 固定で `subprocess.run(..., text=True, encoding="cp932")` を行うと、Python の `_readerthread` 側で `UnicodeDecodeError` が発生します。

### 1.2 現行方針

`src/uagent/core.py` の `CMD_ENCODING` は以下の方針です。

- 既定: `utf-8`
- 上書き: 環境変数 `UAGENT_CMD_ENCODING`

開発・運用環境が cp932 前提の場合は、環境変数で明示的に戻してください。

---

## 2. 全体アーキテクチャ

### 2.1 実行の流れ

1. `uag` / `uagg` / `uvgw` が起動。
2. 起動時初期化（主に `runtime_init.py` / `util_tools.py`）
   - workdir の決定・作成・chdir（CLI引数 `--workdir/-C`、環境変数 `UAGENT_WORKDIR`、または自動）
   - 起動時INFO（provider/base_url/api_version/Responses等）の banner 生成（文字列）
   - tools callbacks の注入（`util_tools.init_tools_callbacks`）
   - `util.py` は互換層（外部互換のための再export）であり、内部処理は原則 `util_tools/util_providers/uagent_llm/runtime_init` を直接参照する。
3. `src/uagent/tools/`（および `UAGENT_EXTERNAL_TOOLS_DIR`）からツールを動的ロード。
4. 設定された LLM プロバイダ（Azure/OpenAI/Gemini/Grok/Claude）のクライアントを初期化。
5. ユーザー入力待ちループ（CUI/GUI/Web）。
6. LLM との対話ラウンド実行（`uagent_llm.run_llm_rounds`）。
   - Tool Calls があれば実行し、結果を履歴に追加して再帰。
   - 429 Rate Limit 発生時は Exponential Backoff でリトライ。
7. 最終回答を出力。

### 2.2 LLM プロバイダの実装差異

- **OpenAI / Azure**:
  - Chat Completions と Responses API (`UAGENT_RESPONSES=1`) をサポート。
  - Responses モードでは `llm_openai_responses.py` でメッセージ構造変換を行う。
  - Azure のエンドポイント指定は `UAGENT_AZURE_BASE_URL` を使用（`azure_endpoint` 引数へ渡される）。
- **Gemini**:
  - `google-genai` ライブラリを使用。
  - `llm_gemini.py` で JSON Schema を Gemini 用の型定義へ変換 (`_sanitize_gemini_parameters`)。
  - コンテキストキャッシュ (`GeminiCacheManager`) をサポート。システムプロンプトやツール定義をキャッシュして高速化・コスト削減を図る。
- **Claude**:
  - `anthropic` ライブラリを使用。
  - `llm_claude.py` で OpenAI 互換の messages を Anthropic 形式（System分離、User/Assistant交互制限など）へ変換。
  - System Prompt キャッシュ (`cache_control`) を部分的にサポート。

### 2.3 起動時挙動の補足（workdir / banner / 長期記憶）

#### workdir の決定ルール
workdir は次の優先順位で決定されます。

1. CLI引数: `--workdir` / `-C`
2. 環境変数: `UAGENT_WORKDIR`
3. 自動: カレントディレクトリ（`./` の絶対パス）

補足:
- CLI/Web は `main()` 内で workdir を作成・`chdir` します（モジュール import 時に `chdir` しません）。
- GUI は `main()` 内で同様に workdir を作成・`chdir` します。

GUI の例:
- `uag gui -C ./work`

#### 起動時INFO（banner）
起動時INFO（workdir/provider/base_url/api_version/Responses等）は `runtime_init.build_startup_banner()` が文字列として生成します。
表示経路はUIごとに異なりますが、生成内容は統一されています。

#### 長期記憶/共有メモ
長期記憶（個人）および共有メモ（共有長期記憶）は、可能な場合 system message として履歴に挿入されます。
共有メモは content の先頭に `【共有長期記憶（共有メモ）】` を付与します。

#### GUI/WEB のログ表示について（複数行案内の抑制）
GUI/WEB では CLI専用の操作案内（例: 「複数行」）が表示に混ざらないよう、UI表示側で該当行をフィルタします。
クイックガイド自体は表示しますが、「複数行」を含む案内行は抑制されます。

#### NVIDIA の base_url について
`UAGENT_NVIDIA_BASE_URL` の既定値は `https://integrate.api.nvidia.com/v1` です。
環境変数で上書きする場合も、原則 `/v1` を指定してください。

---

## 3. Responses API と画像入力（Vision）

### 3.1 UAGENT_RESPONSES

OpenAI/Azure の場合、`UAGENT_RESPONSES=1` で **Responses API** を使用します。これにより Structured Outputs や JSON Schema の恩恵を受けやすくなりますが、入力形式が厳格になります。

### 3.2 画像入力（Multimodal）

- GUI/CUI でユーザーが画像を添付した場合、内部メッセージには `{"type": "image_url", ...}` が含まれます。
- **Chat Completions モード**: 動作しません（画像は無視されるかエラーになる可能性があります）。
- **Responses モード**: `llm_openai_responses.py` が `input_image` アイテムに変換して送信します。
- **Gemini**: `google-genai` はネイティブで画像入力をサポートしていない場合があるため、現状は `analyze_image` ツール等での代替を推奨するか、ライブラリの対応状況に合わせて実装を更新します。

### 3.3 画像解析ツール (`analyze_image`) のモデル指定

Vision 入力を LLM 本体へ直接渡すのではなく、ツールとして画像解析を実行する場合、以下の環境変数でモデルを指定できます。

- `UAGENT_AZURE_IM_DEPNAME`: Azure 用 Vision 対応モデル（デプロイ名）
- `UAGENT_OPENAI_IM_DEPNAME`: OpenAI 用 Vision 対応モデル
- `UAGENT_GEMINI_VISION_MODEL`: Gemini 用 Vision 対応モデル

### 3.4 画像生成ツール (`generate_image`) の設定

- `UAGENT_IMAGE_DEPNAME`: 画像生成用モデル/デプロイ名 (Azure/OpenAI/Gemini用)
- `UAGENT_IMAGE_OPEN`: 生成後に自動で画像を開くかどうか
    - `1`, `true`, `yes`, `on`: 有効 (既定)
    - `0`, `false`, `no`, `off`: 無効

---

## 4. ツール（プラグイン）の開発

### 4.1 ツール登録

ツールは以下のいずれかに配置された Python モジュールから自動ロードされます。

1. **内部ディレクトリ**: `src/uagent/tools/` 直下
2. **外部ディレクトリ**: 環境変数 `UAGENT_EXTERNAL_TOOLS_DIR` で指定されたパス

モジュールは以下をエクスポートする必要があります。

- `TOOL_SPEC: dict`: OpenAI 互換の Function Calling 定義
- `run_tool(args: dict) -> str`: 実行ロジック。JSON 文字列またはテキストを返す。

### 4.2 ホスト機能へのアクセス (`context.py`)

ツール内で `from .context import get_callbacks` を呼び出すと、ホスト側の機能を利用できます。

- `cb.human_ask(message, is_password)`: ユーザー確認・入力（CUI/GUI共通）
- `cb.set_status(busy, label)`: ステータス表示更新
- `cb.get_env(name)`: 環境変数取得（マスク対応）
- `cb.file_exists(path)`: ファイル存在確認

### 4.3 安全性ガイドライン

- **ファイル操作**: `safe_file_ops.py` を使用し、原則として `workdir` 配下に操作を限定する。
- **コマンド実行**: `safe_exec_ops.py` を使用し、危険なコマンドや引数をブロックまたは確認する。
- **秘匿情報**: `human_ask(is_password=True)` を使い、ログにも平文で残さない。

---

## 5. テストと品質管理

### 5.1 テスト実行

```bash
# 全体テスト
python -m unittest discover tests

# テストツール経由（scheck内から実行可能）
run_tests
```

### 5.2 静的解析

```bash
# lint
ruff check src

# type check
mypy src
```

---

## 6. MCP (Model Context Protocol) 連携

uag は MCP クライアント機能を内蔵しています。

- `handle_mcp_v2`: 汎用的なツール実行ラッパー
- `mcp_tools_list`: サーバーからツール一覧を取得
- `mcp_servers_*`: サーバー定義ファイル (`mcp_servers.json`) の CRUD

ツール拡張の際は、まず既存の MCP サーバーで実現できないか検討してください。

---

## 7. 依存関係

- **必須**: `python-dotenv`, `requests`, `regex` 等（`pyproject.toml` 参照）
- **プロバイダ別**: `openai`, `google-genai`, `anthropic`
- **GUI**: `PySide6`
- **Web**: `fastapi`, `uvicorn`, `websockets`
- **Excel/Doc**: `pandas`, `openpyxl`, `pdfminer.six`, `python-pptx`, `exstruct`
- **Network/Security**: `requests`, `httpx`, `pyOpenSSL`, `certifi`, `playwright`
- **Data/Math**: `numpy`

---

## 8. ライセンス

Apache License 2.0 に基づき公開されています。
コントリビューションの際は、既存のライセンスヘッダや著作権表記を尊重してください。