# Startup model info specification

This document defines the startup `[INFO]` output for the effective provider/model settings used by uagent.

## Goals

- Show the effective main chat provider and model/deployment name at startup.
- Show configured optional model capabilities when they appear usable:
  - embedding
  - audio speech (text-to-speech)
  - audio transcribe (speech-to-text)
  - image generation
  - image analysis
- Show the resolved provider after fallback, not only the directly configured environment variable.
- Do not print secrets such as API keys, credentials, tokens, or full credential JSON.
- Do not perform network connectivity checks during startup for optional capabilities.

## Output format

Startup info lines use the existing `[INFO]` prefix.

Primary chat model:

```text
[INFO] provider = <provider>; model = <model-or-deployment>
```

Optional capabilities:

```text
[INFO] embedding = <provider>; model = <model-or-deployment>
[INFO] audio speech = <provider>; model = <model-or-deployment>
[INFO] audio transcribe = <provider>; model = <model-or-deployment>
[INFO] image generation = <provider>; model = <model-or-deployment>
[INFO] image analysis = <provider>; model = <model-or-deployment>
```

If a capability is not configured, unsupported, or missing required non-secret configuration, its line is omitted.

## General rules

- Environment variables are read after startup dotenv/envsec loading and validation.
- Provider names are normalized to lowercase for display and comparison.
- Empty environment variable values are ignored.
- Startup info must never display:
  - `*_API_KEY`
  - tokens
  - passwords
  - `UAGENT_GOOGLE_CREDENTIALS`
  - any credential JSON
- Optional capability detection is best-effort only. It checks configured environment variables and required model/deployment fields, but does not call provider APIs.
- If a provider fallback is used, the displayed provider is the resolved fallback provider.

## Main chat provider/model

The primary chat provider/model line is printed after `providers.make_client(core)` succeeds.

The displayed values are the actual values returned by client creation:

- `provider`: resolved main provider
- `depname`: resolved main model/deployment name

## OpenRouter fallback models

When all of the following are true:

- main provider is `openrouter`
- main model is `openrouter/auto`
- `UAGENT_OPENROUTER_FALLBACK_MODELS` is set

startup prints an additional line indicating that OpenRouter fallback models are enabled. The configured fallback model list may be displayed because it contains model identifiers, not secrets.

## Embedding

### Provider resolution

```text
UAGENT_EMBEDDING_PROVIDER -> UAGENT_PROVIDER
```

### Supported providers

- `openai`
- `azure`
- `bedrock`
- `openrouter`
- `ollama`
- `nvidia`

### Model/deployment resolution

Provider-specific embedding deployment variables are used:

```text
UAGENT_<PROVIDER>_EMBEDDING_DEPNAME
```

For example:

- `UAGENT_OPENAI_EMBEDDING_DEPNAME`
- `UAGENT_AZURE_EMBEDDING_DEPNAME`
- `UAGENT_OLLAMA_EMBEDDING_DEPNAME`

### Required configuration for display

- `azure`: base URL, API key, API version, and embedding deployment name must be configured.
- `openai`, `bedrock`, `openrouter`, `nvidia`: embedding API key and embedding deployment name must be configured.
- `ollama`: embedding deployment name must be configured; API key is optional.

## Audio speech

Audio speech means text-to-speech output.

### Provider resolution

```text
UAGENT_AUDIO_SPEECH_PROVIDER -> UAGENT_PROVIDER -> openai
```

### Supported providers

- `openai`
- `azure`
- `gemini`
- `vertexai`

### Model/deployment resolution

- `azure`: `UAGENT_AZURE_SPEECH_DEPNAME`
- `gemini`, `vertexai`: `UAGENT_GEMINI_SPEECH_DEPNAME`, then `UAGENT_GEMINI_MODEL`, then default `ja-JP-Neural2-B`
- `openai`: `UAGENT_OPENAI_SPEECH_DEPNAME`, then default `gpt-4o-mini-tts`

### Required configuration for display

- `azure`: Azure speech deployment name and the required Azure client settings must be present.
- `openai`: OpenAI API key must be present; the model may come from the default.
- `gemini`, `vertexai`: provider-specific Google/Gemini credentials must appear configured; the model may come from the default.

## Audio transcribe

Audio transcribe means speech-to-text input.

### Provider resolution

```text
UAGENT_AUDIO_TRANSCRIBE_PROVIDER -> UAGENT_PROVIDER -> openai
```

### Supported providers

- `openai`
- `azure`
- `gemini`
- `vertexai`

### Model/deployment resolution

- `azure`: `UAGENT_AZURE_TRANSCRIBE_DEPNAME`
- `gemini`, `vertexai`: `UAGENT_GEMINI_TRANSCRIBE_DEPNAME`, then `UAGENT_GEMINI_MODEL`, then default `gemini-1.5-flash`
- `openai`: `UAGENT_OPENAI_TRANSCRIBE_DEPNAME`, then default `gpt-4o-mini-transcribe`

### Required configuration for display

- `azure`: Azure transcribe deployment name and the required Azure client settings must be present.
- `openai`: OpenAI API key must be present; the model may come from the default.
- `gemini`, `vertexai`: provider-specific Google/Gemini credentials must appear configured; the model may come from the default.

## Image generation

### Provider resolution

```text
UAGENT_IMG_GENERATE_PROVIDER -> UAGENT_PROVIDER -> azure
```

### Supported providers

- `azure`
- `openai`
- `bedrock`
- `openrouter`
- `gemini`
- `nvidia`
- `vertexai`

### Model/deployment resolution

Image generation environment lookup is provider-specific:

```text
UAGENT_<PROVIDER>_IMG_GENERATE_DEPNAME -> UAGENT_<PROVIDER>_DEPNAME
```

For example:

- `UAGENT_OPENAI_IMG_GENERATE_DEPNAME`, then `UAGENT_OPENAI_DEPNAME`
- `UAGENT_AZURE_IMG_GENERATE_DEPNAME`, then `UAGENT_AZURE_DEPNAME`

### Required configuration for display

The resolved provider must be supported, a model/deployment name must be resolvable, and required non-secret endpoint/version fields for that provider must appear configured where applicable. API keys are required for providers that need them, but key values are never printed.

## Image analysis

### Provider resolution

```text
UAGENT_IMG_ANALYSIS_PROVIDER -> UAGENT_PROVIDER
```

There is no provider-specific hardcoded default for image analysis. If neither variable is set, no image analysis line is printed.

### Supported providers

- `openai`
- `azure`
- `gemini`
- `vertexai`
- `ollama`

### Model/deployment resolution

OpenAI/Azure/Gemini/VertexAI image analysis lookup uses image-analysis-specific variables first and then provider-generic variables.

Generic lookup pattern:

```text
UAGENT_IMG_ANALYSIS_DEPNAME -> UAGENT_<PROVIDER>_IMG_ANALYSIS_DEPNAME -> UAGENT_<PROVIDER>_DEPNAME
```

Ollama image analysis uses:

```text
UAGENT_OLLAMA_DEPNAME
```

with the tool default if applicable.

### Required configuration for display

- `azure`: image analysis model/deployment plus required Azure client settings must be present.
- `openai`: model plus OpenAI API key must be present.
- `gemini`, `vertexai`: model/default model and provider-specific credentials must appear configured.
- `ollama`: model/default model and Ollama provider configuration must appear usable.

## Audio provider split

The audio provider can be configured independently for input and output:

```text
UAGENT_AUDIO_SPEECH_PROVIDER
UAGENT_AUDIO_TRANSCRIBE_PROVIDER
```

`UAGENT_AUDIO_PROVIDER` is not used for audio provider resolution.

Examples:

```text
UAGENT_AUDIO_SPEECH_PROVIDER=openai
UAGENT_OPENAI_SPEECH_DEPNAME=gpt-4o-mini-tts

UAGENT_AUDIO_TRANSCRIBE_PROVIDER=azure
UAGENT_AZURE_TRANSCRIBE_DEPNAME=whisper
```

Expected startup output:

```text
[INFO] audio speech = openai; model = gpt-4o-mini-tts
[INFO] audio transcribe = azure; model = whisper
```

## Examples

### Main OpenAI plus OpenAI optional capabilities

Environment:

```text
UAGENT_PROVIDER=openai
UAGENT_OPENAI_DEPNAME=gpt-4.1-mini
UAGENT_OPENAI_API_KEY=...
UAGENT_OPENAI_EMBEDDING_DEPNAME=text-embedding-3-small
UAGENT_OPENAI_SPEECH_DEPNAME=gpt-4o-mini-tts
UAGENT_OPENAI_TRANSCRIBE_DEPNAME=gpt-4o-mini-transcribe
UAGENT_OPENAI_IMG_GENERATE_DEPNAME=gpt-image-1
UAGENT_OPENAI_IMG_ANALYSIS_DEPNAME=gpt-4o-mini
```

Startup output may include:

```text
[INFO] provider = openai; model = gpt-4.1-mini
[INFO] embedding = openai; model = text-embedding-3-small
[INFO] audio speech = openai; model = gpt-4o-mini-tts
[INFO] audio transcribe = openai; model = gpt-4o-mini-transcribe
[INFO] image generation = openai; model = gpt-image-1
[INFO] image analysis = openai; model = gpt-4o-mini
```

### Split audio providers

Environment:

```text
UAGENT_PROVIDER=openai
UAGENT_AUDIO_SPEECH_PROVIDER=openai
UAGENT_AUDIO_TRANSCRIBE_PROVIDER=azure
UAGENT_OPENAI_API_KEY=...
UAGENT_AZURE_BASE_URL=https://example.openai.azure.com/
UAGENT_AZURE_API_KEY=...
UAGENT_AZURE_API_VERSION=2024-05-01-preview
UAGENT_AZURE_TRANSCRIBE_DEPNAME=whisper
```

Startup output may include:

```text
[INFO] audio speech = openai; model = gpt-4o-mini-tts
[INFO] audio transcribe = azure; model = whisper
```

### Fallback provider display

Environment:

```text
UAGENT_PROVIDER=azure
UAGENT_AZURE_SPEECH_DEPNAME=tts-deployment
```

No audio-specific provider is configured, so audio speech resolves through fallback:

```text
UAGENT_AUDIO_SPEECH_PROVIDER -> UAGENT_PROVIDER
```

Startup output should show the resolved provider:

```text
[INFO] audio speech = azure; model = tts-deployment
```
