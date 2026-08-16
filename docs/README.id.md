<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Gerbang AI Universal</h1>

<p align="center">
 <b>U</b>universal <b>A</b>I <b>G</b>ateway — Lingkungan Anda, kebebasan Anda.
</p>

<p align="center">
 Operasi file / Web pencarian / Pembuatan & analisis gambar / Ekstraksi PDF & Excel / Kontrol IoT / integrasi MCP<br>
 24 penyedia / 3 UI / Eksekusi alat paralel / Keahlian Agen pasar
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a href="https://pypi.org/project/uag/">PyPI</a>
 ·
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Baca ini dalam bahasa Anda</a>
</p>

______________________________________________________________________

## Mengapa uag?

**Membebaskan diri dari penguncian vendor.** Sebagian besar asisten AI mengikat Anda ke penyedia atau layanan cloud tertentu. uag berbeda.

- **Berjalan secara lokal** di mesin Anda. Data Anda tetap bersama Anda (kecuali API panggilan yang Anda lakukan).
- **Kebebasan penyedia**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 penyedia, semuanya dapat diakses dari satu antarmuka. Bertukar di antara keduanya dengan mengonfigurasi ulang variabel lingkungan — tanpa instal ulang, tanpa migrasi.
- **222 alat**: I/O file, penelusuran web, pembuatan gambar, Gmail, pemindaian perangkat BLE, MCP integrasi server — **130 ditandai secara statis aman paralel** (hingga 8 dijalankan secara bersamaan melalui kumpulan thread, dapat dikonfigurasi melalui `UAGENT_PARALLEL_WORKERS`). Saat LLM mengaktifkan beberapa panggilan alat sekaligus, uag secara otomatis memparalelkannya.
- **3 UI + A2A**: CLI, GUI, Web, dan protokol Agen-ke-Agen. Mesin yang sama, antarmuka apa pun.
- **Siap IoT**: SwitchBot, ECHONET Lite, Matter, UPnP — kendalikan perangkat rumah Anda melalui AI.
- **Keterampilan Agen**: Instal keterampilan yang dibangun komunitas dari pasar. Perpanjang uag tanpa henti.

uag adalah **asisten AI sesuai keinginan Anda**. Tidak terikat pada penyedia, tidak terikat pada antarmuka, tidak terikat pada platform.

## Mulai Cepat

```bash
pip install uag
uag
```

Pada peluncuran pertama, wizard pengaturan memandu Anda melalui konfigurasi penyedia.
Lihat [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) untuk semua variabel lingkungan.

## Computer Use

Computer Use ikut serta dan mendukung Playwright runtime browser yang terlihat
dan runtime desktop. Bila diaktifkan, kedua runtime akan dibuat dan didaftarkan;

```bat
set UAGENT_COMPUTER_USE=1
```

Gunakan `desktop` untuk memilih runtime desktop OS. Runtime sumber daya
ditutup bersama saat keluar normal, `Ctrl-C`, dan penghentian proses. Set
`UAGENT_COMPUTER_HEADLESS=1` untuk CI berbasis browser atau tes asap.
Lihat [docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
untuk detail integrasi dan keamanan.

## Suara Realtime dan AEC3

Mode suara realtime mendukung OpenAI Realtime, Azure OpenAI GPT Realtime, xAI Grok Voice API, Google Gemini Multimodal Live API, dan Amazon Bedrock Nova Sonic dengan mikrofon dupleks penuh dan I/O speaker. Backend AEC3 `pywebrtc-audio` yang diperlukan diinstal secara otomatis, dan SDK streaming dua arah opsional Bedrock diinstal secara otomatis hanya ketika penyedia Bedrock dipilih:

```bash
python scheck.py realtime
```

Pipa AEC3 menerima sinyal mikrofon sebenarnya (`dekat`) dan audio benar-benar diserahkan ke speaker (`far`) sehingga asisten dapat mendengarkan sambil berbicara. Aktifkan diagnostik hanya ketika menyelidiki masalah audio:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Panggilan Fungsi Realtime

OpenAI Realtime mendukung integrasi Panggilan Fungsi dengan keamanan terbatas. Adaptor waktu nyata saat ini menampilkan `get_current_time` yang hanya dapat dibaca secara otomatis. Alat perusak dan kontrol perangkat tidak akan terekspos tanpa alur konfirmasi dan daftar izin yang jelas. Grok realtime menggunakan adaptor terpisah dan tidak menggunakan jalur panggilan fungsi khusus OpenAI ini.

## Fitur

### 🧠 Arsitektur Multi-Penyedia

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

Semua penyedia berbagi perangkat dan antarmuka yang sama. Beralih berdasarkan pengaturan `UAGENT_PROVIDER` — tidak ada perubahan kode, tidak ada instalasi terpisah.

#### Ollama dan llama.cpp

Ollama dan llama.cpp adalah penyedia terpisah. Ollama menggunakan layanan dan manajemen modelnya sendiri, sementara `llama.cpp` terhubung ke `server llama` titik akhir yang kompatibel dengan OpenAI:

```bash
# Ollama
UAGENT_PROVIDER=ollama
UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
UAGENT_OLLAMA_DEPNAME=llama3.1

# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY=dummy
```

Penyedia llama.cpp menggunakan jalur yang kompatibel dengan Penyelesaian Obrolan. Pertahankan `UAGENT_RESPONSES=0` kecuali proxy yang kompatibel dikonfigurasi.

### ⚡ Eksekusi Alat Paralel

Saat LLM meminta beberapa alat secara bersamaan, uag **secara otomatis memparalelkannya**.
130 alat ditandai secara statis `x_parallel_safe` dan dijalankan secara bersamaan melalui `ThreadPoolExecutor` (8 thread secara default; setel `UAGENT_PARALLEL_WORKERS` untuk berubah).

**Contoh**: Tanyakan "Periksa cuaca di ibu kota Nordik" → LLM mengaktifkan `search_web` × 5 negara → kelima penelusuran dijalankan secara paralel → hasil dikumpulkan dalam satu kelompok.

Penghitungan saat ini didasarkan pada modul alat yang menentukan `TOOL_SPEC` (saat ini 222, termasuk 2 Alat yang didukung karat di `src/uagent/tools_rust/`). `http_request` menggunakan keamanan yang sensitif terhadap metode: panggilan `GET`/`HEAD`/`OPTIONS` dapat berjalan secara paralel, sedangkan metode tulis tetap serial.

Alat baca-saja (pencarian file, penghitungan hash, daftar direktori, terjemahan, kueri DB, dll.) diparalelkan secara agresif.

### 🧩 Sistem Plugin (Kompatibel dengan Kode Claude)

uagent mengimplementasikan **Claude Sistem plugin yang kompatibel dengan kode**. Plugin menggabungkan keterampilan, agen, server MCP, hook, dan lainnya ke dalam direktori mandiri dengan manifes `.claude-plugin/plugin.json`.

**Komponen yang didukung**: Keterampilan, Sub-agen, server MCP, Hooks (12 peristiwa siklus hidup), perintah Slash, Gaya keluaran, userConfig, Dependensi, Saluran, Marketplaces

**CLI perintah**:

```
:daftar plugin # Daftar plugin yang diinstal
:instal plugin <sumber> [--scope] # Instal (dir/zip/git/http)
:instal plugin <nama>@<marketplace> # Instal dari pasar
:plugin hapus <nama> # Uninstall
:plugin aktifkan/nonaktifkan <nama> # Toggle
:plugin pasar tambah/hapus/daftar # Kelola pasar
:plugin init <nama> # Perancah plugin baru
```

Lihat [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) untuk dokumentasi lengkap.

### 🔄 Kontinuitas Sesi

- **Beralih penyedia pertengahan sesi** dengan `UAGENT_PROVIDER` — riwayat percakapan dipertahankan.
- **Muat ulang sesi sebelumnya** dengan `:load <index>` — lanjutkan dari bagian terakhir yang Anda tinggalkan.
- **Caching hasil alat** menghindari eksekusi ulang yang berlebihan saat panggilan alat yang sama diulang.

### 🛠 229 Alat

| Kategori | Alat |
|---|---|
| **Operasi File** | baca/tulis/buat/hapus/search/grep/hash/zip, file_type, parse_eml (file .eml), `path_alias` |
| **Web** | ambil_url, cari_web, tangkapan layar, browser_playwright, `url_alias`, `public_transit_route` ([panduan](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **Media** | menghasilkan_gambar, menganalisis_gambar, img2img, audio_speech, audio_transcribe |
| **Dokumen** | Ekstraksi PDF/PPTX/DOCX/RTF/ODT, ekstraksi terstruktur Excel |
| **Prakiraan** | Perkiraan deret waktu dengan 9 model (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, dll.), pemilihan model otomatis, pembuatan plot, i18n |
| **Komunikasi** | gmail_send, gmail_read, bluesky, discord_channel, team_webhook, **pybitchat** (BLE Mesh) — lihat [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) dan [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Materi, UPnP, reverse_geocode |
| **Cloud API** | `aws_api`, `gcp_api`, `azure_api` — operasi generik AWS, Google Cloud, dan Azure API; operasi tulis memerlukan konfirmasi eksplisit |
| **Alat Pengembang** | workspace_status, git_ops, git_review, security_scan, coverage_report, python_compile, lint_format, run_tests, db_query, **29 navigator kode sumber (keluarga idx)** |
| **MCP** | Hubungkan ke server MCP eksternal, buat daftar alat, jalankan — [Panduan OAuth / Proxy](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Komunikasi agen-ke-agen (dengan instance uag lain atau server yang kompatibel dengan A2A) |
| **Sistem** | env vars, spesifikasi sistem, waktu, penghitungan tanggal, [jumlah](docs/QUANTITIES.md), [jarak_geodesik](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **Nav Sumber** | **29 alat idx** untuk Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — dapatkan indeks fungsi/kelas atau definisi spesifik tanpa membaca keseluruhan file |

#### Tinjauan dan cakupan repositori

- `workspace_status`: laporkan Git ruang kerja yang aktif cabang, perubahan, status sinkronisasi upstream, runtime Python, dan penanda proyek umum tanpa mengubah file.
- `git_review`: meringkas perubahan Git, file berisiko, kandidat pengujian, dan temuan rahasia tanpa mengungkap nilai rahasia.
- `security_scan`: memindai file repositori untuk mengetahui kemungkinan rahasia dan file konfigurasi berisiko.
- `coverage_report`: menjalankan dan menormalkan cakupan untuk Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift, dan Dart/Flutter.
- Dependensi cakupan yang hilang dapat diinstal secara otomatis saat eksekusi diminta; `dry_run` tidak pernah menginstal paket.

Lihat [Alat Analisis Repositori](docs/REPOSITORY_TOOLS.md) untuk parameter, keluaran, dan detail keamanan.

Lihat [Alat Analisis Repositori](docs/PATH_URL_ALIASES.md) untuk memperpendek jalur file dan URL berulang dalam argumen alat.

### 🖥 4 Antarmuka + Kode VS Ekstensi

| Modus | Perintah | Tujuan |
|---|---|---|
| **CLI** | `uag` | Pengoperasian cepat berbasis terminal |
| **GUI** | `uagg` | UI desktop melalui tkinter |
| **Web** | `uagw` | Akses berbasis browser |
| **A2A Server** | `uaga` | Protokol Agent2Agent untuk komunikasi multi-agen |
| **Kode VS** | — | [Ekstensi](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) dengan Panel Obrolan, Penjelasan, Pemfaktoran Ulang, Perbaiki Kesalahan, dan Tampilan Pohon Alat |

Lihat [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) untuk detail tentang ekstensi VS Code — instalasi, perintah, pengikatan kunci, dan konfigurasi.

### 🏠 Kontrol Perangkat IoT

- **BACnet**: Membaca/menulis perangkat BACnet/IP (HVAC, penerangan, pengukur daya). Berlangganan COV untuk pemberitahuan push
- **Modbus TCP**: Baca/tulis holding/input register dan koil. Pemantauan perubahan berbasis polling
- **OPC UA**: Telusuri ruang alamat, baca/tulis variabel, berlangganan perubahan data
- **SwitchBot**: Kontrol batch cloud & pemindaian/kontrol BLE. Langganan berbasis polling
- **ECHONET Lite**: Temukan, kontrol, dan berlangganan notifikasi INF dari peralatan rumah tangga (AC, lampu, pemanas air, dll.)
- **Materi**: Kontrol baca/tulis + langganan atribut untuk pemantauan perubahan status
- **UPnP**: Penemuan perangkat & penerusan port IGD

Lihat [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` untuk menjelajahi [SkillsMP](https://skillsmp.com) dan [ClawHub](https://clawhub.ai) untuk komunitas keterampilan.
Menginstal dan memperluas kemampuan uag dengan cepat.

### 🤖 Auto-Pilot (`:auto`)

uag dapat **secara mandiri mengejar sasaran dalam beberapa putaran LLM**. Sempurna untuk tugas multi-langkah kompleks yang memerlukan penyempurnaan berulang.

- **Cara kerjanya**: Setiap putaran memiliki kueri utama (Langkah A) diikuti dengan penilaian peninjau (Langkah B) yang memutuskan "SELESAI atau LANJUTKAN?"
- **Penyedia yang sama, API yang sama**: Penilaian peninjau menggunakan jalur kode yang sama dengan kueri utama — termasuk dukungan Respons API.
- **Juri terpisah LLM** (opsional): Setel `UAGENT_AP_PROVIDER` untuk menggunakan penyedia/model yang berbeda untuk pengulas (misalnya, gunakan model yang lebih murah untuk menilai).
- **Keluar kapan saja**: Tekan tombol `x` untuk segera berhenti, bahkan di tengah respons. Atau biarkan peninjau memutuskan kapan sasaran tercapai.
- **Dapat dikonfigurasi**: `--max-rounds N` untuk mengontrol anggaran.

Lihat [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) untuk dokumentasi lengkap.

### 🧩 Status Batch Manajer

uag dapat melacak kemajuan tugas multi-file yang sudah berjalan lama. Saat LLM memproses lusinan file, `batch_state` menyimpan daftar file yang tertunda, selesai, dan gagal ke disk. Jika sesi berakhir atau putaran habis, proses berikutnya akan dilanjutkan dari titik berhentinya — tidak ada yang hilang.

### 🛡 Human-in-the-Loop

`human_ask` memungkinkan LLM berhenti sejenak dan meminta konfirmasi Anda sebelum melakukan operasi destruktif (penghapusan file, penimpaan, perintah shell). Anda tetap memegang kendali.

### 🛑 Interupsi (tombol c / tombol Stop)

Hentikan pembuatan respons LLM kapan saja dan masukkan perintah stop kembali ke LLM.

| Antarmuka | Cara menyela |
|---|---|
| **CLI** | Tekan tombol `c` selama LLM streaming — respons saat ini berhenti, dan `"Stop"` dikirim sebagai pesan pengguna sehingga LLM merespons dengan tepat |
| **UI WEB** | Klik tombol merah **■ Stop** (muncul otomatis selama LLM pemrosesan) |
| **Desktop GUI** | Klik tombol merah **■** (muncul secara otomatis selama pemrosesan LLM) |

Interupsi berfungsi sebagai "injeksi cepat": alih-alih hanya dibatalkan, interupsi akan mengumpankan `"Stop"` kembali ke LLM sebagai pesan pengguna, sehingga memungkinkannya mengakhiri atau menerima interupsi dengan baik.

Tekan tombol `x` untuk keluar dari mode pilot otomatis (lihat [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Otomatisasi Browser & Web Inspektur

Dua alat berbasis Playwright yang saling melengkapi:

- **browser_playwright**: Mengotomatiskan sesi browser sebenarnya — navigasi, klik, mengisi formulir, mengekstrak data, menangani aliran multi-halaman. Bekerja tanpa kepala atau kepala.
- **playwright_inspector**: Rekam transisi browser, ambil snapshot DOM dan tangkapan layar di setiap langkah. Berguna untuk men-debug interaksi web atau mengaudit perubahan halaman seiring waktu.

### 🔄 Pemuatan Alat Dinamis

`tool_catalog` dan `tool_load` memungkinkan Anda menemukan dan mengaktifkan alat saat runtime.
Tidak perlu memuat semuanya saat startup — aktifkan hanya yang Anda perlukan, saat Anda memerlukannya.

### 🦀 Rust Native Tools

`uuid_gen` dan `slugify` diimplementasikan di Rust (melalui PyO3) untuk kinerja.
Mereka memuat langsung dari `.pyd` yang telah dibuat sebelumnya — **tidak diperlukan `pip install`**.

Pengembang eksternal juga dapat mengirimkan alat berbasis Rust: letakkan `.pyd` di sebelah
wrapper `.py`, gunakan `load_rust_pyd()` dari `uagent.tools.rust_helper`, dan
pengguna mendapatkan alat tersebut tanpa ketergantungan tambahan. Lihat
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日本語 / Bahasa Inggris / 简体中文 /繁體中文 / 한국어 / Español / Français / Русский / dan masih banyak lagi.
Setel `UAGENT_LANG` untuk beralih. Lihat [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) untuk menambahkan lokal baru.

Terjemahan README ini tersedia dalam bahasa [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Variabel Lingkungan Terenkripsi

Simpan kunci dan rahasia API di `.env.sec` — file `.env` terenkripsi.
Kelola dengan `uag_envsec`.

## Konfigurasi & Detail

- **Variabel lingkungan**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Wizard penyiapan**: `python -m uagent.setup_cli`
- **Env terenkripsi**: `uag_envsec` — mengenkripsi `.env` sebagai `.env.sec`
- **Respons API**: Setel `UAGENT_RESPONSES=1` untuk mode Respons API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Diaktifkan secara otomatis untuk Sakana AI (Fugu).
- **Dokumen pengembang**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Alur alat**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — cara alat dikirim ke LLM (genre mask, tool_catalog, GPT-5.4+ tool_search asli)
- **Kiat kecil LLM**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

* keterampilan

Pengalaman agen AI gratis, bebas dari penguncian vendor.

### ✨ Buat Alat Anda Sendiri

Menulis alat baru untuk uag sangatlah mudah — buat satu file `.py` dengan
`TOOL_SPEC` dan `run_tool()`, letakkan di `UAGENT_EXTERNAL_TOOLS_DIR`, dan
segera tersedia. Untuk pengembang Rust, kirimkan `.pyd` yang telah dibuat sebelumnya dengan
tanpa ketergantungan tambahan untuk pengguna.

Lihat [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
untuk panduan langkah demi langkah.

## Berkontribusi

Kontribusi dipersilakan! Laporan bug, saran fitur, penyempurnaan dokumentasi, terjemahan, dan permintaan penarikan — semuanya dihargai.

- **Masalah**: Buka masalah GitHub untuk bug atau permintaan fitur.
- **Permintaan tarik**: Buat cabang repo, buat perubahan, dan kirimkan PR. Lihat [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) untuk penyiapan dan panduan pengembangan.
- **Terjemahan**: README terjemahan dan penambahan lokal dipersilakan. Lihat [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Alat & Keterampilan**: Plugin alat baru dan Keterampilan Agen dapat disumbangkan melalui pasar.

### Pemeriksaan pengembangan (sebelum PR)

Instal dependensi khusus pengujian terlebih dahulu. Mereka dijauhkan dari daftar runtime
dependency:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
```

Jalankan pemeriksaan yang sama yang digunakan oleh GitHub Tindakan sebelum mendorong:

```bash
python -m ruff check src test
python -m black --check src tes
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .
```

Untuk iterasi lokal yang lebih cepat, jalankan hanya pengujian yang terpengaruh:

```bash
pytest -q tes/<affected_area>
```

Pemeriksaan tambahan bila relevan:

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

Setelah pengeditan lokal (`.po`): `python scripts/compile_locales.py` dan `python scripts/po_qc_summary.py`.

Runtime kebijakan (detailnya ada di [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) §6.1): pembantu menaikkan, bukan `sys.exit`; host alat mengubah alat `SystemExit`/`Exception` menjadi string kesalahan sehingga satu alat tidak dapat menghentikan proses. Startup gagal-cepat keluar tetap disengaja.

## Arsitektur dan invarian operasional

Lihat [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) untuk kontrak tahan lama yang mencakup siklus hidup A2A, konteks I18N, instalasi ketergantungan opsional, keamanan alat, kemampuan penyedia, batasan kepercayaan OAuth, peristiwa terstruktur, dan verifikasi penerimaan.

## Mesin Kebijakan Perusahaan

Kebijakan tingkat organisasi untuk alat, penyedia, kredensial, server MCP, jaringan, keterampilan, dan plugin didukung. Setel `UAGENT_POLICY_FILE` ke file kebijakan JSON/YAML; lihat [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) untuk contoh konfigurasi, peran, konfirmasi, dan daftar yang diizinkan.

### Runtime pemulihan dan orkestrasi

Lihat [RESTART_RECOVERY.md](docs/RESTART_RECOVERY.md) / [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) untuk pemulihan yang tahan lama, eksekusi sadar ketergantungan, orkestrasi multi-agen, dan penggunaan A2A jarak jauh.

Lihat [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) untuk koordinasi sewa pemimpin waktu proses bersama.
