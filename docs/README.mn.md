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
- **Олон нийлүүлэгчийн дэмжлэг**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA.
- **Гурван интерфэйс**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **A2A сервер**: `uaga` / `python -m uagent.a2a.server`
- **MCP дэмжлэг**: гаднын MCP хэрэгслийн серверүүдтэй холбогдох боломжтой.
- **Session-ийн үргэлжлэл**: модел эсвэл provider солигдсон ч контекст хадгалагдана.
- **Web Inspector**: `playwright_inspector`-оор browser navigation, DOM snapshot, screenshot хадгална.
- **Дагалдах docs**: `uag docs`-оор bundled docs уншиж болно.

## Ашиглах

### Эхлүүлэх ба гарах

Терминал дээр `uag` ажиллуулаад эхлүүлнэ. Гарахын тулд `:exit` гэж бичнэ.

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
- `:skills`: Agent Skills-ийг сонгож ачаална
- `:shrink [n]`: history-г товчилж, сүүлийн `n` мессежийг үлдээнэ

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
- **Other README translations**: [English](https://github.com/awaku7/agentcli/blob/main/README.md) / [日本語](https://github.com/awaku7/agentcli/blob/main/docs/README.ja.md) / [Deutsch](https://github.com/awaku7/agentcli/blob/main/docs/README.de.md) / [Español](https://github.com/awaku7/agentcli/blob/main/docs/README.es.md) / [Français](https://github.com/awaku7/agentcli/blob/main/docs/README.fr.md) / [Italiano](https://github.com/awaku7/agentcli/blob/main/docs/README.it.md) / [한국어](https://github.com/awaku7/agentcli/blob/main/docs/README.ko.md) / [Português](https://github.com/awaku7/agentcli/blob/main/docs/README.pt_BR.md) / [Русский](https://github.com/awaku7/agentcli/blob/main/docs/README.ru.md) / [ไทย](https://github.com/awaku7/agentcli/blob/main/docs/README.th.md) / [简体中文](https://github.com/awaku7/agentcli/blob/main/docs/README.zh_CN.md) / [繁體中文](https://github.com/awaku7/agentcli/blob/main/docs/README.zh_TW.md) / [Polski](https://github.com/awaku7/agentcli/blob/main/docs/README.pl.md) / [Tiếng Việt](https://github.com/awaku7/agentcli/blob/main/docs/README.vi.md) / [Bahasa Indonesia](https://github.com/awaku7/agentcli/blob/main/docs/README.id.md) / [العربية](https://github.com/awaku7/agentcli/blob/main/docs/README.ar.md) / [हिन्दी](https://github.com/awaku7/agentcli/blob/main/docs/README.hi.md) / [Português](https://github.com/awaku7/agentcli/blob/main/docs/README.pt.md) / [Svenska](https://github.com/awaku7/agentcli/blob/main/docs/README.sv.md) / [Norsk bokmål](https://github.com/awaku7/agentcli/blob/main/docs/README.nb.md) / [Suomi](https://github.com/awaku7/agentcli/blob/main/docs/README.fi.md) / [Nederlands](https://github.com/awaku7/agentcli/blob/main/docs/README.nl.md) / [Čeština](https://github.com/awaku7/agentcli/blob/main/docs/README.cs.md) / [Українська](https://github.com/awaku7/agentcli/blob/main/docs/README.uk.md) / [Swahili](https://github.com/awaku7/agentcli/blob/main/docs/README.sw.md) / [Bengali](https://github.com/awaku7/agentcli/blob/main/docs/README.bn.md) / [Persian](https://github.com/awaku7/agentcli/blob/main/docs/README.fa.md) / [Mongolian](https://github.com/awaku7/agentcli/blob/main/docs/README.mn.md) / [Marathi](https://github.com/awaku7/agentcli/blob/main/docs/README.mr.md)
