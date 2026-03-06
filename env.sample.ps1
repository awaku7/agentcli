<#
 env.sample.ps1 - minimal environment variables (sample)

 使い方:
   1) このファイルを env.ps1 等にコピーして値を埋める
   2) PowerShell で「ドットソース」実行:
        . .\env.ps1

 注意:
 - これは SAMPLE です。APIキー等を入れたらコミットしないでください。
 - OpenAI互換（互換エンドポイント含む）を使う場合は UAGENT_PROVIDER=openai を使用します。
 - OpenRouter を使う場合は UAGENT_PROVIDER=openrouter を使用します。
#>

# ==============================
# Provider 選択
# ==============================
# azure / openai / openrouter / gemini / grok / claude / nvidia
$env:UAGENT_PROVIDER = 'openai'

# ==============================
# OpenAI互換 (UAGENT_PROVIDER=openai)
# ==============================
# OpenAI互換のエンドポイントを使う場合は UAGENT_OPENAI_BASE_URL を指定
# 例: $env:UAGENT_OPENAI_BASE_URL = 'https://api.openai.com/v1'
# $env:UAGENT_OPENAI_BASE_URL = 'https://api.openai.com/v1'
$env:UAGENT_OPENAI_API_KEY = '<your-openai-api-key>'

# chat 用モデル名（互換サービスの場合も「モデル名」または「デプロイ名」をここに）
# Responses + GPT-5.4+ の軽量 tool narrowing を使いたい場合の例: gpt-5.4
$env:UAGENT_DEPNAME = 'gpt-4o'

# 任意: OpenAI/Azure Responses API を使う場合
# $env:UAGENT_RESPONSES = '1'

# ==============================
# OpenRouter (UAGENT_PROVIDER=openrouter)
# ==============================
# OpenRouter は OpenAI互換の統一APIです。
# https://openrouter.ai/
# 既定 base_url: https://openrouter.ai/api/v1
$env:UAGENT_OPENROUTER_API_KEY = '<your-openrouter-api-key>'
# $env:UAGENT_OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'
# $env:UAGENT_OPENROUTER_DEPNAME = 'gpt-4o'
# Responses + GPT-5.4+ の例:
# $env:UAGENT_OPENROUTER_DEPNAME = 'openai/gpt-5.4'
#
# OpenRouter モデルフォールバック（OpenRouter独自拡張）
# - 有効化条件: UAGENT_OPENROUTER_DEPNAME='openrouter/auto'
# - UAGENT_OPENROUTER_FALLBACK_MODELS を指定すると、リクエストに models=[...] を付与して OpenRouter 側でフォールバックします
# $env:UAGENT_OPENROUTER_DEPNAME = 'openrouter/auto'
# $env:UAGENT_OPENROUTER_FALLBACK_MODELS = 'anthropic/claude-4.5-sonnet,openai/gpt-4o,mistral/mistral-x'

# ==============================
# Azure OpenAI (UAGENT_PROVIDER=azure)
# ==============================
# $env:UAGENT_AZURE_BASE_URL    = 'https://<your-azure-openai-endpoint>'
# $env:UAGENT_AZURE_API_KEY     = '<your-azure-api-key>'
# $env:UAGENT_AZURE_API_VERSION = '2024-05-01-preview'
# $env:UAGENT_DEPNAME           = 'gpt-4o'
# Responses + GPT-5.4+ の軽量 tool narrowing を使う例:
# $env:UAGENT_DEPNAME           = 'gpt-5.4'
# $env:UAGENT_RESPONSES         = '1'

# ==============================
# Google Gemini (UAGENT_PROVIDER=gemini)
# ==============================
# $env:UAGENT_GEMINI_API_KEY = '<your-gemini-api-key>'
# $env:UAGENT_DEPNAME        = 'gemini-1.5-flash'

# ==============================
# Grok (UAGENT_PROVIDER=grok)
# ==============================
# $env:UAGENT_GROK_API_KEY = '<your-grok-api-key>'
# $env:UAGENT_DEPNAME      = 'grok-2-1212'

# ==============================
# Claude (UAGENT_PROVIDER=claude)
# ==============================
# $env:UAGENT_CLAUDE_API_KEY = '<your-claude-api-key>'
# $env:UAGENT_DEPNAME        = 'claude-3-5-sonnet-20241022'

# ==============================
# NVIDIA (UAGENT_PROVIDER=nvidia)
# ==============================
# $env:UAGENT_NVIDIA_API_KEY  = '<your-nvidia-api-key>'
# $env:UAGENT_NVIDIA_BASE_URL = 'https://integrate.api.nvidia.com/v1'
# $env:UAGENT_DEPNAME         = 'meta/llama-3.1-70b-instruct'

# ==============================
# 任意: 起動時workdir
# ==============================
# $env:UAGENT_WORKDIR = '.'

# ==============================
# 任意: 画像生成ツール (generate_image)
# ==============================
# 生成後に自動で画像を開くかどうか (1:有効(既定), 0:無効)
# $env:UAGENT_IMAGE_OPEN = '1'

# 画像生成用モデル/デプロイ名 (プロバイダ別)
# 例:
# $env:UAGENT_OPENAI_IMG_GENERATE_DEPNAME = 'gpt-image-1'
# $env:UAGENT_AZURE_IMG_GENERATE_DEPNAME  = 'dall-e-3'
