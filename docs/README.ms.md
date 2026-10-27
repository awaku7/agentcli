<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  Satu ejen tempatan. Mana-mana model. Mana-mana alat. Persekitaran anda, peraturan anda.
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
  <a href="https://github.com/awaku7/agentcli/discussions">Perbincangan</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Terjemahan</a>
</p>

______________________________________________________________________

**Mengapa uag?**

uag ialah ejen AI berteraskan tempatan yang menghubungkan model pilihan anda dengan alat yang sebenarnya anda gunakan.
Ia menyediakan satu masa jalan yang boleh diperluas untuk fail, pelayar, pangkalan kod, komunikasi, API awan,
peranti IoT, pelayan MCP dan aliran kerja berbilang ejen.

- **Kebebasan penyedia** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek dan banyak lagi.
- **Pelaksanaan berteraskan tempatan** — masa jalan ejen dan pelaksanaan alat kekal pada mesin anda; hanya panggilan API yang anda pilih akan meninggalkannya.
- **Satu lapisan alat** — alat yang sama berfungsi daripada CLI, GUI desktop, UI web, VS Code dan A2A.
- **Direka untuk selari** — operasi baca sahaja yang bebas boleh dijalankan serentak.
- **Boleh diperluas** — tambah alat, pemalam, Agent Skills, pelayan MCP dan alat berasaskan Rust tanpa mengubah teras.
- **Mengutamakan keselamatan** — tindakan memusnahkan, kelayakan, kawalan peranti dan penulisan rangkaian menyokong pengesahan eksplisit serta kawalan dasar.

> **Ringkasnya:** uag ialah satah kawalan antara model AI anda dengan persekitaran sebenar anda.

> **🧠 Hasil alat yang peka konteks** — Hasil alat yang besar disimpan di luar konteks model aktif apabila boleh. uag menyimpannya sebagai Artifacts dan sebaliknya menghantar pratonton terhad dengan rujukan Artifact yang stabil kepada model. Ini boleh mengurangkan jumlah token input yang diperlukan untuk giliran susulan dengan ketara apabila alat menghasilkan hasil yang besar.
> [Panduan terperinci pemampatan konteks](CONTEXT_COMPRESSION.ms.md)

## Mula pantas

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

Pelancaran pertama membuka wizard persediaan. Wizard ini membantu mengkonfigurasi penyedia dan menyimpan tetapan yang dipilih
dalam persekitaran tempatan anda.

Untuk kumpulan ciri umum:

```bash
python -m pip install "uag[core,providers,tools]"
```

> Integrasi platform adalah pilihan. Pasang hanya perkara yang diperlukan oleh sistem pengendalian anda; lihat

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Antara muka

| Antara muka | Perintah | Paling sesuai untuk |
|---|---|---|
| **CLI** | `uag` | Kerja pantas berasaskan papan kekunci |
| **GUI desktop** | `uagg` | Pengalaman desktop natif |
| **UI web** | `uagw` | Akses berasaskan pelayar |
| **Pelayan A2A** | `uaga` | Komunikasi antara ejen |
| **VS Code** | Extension | Menjelaskan, memfaktor semula, membaiki dan menyemak imbas alat dalam editor |

Semua antara muka berkongsi konfigurasi penyedia, daftar alat, peraturan keselamatan dan data sesi yang sama.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## Perkara yang boleh anda bina

Penyesuai penyedia meliputi masa jalan hos dan tempatan, termasuk:

- Membaca, mencipta, mengedit, mencari, mencincang, mengarkib dan memeriksa fail
- Menyemak perubahan Git, mengimbas rahsia, menjalankan ujian, lint, kompilasi dan mengukur liputan
- Menavigasi pangkalan kod Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA dan lain-lain yang besar
- Mengautomatikkan pelayar dengan Playwright, termasuk aliran berbilang halaman dan muat turun

- **MCP** — sambungkan pelayan alat luaran, termasuk perkhidmatan yang didayakan OAuth
- **A2A** — selaraskan dengan ejen lain dan pelayan yang serasi
- **Cloud** — akses API AWS, Google Cloud dan Azure dengan pengesahan untuk penulisan
- **Communication** — Gmail, Bluesky, Discord, Microsoft Teams dan pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA dan UPnP
- **Media** — penjanaan/penyuntingan imej, transkripsi/pertuturan audio, tangkapan kamera dan kod QR
- **Documents** — PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL dan analisis log

- **SwitchBot** — penemuan Cloud dan BLE, status, kawalan, pengelompokan dan langganan
- **ECHONET Lite** — menemui dan mengawal perkakas rumah Jepun, termasuk pemberitahuan INF
- **Matter** — endpoint, kluster, atribut, sejarah keadaan, langganan dan kawalan
- **BACnet / Modbus TCP / OPC UA** — pembacaan, penulisan, pelayaran dan pemantauan automasi industri serta bangunan
- **UPnP** — penemuan peranti, status WAN dan pengurusan pemetaan port penghala

### Kedudukan uag

uag berada di antara manusia dan antara muka di satu pihak, serta model, alat dan sistem dunia sebenar di pihak yang lain.
Ia menyelaraskan perbualan, memilih keupayaan, menerapkan peraturan keselamatan dan memastikan aliran kerja boleh disambung semula.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Pemalam, Agent Skills dan marketplace

Jadikan uag ejen khusus tanpa mem-fork teras:

- Pasang **pemalam serasi Claude Code** daripada direktori, ZIP, repositori Git, sumber HTTP atau marketplace
- Himpunkan kemahiran, sub-ejen, pelayan MCP, hook, arahan slash, gaya output, kebergantungan dan saluran
- Semak imbas keupayaan komuniti daripada [SkillsMP](https://skillsmp.com) dan [ClawHub](https://clawhub.ai)
- Tambah kemahiran serta alat organisasi peribadi secara tempatan melalui `UAGENT_EXTERNAL_TOOLS_DIR`

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

Lihat [Panduan Pembangunan Pemalam](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **200+ alat** untuk fail, web, media, dokumen, kod, awan, komunikasi dan IoT
- **Penemuan dan pemuatan dinamik** — gunakan `tool_catalog` untuk mencari keupayaan dan `tool_load` untuk mendayakannya hanya apabila diperlukan
- **Kecerdasan kod** — `code_map`, penavigasi `idx` khusus bahasa, semakan Git, pelaksanaan ujian, linting, kompilasi dan liputan
- **Pemalam serasi Claude Code** dengan kemahiran, ejen, pelayan MCP, hook, arahan dan marketplace
- **Agent Skills** daripada SkillsMP dan ClawHub
- **Alat Python tersuai** dengan `TOOL_SPEC` dan `run_tool()`
- **Alat berasaskan Rust** untuk sambungan natif ringan

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Dibina untuk aliran kerja sebenar

### 🧠 Hasil alat yang peka konteks

Hasil alat yang besar disimpan di luar konteks model aktif apabila boleh. uag menyimpannya sebagai Artifacts dan sebaliknya menghantar pratonton terhad dengan rujukan Artifact yang stabil kepada model. Ini boleh mengurangkan jumlah token input yang diperlukan untuk giliran susulan dengan ketara apabila alat menghasilkan hasil yang besar.

Sambung semula perbualan terdahulu dengan `:load <index>`. Hasil alat boleh dicache dan penyedia boleh ditukar
tanpa membina semula aplikasi.

[Context compression](CONTEXT_COMPRESSION.ms.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Auto-pilot

Gunakan `:auto` untuk kerja berbilang pusingan dengan model penyemak pilihan. Tetapkan had pusingan dengan `--max-rounds N`.
Tekan **F12** untuk menghentikan auto-pilot atau **F12** untuk menghentikan respons semasa.

Operasi baca sahaja yang bebas berjalan serentak apabila selamat. Carian web, pemeriksaan fail,
analisis repositori dan beban kerja seumpamanya boleh diselesaikan secara selari dengan kumpulan pekerja
yang boleh dikonfigurasi (`UAGENT_PARALLEL_WORKERS`). Operasi tulis kekal bersiri atau memerlukan pengesahan.

Kesinambungan sesi, caching hasil alat, keadaan kelompok, pemulihan selepas mula semula, penjadualan DAG dan
orkestrasi berbilang ejen menjadikan kerja kompleks boleh disambung semula dan bukan sekali jalan.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Peribadi, berbilang bahasa dan peka dasar

`human_ask` berhenti seketika sebelum tindakan sensitif. Pemadaman fail, penindihan, arahan shell, kawalan peranti,
operasi kelayakan dan penulisan rangkaian boleh ditadbir oleh peraturan pengesahan dan dasar.

Gunakan stor kelayakan dan bukannya meletakkan rahsia jangka panjang dalam gesaan:

UI Web merangkumi log masuk OIDC menggunakan Authorization Code + PKCE, token ID yang disahkan, sesi sisi pelayan, dan kawalan akses projek/bilik. Tuntutan kumpulan Microsoft Entra ID yang disahkan boleh menyokong dasar akses berasaskan direktori apabila dikonfigurasikan. Penempatan Windows Active Directory, OAuth, dan trusted-proxy boleh diintegrasikan melalui penyesuai identiti yang disahkan secara eksplisit; Windows AD memerlukan pengesah Kerberos/Negotiate khusus penempatan dan tidak diaktifkan secara lalai.

uag termasuk penjejakan OpenTelemetry dan metrik ikut serta, neutral pembekal untuk Agent, LLM, alat, Context, Memory dan operasi pengambilan semula. Kebolehlihatan dilumpuhkan secara lalai.

Pendekatan local-first tidak bermakna UAG berfungsi sepenuhnya luar talian atau semua alat diasingkan secara lalai. Panggilan kepada model dan perkhidmatan luaran bergantung pada konfigurasi.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Terjemahan berbilang bahasa

- `translate_text` menyokong Google Translate dan klien DeepL Python rasmi melalui `provider=auto`, `provider=deepl`, atau `provider=google`.
- Definisi alat tersedia dalam 37 lokalisasi ditambah Bahasa Inggeris (jumlah 38), dengan penanda tempat dan pengecam teknikal dikekalkan.

Suara dupleks penuh tersedia melalui OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live
dan Bedrock Nova Sonic, dengan pembatalan gema AEC3 pilihan serta panggilan fungsi masa nyata yang dihadkan keselamatannya.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Dokumentasi

| Topik | Dokumentasi |
|---|---|
| Pemboleh ubah persekitaran | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Seni bina dan invarian | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Alat repositori | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| Kes penggunaan IoT | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Alat komunikasi | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Auto-pilot | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proksi | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| Sambungan VS Code | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Panduan pembangun | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Aliran alat | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## Pembangunan dan sumbangan

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Jalankan pemeriksaan pra-PR:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

Untuk aliran kerja pembangunan penuh, lihat [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md).

Laporan pepijat, idea ciri, penambahbaikan dokumentasi, terjemahan, alat, kemahiran dan pull request dialu-alukan.
Sila buka isu atau perbincangan sebelum perubahan besar. Baca [Panduan Pembangun](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
dan jalankan pemeriksaan di atas sebelum menghantar pull request.

## Lesen

Dilesenkan di bawah [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
