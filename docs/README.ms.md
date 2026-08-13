<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Universal AI Gateway</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Persekitaran anda, kebebasan anda.
</p>

<p align="center">
  Operasi fail / Carian web / Penjanaan & analisis imej / Pengekstrakan PDF & Excel / Kawalan IoT / Penyepaduan MCP<br>
  24 pembekal / 3 UI / Perlaksanaan alat selari / Pasaran Kemahiran Ejen
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Baca ini dalam bahasa anda</a>
</p>

______________________________________________________________________

## Mengapa uag?

**Berhenti dari kunci masuk vendor.** Kebanyakan pembantu AI mengikat anda dengan pembekal atau perkhidmatan awan tertentu. uag berbeza.

- **Berjalan secara setempat** pada mesin anda. Data anda kekal bersama anda (kecuali panggilan API yang anda buat).
- **Kebebasan pembekal**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 pembekal, semuanya boleh diakses daripada satu antara muka. Tukar antara mereka dengan mengkonfigurasi semula pembolehubah persekitaran — tiada pemasangan semula, tiada penghijrahan.
- **229 alatan**: Fail I/O, carian web, penjanaan imej, Gmail, pengimbasan peranti BLE, penyepaduan pelayan MCP — **130 ditandakan secara statik selamat selari** (sehingga 8 dilaksanakan serentak melalui kumpulan benang, boleh dikonfigurasikan melalui `UAGENT_PARALLEL_WORKERS`). Apabila LLM melancarkan berbilang panggilan alat serentak, uag menyamakannya secara automatik.
- **3 UI + A2A**: CLI, GUI, Web dan protokol Ejen-ke-Ejen. Enjin yang sama, mana-mana antara muka.
- **IoT sedia**: SwitchBot, ECHONET Lite, Matter, UPnP — mengawal peranti rumah anda melalui AI.
- **Kemahiran Ejen**: Pasang kemahiran yang dibina komuniti daripada pasaran. Panjangkan uag tanpa henti.

uag ialah **pembantu AI anda mengikut syarat anda**. Tidak terikat dengan pembekal, tidak terikat pada antara muka, tidak terikat pada platform.

## Mula Pantas

```bash
pip install uag
uag
```

Pada pelancaran pertama, wizard persediaan membimbing anda melalui konfigurasi pembekal.
Lihat [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) untuk semua pembolehubah persekitaran.

## Suara Masa Nyata dan AEC3

Mod suara masa nyata menyokong OpenAI Realtime, Azure OpenAI GPT Realtime, xAI Grok Voice API, Google Gemini Multimodal Live API dan Amazon Bedrock Nova Sonic dengan mikrofon dupleks penuh dan I/O pembesar suara. Bahagian belakang `pywebrtc-audio` AEC3 yang diperlukan dipasang secara automatik dan SDK penstriman dua arah pilihan Bedrock dipasang secara automatik hanya apabila pembekal Bedrock dipilih:

```bash
python scheck.py realtime
```

Saluran paip AEC3 menerima isyarat mikrofon sebenar (`near`) dan audio sebenarnya diserahkan kepada pembesar suara (`far`) supaya pembantu boleh mendengar semasa bercakap. Dayakan diagnostik hanya apabila menyiasat isu audio:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### Panggilan Fungsi Masa Nyata OpenAI

OpenAI Realtime menyokong integrasi Panggilan Fungsi terhad keselamatan. Penyesuai masa nyata semasa mendedahkan `get_current_time` baca sahaja secara automatik. Alat yang merosakkan dan kawalan peranti tidak didedahkan tanpa senarai kebenaran dan aliran pengesahan yang jelas. Masa nyata Grok menggunakan penyesuai berasingan dan tidak menggunakan laluan panggilan fungsi khusus OpenAI ini.

## Ciri-ciri

### 🧠 Seni Bina Berbilang Penyedia

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Foto: Enjin Gerbang) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (FIRAU AIGU) / Sakana AI (FIRAU AIGU).

Semua pembekal berkongsi set alat dan antara muka yang sama. Tukar dengan menetapkan `UAGENT_PROVIDER` — tiada perubahan kod, tiada pemasangan berasingan.

### ⚡ Perlaksanaan Alat Selari

Apabila LLM meminta berbilang alatan secara serentak, uag **menyamakannya secara automatik** mereka.
130 alatan ditandakan secara statik `x_parallel_safe` dan laksanakan serentak melalui `ThreadPoolExecutor` (8 utas secara lalai; tetapkan `UAGENT_PARALLEL_WORKERS` untuk berubah).

**Contoh**: Tanya "Semak cuaca di ibu kota Nordic" → LLM menembak `search_web` × 5 negara → kesemua 5 carian dijalankan secara selari → hasil dikumpul dalam satu kelompok.

Kiraan semasa adalah berdasarkan modul alat yang mentakrifkan `TOOL_SPEC` (pada masa ini 229, termasuk 2 alat bersandarkan Karat dalam `src/uagent/tools_rust/`). `http_request` menggunakan keselamatan sensitif kaedah: Panggilan `GET`/`HEAD`/`OPTIONS` mungkin berjalan selari, manakala kaedah tulis kekal bersiri.

Alat baca sahaja (carian fail, pengiraan cincang, penyenaraian direktori, terjemahan, pertanyaan DB, dll.) diselaraskan secara agresif.

### 🧩 Sistem Pemalam (Serasi Kod Claude)

uagent melaksanakan **sistem pemalam yang serasi Kod Claude**. Pemalam menggabungkan kemahiran, ejen, pelayan MCP, cangkuk dan banyak lagi ke dalam direktori serba lengkap dengan manifes `.claude-plugin/plugin.json`.

**Komponen yang disokong**: Kemahiran, Sub-agen, pelayan MCP, Cangkuk (12 peristiwa kitaran hayat), arahan Slash, Gaya Output, UserConfig, Ketergantungan, Saluran, Pasaran

**Arahan CLI**:

```
:plugin list                         # List installed plugins
:plugin install <source> [--scope]   # Install (dir/zip/git/http)
:plugin install <name>@<marketplace>  # Install from marketplace
:plugin remove <name>                # Uninstall
:plugin enable/disable <name>        # Toggle
:plugin marketplace add/remove/list  # Manage marketplaces
:plugin init <name>                  # Scaffold new plugin
```

Lihat [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) untuk dokumentasi penuh.

### 🔄 Kesinambungan Sesi

- **Tukar penyedia pertengahan sesi** dengan `UAGENT_PROVIDER` — sejarah perbualan dikekalkan.
- **Muat semula sesi lepas** dengan `:load <index>` — sambung semula dari tempat anda berhenti.
- **Caching hasil alat** mengelakkan pelaksanaan semula yang berlebihan apabila panggilan alat yang sama berulang.

### 🛠 229 Alat

| Kategori | Alatan |
|---|---|
| **Operasi Fail** | baca/tulis/buat/padam/cari/grep/cincang/zip, jenis_fail, parse_eml (fail.eml) |
| **Web** | fetch_url, search_web, screenshot, browser_playwright, `public_transit_route` ([panduan](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **Media** | generate_image, analysis_image, img2img, audio_speech, audio_transcribe |
| **Dokumen** | Pengekstrakan PDF/PPTX/DOCX/RTF/ODT, Pengekstrakan berstruktur Excel |
| **Ramalan** | Ramalan siri masa dengan 9 model (AutoARIMA, Nabi, LightGBM, CatBoost, TimesFM, dll.), pemilihan model automatik, penjanaan plot, i18n |
| **Komunikasi** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook, **pybitchat** (BLE Mesh) — lihat [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) dan [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP, reverse_geocode |
| **API Cloud** | `aws_api`, `gcp_api`, `azure_api` — operasi AWS generik, Google Cloud dan API Azure; operasi tulis memerlukan pengesahan yang jelas |
| **Alat Pembangun** | git_ops, git_review, security_scan, coverage_report, python_compile, lint_format, run_tests, db_query, **29 navigator kod sumber (keluarga idx)** |
| **MCP** | Sambung ke pelayan MCP luaran, senaraikan alatan, jalankan — [OAuth / Proxy guide](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Komunikasi ejen-ke-ejen (dengan kejadian uag lain atau pelayan serasi A2A) |
| **Sistem** | env vars, spesifikasi sistem, masa, pengiraan tarikh, [kuantiti](docs/QUANTITIES.md), [geodesic_distance](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **Nav Sumber** | **29 alat idx** untuk Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — dapatkan indeks fungsi/kelas atau definisi khusus tanpa membaca keseluruhan fail |

#### Semakan dan liputan repositori

- `git_review`: meringkaskan perubahan Git, fail berisiko, calon ujian dan penemuan rahsia tanpa mendedahkan nilai rahsia.
- `security_scan`: imbas fail repositori untuk kemungkinan rahsia dan fail konfigurasi berisiko.
- `coverage_report`: jalankan dan normalkan liputan untuk Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift dan Dart/Flutter.
- Kebergantungan perlindungan yang hilang boleh dipasang secara automatik apabila pelaksanaan diminta; `dry_run` tidak pernah memasang pakej.

Lihat [Alat Analisis Repositori](docs/REPOSITORY_TOOLS.md) untuk parameter, output dan butiran keselamatan.

### 🖥 4 Antara Muka + Sambungan Kod VS

| Mod | Perintah | Tujuan |
|---|---|---|
| **CLI** | `uag` | Operasi berasaskan terminal pantas |
| **GUI** | `uagg` | UI Desktop melalui tkinter |
| **Web** | `uagw` | Akses berasaskan pelayar |
| **Pelayan A2A** | `uaga` | Protokol Agent2Agent untuk komunikasi berbilang ejen |
| **Kod VS** | — | [Sambungan](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) dengan Panel Sembang, Terangkan, Refactor, Betulkan Ralat dan Paparan Pokok Alat |

Lihat [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) untuk mendapatkan butiran tentang sambungan Kod VS — pemasangan, arahan, ikatan kekunci dan konfigurasi.

### 🏠 Kawalan Peranti IoT

- **BACnet**: Baca/tulis peranti BACnet/IP (HVAC, pencahayaan, meter kuasa). Langganan COV untuk pemberitahuan tolak
- **Modbus TCP**: Baca/tulis pegangan/input daftar dan gegelung. Pemantauan perubahan berasaskan pengundian
- **OPC UA**: Semak imbas ruang alamat, baca/tulis pembolehubah, langgan perubahan data
- **SwitchBot**: Kawalan kelompok awan & imbasan/kawalan BLE. Langganan berasaskan pengundian
- **ECHONET Lite**: Temui, kawal dan langgan pemberitahuan INF daripada peralatan rumah (AC, lampu, pemanas air, dll.)
- **Perkara**: Kawalan baca/tulis + langganan atribut untuk pemantauan perubahan keadaan
- **UPnP**: Penemuan peranti & pemajuan port IGD

Lihat [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Pasaran Kemahiran Ejen

`:skills mp_search` untuk menyemak imbas [SkillsMP](https://skillsmp.com) dan [ClawHub](https://clawhub.ai) untuk kemahiran komuniti.
Pasang dan lanjutkan keupayaan uag dengan cepat.

### 🤖 Auto-Pilot (`:auto`)

uag boleh **berautonomi mengejar matlamat merentasi berbilang pusingan LLM**. Sesuai untuk tugasan yang kompleks dan berbilang langkah yang memerlukan penghalusan berulang.

- **Cara ini berfungsi**: Setiap pusingan mempunyai pertanyaan utama (Langkah A) diikuti dengan penghakiman penyemak (Langkah B) yang memutuskan "SELESAI atau TERUSKAN?"
- **Pembekal yang sama, API yang sama**: Pertimbangan penyemak menggunakan laluan kod yang sama sebagai pertanyaan utama — termasuk sokongan API Respons.
- **LLM hakim berasingan** (pilihan): Tetapkan `UAGENT_AP_PROVIDER` untuk menggunakan pembekal/model yang berbeza untuk penyemak (mis. gunakan model yang lebih murah untuk menilai).
- **Keluar pada bila-bila masa**: Tekan kekunci `x` untuk berhenti serta-merta, walaupun pada pertengahan tindak balas. Atau biarkan penyemak membuat keputusan apabila matlamat dicapai.
- **Boleh dikonfigurasikan**: `--max-rounds N` untuk mengawal belanjawan.

Lihat [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) untuk dokumentasi penuh.

### 🧩 Pengurus Negeri Kumpulan

uag boleh menjejaki kemajuan merentas tugasan berbilang fail yang berjalan lama. Apabila LLM memproses berpuluh-puluh fail, `batch_state` mengekalkan senarai fail yang belum selesai, lengkap dan gagal ke cakera. Jika sesi tamat atau masa pusingan tamat, larian seterusnya disambung semula dari tempat ia berhenti — tiada apa yang hilang.

### 🛡 Manusia-dalam-Gelung

`human_ask` membenarkan LLM berhenti seketika dan meminta pengesahan anda sebelum melakukan operasi yang merosakkan (pemadaman fail, timpa ganti, arahan shell). Anda kekal dalam kawalan.

### 🛑 Gangguan (kunci c / butang Berhenti)

Hentikan penjanaan tindak balas LLM pada bila-bila masa dan suntikan arahan berhenti kembali ke LLM.

| Antara muka | Bagaimana untuk mengganggu |
|---|---|
| **CLI** | Tekan kekunci `c` semasa penstriman LLM — respons semasa berhenti dan `"Stop"` dihantar sebagai mesej pengguna supaya LLM bertindak balas dengan sewajarnya |
| **UI WEB** | Klik butang merah **■ Berhenti** (muncul secara automatik semasa pemprosesan LLM) |
| **GUI Desktop** | Klik butang **■** merah (muncul secara automatik semasa pemprosesan LLM) |

Sampukan berfungsi sebagai "suntikan segera": bukannya hanya menggugurkan, ia menyuap `"Stop"` kembali ke LLM sebagai mesej pengguna, membolehkannya membuat kesimpulan atau mengakui gangguan dengan anggun.

Tekan kekunci `x` untuk keluar dari mod auto-pilot (lihat [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Automasi Penyemak Imbas & Pemeriksa Web

Dua alatan pelengkap berasaskan Drama:

- **browser_playwright**: Automatikkan sesi penyemak imbas sebenar — navigasi, klik, isi borang, ekstrak data, kendalikan aliran berbilang halaman. Berfungsi tanpa kepala atau berkepala.
- **playwright_inspector**: Rakam peralihan penyemak imbas, tangkap syot kilat DOM dan tangkapan skrin pada setiap langkah. Berguna untuk menyahpepijat interaksi web atau mengaudit perubahan halaman dari semasa ke semasa.

### 🔄 Pemuatan Alat Dinamik

`tool_catalog` dan `tool_load` membolehkan anda menemui dan mendayakan alatan pada masa jalan.
Tidak perlu memuatkan semuanya semasa permulaan — aktifkan hanya apa yang anda perlukan, apabila anda memerlukannya.

### 🦀 Alat Asli Karat

`uuid_gen` dan `slugify` dilaksanakan dalam Rust (melalui PyO3) untuk prestasi.
Ia dimuatkan terus dari `.pyd` pra-bina — **tiada `pip install` diperlukan**.

Pembangun luar juga boleh menghantar alatan berasaskan Rust: letakkan `.pyd` di sebelah
pembalut `.py`, gunakan `load_rust_pyd()` daripada `uagent.tools.rust_helper`, dan
pengguna mendapat alat tanpa sebarang kebergantungan tambahan. Lihat
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日本語 / Bahasa Inggeris / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / dan banyak lagi.
Tetapkan `UAGENT_LANG` untuk bertukar. Lihat [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) untuk menambah tempat baharu.

Terjemahan README ini tersedia dalam [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Pembolehubah Persekitaran Disulitkan

Simpan kunci dan rahsia API dalam `.env.sec` — fail `.env` yang disulitkan.
Urus dengan `uag_envsec`.

## Konfigurasi & Butiran

- **Pembolehubah persekitaran**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Wizard persediaan**: `python -m uagent.setup_cli`
- **Env yang disulitkan**: `uag_envsec` — menyulitkan `.env` sebagai `.env.sec`
- **Responses API**: Tetapkan `UAGENT_RESPONSES=1` untuk mod API Respons (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Didayakan secara automatik untuk Sakana AI (Fugu).
- **Dokumen pembangun**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Aliran alat**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — cara alatan dihantar ke LLM (topeng genre, katalog_alat, GPT-5.4+ carian alat asli)
- **Petua LLM kecil**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Falsafah Projek

uag bercita-cita untuk menjadi **AI anda, pada mesin anda, mengikut syarat anda.**

- Tiada pergantungan SaaS — berjalan secara setempat
- Tiada kunci masuk pembekal — tukar bila-bila masa
- Tiada kunci masuk UI — CLI / GUI / Web / A2A
- Tiada kunci masuk ciri — lanjutkan dengan alatan dan kemahiran

Pengalaman ejen AI percuma, bebas daripada kunci masuk vendor.

### ✨ Cipta Alat Anda Sendiri

Menulis alat baharu untuk uag adalah mudah — buat satu fail `.py` dengan
`TOOL_SPEC` dan `run_tool()`, letakkannya dalam `UAGENT_EXTERNAL_TOOLS_DIR`, dan
ia segera tersedia. Untuk pembangun Rust, hantarkan `.pyd` pra-bina dengan
sifar kebergantungan tambahan untuk pengguna.

Lihat [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
untuk panduan langkah demi langkah.

## Menyumbang

Sumbangan dialu-alukan! Laporan pepijat, cadangan ciri, penambahbaikan dokumentasi, terjemahan dan permintaan tarik — semuanya dihargai.

- **Isu**: Buka isu GitHub untuk pepijat atau permintaan ciri.
- **Tarik permintaan**: Buat repo, buat perubahan anda dan serahkan PR. Lihat [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) untuk persediaan pembangunan dan garis panduan.
- **Terjemahan**: Terjemahan README dan penambahan tempat adalah dialu-alukan. Lihat [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Alat & Kemahiran**: Pemalam alat baharu dan Kemahiran Ejen boleh disumbangkan melalui pasaran.

### Pemeriksaan pembangunan (sebelum PR)

```bash
python -m py_compile src/uagent/
ruff format src/ && ruff check src/
mypy src/uagent
pytest -q tests/<affected_area>
```

Selepas suntingan setempat (`.po`): `python scripts/compile_locales.py` dan `python scripts/po_qc_summary.py`.

Dasar masa jalan (butiran dalam [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) §6.1): pembantu menaikkan bukannya `sys.exit`; hos alat menukar alat `SystemExit`/`Exception` menjadi rentetan ralat supaya satu alat tidak boleh mematikan proses. Keluar cepat gagal permulaan kekal disengajakan.
