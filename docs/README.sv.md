<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Universal AI Gateway</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Din miljö, din frihet.
</p>

<p align="center">
  Filoperationer / Webbsökning / Bildgenerering och analys / PDF- och Excel-extraktion / IoT-kontroll / MCP-integration<br>
  15+ leverantörer / 3 användargränssnitt / Parallellt verktygsutförande / Agent Skills marknadsplats
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Läs detta på ditt språk</a>
</p>

---

## Varför uag?

**Slut dig från leverantörslåsning.** De flesta AI-assistenter knyter dig till en specifik leverantör eller molntjänst. uag är annorlunda.

- **Körs lokalt** på din maskin. Din data stannar hos dig (förutom API-anrop du gör).
- **Leverantörsfrihet**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock... 15+ leverantörer, alla tillgängliga från ett enda gränssnitt. Byt mellan dem genom att konfigurera om miljövariabler – ingen ominstallation, ingen migrering.
- **111 verktyg**: Fil-I/O, webbsökning, bildgenerering, BLE-enhetsskanning, MCP-serverintegrering — och **55 av dem körs parallellt**. När LLM avfyrar flera verktygsanrop samtidigt, kör uag dem automatiskt via en trådpool.
- **3 användargränssnitt + A2A**: CLI, GUI, webb och Agent-to-Agent-protokoll. Samma motor, vilket gränssnitt som helst.
- **IoT redo**: SwitchBot, ECHONET Lite, Matter, UPnP — styr dina hemenheter genom AI.
- **Agent Skills**: Installera community-byggda färdigheter från marknadsplatsen. Förläng uag oändligt.

uag är **din AI-assistent på dina villkor**. Inte bunden till en leverantör, inte bunden till ett gränssnitt, inte bunden till en plattform.

## Snabbstart

```bash
pip install uag
uag
```

Vid första lanseringen leder installationsguiden dig genom leverantörskonfigurationen.
Se [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) för alla miljövariabler.

## Funktioner

### 🧠 Arkitektur för flera leverantörer

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax

Alla leverantörer delar samma verktygsuppsättning och gränssnitt. Byt genom att ställa in "UAGENT_PROVIDER" — inga kodändringar, inga separata installationer.

### ⚡ Parallell verktygsexekvering

När LLM begär flera verktyg samtidigt, uag **parallellerar automatiskt** dem.
55 verktyg är märkta "x_parallel_safe" och körs samtidigt via en 4-tråds "ThreadPoolExecutor".

**Exempel**: Fråga "Kontrollera vädret i nordiska huvudstäder" → LLM avfyrar `search_web` × 5 länder → alla 5 sökningar körs parallellt → resultat samlade i en batch.

Läsbara verktyg (filsökning, hashberäkning, kataloglistning, översättning, DB-frågor, etc.) parallelliseras aggressivt.

### 🔄 Sessionskontinuitet

- **Byt leverantör mitt i sessionen** med 'UAGENT_PROVIDER' — konversationshistoriken bevaras.
- **Ladda om tidigare sessioner** med `:load <index>` — fortsätt där du slutade.
- **Caching av verktygsresultat** undviker redundant återexekvering när samma verktygsanrop upprepas.

### 🛠 111 Verktyg

| Kategori | Verktyg |
|---|---|
| **Filoperationer** | read/write/create/delete/search/grep/hash/zip |
| **Webb** | fetch_url, search_web, screenshot, browser_playwright |
| **Media** | generera_bild, analysera_bild, img2img, audio_tal, audio_transcribe |
| **Dokument** | PDF/PPTX/DOCX/RTF/ODT-extraktion, Excel-strukturerad extrahering |
| **IoT** | SwitchBot (moln + BLE), ECHONET Lite, Matter, UPnP |
| **Utvecklarverktyg** | git_ops, python_compile, lint_format, run_tests, db_query |
| **MCP** | Anslut till externa MCP-servrar, lista verktyg, kör |
| **A2A** | Agent-till-agent-kommunikation (med andra uag-instanser eller A2A-kompatibla servrar) |
| **System** | env vars, systemspecifikationer, tid, datumberäkning |

### 🖥 3 gränssnitt + A2A

| Läge | Kommando | Syfte |
|---|---|---|
| **CLI** | `uag` | Snabb terminalbaserad drift |
| **GUI** | `uagg` | Desktop UI via tkinter |
| **Webb** | `uagw` | Webbläsarbaserad åtkomst |
| **A2A-server** | `uaga` | Agent2Agent-protokoll för multiagentkommunikation |

### 🏠 IoT-enhetskontroll

- **SwitchBot**: Molnbatchkontroll och BLE-skanning/kontroll
- **ECHONET Lite**: Upptäck och kontrollera hushållsapparater (AC, lampor, varmvattenberedare, etc.) på det lokala nätverket
- **Ärende**: Skrivskyddad inspektion av styrenhet/brygga/enhetstopologi
- **UPnP**: Enhetsupptäckt och vidarebefordran av IGD-portar

Se [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` för att bläddra i [SkillsMP](https://skillsmp.com) och [ClawHub](https://clawhub.ai) för gemenskapskunskaper.
Installera och utöka uags kapacitet i farten.

### 🧩 Batch State Manager

uag kan spåra framsteg över långvariga flerfilsuppgifter. När LLM bearbetar dussintals filer, kvarstår `batch_state` listan över väntande, slutförda och misslyckade filer till disken. Om sessionen slutar eller en omgång tar slut, återupptas nästa körning där den slutade – ingenting går förlorat.

### 🛡 Människan-i-slingan

`human_ask` låter LLM pausa och be om din bekräftelse innan du utför destruktiva operationer (filradering, överskrivningar, skalkommandon). Du behåller kontrollen.

### 🕵️ Webbläsarautomation och webbinspektör

Två kompletterande dramatikerbaserade verktyg:

- **browser_playwright**: Automatisera riktiga webbläsarsessioner - navigera, klicka, fyll i formulär, extrahera data, hantera flersidiga flöden. Fungerar utan huvud eller huvud.
- **playwright_inspector**: Spela in webbläsarövergångar, fånga DOM-ögonblicksbilder och skärmdumpar vid varje steg. Användbar för att felsöka webbinteraktioner eller granska sidändringar över tid.

### 🔄 Dynamisk verktygsladdning

`tool_catalog` och `tool_load` låter dig upptäcka och aktivera verktyg vid körning.
Inget behov av att ladda allt vid start - aktivera bara det du behöver, när du behöver det.

### 🌐 i18n / L10n

日本語 / Engelska / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / och mer.
Ställ in "UAGENT_LANG" för att byta. Se [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) för att lägga till ett nytt språk.

Översättningar av denna README finns i [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Krypterade miljövariabler

Lagra API-nycklar och hemligheter i `.env.sec` - en krypterad `.env`-fil.
Hantera med `uag_envsec`.

## Konfiguration och detaljer

- **Miljövariabler**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **Installationsguide**: `python -m uagent.setup_cli`
- **Krypterad env**: `uag_envsec` — kryptera `.env` som `.env.sec`
- **Responses API**: Ställ in `UAGENT_RESPONSES=1` för Responses API-läge (OpenAI/Azure/Bedrock/OpenRouter/Ollama/LM Studio)
- **Utvecklardokument**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Små LLM-tips**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Projektfilosofi

uag strävar efter att vara **din AI, på din maskin, på dina villkor.**

- Inget SaaS-beroende — körs lokalt
- Ingen leverantörslåsning - byt när som helst
- Ingen UI-låsning — CLI / GUI / Web / A2A
- Ingen funktionslåsning - utöka med verktyg och färdigheter

En gratis AI-agentupplevelse, fri från leverantörslåsning.