@echo off
REM uag_setup により自動生成
REM このファイルを直接編集しないでください。再生成するには uag_setup を再実行してください。

REM uag 用 .env（`uag_setup` で生成）
REM
REM 注記:
REM - このファイルには秘密情報（API キー）が含まれる場合があります。Git にコミットしないでください。
REM - `uag_setup` はいつでも再実行して再生成できます。

REM ==============================
REM Provider selection
REM ==============================
REM azure / openai / bedrock / openrouter / gemini / grok / claude / ollama / nvidia
set UAGENT_PROVIDER=ollama

REM ==============================
REM set OpenAI 互換 (UAGENT_PROVIDER=openai)
REM ==============================
REM set UAGENT_OPENAI_API_KEY=
REM set UAGENT_OPENAI_BASE_URL=
REM set UAGENT_OPENAI_DEPNAME=

REM ==============================
REM set Azure OpenAI (UAGENT_PROVIDER=azure)
REM ==============================
REM set UAGENT_AZURE_BASE_URL=
REM set UAGENT_AZURE_API_KEY=
REM set UAGENT_AZURE_API_VERSION=
REM set UAGENT_AZURE_DEPNAME=

REM ==============================
REM set Bedrock の OpenAI 互換ゲートウェイ (UAGENT_PROVIDER=bedrock)
REM ==============================
REM set UAGENT_BEDROCK_BASE_URL=
REM set UAGENT_BEDROCK_API_KEY=
REM set UAGENT_BEDROCK_DEPNAME=

REM ==============================
REM set OpenRouter (UAGENT_PROVIDER=openrouter)
REM ==============================
REM set UAGENT_OPENROUTER_API_KEY=
REM set UAGENT_OPENROUTER_BASE_URL=
REM set UAGENT_OPENROUTER_DEPNAME=
REM set UAGENT_OPENROUTER_FALLBACK_MODELS=

REM ==============================
REM set Gemini (UAGENT_PROVIDER=gemini)
REM ==============================
REM set UAGENT_GEMINI_API_KEY=
REM set UAGENT_GEMINI_DEPNAME=

REM ==============================
REM set Grok (UAGENT_PROVIDER=grok)
REM ==============================
REM set UAGENT_GROK_API_KEY=
REM set UAGENT_GROK_BASE_URL=
REM set UAGENT_GROK_DEPNAME=

REM ==============================
REM set Claude (UAGENT_PROVIDER=claude)
REM ==============================
REM set UAGENT_CLAUDE_API_KEY=
REM set UAGENT_CLAUDE_DEPNAME=

REM ==============================
REM set Ollama (UAGENT_PROVIDER=ollama)
REM ==============================
set UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
set UAGENT_OLLAMA_API_KEY=
set UAGENT_OLLAMA_DEPNAME=gemma4:e4b
set UAGENT_OLLAMA_TIMEOUT_SEC=
set UAGENT_OLLAMA_TEMPERATURE=
set UAGENT_OLLAMA_TOP_P=
set UAGENT_OLLAMA_TOP_K=
set UAGENT_OLLAMA_REPEAT_PENALTY=
set UAGENT_OLLAMA_KEEP_ALIVE=
set UAGENT_OLLAMA_NUM_CTX=
set UAGENT_OLLAMA_NUM_PREDICT=

REM ==============================
REM set NVIDIA (UAGENT_PROVIDER=nvidia)
REM ==============================
REM set UAGENT_NVIDIA_API_KEY=
REM set UAGENT_NVIDIA_BASE_URL=
REM set UAGENT_NVIDIA_DEPNAME=

REM ==============================
REM 任意: Responses API（Azure/OpenAI/Bedrock）
REM ==============================
REM set UAGENT_RESPONSES=1
REM set UAGENT_REASONING=medium
REM set UAGENT_VERBOSITY=medium
set UAGENT_RESPONSES=1
set UAGENT_REASONING=最小
set UAGENT_VERBOSITY=低

REM ==============================
REM 任意のランタイム
REM ==============================
REM set UAGENT_WORKDIR=.
REM set UAGENT_LANG=ja

REM ==============================
REM Optional image / embedding settings
REM ==============================
REM (optional image / embedding settings not configured)
