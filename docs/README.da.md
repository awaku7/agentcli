# uag — Universal AI Gateway

uag er en lokal AI-agent, der giver dig frihed til at vælge modeludbyder, brugerflade og værktøjer.

## Hurtig start

```bash
pip install uag
uag
```

Første gang guider opsætningsguiden dig gennem konfigurationen. Se [miljøvariabler](ENVIRONMENT.md) for alle indstillinger.

## Nøglefunktioner

- **24 udbydere**: OpenAI, PFN (PLaMo), Azure, Bedrock, OpenRouter, Ollama, Gemini, Vertex AI, Claude, Grok, NVIDIA, Novita, DeepSeek, Z.AI, HuggingFace, Alibaba Cloud, Moonshot, Xiaomi MiMo, LM Studio, MiniMax, Sakana AI, SAKURA AI Engine, Together AI og Vercel AI Gateway.
- **195 værktøjer** til filhåndtering, websøgning, billeder, lyd, dokumenter, IoT, MCP, A2A og udvikling.
- **111 værktøjer** er markeret som `x_parallel_safe` og kan køres parallelt.
- **4 tilgange**: CLI, GUI, Web og A2A samt en VS Code-udvidelse.
- Dynamisk indlæsning af værktøjer, Agent Skills, sessionskontinuitet og lokal drift.

## Værktøjer og IoT

uag understøtter blandt andet BACnet, Modbus TCP, OPC UA, SwitchBot, ECHONET Lite, Matter og UPnP. Værktøjer kan opdages og aktiveres under kørsel med `tool_catalog` og `tool_load`.

## Dokumentation

- [Miljøvariabler](ENVIRONMENT.md)
- [Quickstart](QUICKSTART.md)
- [Kommunikation og bitchat](COMMUNICATION.md)
- [IoT-brugsscenarier](IOT_USECASE.md)
- [Alle README-oversættelser](README.translations.md)

Skift udbyder med `UAGENT_PROVIDER`. For PFN/PLaMo bruges `UAGENT_PROVIDER=pfn` sammen med `UAGENT_PFN_API_KEY`, `UAGENT_PFN_BASE_URL` og `UAGENT_PFN_DEPNAME`.

Se [README.md](../README.md) for den komplette dokumentation på engelsk.
