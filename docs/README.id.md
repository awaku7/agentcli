<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Gerbang AI Universal</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Your environment, your freedom.
</p>

<p align="center">
  File ops / Web search / Image generation &amp; analysis / PDF &amp; Excel extraction / IoT control / MCP integration<br>
  24 providers / 3 UIs / Parallel tool execution / Agent Skills marketplace
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

---

## Kenapa harus?

**Bebaskan diri dari penguncian vendor.** Sebagian besar asisten AI mengikat Anda ke penyedia atau layanan cloud tertentu. uag berbeda.

- **Berjalan secara lokal** di mesin Anda. Data Anda tetap bersama Anda (kecuali panggilan API yang Anda lakukan).
- **Kebebasan penyedia**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 21+ penyedia, semuanya dapat diakses dari satu antarmuka. Bertukar di antara keduanya dengan mengonfigurasi ulang variabel lingkungan — tanpa instalasi ulang, tanpa migrasi.
- **195 alat**: I/O file, penelusuran web, pembuatan gambar, Gmail, pemindaian perangkat BLE, integrasi server MCP — **111 aman secara paralel** (hingga 8 dijalankan secara bersamaan melalui kumpulan thread, dapat dikonfigurasi melalui `UAGENT_PARALLEL_WORKERS`). Saat LLM mengaktifkan beberapa panggilan alat sekaligus, uag secara otomatis memparalelkannya.
- **3 UI + A2A**: CLI, GUI, Web, dan protokol Agen-ke-Agen. Mesin yang sama, antarmuka apa pun.
- **Keterampilan Agen**: Instal keterampilan yang dibangun komunitas dari pasar. Perpanjang uag tanpa henti.

uag adalah **asisten AI sesuai keinginan Anda**. Tidak terikat pada penyedia, tidak terikat pada antarmuka, tidak terikat pada platform.

## Mulai Cepat

```bash
pip install uag
uag
```

Pada peluncuran pertama, wizard pengaturan memandu Anda melalui konfigurasi penyedia.
Lihat [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) untuk semua variabel lingkungan.

## Fitur

### 🧠 Arsitektur Multi-Penyedia

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI (Fugu)** / **Together AI** / **Vercel AI Gateway**

Semua penyedia berbagi perangkat dan antarmuka yang sama. Beralih berdasarkan pengaturan `UAGENT_PROVIDER` — tidak ada perubahan kode, tidak ada instalasi terpisah.

### ⚡ Eksekusi Alat Paralel

Saat LLM meminta beberapa alat secara bersamaan, uag **secara otomatis memparalelkannya**.
111 alat ditandai `x_parallel_safe` dan dieksekusi secara bersamaan melalui `ThreadPoolExecutor` (8 thread secara default; setel `UAGENT_PARALLEL_WORKERS` untuk diubah).

**Contoh**: Tanyakan "Periksa cuaca di ibu kota Nordik" → LLM mengaktifkan `search_web` × 5 negara → kelima penelusuran dijalankan secara paralel → hasil dikumpulkan dalam satu kelompok.

Alat read-only (pencarian file, penghitungan hash, daftar direktori, terjemahan, kueri DB, dll.) diparalelkan secara agresif.


### 🧩 Plugin System (Claude Code Compatible)

uagent implements a **Claude Code-compatible plugin system**. Plugins bundle skills, agents, MCP servers, hooks, and more into self-contained directories with a `.claude-plugin/plugin.json` manifest.

**Supported components**: Skills, Sub-agents, MCP servers, Hooks (12 lifecycle events), Slash commands, Output styles, userConfig, Dependencies, Channels, Marketplaces

**CLI commands**:
```
:plugin list                         # List installed plugins
:plugin install <source> [--scope]   # Install (dir/zip/git/http)
:plugin install <name>@<marketplace>  # Install from marketplace
:plugin remove <name>                # Uninstall
:plugin enable/disable <name>        # Toggle
:plugin marketplace add/remove/list  # Manage marketplaces
:plugin init <name>                  # Scaffold new plugin
```

See [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) for full documentation.


### 🔄 Kontinuitas Sesi

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 195 Alat

| Kategori | Alat |
|---|---|
| **Operasi File** | baca/tulis/buat/hapus/pencarian/grep/hash/zip, file_type, parse_eml (file .eml) |
| **Jaringan** | ambil_url, cari_web, tangkapan layar, browser_playwright |
| **Media** | menghasilkan_gambar, menganalisis_gambar, img2img, audio_speech, audio_transkripsikan |
| **Dokumen** | Ekstraksi PDF/PPTX/DOCX/RTF/ODT, ekstraksi terstruktur Excel |
| **Peramalan** | Peramalan deret waktu dengan 9 model (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, dll.), pemilihan model otomatis, pembuatan plot, i18n |
| **Komunikasi** | gmail_send, gmail_read, bluesky, discord_channel, team_webhook , **pybitchat** (BLE Mesh) — lihat [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) and [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md)|
| **IoT** | BACnet、Modbus TCP、OPC UA、SwitchBot（Cloud + BLE）、ECHONET Lite、Matter、UPnP、reverse_geocode |
| **Alat Pengembang** | git_ops, python_compile, lint_format, run_tests, db_query, **26 navigator kode sumber (keluarga idx)** |
| **MCP** | Hubungkan ke server MCP eksternal, daftar alat, jalankan |
| **A2A** | Komunikasi agen-ke-agen (dengan instans uag lain atau server yang kompatibel dengan A2A) |
| **Sistem** | env vars, spesifikasi sistem, waktu, perhitungan tanggal, uuid_gen, slugify ||
| **Nav Sumber** | **26 alat idx** untuk Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL — dapatkan indeks fungsi/kelas atau definisi spesifik tanpa membaca keseluruhan file |

### 🖥 4 Antarmuka + Ekstensi Kode VS

| Modus | Perintah | Tujuan |
|---|---|---|
| **KLI** | `uag` | Pengoperasian cepat berbasis terminal |
| **GUI** | `uagg` | UI Desktop melalui tkinter |
| **Jaringan** | `uagw` | Akses berbasis browser |
| **Server A2A** | `uaga` | Protokol Agent2Agent untuk komunikasi multi-agen |
| **Kode VS** | — | [Ekstensi](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) dengan Panel Obrolan, Penjelasan, Refaktor, Perbaiki Kesalahan, dan Tampilan Pohon Alat |

Lihat [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) untuk detail tentang ekstensi VS Code — instalasi, perintah, pengikatan kunci, dan konfigurasi.

### 🏠 Kontrol Perangkat IoT
- **Materi**: Pemeriksaan topologi pengontrol/jembatan/perangkat hanya-baca

Lihat [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)


### 🎯 Pasar Keterampilan Agen

`:skills mp_search` untuk menelusuri [SkillsMP](https://skillsmp.com) dan [ClawHub](https://clawhub.ai) untuk keterampilan komunitas.
Instal dan perluas kemampuan uag dengan cepat.

### 🤖 Pilot Otomatis (`:otomatis`)

uag dapat **secara mandiri mengejar tujuan di beberapa putaran LLM**. Sempurna untuk tugas-tugas kompleks dan multi-langkah yang memerlukan penyempurnaan berulang.

- **Cara kerjanya**: Setiap putaran memiliki kueri utama (Langkah A) diikuti dengan penilaian peninjau (Langkah B) yang memutuskan "SELESAI atau LANJUTKAN?"
- **Penyedia yang sama, API yang sama**: Penilaian peninjau menggunakan jalur kode yang sama dengan kueri utama — termasuk dukungan Responses API.
- **Juri LLM terpisah** (opsional): Setel `UAGENT_AP_PROVIDER` untuk menggunakan penyedia/model yang berbeda untuk pengulas (misalnya, gunakan model yang lebih murah untuk menilai).
- **Keluar kapan saja**: Tekan tombol `x` untuk segera berhenti, bahkan di tengah respons. Atau biarkan pengulas memutuskan kapan tujuannya tercapai.
- **Dapat dikonfigurasi**: `--max-rounds N` untuk mengontrol anggaran.

Lihat [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) untuk dokumentasi lengkap.

### 🧩 Manajer Status Batch

uag dapat melacak kemajuan tugas multi-file yang berjalan lama. Saat LLM memproses puluhan file, `batch_state` menyimpan daftar file yang tertunda, selesai, dan gagal ke disk. Jika sesi berakhir atau putaran habis, putaran berikutnya dilanjutkan dari titik berhentinya — tidak ada yang hilang.

### 🛡 Manusia dalam Lingkaran

`human_ask` memungkinkan LLM berhenti sejenak dan meminta konfirmasi Anda sebelum melakukan operasi destruktif (penghapusan file, penimpaan, perintah shell). Anda tetap memegang kendali.

### 🛑 Interupsi (tombol c / tombol Stop)

Hentikan pembuatan respons LLM kapan saja dan masukkan perintah stop kembali ke LLM.

| Antarmuka | Bagaimana cara menyela |
|---|---|
| **KLI** | Tekan tombol `c` selama streaming LLM — respons saat ini berhenti, dan `"Stop"` dikirim sebagai pesan pengguna sehingga LLM merespons sesuai |
| **UI WEB** | Klik tombol merah **■ Stop** (muncul secara otomatis selama pemrosesan LLM) |
| **GUI Desktop** | Klik tombol merah **■** (muncul otomatis selama pemrosesan LLM) |

Interupsi berfungsi sebagai "injeksi cepat": alih-alih dibatalkan, interupsi tersebut mengumpankan `"Stop"` kembali ke LLM sebagai pesan pengguna, sehingga memungkinkannya menyimpulkan atau mengakui interupsi dengan baik.

Tekan tombol `x` untuk keluar dari mode auto-pilot (lihat [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Otomatisasi Browser & Inspektur Web

Dua alat berbasis Penulisan Drama yang saling melengkapi:

- **browser_playwright**: Mengotomatiskan sesi browser sebenarnya — menavigasi, mengklik, mengisi formulir, mengekstrak data, menangani alur multi-halaman. Bekerja tanpa kepala atau berkepala.
- **playwright_inspector**: Rekam transisi browser, ambil cuplikan DOM dan tangkapan layar di setiap langkah. Berguna untuk men-debug interaksi web atau mengaudit perubahan halaman seiring waktu.

### 🔄 Pemuatan Alat Dinamis

`tool_catalog` dan `tool_load` memungkinkan Anda menemukan dan mengaktifkan alat saat runtime.
Tidak perlu memuat semuanya saat startup — aktifkan hanya yang Anda perlukan, saat Anda membutuhkannya.


### 🦀 Rust Native Tools

`uuid_gen` and `slugify` are implemented in Rust (via PyO3) for performance.
They load directly from a pre-built `.pyd` — **no `pip install` required**.

External developers can also ship Rust-based tools: place a `.pyd` next to the
wrapper `.py`, use ``load_rust_pyd()`` from ``uagent.tools.rust_helper``, and
users get the tool without any extra dependencies. See
[TOOL_CREATOR_GUIDE.id.md](TOOL_CREATOR_GUIDE.id.md).

### 🌐 i18n / L10n

日本語 / Inggris / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / dan masih banyak lagi.
Setel `UAGENT_LANG` untuk beralih. Lihat [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) untuk menambahkan lokal baru.

Terjemahan README ini tersedia di [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Variabel Lingkungan Terenkripsi

Simpan kunci dan rahasia API di `.env.sec` — file `.env` terenkripsi.
Kelola dengan `uag_envsec`.

## Konfigurasi & Detail

- **Variabel lingkungan**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Wizard penyiapan**: `python -m uagent.setup_cli`
- **Env terenkripsi**: `uag_envsec` — mengenkripsi `.env` sebagai `.env.sec`
- **Responses API**: Setel `UAGENT_RESPONSES=1` untuk mode Responses API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Diaktifkan secara otomatis untuk Sakana AI (Fugu).
- **Dokumen pengembang**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Tool flow**: [TOOL_FLOW.md](../src/uagent/docs/TOOL_FLOW.md)
- **Tips LLM kecil**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Filosofi Proyek

uag bercita-cita menjadi **AI Anda, di mesin Anda, sesuai keinginan Anda.**

- Tidak ada ketergantungan SaaS — berjalan secara lokal
- Tidak ada penguncian penyedia — beralih kapan saja
- Tidak ada penguncian UI — CLI / GUI / Web / A2A
- Tidak ada penguncian fitur — perluas dengan alat dan keterampilan

Pengalaman agen AI gratis, bebas dari penguncian vendor.

### ✨ Create Your Own Tools

Writing a new tool for uag is straightforward — create a single `.py` file with
`TOOL_SPEC` and `run_tool()`, place it in ``UAGENT_EXTERNAL_TOOLS_DIR``, and
it's immediately available. For Rust developers, ship a pre-built `.pyd` with
zero extra dependencies for users.

See [TOOL_CREATOR_GUIDE.id.md](TOOL_CREATOR_GUIDE.id.md)
for the step-by-step guide.

## Contributing

Contributions are welcome! Bug reports, feature suggestions, documentation improvements, translations, and pull requests — all appreciated.

- **Issues**: Open a GitHub issue for bugs or feature requests.
- **Pull requests**: Fork the repo, make your changes, and submit a PR. See [DEVELOP.md](../src/uagent/docs/DEVELOP.md) for development setup and guidelines.
- **Translations**: README translations and locale additions are welcome. See [ADD_LOCALE.md](../src/uagent/docs/ADD_LOCALE.md).
- **Tools & Skills**: New tool plugins and Agent Skills can be contributed via the marketplace.

Realtime Suara dan AEC3

## Realtime mode suara mendukung mikrofon dupleks penuh dan input/output speaker. Jika backend AEC3 hilang, uag secara otomatis menginstal pywebrtc-audio.

**Realtime providers:** OpenAI Realtime, Azure OpenAI GPT Realtime, Google Gemini Live, xAI Grok Voice, and Amazon Bedrock Nova Sonic. The Bedrock bidirectional-streaming SDK is installed automatically only when Bedrock is selected.

```bat
python scheck.py realtime
```

AEC3 menggunakan sinyal mikrofon sebenarnya (dekat) dan audio sebenarnya dikirim ke speaker (jauh). Aktifkan diagnostik hanya ketika menyelidiki masalah audio.

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime mendukung integrasi Function Calling terbatas keamanan. Adaptor saat ini menampilkan fungsi read-only get_current_time secara otomatis. Alat perusak dan kontrol perangkat memerlukan daftar izin dan alur konfirmasi yang eksplisit. Grok realtime menggunakan adaptor terpisah dan tidak menggunakan jalur Function Calling khusus OpenAI ini.
