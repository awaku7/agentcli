<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag-logo" width="720">
</p>

<h1 align="center">uag — Universele AI-gateway</h1>

<p align="center">
  <b>U</b>universele <b>A</b>I <b>G</b>ateway — Jouw omgeving, jouw vrijheid.
</p>

<p align="center">
  Bestandsbeheer / Zoeken op internet / Genereren en analyseren van afbeeldingen / PDF- en Excel-extractie / IoT-controle / MCP-integratie<br>
  15+ providers / 3 UI's / Parallelle tool-uitvoering / Agent Skills-marktplaats
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Lees dit in jouw taal</a>
</p>

---

## Waarom uag?

**Ontsnap aan de afhankelijkheid van een bepaalde leverancier.** De meeste AI-assistenten binden u aan een specifieke provider of cloudservice. ug is anders.

- **Wordt lokaal uitgevoerd** op uw computer. Uw gegevens blijven bij u (behalve API-aanroepen die u doet).
- **Providervrijheid**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock... 15+ providers, allemaal toegankelijk via één enkele interface. Wissel ertussen door de omgevingsvariabelen opnieuw te configureren: geen herinstallatie, geen migratie.
- **131 tools**: bestands-I/O, zoeken op internet, het genereren van afbeeldingen, scannen van BLE-apparaten, MCP-serverintegratie — en **76 zijn parallel-safe (max 4 tegelijk)**. Wanneer de LLM meerdere tooloproepen tegelijk afvuurt, voert uag deze automatisch uit via een threadpool.
- **4 UI's + A2A**: CLI-, GUI-, web- en agent-naar-agent-protocol. Dezelfde engine, elke interface.
- **IoT ready**: SwitchBot, ECHONET Lite, Matter, UPnP — bedien uw apparaten thuis via AI.
- **Agentvaardigheden**: installeer door de community ontwikkelde vaardigheden van de marktplaats. Breid uag eindeloos uit.

uag is **uw AI-assistent op uw voorwaarden**. Niet gebonden aan een provider, niet gebonden aan een interface, niet gebonden aan een platform.

## Snelle start

```bash
pip install uag
uag
```

Bij de eerste keer opstarten leidt de installatiewizard u door de providerconfiguratie.
Zie [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) voor alle omgevingsvariabelen.

## Kenmerken

### 🧠 Architectuur met meerdere providers

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI (Fugu)**

Alle providers delen dezelfde toolset en interface. Schakel over door `UAGENT_PROVIDER` in te stellen - geen codewijzigingen, geen afzonderlijke installaties.

### ⚡ Parallelle gereedschapsuitvoering

Wanneer de LLM meerdere tools tegelijkertijd aanvraagt, parallelliseert uag deze automatisch.
76 tools zijn gemarkeerd als `x_parallel_safe` en worden gelijktijdig uitgevoerd via een 4-thread `ThreadPoolExecutor`.

**Voorbeeld**: Vraag "Check het weer in de Scandinavische hoofdsteden" → LLM activeert `search_web` × 5 landen → alle 5 zoekopdrachten worden parallel uitgevoerd → resultaten verzameld in één batch.

Alleen-lezen tools (zoeken naar bestanden, hash-berekening, directorylijst, vertaling, DB-query's, enz.) worden agressief geparallelliseerd.

### 🔄 Sessiecontinuïteit

- **Wissel halverwege de sessie van provider** met `UAGENT_PROVIDER` — de gespreksgeschiedenis blijft behouden.
- **Herlaad eerdere sessies** met `:load <index>` — ga verder waar je was gebleven.
- **Cache van gereedschapsresultaten** voorkomt redundante heruitvoering wanneer dezelfde tooloproep wordt herhaald.

### 🛠 131 Gereedschap

| Categorie | Gereedschap |
|---|---|
| **Bestandsbewerkingen** | lezen/schrijven/maken/verwijderen/zoeken/grep/hash/zip |
| **Web** | fetch_url, zoek_web, screenshot, browser_playwright |
| **Media** | genereer_afbeelding, analyseer_afbeelding, img2img, audio_speech, audio_transcribe |
| **Documenten** | PDF/PPTX/DOCX/RTF/ODT-extractie, gestructureerde extractie in Excel |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP |
| **Ontwikkeltools**, ****13 idx-tools** (Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL) — krijg een functie/klasse-index of specifieke definitie zonder het hele bestand te lezen** | git_ops, python_compile, lint_format, run_tests, db_query, ****13 idx-tools** (Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL) — krijg een functie/klasse-index of specifieke definitie zonder het hele bestand te lezen** |
| **MCP** | Verbinding maken met externe MCP-servers, tools weergeven, uitvoeren |
| **A2A** | Agent-tot-agent-communicatie (met andere uag-instanties of A2A-compatibele servers) |
| **Bronnavigatie** | **13 idx-tools** (Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL) — krijg een functie/klasse-index of specifieke definitie zonder het hele bestand te lezen |
| **Systeem** | env vars, systeemspecificaties, tijd, datumberekening |

### 🖥 3 interfaces + A2A + VS Code

| Modus | Commando | Doel |
|---|---|---|
| **CLI** | `uag` | Snelle terminalgebaseerde bediening |
| **GUI** | `uagg` | Desktop-UI via tkinter |
| **Web** | `uagw` | Browsergebaseerde toegang |
| **A2A-server** | `uaga` | Agent2Agent-protocol voor communicatie met meerdere agenten |
| **VS Code** | — | Extension (Chat Panel, Explain, Refactor, Fix Error, Tools Tree View) — see [VSCODE.md](VSCODE.md) |

### 🏠 IoT-apparaatbeheer

- **SwitchBot**: Cloud batchcontrole en BLE-scan/controle
- **ECHONET Lite**: Ontdek en bedien huishoudelijke apparaten (AC, verlichting, boilers, enz.) op een lokaal netwerk
- **Kwestie**: alleen-lezen-inspectie van controller/bridge/apparaattopologie
- **UPnP**: apparaatdetectie en IGD-poort doorsturen

Zie [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 Marktplaats voor agentenvaardigheden

`:skills mp_search` om door [SkillsMP](https://skillsmp.com) en [ClawHub](https://clawhub.ai) te bladeren voor communityvaardigheden.
Installeer en breid de mogelijkheden van uag direct uit.

### 🧩 Batchstatusmanager

uag kan de voortgang van langlopende taken met meerdere bestanden volgen. Wanneer de LLM tientallen bestanden verwerkt, bewaart `batch_state` de lijst met openstaande, voltooide en mislukte bestanden op schijf. Als de sessie eindigt of er een time-out optreedt in een ronde, wordt de volgende run hervat vanaf het punt waar deze was gestopt. Er gaat niets verloren.

### 🛡 Mens-in-de-loop

Met `human_ask` kan de LLM pauzeren en om uw bevestiging vragen voordat destructieve bewerkingen worden uitgevoerd (verwijderen van bestanden, overschrijven, shell-opdrachten). Jij behoudt de controle.

### 🛑 Interrupt (c-key / Stop button)

Stop LLM response generation at any time and inject a stop command back to the LLM.

| Interface | How to interrupt |
|---|---|
| **CLI** | Press `c` key during LLM streaming -- the current response stops, and `"Stop"` is sent as a user message so the LLM responds accordingly |
| **WEB UI** | Click the red **■ Stop** button (appears automatically during LLM processing) |
| **Desktop GUI** | Click the red **■** button (appears automatically during LLM processing) |

The interrupt works as "prompt injection": instead of just aborting, it feeds `"Stop"` back to the LLM as a user message, allowing it to gracefully conclude or acknowledge the interruption.

Press `x` key to exit auto-pilot mode (see `:auto` command).

### 🕵️ Browserautomatisering en webinspecteur

Twee complementaire, op Toneelschrijvers gebaseerde tools:

- **browser_playwright**: automatiseer echte browsersessies: navigeer, klik, vul formulieren in, extraheer gegevens, beheer stromen van meerdere pagina's. Werkt zonder hoofd of zonder hoofd.
- **playwright_inspector**: neem browserovergangen op, maak bij elke stap DOM-snapshots en schermafbeeldingen. Handig voor het debuggen van webinteracties of het controleren van paginawijzigingen in de loop van de tijd.

### 🔄 Dynamisch gereedschap laden

Met `tool_catalog` en `tool_load` kunt u tools tijdens runtime ontdekken en inschakelen.
U hoeft niet alles te laden bij het opstarten; activeer alleen wat u nodig heeft, wanneer u het nodig heeft.

### 🌐 i18n / L10n

日本語 / Engels / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / en meer.
Stel `UAGENT_LANG` in om te schakelen. Zie [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) om een ​​nieuwe landinstelling toe te voegen.

Vertalingen van deze README zijn beschikbaar in [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Gecodeerde omgevingsvariabelen

Bewaar API-sleutels en geheimen in `.env.sec` — een gecodeerd `.env`-bestand.
Beheer met `uag_envsec`.

## Configuratie en details

- **Omgevingsvariabelen**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **Installatiewizard**: `python -m uagent.setup_cli`
- **Gecodeerde env**: `uag_envsec` — versleutel `.env` als `.env.sec`
- **Responses API**: Stel `UAGENT_RESPONSES=1` in voor de Responses API-modus (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI)
- **Ontwikkelaarsdocumentatie**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Kleine LLM-tips**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Projectfilosofie

uag streeft ernaar **uw AI te zijn, op uw machine, op uw voorwaarden.**

- Geen SaaS-afhankelijkheid — draait lokaal
- Geen provider-lock-in: u kunt op elk gewenst moment overstappen
- Geen UI-lock-in - CLI / GUI / Web / A2A
- Geen functievergrendeling - breid uit met tools en vaardigheden

Een gratis AI-agentervaring, vrij van leveranciersafhankelijkheid.