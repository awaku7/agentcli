<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Universal AI Gateway</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Din miljö, din frihet.
</p>

<p align="center">
  Filoperationer / Webbsökning / Bildgenerering och analys / PDF och Excel extraktion / IoT kontroll / MCP integration<br>
  24 providers / 3 användargränssnitt / Parallell verktygsexekvering / Agent Skills marknadsplats
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

---

## Varför uag?

**Bli fria från leverantörslåsning.** De flesta AI-assistenter knyter dig till en specifik leverantör eller molntjänst. uag är annorlunda.

- **Körs lokalt** på din maskin. Din data stannar hos dig (förutom API-anrop du gör).
- **Leverantörsfrihet**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 21+ leverantörer, alla tillgängliga från ett enda gränssnitt. Byt mellan dem genom att konfigurera om miljövariabler – ingen ominstallation, ingen migrering.
- **195  verktyg**: Fil-I/O, webbsökning, bildgenerering, Gmail, BLE-enhetsskanning, MCP-serverintegrering — **111 är parallellsäkra** (upp till 8 exekveras samtidigt via trådpool, konfigurerbara via `UAGENT_PARALLEL_WORKERS`). När LLM avfyrar flera verktygsanrop samtidigt, parallelliserar uag dem automatiskt.
- **3 användargränssnitt + A2A**: CLI, GUI, webb och Agent-to-Agent-protokoll. Samma motor, vilket gränssnitt som helst.
- **Agent Skills**: Installera community-byggda färdigheter från marknadsplatsen. Förläng uag oändligt.

uag är **din AI-assistent på dina villkor**. Inte bunden till en leverantör, inte bunden till ett gränssnitt, inte bunden till en plattform.

## Snabbstart

```bash
pip install uag
uag
```

Vid första lanseringen leder installationsguiden dig genom leverantörskonfigurationen.
Se [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) för alla miljövariabler.

## Funktioner

### 🧠 Arkitektur för flera leverantörer

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

Alla leverantörer delar samma verktygsuppsättning och gränssnitt. Byt genom att ställa in "UAGENT_PROVIDER" — inga kodändringar, inga separata installationer.

### ⚡ Parallell verktygsexekvering

När LLM begär flera verktyg samtidigt, uag **parallellerar automatiskt** dem.
111 verktyg är märkta med `x_parallel_safe` och körs samtidigt via en `ThreadPoolExecutor` (8 trådar som standard; ställ in `UAGENT_PARALLEL_WORKERS` för att ändra).

**Exempel**: Fråga "Kontrollera vädret i nordiska huvudstäder" → LLM avfyrar `search_web` × 5 länder → alla 5 sökningar körs parallellt → resultat samlade i en batch.

Läsbara verktyg (filsökning, hashberäkning, kataloglistning, översättning, DB-frågor, etc.) parallelliseras aggressivt.


### 🧩 Pluginsystem (Claude Code-kompatibelt)

uagent implementerar ett **Claude Code-kompatibelt pluginsystem**. Plugins samlar färdigheter, agenter, MCP-servrar, hooks och mer i fristående kataloger med manifestet `.claude-plugin/plugin.json`.

**Komponenter som stöds**: färdigheter, underagenter, MCP-servrar, hooks (12 livscykelhändelser), snedstreckkommandon, utdatastilar, userConfig, beroenden, kanaler, marknadsplatser

**CLI commands**:
```
:plugin list                         # Lista installerade plugins
:plugin install <source> [--scope]
:plugin install <name>@<marketplace>  # Installera från marknadsplatsen
:plugin remove <name>                # Avinstallera
:plugin enable/disable <name>        # Växla
:plugin marketplace add/remove/list  # Hantera marknadsplatser
:plugin init <name>                  # Skapa ett nytt plugin-skelett
```

Se den fullständiga dokumentationen i [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md).


### 🔄 Sessionskontinuitet

- **Byt leverantör under sessionen**: `UAGENT_PROVIDER` — konversationshistoriken bevaras.
- **Ladda om tidigare sessioner**: `:load <index>` — fortsätt där du slutade.

### 🛠 195  Verktyg

| Kategori | Verktyg |
|---|---|
| **Filoperationer** | read/write/create/delete/search/grep/hash/zip, file_type, parse_eml (.eml-filer) |
| **Webb** | fetch_url, search_web, screenshot, browser_playwright |
| **Media** | generera_bild, analysera_bild, img2img, audio_tal, audio_transcribe |
| **Dokument** | PDF/PPTX/DOCX/RTF/ODT-extraktion, Excel-strukturerad extrahering |
| **Prognos** | Tidsserieprognos med 9 modeller (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, etc.), automatiskt modellval, plotgenerering, i18n |
| **Kommunikation** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook , **pybitchat** (BLE Mesh) — se [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) and [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md)|
| **IoT** | BACnet、Modbus TCP、OPC UA、SwitchBot（Cloud + BLE）、ECHONET Lite、Matter、UPnP、reverse_geocode |
| **Utvecklarverktyg** | git_ops, python_compile, lint_format, run_tests, db_query, **26 källkodsnavigatorer (idx-familjen)** |
| **MCP** | Anslut till externa MCP-servrar, lista verktyg, kör |
| **A2A** | Agent-till-agent-kommunikation (med andra uag-instanser eller A2A-kompatibla servrar) |
| **System** | env vars, systemspecifikationer, tid, datumberäkning, uuid_gen, slugify ||
| **Källnavigering** | **26 idx-verktyg** för Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL — få ett funktions-/klassindex eller specifik definition utan att läsa hela filen |

### 🖥 4 gränssnitt + VS-kodförlängning

| Läge | Kommando | Syfte |
|---|---|---|
| **CLI** | `uag` | Snabb terminalbaserad drift |
| **GUI** | `uagg` | Desktop UI via tkinter |
| **Webb** | `uagw` | Webbläsarbaserad åtkomst |
| **A2A-server** | `uaga` | Agent2Agent-protokoll för multiagentkommunikation |
| **VS-kod** | — | [Tillägg](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) med Chat Panel, Explain, Refactor, Fix Error och Tools Trädvy |

Se [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) för detaljer om VS Code-tillägget — installation, kommandon, tangentbindningar och konfiguration.

### 🏠 IoT-enhetskontroll
- **Ärende**: Skrivskyddad inspektion av styrenhet/brygga/enhetstopologi

Se [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)


### 🎯 Agent Skills Marketplace

`:skills mp_search` för att bläddra i [SkillsMP](https://skillsmp.com) och [ClawHub](https://clawhub.ai) för gemenskapskunskaper.
Installera och utöka uags kapacitet i farten.

### 🤖 Auto-pilot (`:auto`)

uag kan **autonomt sträva efter ett mål över flera LLM-omgångar**. Perfekt för komplexa, flerstegsuppgifter som behöver iterativ förfining.

- **Hur det fungerar**: Varje omgång har en huvudfråga (steg A) följt av en granskarens bedömning (steg B) som avgör "SLUTFÖR eller FORTSÄTT?"
- **Samma leverantör, samma API**: Granskarens bedömning använder den identiska kodsökvägen som huvudfrågan – inklusive Responses API-stöd.
- **Separat domare LLM** (valfritt): Ställ in "UAGENT_AP_PROVIDER" för att använda en annan leverantör/modell för granskaren (använd t.ex. en billigare modell för bedömning).
- **Avsluta när som helst**: Tryck på `x`-tangenten för att stoppa omedelbart, även mitt i svaret. Eller låt granskaren bestämma när målet är uppfyllt.
- **Konfigurerbar**: `--max-rounds N` för att styra budgeten.

Se [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) för fullständig dokumentation.

### 🧩 Batch State Manager

uag kan spåra framsteg över långvariga flerfilsuppgifter. När LLM bearbetar dussintals filer, kvarstår `batch_state` listan över väntande, slutförda och misslyckade filer till disken. Om sessionen slutar eller en omgång tar slut, återupptas nästa körning där den slutade – ingenting går förlorat.

### 🛡 Människan-i-slingan

`human_ask` låter LLM pausa och be om din bekräftelse innan du utför destruktiva operationer (filradering, överskrivningar, skalkommandon). Du behåller kontrollen.

### 🛑 Avbryt (c-knapp / stoppknapp)

Stoppa generering av LLM-svar när som helst och injicera ett stoppkommando tillbaka till LLM.

| Gränssnitt | Hur man avbryter |
|---|---|
| **CLI** | Tryck på `c`-tangenten under LLM-strömning — det aktuella svaret stoppas, och `"Stopp"` skickas som ett användarmeddelande så att LLM svarar i enlighet med detta |
| **WEB UI** | Klicka på den röda **■ Stopp**-knappen (visas automatiskt under LLM-bearbetning) |
| **GUI för skrivbord** | Klicka på den röda **■**-knappen (visas automatiskt under LLM-bearbetning) |

Avbrottet fungerar som "prompt injektion": istället för att bara avbryta, matar det "Stopp"" tillbaka till LLM som ett användarmeddelande, vilket gör det möjligt för den att på ett elegant sätt avsluta eller bekräfta avbrottet.

Tryck på `x`-tangenten för att avsluta autopilotläget (se [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Webbläsarautomation och webbinspektör

Två kompletterande dramatikerbaserade verktyg:

- **browser_playwright**: Automatisera riktiga webbläsarsessioner - navigera, klicka, fyll i formulär, extrahera data, hantera flersidiga flöden. Fungerar utan huvud eller huvud.
- **playwright_inspector**: Spela in webbläsarövergångar, fånga DOM-ögonblicksbilder och skärmdumpar vid varje steg. Användbar för att felsöka webbinteraktioner eller granska sidändringar över tid.

### 🔄 Dynamisk verktygsladdning

`tool_catalog` och `tool_load` låter dig upptäcka och aktivera verktyg vid körning.
Inget behov av att ladda allt vid start – aktivera bara det du behöver, när du behöver det.


### 🦀 Rust Native Tools

`uuid_gen` och `slugify` är implementerade i Rust (via PyO3) för bättre prestanda.

### 🌐 i18n / L10n

日本語 / Engelska / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / och mer.
Ställ in "UAGENT_LANG" för att byta. Se [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) för att lägga till ett nytt språk.

Översättningar av denna README finns i [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Krypterade miljövariabler

Lagra API-nycklar och hemligheter i `.env.sec` - en krypterad `.env`-fil.
Hantera med `uag_envsec`.

## Konfiguration och detaljer

- **Miljövariabler**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Installationsguide**: `python -m uagent.setup_cli`
- **Krypterad env**: `uag_envsec` — kryptera `.env` som `.env.sec`
- **Responses API**: Ställ in `UAGENT_RESPONSES=1` för Responses API-läge (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Autoaktiverad för Sakana AI (Fugu).
- **Utvecklardokument**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Tool flow**: [TOOL_FLOW.md](../src/uagent/docs/TOOL_FLOW.md)
- **Små LLM-tips**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Projektfilosofi

uag strävar efter att vara **din AI, på din maskin, på dina villkor.**

- Inget SaaS-beroende — körs lokalt
- Ingen leverantörslåsning - byt när som helst
- Ingen UI-låsning — CLI / GUI / Web / A2A
- Ingen funktionslåsning - utöka med verktyg och färdigheter

En gratis AI-agentupplevelse, fri från leverantörslåsning.

### ✨ Skapa dina egna verktyg


[sv.md](TOOL_CREATOR_GUIDE.sv.md)
Se den stegvisa guiden här.

## Bidra

Bidrag är välkomna! Felrapporter, förslag på funktioner, dokumentationsförbättringar, översättningar och pull-förfrågningar – allt uppskattas.

- **Issues**: Öppna ett GitHub-problem för buggar eller funktionsförfrågningar.
- **Pull-förfrågningar**: Skapa en fork av repot, gör dina ändringar och skicka in en PR. Se [DEVELOP.md](../src/uagent/docs/DEVELOP.md) för utvecklingskonfiguration och riktlinjer.



Realtime Röst och AEC3

## Realtime röstläge stöder full-duplex mikrofon och högtalaringång/utgång. Om AEC3 backend saknas, installerar uag automatiskt pywebrtc-audio.

**Realtidsleverantörer**: OpenAI Realtime, Azure OpenAI GPT Realtime, Google Gemini Live, xAI Grok Voice och Amazon Bedrock Nova Sonic. SDK:t för dubbelriktad Bedrock-streaming installeras automatiskt endast när Bedrock har valts.

```bat
python scheck.py realtime
```

AEC3 använder den faktiska mikrofonsignalen (nära) och ljudet som faktiskt skickas till högtalaren (avlägsen). Aktivera diagnostik endast när du undersöker ljudproblem.

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime stöder en säkerhetsbegränsad Function Calling-integrering. Den aktuella adaptern exponerar den skrivskyddade get_current_time-funktionen automatiskt. Destruktiva verktyg och enhetskontroller kräver en explicit godkännandelista och bekräftelseflöde. Grok realtid använder en separat adapter och använder inte denna OpenAI-specifika Function Calling-sökväg.
