#!/usr/bin/env bash
# env.sample.sh - minimal environment variables (sample)
#
# 使い方:
#   1) このファイルを env.sh 等にコピーして値を埋める
#   2) 現在のシェルに反映するなら source 実行:
#        source ./env.sh
#
# 注意:
# - これは SAMPLE です。APIキー等を入れたらコミットしないでください。
# - OpenAI互換（互換エンドポイント含む）を使う場合は UAGENT_PROVIDER=openai を使用します。

# ==============================
# Provider 選択
# ==============================
# azure / openai / gemini / grok / claude
export UAGENT_PROVIDER="openai"

# ==============================
# OpenAI互換 (UAGENT_PROVIDER=openai)
# ==============================
# OpenAI互換のエンドポイントを使う場合は UAGENT_OPENAI_BASE_URL を指定
# 例: export UAGENT_OPENAI_BASE_URL="https://api.openai.com/v1"
# export UAGENT_OPENAI_BASE_URL="https://api.openai.com/v1"
export UAGENT_OPENAI_API_KEY="<your-openai-api-key>"

# chat 用モデル名（互換サービスの場合も「モデル名」または「デプロイ名」をここに）
export UAGENT_DEPNAME="gpt-4o"

# ==============================
# OpenRouter (UAGENT_PROVIDER=openrouter)
# ==============================
# OpenRouter は OpenAI互換の統一APIです。
# https://openrouter.ai/
# 既定 base_url: https://openrouter.ai/api/v1
export UAGENT_OPENROUTER_API_KEY="<your-openrouter-api-key>"
# export UAGENT_OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"
# export UAGENT_OPENROUTER_DEPNAME="gpt-4o"
#
# OpenRouter モデルフォールバック（OpenRouter独自拡張）
# - 有効化条件: UAGENT_OPENROUTER_DEPNAME="openrouter/auto"
# - UAGENT_OPENROUTER_FALLBACK_MODELS を指定すると、リクエストに models=[...] を付与して OpenRouter 側でフォールバックします
# export UAGENT_OPENROUTER_DEPNAME="openrouter/auto"
# export UAGENT_OPENROUTER_FALLBACK_MODELS="anthropic/claude-4.5-sonnet,openai/gpt-4o,mistral/mistral-x"

# ==============================
# Azure OpenAI (UAGENT_PROVIDER=azure)
# ==============================
# export UAGENT_AZURE_BASE_URL="https://<your-azure-openai-endpoint>"
# export UAGENT_AZURE_API_KEY="<your-azure-api-key>"
# export UAGENT_AZURE_API_VERSION="2024-05-01-preview"
# export UAGENT_DEPNAME="gpt-4o"

# ==============================
# Google Gemini (UAGENT_PROVIDER=gemini)
# ==============================
# export UAGENT_GEMINI_API_KEY="<your-gemini-api-key>"
# export UAGENT_DEPNAME="gemini-1.5-flash"

# ==============================
# Grok (UAGENT_PROVIDER=grok)
# ==============================
# export UAGENT_GROK_API_KEY="<your-grok-api-key>"
# export UAGENT_DEPNAME="grok-2-1212"

# ==============================
# Claude (UAGENT_PROVIDER=claude)
# ==============================
# export UAGENT_CLAUDE_API_KEY="<your-claude-api-key>"
# export UAGENT_DEPNAME="claude-3-5-sonnet-20241022"

# ==============================
# 任意: 起動時workdir
# ==============================
# export UAGENT_WORKDIR="."

# ==============================
# 任意: 画像生成ツール (generate_image)
# ==============================
# 生成後に自動で画像を開くかどうか (1:有効(既定), 0:無効)
# export UAGENT_IMAGE_OPEN="1"

# 画像生成用モデル/デプロイ名 (Azure/OpenAI/Gemini用)
# export UAGENT_IMAGE_DEPNAME="dall-e-3"
