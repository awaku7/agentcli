<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  Satu agen lokal. Model apa pun. Alat apa pun. Lingkungan Anda, aturan Anda.
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
  <a href="https://github.com/awaku7/agentcli/discussions">Discussions</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Translations</a>
</p>

______________________________________________________________________

**Mengapa uag?**

uag adalah agen AI local-first yang menghubungkan model pilihan Anda dengan alat yang benar-benar Anda gunakan.
Agen ini menyediakan satu runtime yang dapat diperluas untuk file, browser, basis kode, komunikasi, API cloud,
perangkat IoT, server MCP, dan alur kerja multi-agen.

- **Kebebasan provider** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek, dan lainnya.
- **Eksekusi local-first** — runtime agen dan eksekusi alat tetap berada di mesin Anda; hanya panggilan API yang Anda pilih yang keluar.
- **Satu lapisan alat** — alat yang sama dapat digunakan dari CLI, GUI desktop, UI web, VS Code, dan A2A.
- **Dirancang untuk paralel** — operasi baca-saja yang independen dapat berjalan secara bersamaan.
- **Dapat diperluas** — tambahkan alat, plugin, Agent Skills, server MCP, dan alat berbasis Rust tanpa mengubah inti.
- **Sadar akan keamanan** — tindakan destruktif, kredensial, kontrol perangkat, dan penulisan jaringan mendukung konfirmasi eksplisit serta kontrol kebijakan.

> **Singkatnya:** uag adalah bidang kendali antara model AI Anda dan lingkungan nyata Anda.

> **🧠 Hasil alat yang peka konteks** — Hasil alat yang berukuran besar disimpan di luar konteks model aktif jika memungkinkan. uag menyimpannya sebagai Artifak dan memberikan pratinjau terbatas kepada model dengan referensi Artifact yang stabil sebagai gantinya. Hal ini dapat secara signifikan mengurangi jumlah token masukan yang diperlukan untuk giliran berikutnya ketika sebuah alat menghasilkan hasil yang besar.
> [Panduan lengkap kompresi konteks](CONTEXT_COMPRESSION.id.md)

## Mulai cepat

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

Peluncuran pertama membuka wizard penyiapan. Wizard ini membantu mengonfigurasi provider dan menyimpan pengaturan yang dipilih
di lingkungan lokal Anda.

Untuk kelompok fitur umum:

```bash
python -m pip install "uag[core,providers,tools]"
```

> Integrasi platform bersifat opsional. Instal hanya yang dibutuhkan sistem operasi Anda; lihat

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Antarmuka

| Antarmuka | Perintah | Terbaik untuk |
|---|---|---|
| **CLI** | `uag` | Pekerjaan cepat yang mengutamakan keyboard |
| **GUI desktop** | `uagg` | Pengalaman desktop native |
| **UI web** | `uagw` | Akses berbasis browser |
| **Server A2A** | `uaga` | Komunikasi antargen |
| **VS Code** | Extension | Menjelaskan, melakukan refactor, memperbaiki, dan menelusuri alat di editor |

Semua antarmuka menggunakan konfigurasi provider, registri alat, aturan keamanan, dan data sesi yang sama.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## Apa yang dapat Anda bangun

Adaptor provider mencakup runtime hosted dan lokal, termasuk:

- Membaca, membuat, mengedit, mencari, melakukan hash, mengarsipkan, dan memeriksa file
- Meninjau perubahan Git, memindai rahasia, menjalankan pengujian, melakukan lint, kompilasi, dan mengukur cakupan
- Menelusuri basis kode Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA, dan lainnya yang berukuran besar
- Mengotomatiskan browser dengan Playwright, termasuk alur multi-halaman dan unduhan

- **MCP** — hubungkan server alat eksternal, termasuk layanan yang mendukung OAuth
- **A2A** — berkoordinasi dengan agen lain dan server yang kompatibel
- **Cloud** — akses API AWS, Google Cloud, dan Azure dengan konfirmasi untuk penulisan
- **Communication** — Gmail, Bluesky, Discord, Microsoft Teams, dan pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA, dan UPnP
- **Media** — pembuatan/pengeditan gambar, transkripsi/ucapan audio, pengambilan kamera, dan kode QR
- **Documents** — analisis PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL, dan log

- **SwitchBot** — penemuan Cloud dan BLE, status, kontrol, batching, dan subscription
- **ECHONET Lite** — menemukan dan mengontrol peralatan rumah tangga Jepang, termasuk notifikasi INF
- **Matter** — endpoint, cluster, atribut, riwayat status, subscription, dan kontrol
- **BACnet / Modbus TCP / OPC UA** — pembacaan, penulisan, penelusuran, dan pemantauan otomasi industri serta gedung
- **UPnP** — penemuan perangkat, status WAN, dan pengelolaan pemetaan port router

### Posisi uag

uag berada di antara manusia dan antarmuka di satu sisi, serta model, alat, dan sistem dunia nyata di sisi lain.
Agen ini mengoordinasikan percakapan, memilih kapabilitas, menerapkan aturan keamanan, dan menjaga agar alur kerja dapat dilanjutkan.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Plugin, Agent Skills, dan marketplace

Ubahlah uag menjadi agen khusus tanpa melakukan fork terhadap inti:

- Instal **plugin yang kompatibel dengan Claude Code** dari direktori, ZIP, repositori Git, sumber HTTP, atau marketplace
- Gabungkan skill, sub-agen, server MCP, hook, perintah slash, gaya keluaran, dependensi, dan channel
- Jelajahi kapabilitas komunitas dari [SkillsMP](https://skillsmp.com) dan [ClawHub](https://clawhub.ai)
- Tambahkan skill dan alat organisasi privat secara lokal melalui `UAGENT_EXTERNAL_TOOLS_DIR`

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

Lihat [Plugin Development Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **200+ alat** untuk file, web, media, dokumen, kode, cloud, komunikasi, dan IoT
- **Penemuan dan pemuatan dinamis** — gunakan `tool_catalog` untuk menemukan kapabilitas dan `tool_load` untuk mengaktifkannya hanya saat diperlukan
- **Inteligensi kode** — `code_map`, navigator `idx` khusus bahasa, peninjauan Git, eksekusi pengujian, linting, kompilasi, dan cakupan
- **Plugin yang kompatibel dengan Claude Code** dengan skill, agen, server MCP, hook, perintah, dan marketplace
- **Agent Skills** dari SkillsMP dan ClawHub
- **Alat Python khusus** dengan `TOOL_SPEC` dan `run_tool()`
- **Alat berbasis Rust** untuk ekstensi native yang ringan

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Dibuat untuk alur kerja nyata

### 🧠 Hasil alat yang peka konteks

Hasil alat yang berukuran besar disimpan di luar konteks model aktif jika memungkinkan. uag menyimpannya sebagai Artifak dan memberikan pratinjau terbatas kepada model dengan referensi Artifact yang stabil sebagai gantinya. Hal ini dapat secara signifikan mengurangi jumlah token masukan yang diperlukan untuk giliran berikutnya ketika sebuah alat menghasilkan hasil yang besar.

Lanjutkan percakapan sebelumnya dengan `:load <index>`. Hasil alat dapat di-cache, dan provider dapat diganti
tanpa membangun ulang aplikasi.

[Context compression](CONTEXT_COMPRESSION.id.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Auto-pilot

Gunakan `:auto` untuk pekerjaan multi-putaran dengan model peninjau opsional. Tetapkan batas putaran dengan `--max-rounds N`.
Tekan **F12** untuk menghentikan auto-pilot atau **F12** untuk menghentikan respons saat ini.

Operasi baca-saja yang independen berjalan secara bersamaan jika aman. Pencarian web, pemeriksaan file,
analisis repositori, dan beban kerja serupa dapat diselesaikan secara paralel dengan pool pekerja yang dapat dikonfigurasi
(`UAGENT_PARALLEL_WORKERS`). Operasi penulisan tetap diserialkan atau memerlukan konfirmasi.

Kontinuitas sesi, caching hasil alat, status batch, pemulihan setelah mulai ulang, penjadwalan DAG, dan
orkestrasi multi-agen membuat pekerjaan kompleks dapat dilanjutkan, bukan hanya dijalankan sekali.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Privat, multibahasa, dan sadar kebijakan

`human_ask` berhenti sejenak sebelum tindakan sensitif. Penghapusan file, penimpaan, perintah shell, kontrol perangkat,
operasi kredensial, dan penulisan jaringan dapat diatur oleh aturan konfirmasi dan kebijakan.

Gunakan penyimpanan kredensial alih-alih menempatkan rahasia jangka panjang di dalam prompt:

Web UI mencakup sign-in OIDC menggunakan Authorization Code + PKCE, token ID yang terverifikasi, sesi sisi server, dan kontrol akses proyek/ruang. Klaim grup Microsoft Entra ID yang terverifikasi dapat mendukung kebijakan akses berbasis direktori saat dikonfigurasi. Deployment Windows Active Directory, OAuth, dan trusted-proxy dapat terintegrasi melalui adapter identitas terverifikasi yang eksplisit; Windows AD memerlukan verifier Kerberos/Negotiate spesifik deployment dan tidak diaktifkan secara default.

uag mencakup penelusuran dan metrik OpenTelemetry netral penyedia untuk Agent, LLM, alat, Context, Memory, dan operasi pengambilan. Observabilitas dinonaktifkan secara default.

Local-first tidak berarti UAG sepenuhnya offline atau semua eksekusi alat terisolasi secara bawaan. Permintaan ke model dan layanan eksternal bergantung pada konfigurasi.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Terjemahan multibahasa

- `translate_text` mendukung Google Translate dan klien Python resmi DeepL melalui `provider=auto`, `provider=deepl`, atau `provider=google`.
- Definisi alat tersedia dalam 37 bahasa lokal ditambah bahasa Inggris (total 38), dengan penanda tempat dan pengenal teknis tetap dipertahankan.

Suara full-duplex tersedia melalui OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live,
dan Bedrock Nova Sonic, dengan pembatalan gema AEC3 opsional dan pemanggilan fungsi realtime yang dibatasi demi keamanan.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Dokumentasi

| Topik | Dokumentasi |
|---|---|
| Variabel lingkungan | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Arsitektur dan invarian | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Alat repositori | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| Kasus penggunaan IoT | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Alat komunikasi | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Auto-pilot | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| Ekstensi VS Code | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Panduan pengembang | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Alur alat | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## Pengembangan dan kontribusi

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Jalankan pemeriksaan sebelum PR:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

Untuk alur kerja pengembangan lengkap, lihat [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md).

Laporan bug, ide fitur, perbaikan dokumentasi, terjemahan, alat, skill, dan pull request dipersilakan.
Harap buka issue atau diskusi sebelum melakukan perubahan besar. Baca [Developer Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
dan jalankan pemeriksaan di atas sebelum mengirimkan pull request.

## Lisensi

Dilisensikan di bawah [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
