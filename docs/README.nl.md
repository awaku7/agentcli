<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Universele AI-gateway</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Your environment, your freedom.
</p>

<p align="center">
  File ops / Web search / Image generation &amp; analysis / PDF &amp; Excel extraction / IoT control / MCP integration<br>
  15+ providers / 3 UIs / Parallel tool execution / Agent Skills marketplace
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

---

## Waarom uag?

**Ontsnap aan de afhankelijkheid van een bepaalde leverancier.** De meeste AI-assistenten binden u aan een specifieke provider of cloudservice. uag is anders.

- **Wordt lokaal uitgevoerd** op uw computer. Uw gegevens blijven bij u (behalve API-aanroepen die u doet).
- **Providervrijheid**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 15+ providers, allemaal toegankelijk via één enkele interface. Wissel ertussen door de omgevingsvariabelen opnieuw te configureren: geen herinstallatie, geen migratie.
- **131 tools**: bestands-I/O, zoeken op internet, genereren van afbeeldingen, Gmail, scannen van BLE-apparaten, MCP-serverintegratie — **76 zijn parallel veilig** (maximaal 8 worden gelijktijdig uitgevoerd via threadpool, configureerbaar via `UAGENT_PARALLEL_WORKERS`). Wanneer de LLM meerdere tooloproepen tegelijk afvuurt, parallelliseert uag deze automatisch.
- **3 UI's + A2A**: CLI-, GUI-, web- en agent-naar-agent-protocol. Dezelfde engine, elke interface.
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

## Functies

### 🧠 Architectuur met meerdere providers

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI (Fugu)**

Alle providers delen dezelfde toolset en interface. Schakel over door `UAGENT_PROVIDER` in te stellen - geen codewijzigingen, geen afzonderlijke installaties.

### ⚡ Parallelle gereedschapsuitvoering

Wanneer de LLM meerdere tools tegelijkertijd aanvraagt, parallelliseert uag deze automatisch.
76 tools zijn gemarkeerd als `x_parallel_safe` en worden gelijktijdig uitgevoerd via een `ThreadPoolExecutor` (standaard 8 threads; stel `UAGENT_PARALLEL_WORKERS` in op wijzigen).

**Voorbeeld**: Vraag "Check het weer in de Scandinavische hoofdsteden" → LLM activeert `search_web` × 5 landen → alle 5 zoekopdrachten worden parallel uitgevoerd → resultaten verzameld in één batch.

Alleen-lezen tools (zoeken naar bestanden, hash-berekening, directorylijst, vertaling, DB-query's, enz.) worden op agressieve wijze geparallelliseerd.

### 🔄 Sessiecontinuïteit

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 131 Gereedschap

| Categorie | Gereedschap |
|---|---|
| **Bestandsbewerkingen** | lezen/schrijven/maken/verwijderen/zoeken/grep/hash/zip, parse_eml (.eml-bestanden) |
| **Web** | fetch_url, zoek_web, screenshot, browser_playwright |
| **Media** | genereer_afbeelding, analyseer_afbeelding, img2img, audio_speech, audio_transcribe |
| **Documenten** | PDF/PPTX/DOCX/RTF/ODT-extractie, gestructureerde extractie in Excel |
| **Communicatie** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook — zie [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP |
| **Ontwikkeltools** | git_ops, python_compile, lint_format, run_tests, db_query, **13 broncode-navigators (idx-familie)** |
| **MCP** | Verbinding maken met externe MCP-servers, tools weergeven, uitvoeren |
| **A2A** | Agent-tot-agent-communicatie (met andere uag-instanties of A2A-compatibele servers) |
| **Systeem** | env vars, systeemspecificaties, tijd, datumberekening |
| **Bronnavigatie** | **13 idx-tools** voor Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL — verkrijg een functie/klasse-index of specifieke definitie zonder het hele bestand te lezen |

### 🖥 4 interfaces + VS-code-extensie

| Modus | Commando | Doel |
|---|---|---|
| **CLI** | `ug` | Snelle terminalgebaseerde bediening |
| **GUI** | `uagg` | Desktop-UI via tkinter |
| **Web** | `uagw` | Browsergebaseerde toegang |
| **A2A-server** | `uaga` | Agent2Agent-protocol voor communicatie met meerdere agenten |
| **VS-code** | — | [Extensie](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) met chatpaneel, uitleg, refactor, fout repareren en boomstructuurweergave van tools |

Zie [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) voor details over de VS Code-extensie: installatie, opdrachten, sneltoetsen en configuratie.

### 🏠 IoT-apparaatbeheer

- **SwitchBot**: Cloud batchcontrole en BLE-scan/controle
- **ECHONET Lite**: Ontdek en bedien huishoudelijke apparaten (AC, verlichting, boilers, enz.) op een lokaal netwerk
- **Kwestie**: alleen-lezen-inspectie van controller/bridge/apparaattopologie
- **UPnP**: apparaatdetectie en IGD-poort doorsturen

Zie [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 Marktplaats voor agentenvaardigheden

`:skills mp_search` om door [SkillsMP](https://skillsmp.com) en [ClawHub](https://clawhub.ai) te bladeren voor communityvaardigheden.
Installeer en breid de mogelijkheden van uag direct uit.

### 🤖 Automatische piloot (`:auto`)

uag kan **autonoom een ​​doel nastreven in meerdere LLM-rondes**. Perfect voor complexe taken die uit meerdere stappen bestaan ​​en die iteratieve verfijning vereisen.

- **Hoe het werkt**: elke ronde heeft een hoofdvraag (Stap A), gevolgd door een oordeel van de recensent (Stap B) die beslist: "VOLTOOID of DOORGAAN?"
- **Dezelfde provider, dezelfde API**: het oordeel van de recensent gebruikt hetzelfde codepad als de hoofdquery, inclusief ondersteuning voor de Responses API.
- **Afzonderlijke jury LLM** (optioneel): Stel `UAGENT_AP_PROVIDER` in om een ​​andere provider/model te gebruiken voor de recensent (gebruik bijvoorbeeld een goedkoper model voor jurering).
- **Op elk gewenst moment afsluiten**: druk op de `x`-toets om onmiddellijk te stoppen, zelfs halverwege de reactie. Of laat de reviewer beslissen wanneer het doel bereikt is.
- **Configureerbaar**: `--max-rondes N` om het budget te controleren.

Zie [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md) voor volledige documentatie.

### 🧩 Batchstatusmanager

uag kan de voortgang van langlopende taken met meerdere bestanden volgen. Wanneer de LLM tientallen bestanden verwerkt, bewaart `batch_state` de lijst met openstaande, voltooide en mislukte bestanden op schijf. Als de sessie eindigt of er een time-out optreedt in een ronde, wordt de volgende run hervat vanaf het punt waar deze was gestopt. Er gaat niets verloren.

### 🛡 Mens-in-de-loop

Met `human_ask` kan de LLM pauzeren en om uw bevestiging vragen voordat destructieve bewerkingen worden uitgevoerd (verwijderen van bestanden, overschrijven, shell-opdrachten). Jij behoudt de controle.

### 🛑 Onderbreken (c-toets / Stop-knop)

Stop het genereren van LLM-reacties op elk gewenst moment en injecteer een stopcommando terug naar de LLM.

| Interface | Hoe te onderbreken |
|---|---|
| **CLI** | Druk op de `c`-toets tijdens LLM-streaming - het huidige antwoord stopt en `"Stop"` wordt verzonden als een gebruikersbericht, zodat de LLM dienovereenkomstig reageert |
| **WEBUI** | Klik op de rode **■ Stop**-knop (verschijnt automatisch tijdens LLM-verwerking) |
| **Bureaublad-GUI** | Klik op de rode **■** knop (verschijnt automatisch tijdens LLM-verwerking) |

De interrupt werkt als een "prompt injectie": in plaats van alleen maar af te breken, stuurt hij "Stop" terug naar de LLM als een gebruikersbericht, waardoor deze de onderbreking netjes kan beëindigen of bevestigen.

Druk op de `x`-toets om de automatische pilootmodus te verlaten (zie [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md)).

### 🕵️ Browserautomatisering en webinspecteur

Twee complementaire, op Toneelschrijvers gebaseerde tools:

- **browser_playwright**: automatiseer echte browsersessies: navigeer, klik, vul formulieren in, extraheer gegevens, beheer stromen van meerdere pagina's. Werkt zonder of met hoofd.
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
- **Responses API**: Stel `UAGENT_RESPONSES=1` in voor de Responses API-modus (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Automatisch ingeschakeld voor Sakana AI (Fugu).
- **Ontwikkelaarsdocumentatie**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Kleine LLM-tips**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Projectfilosofie

uag streeft ernaar **uw AI te zijn, op uw machine, op uw voorwaarden.**

- Geen SaaS-afhankelijkheid — draait lokaal
- Geen provider-lock-in: u kunt op elk gewenst moment overstappen
- Geen UI-lock-in - CLI / GUI / Web / A2A
- Geen functievergrendeling - breid uit met tools en vaardigheden

Een gratis AI-agentervaring, vrij van leveranciersafhankelijkheid.
