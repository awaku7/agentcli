<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  Нэг локал агент. Ямар ч загвар. Ямар ч хэрэгсэл. Таны орчин, таны дүрэм.
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI status"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI version"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="https://github.com/awaku7/agentcli/blob/main/LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="PyPI Downloads"></a>
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a> ·
  <a href="https://pypi.org/project/uag/">PyPI</a> ·
  <a href="https://github.com/awaku7/agentcli/discussions">Хэлэлцүүлэг</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Орчуулгууд</a>
</p>

______________________________________________________________________

**Яагаад uag гэж?**

uag нь таны илүүд үздэг загварыг бодитоор ашигладаг хэрэгслүүдтэй тань холбодог, локалыг эрхэмлэдэг AI агент юм.
Энэ нь файл, хөтөч, кодын сан, харилцаа холбоо, cloud API, IoT төхөөрөмж, MCP сервер болон
олон агентын ажлын урсгалд зориулсан нэгэн төрлийн, өргөтгөх боломжтой ажиллах орчныг өгнө.

- **Provider-ийн эрх чөлөө** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek болон бусад.
- **Локалыг эрхэмлэсэн гүйцэтгэл** — таны агентын ажиллах орчин болон хэрэгслийн гүйцэтгэл таны төхөөрөмж дээр үлдэнэ; зөвхөн таны сонгосон API дуудлагууд л гадагшилна.
- **Нэгдсэн хэрэгслийн давхарга** — ижил хэрэгслүүд CLI, desktop GUI, web UI, VS Code болон A2A-гаас ажиллана.
- **Зэрэгцээ ажиллагааг анхнаас нь дэмжинэ** — хамааралгүй, зөвхөн унших үйлдлүүд зэрэгцэн ажиллаж чадна.
- **Өргөтгөх боломжтой** — үндсэн цөмийг өөрчлөхгүйгээр хэрэгсэл, plugin, Agent Skills, MCP server болон Rust-д суурилсан хэрэгслүүд нэмнэ.
- **Аюулгүй байдлыг харгалздаг** — устгах шинжтэй үйлдэл, итгэмжлэл, төхөөрөмжийн удирдлага болон сүлжээний бичих үйлдэлд тодорхой баталгаажуулалт, бодлогын хяналт ашиглана.

> **Товчхондоо:** uag бол таны AI загварууд болон бодит орчны хоорондох удирдлагын давхарга юм.

> **🧠 Контекст мэдрэмжтэй хэрэгслийн үр дүн** — Боломжтой үед том хэмжээний хэрэгслийн үр дүнг идэвхтэй загварын контекстээс гадуур хадгалдаг. uag нь тэдгээрийг Artifacts хэлбэрээр хадгалдаг ба тогтвортой Artifact лавлагаа бүхий хязгаарлагдмал урьдчилсан харагчаар загварт дамжуулдаг. Ингэснээр хэрэгсэл их хэмжээний үр дүн гаргасан тохиолдолд дараагийн ээлжийн оролтын тэмдэгтийн тоог ихээхэн бууруулж болно.
> [Контекст шахалтын дэлгэрэнгүй гарын авлага](CONTEXT_COMPRESSION.mn.md)

## Түргэн эхлүүлэх

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

Анхны асаалтаар тохиргооны wizard нээгдэнэ. Энэ нь provider-ийг тохируулахад тусалж, сонгосон тохиргоог
таны локал орчинд хадгална.

Түгээмэл боломжуудын бүлгүүдийн хувьд:

```bash
python -m pip install "uag[core,providers,tools]"
```

> Platform integration нь сонголттой. Таны үйлдлийн системд хэрэгтэйг нь л суулгана уу;

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Интерфейсүүд

| Интерфейс | Command | Тохиромжтой хэрэглээ |
|---|---|---|
| **CLI** | `uag` | Хурдан, гараар удирдах ажил |
| **Desktop GUI** | `uagg` | Төрөлх desktop орчин |
| **Web UI** | `uagw` | Хөтөчөөр хандах |
| **A2A server** | `uaga` | Agent-to-agent харилцаа |
| **VS Code** | Extension | Editor дотор хэрэгслийг тайлбарлах, refactor хийх, засах, үзэх |

Бүх интерфейс ижил provider тохиргоо, хэрэгслийн бүртгэл, аюулгүй байдлын дүрэм болон session өгөгдлийг хуваалцана.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## Та юу бүтээж болох вэ

Provider adapter-ууд hosted болон локал ажиллах орчныг дэмжинэ. Үүнд:

- Файл унших, үүсгэх, засах, хайх, hash хийх, архивлах болон шалгах
- Git өөрчлөлтийг хянах, нууц мэдээлэл хайх, тест ажиллуулах, lint хийх, compile хийх болон coverage хэмжих
- Том Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA болон бусад кодын сангаар ажиллах
- Олон хуудаст ажлын урсгал, таталт зэрэг Playwright-тэй хөтчийн автоматжуулалт хийх

- **MCP** — OAuth-той үйлчилгээнүүдийг оролцуулан гадаад хэрэгслийн сервер холбох
- **A2A** — бусад агент болон нийцтэй серверүүдтэй уялдах
- **Cloud** — AWS, Google Cloud болон Azure API-д бичих үйлдлийн баталгаажуулалттай хандах
- **Communication** — Gmail, Bluesky, Discord, Microsoft Teams болон pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA болон UPnP
- **Media** — зураг үүсгэх/засах, аудио хөрвүүлэх/яриа, камерын зураг авалт болон QR код
- **Documents** — PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL болон log шинжилгээ

- **SwitchBot** — Cloud болон BLE илрүүлэлт, төлөв, удирдлага, багц ажиллагаа болон subscription
- **ECHONET Lite** — INF notification-ийг оролцуулан Японы гэр ахуйн төхөөрөмжийг илрүүлж удирдах
- **Matter** — endpoint, cluster, attribute, төлөвийн түүх, subscription болон удирдлага
- **BACnet / Modbus TCP / OPC UA** — үйлдвэр ба барилгын автоматжуулалтын уншилт, бичилт, үзэх болон мониторинг
- **UPnP** — төхөөрөмж илрүүлэх, WAN төлөв болон router port-mapping удирдлага

### uag хаана байрладаг вэ?

Нэг талд нь хүмүүс ба интерфейсүүд, нөгөө талд нь загвар, хэрэгсэл болон бодит ертөнцийн системүүд байрлах
хооронд uag ажиллана. Энэ нь харилцан яриаг зохицуулж, боломжуудыг сонгон, аюулгүй байдлын дүрмийг хэрэгжүүлж,
ажлын урсгалыг үргэлжлүүлэн сэргээх боломжтой байлгана.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Plugin, Agent Skills ба marketplace

Үндсэн цөмийг салаалуулахгүйгээр uag-ийг тусгай зориулалтын агент болгоно:

- **Claude Code-тэй нийцтэй plugin**-ийг directory, ZIP, Git repository, HTTP source эсвэл marketplace-ээс суулгах
- Skill, sub-agent, MCP server, hook, slash command, output style, dependency болон channel-ийг багцлах
- [SkillsMP](https://skillsmp.com) болон [ClawHub](https://clawhub.ai)-ээс community боломжуудыг үзэх
- `UAGENT_EXTERNAL_TOOLS_DIR`-ээр хувийн байгууллагын skill болон хэрэгслийг локалаар нэмэх

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

[Plugin Development Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md)-г үзнэ үү.

- Файл, вэб, медиа, баримт бичиг, код, cloud, харилцаа холбоо болон IoT-д зориулсан **200+ хэрэгсэл**
- **Динамик илрүүлэлт ба ачаалалт** — боломжуудыг олохдоо `tool_catalog`, шаардлагатай үед л идэвхжүүлэхдээ `tool_load` ашиглана
- **Кодын оюун** — `code_map`, хэл тус бүрийн `idx` navigator, Git review, тестийн гүйцэтгэл, lint, compilation болон coverage
- Skill, agent, MCP server, hook, command болон marketplace бүхий **Claude Code-тэй нийцтэй plugin**
- SkillsMP болон ClawHub-ийн **Agent Skills**
- `TOOL_SPEC` ба `run_tool()` бүхий **захиалгат Python хэрэгсэл**
- Хөнгөн native өргөтгөлд зориулсан **Rust-д суурилсан хэрэгсэл**

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Бодит ажлын урсгалд зориулан бүтээв

### 🧠 Контекст мэдрэмжтэй хэрэгслийн үр дүн

Боломжтой үед том хэмжээний хэрэгслийн үр дүнг идэвхтэй загварын контекстээс гадуур хадгалдаг. uag нь тэдгээрийг Artifacts хэлбэрээр хадгалдаг ба тогтвортой Artifact лавлагаа бүхий хязгаарлагдмал урьдчилсан харагчаар загварт дамжуулдаг. Ингэснээр хэрэгсэл их хэмжээний үр дүн гаргасан тохиолдолд дараагийн ээлжийн оролтын тэмдэгтийн тоог ихээхэн бууруулж болно.

`:load <index>` ашиглан өмнөх харилцан яриаг үргэлжлүүлнэ. Хэрэгслийн үр дүнг cache хийж болох бөгөөд
application-ийг дахин бүтээлгүйгээр provider-ийг сольж болно.

[Context compression](CONTEXT_COMPRESSION.mn.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Auto-pilot

Сонголтот reviewer model-той олон үе шаттай ажилд `:auto` ашиглана. `--max-rounds N`-ээр үеийн хязгаар тогтооно.
Auto-pilot-ийг зогсоохдоо **F12**, одоогийн хариуг зогсоохдоо **F12** дарна.

Аюулгүй үед хамааралгүй, зөвхөн унших үйлдлүүд зэрэгцэн ажиллана. Вэб хайлт, файл шалгалт,
репозиторийн шинжилгээ зэрэг ажлууд тохируулах боломжтой worker pool (`UAGENT_PARALLEL_WORKERS`)-ийн
тусламжтайгаар зэрэгцэн дуусна. Бичих үйлдлүүд цуваалсан хэвээр байх эсвэл баталгаажуулалт шаардана.

Session continuity, tool-result caching, batch state, restart recovery, DAG scheduling болон
multi-agent orchestration нь нарийн төвөгтэй ажлыг нэг удаагийн бус, үргэлжлүүлэн сэргээх боломжтой болгоно.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Хувийн, олон хэлт, бодлоготой нийцсэн

`human_ask` нь мэдрэмтгий үйлдлийн өмнө түр зогсоно. Файл устгах, дарж бичих, shell command, төхөөрөмжийн удирдлага,
credential operation болон network write-ийг баталгаажуулалт, бодлогын дүрмээр удирдаж болно.

Урт хугацааны нууцыг prompt дотор байрлуулахын оронд credential store ашиглана:

Веб UI нь Authorization Code + PKCE ашиглан OIDC нэвтрэлт, баталгаажсан ID токенууд, сервер талын сессүүд, төслийн/өрөөний хандалтын хяналтыг агуулдаг. Microsoft Entra ID бүлгийн баталгаажсан нэхэмжлэлүүд тохируулсан үед лавлах дэмжлэгтэй хандалтын бодлогыг хангаж чадна. Windows Active Directory, OAuth, trusted-proxy суулгалтууд нь тодорхой баталгаажсан таних адаптеруудыг ашиглан интеграцчилж болно; Windows AD нь суулгалт тусгай Kerberos/Negotiate баталгаажуулагч шаарддаг бөгөөд анхдагчаар идэвхжээгүй байдаг.

uag нь Agent, LLM, хэрэгсэл, Context, Memory болон мэдээлэл сэргээх үйлдлүүдэд зориулсан, сонголтоор идэвхжүүлдэг, үйлчилгээ үзүүлэгчээс үл хамаарах OpenTelemetry мөшгөлт ба хэмжүүрүүдийг агуулна. Ажиглах боломж анхдагчаар идэвхгүй.

Локал орчныг тэргүүнд тавина гэдэг нь UAG анхнаасаа бүрэн офлайн ажиллана, эсвэл бүх хэрэгсэл тусгаарлагдана гэсэн үг биш. Гадаад загвар болон холбогдсон үйлчилгээний хүсэлт тохиргооноос хамаарна.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Олон хэлний орчуулга

- `translate_text` нь `Google Translate` болон албан ёсны DeepL Python клиентийг `provider=auto`, `provider=deepl`, эсвэл `provider=google` ашиглан дэмждэг.
- Хэрэгслийн тодорхойлолтууд 37 орчуулгын хувилбар болон англи хэл дээр (нийт 38) ашиглах боломжтой бөгөөд орлуулагч болон техникийн таних тэмдэглэгээг хадгалсан.

Бүрэн дуплекс дуу хоолойг OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live болон Bedrock Nova Sonic-оор
ашиглах боломжтой. Мөн сонголтоор AEC3 цуурай даралт болон аюулгүй байдлаар хязгаарласан realtime function calling дэмжинэ.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Баримт бичиг

| Сэдэв | Баримт бичиг |
|---|---|
| Environment variables | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Architecture and invariants | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Repository tools | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| IoT use cases | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Communication tools | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Auto-pilot | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| VS Code extension | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Developer guide | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Tool flow | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## Хөгжүүлэлт ба хувь нэмэр

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

PR-ийн өмнөх шалгалтуудыг ажиллуулна:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

Хөгжүүлэлтийн бүрэн ажлын урсгалыг [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)-оос үзнэ үү.

Алдааны мэдээлэл, боломжийн санаа, баримт бичгийн сайжруулалт, орчуулга, хэрэгсэл, skill болон pull request-ийг талархан хүлээн авна.
Томоохон өөрчлөлт хийхийн өмнө issue эсвэл discussion нээнэ үү. [Developer Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)-г уншиж,
pull request илгээхээсээ өмнө дээрх шалгалтуудыг ажиллуулна уу.

## License

Licensed under the [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
