<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (орон нутгийн AI агент)

uag бол **команд ажиллуулах**, **файл удирдах**, мөн PDF, PPTX, Excel зэрэг **өгөгдлийн файлуудыг унших** боломжтой орон нутгийн интерактив агент юм. Энэ нь CLI, GUI, Web гэсэн гурван интерфэйстэй.
uag нь **нэг нийлүүлэгчид түгжигдэхээс** зайлсхийхэд туслахаар бүтээгдсэн: өөрт тохирох интерфэйсийг сонгож, нийлүүлэгчээ сольж, орчноо өөрийн хяналтад байлгаарай.
GitHub: https://github.com/awaku7/agentcli

## Суулгах

PyPI-ээс pip ашиглан суулгаарай:

```bash
pip install uag
```

Хэрэв та virtual environment ашиглаж байгаа бол эхлээд түүнийг идэвхжүүлээд дээрх командыг ажиллуулна уу.

Анхны эхлүүлэлт дээр шаардлагатай нийлүүлэгчийн хувьсагчид байхгүй бол `uag` setup wizard-ийг автоматаар эхлүүлнэ. Тохиргооны дэлгэрэнгүйг [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)-ээс үзнэ үү.

## Гол боломжууд

- **Ашигтай хэрэгслүүдийн багц**: файл өөрчлөлт, вэб хайлт, PDF/PPTX/Excel задлал, зураг үүсгэлт, зураг шинжилгээ.
- **Олон нийлүүлэгчийн дэмжлэг**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / Moonshot AI.
- **Гурван интерфэйс**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **A2A сервер**: `uaga` / `python -m uagent.a2a.server`
- **MCP дэмжлэг**: гаднын MCP хэрэгслийн серверүүдтэй холбогдох боломжтой.
- **Session-ийн үргэлжлэл**: модел эсвэл provider солигдсон ч контекст хадгалагдана.
- **Agent Skills зах зээл**: [SkillsMP](https://skillsmp.com) эсвэл [ClawHub](https://clawhub.ai)-аас `:skills mp_search` ашиглан нийгэмлэгийн Agent Skills-ийг үзэх, суулгах.
- **Web Inspector**: `playwright_inspector`-оор browser navigation, DOM snapshot, screenshot хадгална.
- **Дагалдах docs**: `uag docs`-оор bundled docs уншиж болно.
- **Хэрэгслийн каталог (Шинэ!)**: Хэрэгслийг динамикаар олж, ачаална уу `tool_catalog`/`tool_load`. Дэмжигдсэн бүх үйлчилгээ үзүүлэгч дээр ажилладаг - үйлдвэрлэгчийн тусгай API шаардлагагүй.
- **IoT device support**: Control SwitchBot, ECHONET Lite, Matter, and UPnP devices. See [IOT_USECASE.md](IOT_USECASE.md).


## IoT Device Support

Control smart home and IoT devices through multiple interfaces:

- **SwitchBot Cloud**: List, control, and batch-operate SwitchBot devices (TV, air conditioner, lights, etc.).
  - Infrared remote devices (on/off, brightness, temperature)
  - Air conditioner mode and fan speed control
  - Batch execution of multiple commands
- **SwitchBot BLE**: Scan and control nearby SwitchBot BLE devices.
- **ECHONET Lite**: Discover and control ECHONET Lite home appliances over the local network.
- **Matter**: Inspect Matter controller/bridge/device structure (read-only).
- **UPnP**: Discover UPnP devices and manage IGD port forwarding.

For detailed usage, see [IOT_USECASE.md](IOT_USECASE.md).

## Ашиглах

### Эхлүүлэх ба гарах

Терминал дээр `uag` ажиллуулаад эхлүүлнэ. Гарахын тулд `:exit` гэж бичнэ.

For all command-line options, see [USAGE.md](USAGE.md).

### A2A сервер

Agent2Agent-тэй нийцтэй HTTP сервер эхлүүлнэ:

```bash
uaga
```

`UAGENT_A2A_*` тохиргоонууд — auth, host, port, reload, public base URL, concurrency, engine зэрэг —-ийн талаар [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)-ээс үзнэ үү.

### Тустай зөвлөмжүүд

- `:tools`: ачаалагдсан хэрэгслүүдийг харуулна
- `:logs [n]`: сүүлийн session log-уудыг харуулна
- `:load <index>`: өмнөх session-ийг ачаална
- `:skills`: Agent Skills сонгох, ачаалах (`:skills mp_search` ашиглан [SkillsMP](https://skillsmp.com) эсвэл [ClawHub](https://clawhub.ai) зах зээлээр үзэх)
- `:shrink [n]`: history-г товчилж, сүүлийн `n` мессежийг үлдээнэ
- Small LLM tips: see [SLM_TIPS.md](SLM_TIPS.md).

## Тохиргоо ба дэлгэрэнгүй

### Орчны хувьсагч ба тохиргоо

API key-үүд, language settings (`UAGENT_LANG`), history shrink settings болон бусад зүйлсийн талаар [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)-ээс үзнэ үү.

- **Setup wizard**: `python -m uagent.setup_cli`
- **Encrypted environment**: `.env`-ийг `.env.sec` болгон encrypt хийхдээ `uag_envsec` ашиглана
- **Encrypted values update**: `uag_envsec add --file .env.sec --key NAME --value VALUE`

### Responses API-ийн тэмдэглэл

Хэрэв `UAGENT_RESPONSES=1`-ийг тохируулбал OpenAI / Azure / Bedrock / OpenRouter / Ollama-д Responses API ашиглана.
Gemini / Claude / Vertex AI нь өөрсдийн native API path-аа ашигладаг бөгөөд Responses API-д хамаарахгүй.
Image analysis-д зориулсан Responses API одоогоор зөвхөн OpenAI / Azure / Bedrock / OpenRouter дээр хязгаарлагдана.
Бусад provider-үүдийн хувьд uag нь provider-specific эсвэл chat-completions path руу буцна.

### Developer docs ба орчуулгууд

- **Developer docs**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Add locales**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **Other README translations**: [`docs/README.translations.md`](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)
