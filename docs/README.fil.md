# uag — Universal AI Gateway

Ang uag ay isang lokal na AI agent na nagbibigay sa iyo ng kalayaan sa pagpili ng provider, interface, at mga tool.

## Mabilis na pagsisimula

```bash
pip install uag
uag
```

Sa unang paggamit, gagabayan ka ng setup wizard sa pag-configure ng provider. Tingnan ang [mga environment variable](ENVIRONMENT.md) para sa kumpletong listahan ng setting.

## Mahahalagang feature

- **24 provider**: OpenAI, PFN (PLaMo), Azure, Bedrock, OpenRouter, Ollama, Gemini, Vertex AI, Claude, Grok, NVIDIA, Novita, DeepSeek, Z.AI, HuggingFace, Alibaba Cloud, Moonshot, Xiaomi MiMo, LM Studio, MiniMax, Sakana AI, SAKURA AI Engine, Together AI, at Vercel AI Gateway.
- **222 tool** para sa file I/O, web search, larawan, audio, dokumento, IoT, MCP, A2A, at development.
- **Mga Cloud API**: `aws_api`, `gcp_api`, `azure_api` — AWS, Google Cloud, and Azure API operations; write operations require explicit confirmation.
- **130 tool** ang may markang `x_parallel_safe` at maaaring patakbuhin nang sabay-sabay.
- **4 na interface**: CLI, GUI, Web, at A2A, kasama ang VS Code extension.
- Dynamic tool loading, Agent Skills, session continuity, at lokal na pagpapatakbo.

## Mga tool at IoT

Sinusuportahan ng uag ang BACnet, Modbus TCP, OPC UA, SwitchBot, ECHONET Lite, Matter, at UPnP. Maaaring hanapin at i-enable ang mga tool habang tumatakbo gamit ang `tool_catalog` at `tool_load`.

## Dokumentasyon

- [Environment variables](ENVIRONMENT.md)
- [Quickstart](QUICKSTART.md)
- [Communication at bitchat](COMMUNICATION.md)
- [Mga gamit ng IoT](IOT_USECASE.md)
- [Listahan ng lahat ng README translation](README.translations.md)

Para sa PFN/PLaMo, gamitin ang `UAGENT_PROVIDER=pfn` kasama ang `UAGENT_PFN_API_KEY`, `UAGENT_PFN_BASE_URL`, at `UAGENT_PFN_DEPNAME`.

Tingnan ang [README.md](../README.md) para sa kumpletong dokumentasyon sa Ingles.
#### Pagsusuri at saklaw ng repository

- `git_review`: ibuod ang mga pagbabago sa Git, mapanganib na mga file, mga kandidato sa pagsubok, at mga lihim na natuklasan nang hindi inilalantad ang mga lihim na halaga.
- `security_scan`: i-scan ang mga file ng repositoryo para sa mga malamang na lihim at mapanganib na mga configuration file.
- `coverage_report`: run at Russript/Javat na saklaw, I-type ang JavaScript/Java para sa Go, I-type ang normalize ng Script/Java. .NET, C/C++, Ruby, PHP, Swift, at Dart/Flutter.
- Maaaring awtomatikong mai-install ang mga nawawalang dependency sa coverage kapag hiniling ang pagpapatupad; Ang `dry_run` ay hindi kailanman nag-i-install ng mga package.

Tingnan ang [Repository Analysis Tools](REPOSITORY_TOOLS.md) para sa mga parameter, output, at mga detalye ng kaligtasan.

