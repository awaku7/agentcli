<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Таны AI загварууд. Таны хэрэгслүүд. Таны орчин.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Бусад хэл</a></p>

---

**UAG нь локал ажиллагааг тэргүүнд тавьдаг нээлттэй эхийн AI агентын ажиллах орчин юм.** Энэ нь таны сонгосон хэлний загварыг ашигладаг хэрэгсэл, системтэй холбодог. Код, файл, хөтөч, үйлчилгээ, төхөөрөмжтэй нэгэн жигд интерфейсээр ажиллаж, нэг загвар нийлүүлэгчээс хамаарахгүй байж болно.

| **Загвараа сонгох** | **Бодит хэрэгслүүд холбох** | **Хяналтаа хадгалах** |
| :--- | :--- | :--- |
| OpenAI, Claude, Gemini, Grok, Bedrock, Ollama зэрэг үүлэн болон локал загвар | Файл, код, веб, MCP, Agent Skills, нэмэлтүүд, үүлэн үйлчилгээ, IoT | Локал гүйцэтгэл, хүний зөвшөөрөл, нэвтрэх мэдээлэл хадгалах, тохируулж болох бодлого |

> UAG нь **загвар нийлүүлэгч биш, агент гүйцэтгэх давхарга** юм. Гадаад загвар, холбогдсон үйлчилгээг дуудах эсэх нь тохиргооноос хамаарна. Локал ажиллагааг чухалчлах нь бүрэн офлайн эсвэл бүх хэрэгслийг анхнаасаа тусгаарлана гэсэн баталгаа биш.

## Хурдан эхлэх
<!-- README-SYNC:quick-start -->

**Python 3.11 эсвэл түүнээс шинэ** хувилбар хэрэгтэй. [PyPI](https://pypi.org/project/uag/)-аас UAG суулгаад харилцан үйлчлэлтэй CLI-г ажиллуулна:

~~~bash
python -m pip install --upgrade uag
uag
~~~

Эхний удаа эхлүүлэхэд тохиргооны туслах загвар нийлүүлэгчийг сонгох, нэвтрэх мэдээлэл тохируулахад тусална. Орчны хувьсагч эсвэл хамгаалалттай хадгалалт ашиглаж болно. Загвар болон хэрэгслийн нэмэлт хамаарлуудыг урьдчилан суулгахын тулд:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Дараа нь дараах хүсэлтүүдийг туршиж үзнэ үү:

~~~text
> Энэ Git репозиторт юу өөрчлөгдсөн бэ? Эрсдэлийг товч дүгнэ.
> Энэ сангийн хамгийн сүүлийн баримт бичгийг олоод шилжилтийн алхмыг тайлбарла.
> Эдгээр файлыг шалгаж товч тайлан гарга.
> :help
~~~

Шинэ хэрэглэгчид Git, виртуал орчны тайлбартай Windows суулгах гарын авлага, тохиргооны лавлахыг уншина уу: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Интерфейсүүд
<!-- README-SYNC:interfaces -->

Бүх интерфейс нэг агентын ажиллах орчин, нэг хэрэгслийн бүртгэлийг ашиглана.

| Интерфейс | Эхлүүлэх | Зориулалт |
| :--- | :--- | :--- |
| **CLI** | `uag` | Терминал ба автоматжуулалт |
| **Desktop** | `uagg` | Десктоп програмын яриа |
| **Web** | `uagw` | Хөтчийн яриа ба өрөө |
| **A2A** | `uaga` | Агент хоорондын холболт |
| **VS Code** | [Өргөтгөлийн гарын авлага](VSCODE.md) | Кодтой зэрэгцэн ажиллах |

Desktop болон Web нь `uag[core,providers,tools]` анхны суулгалтад багтаагүй нэмэлт хамаарал шаарддаг:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Web сервер эхлэхдээ FastAPI, Uvicorn суулгахыг оролдож болно. Урьдчилан суулгавал автомат суулгалтаас хамаарахгүй. Дэлгэрэнгүй: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## UAG-аар юу хийж болох вэ
<!-- README-SYNC:capabilities -->

| Боломж | UAG-ийн олгодог зүйл |
| :--- | :--- |
| **Загвараас үл хамаарах урсгал** | `UAGENT_PROVIDER`-аар үүлэн болон локал нийлүүлэгч солих; хэрэгслээ дахин бичих шаардлагагүй |
| **Код ба файл** | Репозитор үзэх, Git шалгах, lint, тест, файлтай ажиллах, хөтчийн автоматжуулалт |
| **Өргөтгөх боломжтой хэрэгсэл** | 200 гаруй хэрэгсэл, `tool_catalog` / `tool_load`-аар динамик хайлт, Python ба Rust тусгай хэрэгсэл |
| **Холбогдсон агентууд** | MCP, A2A, Claude Code-д нийцэх нэмэлтүүд, Agent Skills, дэд агентууд |
| **Удаан ажиллах даалгавар** | Автопилот, хараат бус зэрэгцээ уншилт, хуваарь, сэргээх, хадгалах сессүүд |
| **Терминалаас цааш** | Үүлэн үйлчилгээ, харилцаа холбоо, баримт бичиг, медиа, бодит цагийн дуу, IoT протоколууд |

### Нэг ажиллах орчин, олон холболт
<!-- README-SYNC:integrations -->

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

**Дэмжигдсэн загвар нийлүүлэгчдийн жишээ** доор байна. Тусгай тохиргоог орчны баримт бичгээс харна уу.

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

[ENVIRONMENT.md](ENVIRONMENT.md)

### Ур чадвар болон нэмэлтээр өргөтгөх
<!-- README-SYNC:extensions -->

UAG-ийн үндсэн кодыг өөрчлөхгүйгээр өргөтгөнө. SkillsMP эсвэл ClawHub-аас Agent Skills суулгах, MCP сервер холбох, эсвэл хэрэгсэл, ур чадвар, агент, hook агуулсан Claude Code-д нийцэх нэмэлт ачаална.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Өөрийн хэрэгсэл `TOOL_SPEC`, `run_tool()`-ыг ашиглаж болно; Rust дээрх хэрэгслийг бас дэмжинэ. Гарын авлага: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## Бодит ажлын урсгалд зориулсан
<!-- README-SYNC:workflows -->

### Контекст ба санах ой
<!-- README-SYNC:context-memory -->

Том хэрэгслийн үр дүнг загварын идэвхтэй контекстийг дүүргэхийн оронд **артефакт** болгон хадгалж болно. Агент дараа нь `artifact_read`-аар зөвхөн шаардлагатай хэсгийг авна. Сессүүд анхдагчаар SQLite-д хадгалагдаж, түүхийн хайлт болон санах ойн ил тод хяналттай.

- [Context compression](CONTEXT_COMPRESSION.mn.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Автоматжуулалт ба хамтын ажиллагаа
<!-- README-SYNC:automation -->

UAG нь хараат бус уншилтын зэрэгцээ ажиллагаа, олон агентын зохицуулалт, сесс сэргээх болон олон үе шаттай ажлын автопилотыг дэмждэг. `:auto`-гаар эхлүүлнэ; **F12** одоогийн хариуг тасалж, автопилот зогсоох хүсэлт илгээнэ.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Аюулгүй байдал ба ажиглалт
<!-- README-SYNC:security -->

Мэдрэмтгий үйлдэлд `human_ask` зөвшөөрөл шаардаж болно. Нэвтрэх мэдээллийг үйлдлийн системийн хамгаалалттай хадгалалт эсвэл шифрлэсэн файлд хадгална. Web интерфейс тохируулсан OIDC нэвтрэлт, хандалтын хяналтыг дэмждэг. OpenTelemetry мөр, хэмжүүр **сонголттой**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Эдгээр хяналтыг тохируулж болох ч **дурын хэрэгсэл sandbox-д тусгаарлагдана гэж баталгаажуулахгүй**. Найдваргүй хэрэглэгч, сүлжээнд UAG-ийг нээхээс өмнө байршуулалт болон бодлогын гарын авлагыг уншина уу.

### Хэл, төхөөрөмж ба дуу хоолой
<!-- README-SYNC:languages -->

UAG нь **38 хэлний орчин** (англи ба 37 орчуулга), сонголтот хоёр чиглэлийн дуу болон SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP, OPC UA-д зориулсан хэрэгсэлтэй.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Баримт бичиг
<!-- README-SYNC:documentation -->

Эдгээр гарын авлагаас эхэлж, дараа нь нарийвчлан судлаарай:

| Эндээс эхлэх | Дэлгэрэнгүй |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

Бүх баримт бичиг болон бусад хэлний орчуулгыг үзэж болно: [Documentation](./) · [Other languages](README.translations.md).

## Хөгжүүлэлт ба хувь нэмэр
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

**Python код** өөрчлөх pull request гаргахаас өмнө холбогдох тест, төслийн шалгалтуудыг ажиллуулна уу:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Оролцох дүрэм ба хөгжүүлэгчийн гарын авлага доор байна. Алдааны мэдээлэл, баримт бичгийн сайжруулалт, хэрэгсэл, орчуулга, тодорхой чиглэлийн pull request-ыг хүлээн авна: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Лиценз
<!-- README-SYNC:license -->

UAG дараах лицензээр түгээгдэнэ: [Apache License 2.0](../LICENSE).
