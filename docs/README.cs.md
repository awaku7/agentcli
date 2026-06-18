<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (Lokální AI agent)

uag je lokální interaktivní agent, který spouští **příkazy**, pracuje se **soubory** a čte **datové soubory** jako PDF, PPTX a Excel. Nabízí tři uživatelská rozhraní: CLI, GUI a Web.

uag je navržen tak, aby vás **udržel svobodné od aplikací vázaných na jediného dodavatele**: používejte rozhraní, které odpovídá vašemu workflow, přepínejte poskytovatele a mějte své prostředí pod kontrolou.

GitHub: https://github.com/awaku7/agentcli

## Instalace

Nainstalujte z PyPI pomocí pip:

```bash
pip install uag
```

Pokud používáte virtuální prostředí, nejdřív ho aktivujte a potom spusťte výše uvedený příkaz.

Při prvním spuštění `uag` zkontroluje vaše prostředí a automaticky spustí průvodce nastavením, pokud chybí potřebné proměnné poskytovatele. Podrobnosti ke konfiguraci najdete v [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

## Hlavní vlastnosti

- **Praktická sada nástrojů**: práce se soubory, webové vyhledávání, extrakce z PDF/PPTX/Excel, generování obrázků a analýza obrázků.
- **Podpora více poskytovatelů**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / Moonshot AI.
- **Tři rozhraní**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **A2A server**: `uaga` / `python -m uagent.a2a.server`
- **Podpora MCP**: připojení k externím MCP tool serverům.
- **Kontinuita relace**: zachování kontextu při přepínání modelu nebo poskytovatele.
- **Tržiště dovedností agentů**: Procházejte a instalujte komunitní Agent Skills z [SkillsMP](https://skillsmp.com) nebo [ClawHub](https://clawhub.ai) pomocí `:skills mp_search`.
- **Web Inspector**: ukládání navigací v prohlížeči, DOM snapshotů a screenshotů pomocí `playwright_inspector`.
- **Vestavěná dokumentace**: čtení přiložených dokumentů pomocí `uag docs`.
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

## Použití

### Spuštění a ukončení

Spusťte `uag` v terminálu. Ukončíte ho zadáním `:exit`.

For all command-line options, see [USAGE.md](USAGE.md).

### A2A server

Spusťte HTTP server kompatibilní s Agent2Agent:

```bash
uaga
```

Nastavení `UAGENT_A2A_*`, jako je autentizace, hostitel, port, opětovné načítání, veřejná base URL, souběžnost a engine, najdete v [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

### Užitečné příkazy

- `:tools`: zobrazit načtené nástroje
- `:logs [n]`: zobrazit poslední logy sezení
- `:load <index>`: načíst předchozí sezení
- `:skills`: vybrat a načíst Agent Skills (pomocí `:skills mp_search` procházejte tržiště [SkillsMP](https://skillsmp.com) nebo [ClawHub](https://clawhub.ai))
- `:shrink [n]`: shrnout historii a ponechat posledních `n` zpráv
- Small LLM tips: see [SLM_TIPS.md](SLM_TIPS.md).

## Konfigurace a podrobnosti

### Proměnné prostředí a nastavení

Podrobnosti o API klíčích, nastavení jazyka (`UAGENT_LANG`), zkracování historie a dalších věcech najdete v [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

- **Průvodce nastavením**: `python -m uagent.setup_cli`
- **Šifrované prostředí**: použijte `uag_envsec` k zašifrování `.env` jako `.env.sec`
- **Aktualizace šifrovaných hodnot**: `uag_envsec add --file .env.sec --key NAME --value VALUE`

### Poznámka k Responses API

Pokud nastavíte `UAGENT_RESPONSES=1`, Responses API se použije pro podporované poskytovatele: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI používají své nativní API cesty a Responses API se na ně nevztahuje.
Pro ostatní poskytovatele uag přechází na poskytovatelem specifickou cestu nebo na chat-completions.

### Vývojářská dokumentace a překlady

- **Vývojářská dokumentace**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Přidání locale**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **Other README translations**: [`docs/README.translations.md`](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)
