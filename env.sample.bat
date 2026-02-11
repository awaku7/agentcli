@echo off

REM env.sample.bat - minimal environment variables (sample)

REM

REM 使い方:

REM   1) このファイルを env.bat 等にコピーして値を埋める

REM   2) cmd.exe で実行:  call env.bat

REM

REM 注意:

REM - これは SAMPLE です。APIキー等を入れたらコミットしないでください。

REM - OpenAI互換（互換エンドポイント含む）を使う場合は UAGENT_PROVIDER=openai を使用します。

REM - OpenRouter を使う場合は UAGENT_PROVIDER=openrouter を使用します。



REM ==============================

REM Provider 選択

REM ==============================

REM azure / openai / openrouter / gemini / grok / claude

set UAGENT_PROVIDER=openai



REM ==============================

REM OpenAI互換 (UAGENT_PROVIDER=openai)

REM ==============================

REM OpenAI互換のエンドポイントを使う場合は UAGENT_OPENAI_BASE_URL を指定

REM 例: set UAGENT_OPENAI_BASE_URL=https://api.openai.com/v1

REM set UAGENT_OPENAI_BASE_URL=https://api.openai.com/v1

set UAGENT_OPENAI_API_KEY=<your-openai-api-key>



REM chat 用モデル名（互換サービスの場合も「モデル名」または「デプロイ名」をここに）

set UAGENT_DEPNAME=gpt-4o



REM ==============================

REM OpenRouter (UAGENT_PROVIDER=openrouter)

REM ==============================

REM OpenRouter は OpenAI互換の統一APIです。

REM https://openrouter.ai/

REM 既定 base_url: https://openrouter.ai/api/v1

set UAGENT_OPENROUTER_API_KEY=<your-openrouter-api-key>

REM set UAGENT_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

REM set UAGENT_OPENROUTER_DEPNAME=gpt-4o



REM
REM OpenRouter モデルフォールバック（OpenRouter独自拡張）
REM - 有効化条件: UAGENT_OPENROUTER_DEPNAME=openrouter/auto
REM - UAGENT_OPENROUTER_FALLBACK_MODELS を指定すると、リクエストに models=[...] を付与して OpenRouter 側でフォールバックします
REM set UAGENT_OPENROUTER_DEPNAME=openrouter/auto
REM set UAGENT_OPENROUTER_FALLBACK_MODELS=anthropic/claude-4.5-sonnet,openai/gpt-4o,mistral/mistral-x

REM ==============================

REM Azure OpenAI (UAGENT_PROVIDER=azure)

REM ==============================

REM set UAGENT_AZURE_BASE_URL=https://<your-azure-openai-endpoint>

REM set UAGENT_AZURE_API_KEY=<your-azure-api-key>

REM set UAGENT_AZURE_API_VERSION=2024-05-01-preview

REM set UAGENT_DEPNAME=gpt-4o



REM ==============================

REM Google Gemini (UAGENT_PROVIDER=gemini)

REM ==============================

REM set UAGENT_GEMINI_API_KEY=<your-gemini-api-key>

REM set UAGENT_DEPNAME=gemini-1.5-flash



REM ==============================

REM Grok (UAGENT_PROVIDER=grok)

REM ==============================

REM set UAGENT_GROK_API_KEY=<your-grok-api-key>

REM set UAGENT_DEPNAME=grok-2-1212



REM ==============================

REM Claude (UAGENT_PROVIDER=claude)

REM ==============================

REM set UAGENT_CLAUDE_API_KEY=<your-claude-api-key>

REM set UAGENT_DEPNAME=claude-3-5-sonnet-20241022



REM ==============================

REM 任意: 起動時workdir

REM ==============================

REM set UAGENT_WORKDIR=.



REM ==============================

REM 任意: 画像生成ツール (generate_image)

REM ==============================

REM 生成後に自動で画像を開くかどうか (1:有効(既定), 0:無効)

REM set UAGENT_IMAGE_OPEN=1



REM 画像生成用モデル/デプロイ名 (Azure/OpenAI/Gemini用)

REM set UAGENT_IMAGE_DEPNAME=dall-e-3

