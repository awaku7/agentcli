<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Mga AI model mo. Mga tool mo. Sarili mong environment.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Iba pang wika</a></p>

---

**Ang UAG ay isang open-source na AI agent runtime na inuuna ang lokal na pagpapatakbo.** Ikinokonekta nito ang pinili mong language model sa mga tool at system na ginagamit mo. Maaari kang gumawa sa code, file, browser, serbisyo, at device sa iisang interface nang hindi nakatali sa iisang model provider.

| **Piliin ang modelo** | **Ikonekta ang mga tool** | **Panatilihin ang kontrol** |
| :--- | :--- | :--- |
| Hosted at lokal na model gaya ng OpenAI, Claude, Gemini, Grok, Bedrock, at Ollama | Mga file, code, web, MCP, Agent Skills, plugins, cloud at IoT | Lokal na pagpapatakbo, kumpirmasyon ng tao, pag-iimbak ng credential, at nako-configure na patakaran |

> Ang UAG ay **agent execution layer, hindi model provider**. Depende sa configuration ang mga tawag sa panlabas na modelo at konektadong serbisyo. Hindi awtomatikong ganap na offline o nakahiwalay ang lahat ng tool dahil lang local-first ito.

## Mabilis na pagsisimula
<!-- README-SYNC:quick-start -->

Kailangan ng **Python 3.11 o mas bago**. I-install ang UAG mula sa [PyPI](https://pypi.org/project/uag/) at simulan ang interactive CLI:

~~~bash
python -m pip install --upgrade uag
uag
~~~

Sa unang paglunsad, tutulungan ka ng setup wizard na pumili ng provider at magtakda ng credential. Maaari ring gumamit ng environment variables o credential store. Para ma-install nang mas maaga ang karagdagang dependency ng provider at tool:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Subukan ang mga sumusunod na utos:

~~~text
> Ano ang nagbago sa Git repository na ito? Ibuod ang mga panganib.
> Hanapin ang pinakabagong dokumentasyon ng library na ito at ipaliwanag ang migration.
> Suriin ang mga file na ito at gumawa ng maikling ulat.
> :help
~~~

Kung bago ka sa UAG, basahin ang Windows installation guide kasama ang Git at virtual environments, at ang configuration reference: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Mga interface
<!-- README-SYNC:interfaces -->

Iisang agent runtime at tool registry ang ginagamit sa lahat ng interface.

| Interface | Simulan gamit | Para saan |
| :--- | :--- | :--- |
| **CLI** | `uag` | Terminal at automation |
| **Desktop** | `uagg` | Mga pag-uusap sa desktop app |
| **Web** | `uagw` | Mga pag-uusap at kuwarto sa browser |
| **A2A** | `uaga` | Ugnayan ng mga agent |
| **VS Code** | [Gabay sa extension](VSCODE.md) | Paggawa katabi ng code |

Kailangan ng Desktop at Web ng karagdagang dependency na hindi kasama sa `uag[core,providers,tools]`:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Maaaring subukan ng Web server na i-install ang FastAPI at Uvicorn sa paglunsad. Ang maagang pag-install ay umiiwas sa runtime auto-install. Tingnan ang: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## Ano ang magagawa sa UAG
<!-- README-SYNC:capabilities -->

| Kakayahan | Iniaalok ng UAG |
| :--- | :--- |
| **Workflow na hindi nakatali sa modelo** | Magpalit ng hosted o lokal na provider gamit ang `UAGENT_PROVIDER` nang hindi binabago ang mga tool |
| **Code at file** | Pag-navigate sa repository, pagsuri ng Git, lint, tests, file operations at browser automation |
| **Napapalawak na tool** | Higit 200 tool, dynamic discovery gamit ang `tool_catalog` / `tool_load`, custom Python at Rust tool |
| **Magkakaugnay na agent** | MCP, A2A, plugins na compatible sa Claude Code, Agent Skills at sub-agents |
| **Mahahabang gawain** | Autopilot, parallel na hiwalay na read operations, schedule, recovery at persistent sessions |
| **Lampas sa terminal** | Cloud, communications, dokumento, media, real-time voice at sinusuportahang IoT protocols |

### Isang runtime, maraming integrasyon
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

**Mga halimbawa ng sinusuportahang model provider** ay nakalista sa ibaba. Nasa environment guide ang mga partikular na setting.

### Pag-customize gamit ang skills at plugins
<!-- README-SYNC:extensions -->

Palawakin ang UAG nang hindi binabago ang core. Mag-install ng Agent Skills mula sa SkillsMP o ClawHub, kumonekta sa MCP servers, o mag-load ng plugins na compatible sa Claude Code na may tools, skills, agents at hooks.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Maaaring magbigay ang custom tools ng `TOOL_SPEC` at `run_tool()`; sinusuportahan din ang Rust-based tools. Mga gabay: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## Para sa tunay na daloy ng trabaho
<!-- README-SYNC:workflows -->

### Konteksto at memorya
<!-- README-SYNC:context-memory -->

Maaaring itago ang malalaking tool result bilang **artifacts** sa halip na punuin ang aktibong model context. Mababasa kalaunan ang kinakailangang bahagi gamit ang `artifact_read`. Sa SQLite iniimbak ang sessions bilang default, na may history search at tahasang memory review.

- [Context compression](CONTEXT_COMPRESSION.fil.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Automation at pagtutulungan
<!-- README-SYNC:automation -->

Sinusuportahan ng UAG ang magkakasabay na hiwalay na read operation, multi-agent coordination, session recovery at autopilot para sa maraming round ng trabaho. Simulan gamit ang `:auto`; pindutin ang **F12** para ihinto ang kasalukuyang sagot at hilinging tumigil ang autopilot.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Seguridad at observability
<!-- README-SYNC:security -->

Maaaring mangailangan ang sensitibong operasyon ng kumpirmasyon sa `human_ask`. Ang credentials ay maaaring itago sa secure storage ng operating system o encrypted file. Sinusuportahan ng Web interface ang naka-configure na OIDC sign-in at access controls. **Opsyonal** ang OpenTelemetry tracing at metrics.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Nako-configure ang mga kontrol na ito ngunit **hindi garantisadong** naka-sandbox ang anumang tool execution. Basahin ang deployment at policy guides bago buksan ang UAG sa hindi pinagkakatiwalaang user o network.

### Mga wika, device, at boses
<!-- README-SYNC:languages -->

May resources ang UAG para sa **38 locales** (English at 37 pagsasalin), opsyonal na full-duplex voice integration, at mga tool para sa SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP at OPC UA.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Dokumentasyon
<!-- README-SYNC:documentation -->

Magsimula sa mga gabay na ito at basahin ang mga mas detalyadong paksa:

| Magsimula rito | Mas detalyado |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

Maaari ring tingnan ang buong dokumentasyon at ibang wika: [Documentation](./) · [Other languages](README.translations.md).

## Pag-develop at kontribusyon
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

Bago magsumite ng pull request na nagbabago ng **Python code**, patakbuhin ang nauugnay na tests at project checks:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Nasa ibaba ang contribution rules at developer guide. Malugod na tinatanggap ang bug reports, documentation improvements, tools, pagsasalin at nakatutok na pull requests: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Lisensya
<!-- README-SYNC:license -->

Ibinabahagi ang UAG sa ilalim ng lisensyang: [Apache License 2.0](../LICENSE).
