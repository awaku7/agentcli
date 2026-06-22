<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag-logo" width="720">
</p>

<h1 align="center">uag — Universal AI Gateway</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Ditt miljø, din frihet.
</p>

<p align="center">
  Filoperasjoner / Nettsøk / Bildegenerering og analyse / PDF- og Excel-utvinning / IoT-kontroll / MCP-integrasjon<br>
  15+ leverandører / 3 brukergrensesnitt / Parallell verktøykjøring / Agent Skills markedsplass
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Les dette på ditt språk</a>
</p>

---

## Hvorfor uag?

**Slipp deg løs fra leverandørlåsing.** De fleste AI-assistenter knytter deg til en bestemt leverandør eller skytjeneste. uag er annerledes.

- **Kjører lokalt** på maskinen din. Dataene dine forblir hos deg (unntatt API-anrop du foretar).
- **Leverandørfrihet**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock... 15+ leverandører, alle tilgjengelige fra ett enkelt grensesnitt. Bytt mellom dem ved å rekonfigurere miljøvariabler – ingen reinstallering, ingen migrering.
- **111 verktøy**: Fil-I/O, nettsøk, bildegenerering, BLE-enhetsskanning, MCP-serverintegrasjon — og **55 av dem kjøres parallelt**. Når LLM utløser flere verktøyanrop samtidig, kjører uag dem automatisk via en trådpool.
- **3 brukergrensesnitt + A2A**: CLI, GUI, Web og Agent-to-Agent-protokoll. Samme motor, hvilket som helst grensesnitt.
- **IoT-klar**: SwitchBot, ECHONET Lite, Matter, UPnP — kontroller hjemmeenhetene dine gjennom AI.
- **Agentferdigheter**: Installer fellesskapsbygde ferdigheter fra markedsplassen. Forleng uag uendelig.

uag er **din AI-assistent på dine vilkår**. Ikke knyttet til en leverandør, ikke knyttet til et grensesnitt, ikke knyttet til en plattform.

## Hurtigstart

```bash
pip install uag
uag
```

Ved første oppstart leder oppsettsveiviseren deg gjennom leverandørkonfigurasjonen.
Se [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) for alle miljøvariabler.

## Funksjoner

### 🧠 Arkitektur med flere leverandører

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax

Alle leverandører deler samme verktøysett og grensesnitt. Bytt ved å sette 'UAGENT_PROVIDER' — ingen kodeendringer, ingen separate installasjoner.

### ⚡ Parallell verktøyutførelse

Når LLM ber om flere verktøy samtidig, uag **paralliserer automatisk** dem.
55 verktøy er merket "x_parallel_safe" og kjøres samtidig via en 4-tråds "ThreadPoolExecutor".

**Eksempel**: Spør "Sjekk været i nordiske hovedsteder" → LLM avfyrer `search_web` × 5 land → alle 5 søkene kjøres parallelt → resultater samlet i én batch.

Skrivebeskyttede verktøy (filsøk, hash-beregning, katalogoppføring, oversettelse, DB-spørringer osv.) parallelliseres aggressivt.

### 🔄 Øktkontinuitet

- **Bytt leverandør midt i økten** med 'UAGENT_PROVIDER' — samtalehistorikk er bevart.
- **Last inn tidligere økter på nytt** med `:load <indeks>` – fortsett der du slapp.
- **Bufring av verktøyresultat** unngår redundant re-utførelse når det samme verktøykallet gjentas.

### 🛠 111 Verktøy

| Kategori | Verktøy |
|---|---|
| **Filoperasjoner** | read/write/create/delete/search/grep/hash/zip |
| **Nett** | fetch_url, search_web, screenshot, browser_playwright |
| **Media** | generere_bilde, analyse_bilde, img2img, audio_tale, audio_transkribering |
| **Dokumenter** | PDF/PPTX/DOCX/RTF/ODT-utvinning, Excel-strukturert utvinning |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP |
| **Utviklerverktøy**, ****11 idx-verktøy** (Python, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin) — få funksjons-/klasseindeks eller spesifikk definisjon uten å lese hele filen** | git_ops, python_compile, lint_format, run_tests, db_query, ****11 idx-verktøy** (Python, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin) — få funksjons-/klasseindeks eller spesifikk definisjon uten å lese hele filen** |
| **MCP** | Koble til eksterne MCP-servere, liste opp verktøy, kjør |
| **A2A** | Agent-til-agent-kommunikasjon (med andre uag-instanser eller A2A-kompatible servere) |
| **System** | env vars, systemspesifikasjoner, tid, datoberegning |
| **Kildekodenavigasjon** | **11 idx-verktøy** (Python, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin) — få funksjons-/klasseindeks eller spesifikk definisjon uten å lese hele filen |

### 🖥 3 grensesnitt + A2A

| Modus | Kommando | Formål |
|---|---|---|
| **CLI** | `uag` | Rask terminalbasert drift |
| **GUI** | `uagg` | Desktop UI via tkinter |
| **Nett** | `uagw` | Nettleserbasert tilgang |
| **A2A-server** | `uaga` | Agent2Agent-protokoll for multi-agent kommunikasjon |

### 🏠 IoT-enhetskontroll

- **SwitchBot**: Cloud batchkontroll og BLE-skanning/kontroll
- **ECHONET Lite**: Oppdag og kontroller husholdningsapparater (AC, lys, varmtvannsberedere osv.) på lokalt nettverk
- **Materie**: Skrivebeskyttet inspeksjon av kontroller/bro/enhetstopologi
- **UPnP**: Enhetsoppdagelse og videresending av IGD-porter

Se [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` for å bla gjennom [SkillsMP](https://skillsmp.com) og [ClawHub](https://clawhub.ai) for fellesskapsferdigheter.
Installer og utvid uags muligheter på farten.

### 🧩 Batch State Manager

uag kan spore fremgang på tvers av langvarige flerfiloppgaver. Når LLM behandler dusinvis av filer, vedvarer `batch_state` listen over ventende, fullførte og mislykkede filer til disken. Hvis økten avsluttes eller en runde går ut, fortsetter neste kjøring fra der den stoppet – ingenting går tapt.

### 🛡 Menneske-i-løkken

`human_ask` lar LLM pause og be om din bekreftelse før de utfører destruktive operasjoner (sletting av filer, overskriving, shell-kommandoer). Du holder kontrollen.

### 🕵️ Nettleserautomatisering og nettinspektør

To komplementære dramatikerbaserte verktøy:

- **browser_playwright**: Automatiser ekte nettleserøkter - naviger, klikk, fyll ut skjemaer, trekk ut data, håndter flyter på flere sider. Fungerer hodeløst eller med hodet.
- **playwright_inspector**: Ta opp nettleseroverganger, ta DOM-øyeblikksbilder og skjermbilder ved hvert trinn. Nyttig for feilsøking av nettinteraksjoner eller revisjon av sideendringer over tid.

### 🔄 Dynamisk verktøyinnlasting

`tool_catalog` og `tool_load` lar deg oppdage og aktivere verktøy under kjøring.
Du trenger ikke å laste alt ved oppstart - aktiver bare det du trenger, når du trenger det.

### 🌐 i18n / L10n

日本語 / Engelsk / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / og mer.
Sett «UAGENT_LANG» for å bytte. Se [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) for å legge til en ny lokalitet.

Oversettelser av denne README er tilgjengelig i [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Krypterte miljøvariabler

Lagre API-nøkler og hemmeligheter i `.env.sec` – en kryptert `.env`-fil.
Administrer med `uag_envsec`.

## Konfigurasjon og detaljer

- **Miljøvariabler**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **Oppsettsveiviser**: `python -m uagent.setup_cli`
- **Kryptert env**: `uag_envsec` — krypter `.env` som `.env.sec`
- **Responses API**: Sett `UAGENT_RESPONSES=1` for Responses API-modus (OpenAI/Azure/Bedrock/OpenRouter/Ollama/LM Studio)
- **Utviklerdokumenter**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Små LLM-tips**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Prosjektfilosofi

uag ønsker å være **din AI, på maskinen din, på dine premisser.**

- Ingen SaaS-avhengighet - kjører lokalt
- Ingen leverandørlåsing - bytt når som helst
- Ingen UI-låsing - CLI / GUI / Web / A2A
- Ingen funksjonslåsing - utvide med verktøy og ferdigheter

En gratis AI-agentopplevelse, fri fra leverandørlåsing.