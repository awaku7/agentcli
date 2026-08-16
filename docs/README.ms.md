<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center_4" —uag_center Gerbang</h1>

<p align="center">
 <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Persekitaran anda, kebebasan anda.
</p>

<p align="center">
 Operasi fail / Web carian / Kawalan & analisis pengekstrakan Web / PDF & Penjanaan imej & kecemerlangan imej. penyepaduan<br>
 24 pembekal / 3 UI / Perlaksanaan alat selari / Pasaran Kemahiran Ejen
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a> href="https://pypi.org/project/uag/">PyPI</a>
 ·
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Baca ini dalam bahasa anda</a>
</p>
________________
______________________
## Mengapa uag?

**Berhenti dari kunci masuk vendor.** Kebanyakan pembantu AI mengikat anda dengan pembekal atau perkhidmatan awan tertentu. uag berbeza.

- **Berjalan secara setempat** pada mesin anda. Data anda kekal bersama anda (kecuali API panggilan yang anda buat).
- **Kebebasan penyedia**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 pembekal, semuanya boleh diakses daripada satu antara muka. Bertukar antara mereka dengan mengkonfigurasi semula pembolehubah persekitaran — tiada pemasangan semula, tiada migrasi.
- **222 alatan**: Fail I/O, carian web, penjanaan imej, Gmail, pengimbasan peranti BLE, penyepaduan pelayan MCP — **130 ditandakan secara statik selari-selamat** (sehingga 8 jalankan serentak melalui PAR\`UAD_GENTUR_OR). Apabila LLM melancarkan berbilang panggilan alat serentak, uag menyamakannya secara automatik.
- **3 UI + A2A**: CLI, GUI, Web dan protokol Ejen-ke-Ejen. Enjin yang sama, mana-mana antara muka.
- **IoT sedia**: SwitchBot, ECHONET Lite, Matter, UPnP — kawal peranti rumah anda melalui AI.
- **Kemahiran Ejen**: Pasang kemahiran yang dibina komuniti daripada pasaran. Lanjutkan uag tanpa henti.

uag ialah **pembantu AI anda mengikut syarat anda**. Tidak terikat dengan pembekal, tidak terikat pada antara muka, tidak terikat pada platform.

## Permulaan Pantas

```bash
pemasangan pip uag
uag
```

Pada pelancaran pertama, wizard persediaan memandu anda melalui konfigurasi pembekal.
Lihat [docs/ENVIRONMENT.md](https://github.com/awaku7/agentRONclidocmblo7/agentRONclidocmblo/agentRONclidocs) pembolehubah.

## Computer Use

Computer Use ikut serta dan menyokong kedua-dua Playwright masa jalan penyemak imbas
dan masa jalan desktop. Apabila didayakan, kedua-dua masa jalan dibuat dan didaftarkan;
masa jalan yang dipilih dikawal oleh `UAGENT_COMPUTER_ENVIRONMENT`:

````bat
set UAGENT_COMPUTER_USE=1
tetapkan UAGENT_COMPUTER_ENVIRONMENT=browser
des``top`
 sebaliknya, pilih masa jalankan desktop`

`top`. Runtime sumber
ditutup bersama semasa keluar biasa, `Ctrl-C` dan penutupan proses. Tetapkan
`UAGENT_COMPUTER_HEADLESS=1` untuk ujian CI atau asap berasaskan penyemak imbas.
Lihat [docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
untuk butiran penyepaduan dan keselamatan.

## Suara Masa Nyata dan AEC3

Mod suara masa nyata menyokong OpenAI Masa Nyata, Azure OpenAI GPT Masa Nyata, xAI Grok Suara API, Google Gemini Multimodal Live API dan mikrofon Amazon Bedrock/Nova Sonic dan pembesar suara Iduplex penuh Bahagian belakang AEC3 `pywebrtc-audio` yang diperlukan dipasang secara automatik dan SDK penstriman dua arah pilihan Bedrock dipasang secara automatik hanya apabila penyedia Bedrock dipilih:

```bash
python scheck.py masa nyata
````

Saluran paip AEC3 yang sebenar menerima isyarat (`mikrofon `nerusi) (`jauh`) supaya pembantu boleh mendengar sambil bercakap. Dayakan diagnostik hanya apabila menyiasat isu audio:

```bat
tetapkan UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py masa nyata
```

### OpenAI Panggilan Fungsi Masa Nyata

OpenAI Penyepaduan Masa Nyata menyokong keselamatan Penyepaduan Masa Nyata. Penyesuai masa nyata semasa mendedahkan `get_current_time` baca sahaja secara automatik. Alat yang merosakkan dan kawalan peranti tidak didedahkan tanpa senarai kebenaran dan aliran pengesahan yang jelas. Grok masa nyata menggunakan penyesuai berasingan dan tidak menggunakan laluan panggilan fungsi khusus OpenAI ini.

## Ciri

### 🧠 Seni Bina Berbilang Pembekal

OpenAI / PFN (PLaMo) / Azure / Batuan Dasar / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita. AIgging Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

Semua pembekal berkongsi set alat dan antara muka yang sama. Beralih dengan menetapkan `UAGENT_PROVIDER` — tiada perubahan kod, tiada pemasangan berasingan.

#### Ollama dan llama.cpp

Ollama dan llama.cpp ialah pembekal yang berasingan. Ollama menggunakan perkhidmatan dan pengurusan modelnya sendiri, manakala `llama.cpp` bersambung ke `llama-server` OpenAI-compatible endpoint:

```bash
# Ollama
UAGENT_PROVIDER=ollama
UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
UAGENT_OLLAMA_DEPNAME=llama3.1

# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY`=`dummy
⎎ penyedia. Laluan yang serasi dengan penyelesaian. Kekalkan `UAGENT_RESPONSES=0` melainkan proksi yang serasi dikonfigurasikan.

### ⚡ Perlaksanaan Alat Selari

Apabila LLM meminta berbilang alatan secara serentak, uag **menyejajarkan secara automatik** mereka.
130 `ditandakan secara statik_selamat serentak melalui `ThreadPoolExecutor` (8 utas secara lalai; tetapkan `UAGENT_PARALLEL_WORKERS` untuk berubah).

**Contoh**: Tanya "Periksa cuaca di ibu kota Nordic" → LLM kebakaran `search_web` × 5 negara → semua 5 carian 
 → hasil carian sejajar 
 dijalankan dalam kumpulan semasa. kiraan adalah berdasarkan modul alat yang mentakrifkan `TOOL_SPEC` (pada masa ini 222, termasuk 2 alatan bersandarkan Karat dalam `src/uagent/tools_rust/`). `http_request` menggunakan keselamatan sensitif kaedah: Panggilan `GET`/`HEAD`/`OPTIONS` mungkin dijalankan secara selari, manakala kaedah tulis kekal bersiri.

Alat baca sahaja (carian fail, pengiraan cincang, penyenaraian direktori, terjemahan, pertanyaan DB, dsb.) diselaraskan secara agresif.### 🎧 Sistem Pemalam 
PH Serasi)

uagent melaksanakan **Claude sistem pemalam serasi kod**. Pemalam menggabungkan kemahiran, ejen, pelayan MCP, cangkuk dan banyak lagi ke dalam direktori serba lengkap dengan manifes `.claude-plugin/plugin.json`.

**Komponen yang disokong**: Kemahiran, Sub-ejen, pelayan MCP, Cangkuk (12 peristiwa kitaran hayat pengguna), Perintah Slash Styles, Output Style, Slash Marketplaces

**CLI commands**:

```

:senarai pemalam # Senaraikan pemalam yang dipasang
:pemasangan pemalam <sumber> [--skop] # Pasang (dir/zip/git/http)
:pasang pemalam <name>@<marketplace> # <Pasang dari marketplace
:plugin remove> #disableplugin> Togol
:plugin marketplace tambah/alih keluar/senarai # Urus marketplaces
:plugin init <nama> # Scaffold pemalam baharu

````

Lihat [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) untuk dokumentasi penuh ⟎⏄###. Kesinambungan

- **Tukar penyedia pertengahan sesi** dengan `UAGENT_PROVIDER` — sejarah perbualan dikekalkan.
- **Muat semula sesi yang lalu** dengan `:muat <index>` — sambung dari tempat anda berhenti.
- **Caching hasil alat** mengelakkan pelaksanaan semula yang berlebihan 2 







2###. Alat

| Kategori | Alat |
|---|---|
| **Operasi Fail** | baca/tulis/buat/padam/cari/grep/cincang/zip, jenis_fail, parse_eml (fail.eml), `path_alias` |
| **Web** | fetch_url, search_web, screenshot, browser_playwright, `url_alias`, `public_transit_route` ([panduan](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **Media** | jana_imej, analisis_imej, img2img, audio_speech, audio_transcribe |
| **Dokumen** | Pengekstrakan PDF/PPTX/DOCX/RTF/ODT, Pengekstrakan berstruktur Excel |
| **Ramalan** | Ramalan siri masa dengan 9 model (AutoARIMA, Nabi, LightGBM, CatBoost, TimesFM, dll.), pemilihan model automatik, penjanaan plot, i18n |
| **Komunikasi** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook, **pybitchat** (BLE Mesh) — lihat [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) dan [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP, reverse_geocode |
| **Cloud API** | `aws_api`, `gcp_api`, `azure_api` — operasi AWS, Google Cloud dan Azure API generik; operasi tulis memerlukan pengesahan yang jelas |
| **Alat Pembangun** | workspace_status, git_ops, git_review, security_scan, coverage_report, python_compile, lint_format, run_tests, db_query, **29 navigator kod sumber (keluarga idx)** |
| **MCP** | Sambung ke pelayan MCP luaran, senaraikan alatan, jalankan — [OAuth / Proxy guide](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Komunikasi ejen-ke-ejen (dengan uag contoh lain atau pelayan serasi A2A) |
| **Sistem** | env vars, spesifikasi sistem, masa, pengiraan tarikh, [kuantiti](docs/QUANTITIES.md), [geodesic_distance](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **Nav Sumber** | **29 alat idx** untuk Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — dapatkan indeks fungsi/kelas atau takrifan khusus tanpa membaca keseluruhan fail |

#### Kajian semula dan liputan repositori `:'t_status ruang kerja `:'t_status cawangan, perubahan, keadaan penyegerakan huluan, Python masa jalan dan penanda projek biasa tanpa mengubah suai fail.
- `git_review`: meringkaskan perubahan Git, fail berisiko, calon ujian dan penemuan rahsia tanpa mendedahkan nilai rahsia.
- `security_scan`: imbas fail repositori untuk kemungkinan rahsia dan fail konfigurasi berisiko `, dan 
PH_report-run`.
- normal. TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift dan Dart/Flutter.
- Kebergantungan liputan yang hilang boleh dipasang secara automatik apabila pelaksanaan diminta; `dry_run` tidak sekali-kali memasang pakej.

Lihat [Alat Analisis Repositori](docs/REPOSITORY_TOOLS.md) untuk parameter, output dan butiran keselamatan.

Lihat [Alias Laluan dan URL](docs/PATH_URL_ALIASES.md) untuk memendekkan laluan fail berulang ▎ dan URL.### 4 Antara Muka + Sambungan Kod VS

| Mod | Perintah | Tujuan |
|---|---|---|
| **CLI** | `uag` | Operasi berasaskan terminal pantas |
| **GUI** | `uagg` | UI Desktop melalui tkinter |
| **Web** | `uagw` | Akses berasaskan pelayar |
| **A2A Pelayan** | `uaga` | Protokol Agent2Agent untuk komunikasi berbilang ejen |
| **Kod VS** | — | [Sambungan](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) dengan Panel Sembang, Terangkan, Refactor, Betulkan Ralat dan Paparan Pokok Alat |

Lihat [VSCODE.md](https://github.com/awaku7/agent/docsdblob) sambungan — pemasangan, arahan, ikatan kekunci dan konfigurasi.

### 🏠 Kawalan Peranti IoT

- **BACnet**: Baca/tulis peranti BACnet/IP (HVAC, pencahayaan, meter kuasa). Langganan COV untuk pemberitahuan tolak
- **Modbus TCP**: Baca/tulis daftar pegangan/input dan gegelung. Pemantauan perubahan berasaskan undian
- **OPC UA**: Semak imbas ruang alamat, baca/tulis pembolehubah, langgan perubahan data
- **SwitchBot**: Kawalan kelompok awan & imbasan/kawalan BLE. Langganan berasaskan undian
- **ECHONET Lite**: Temui, kawal dan langgan pemberitahuan INF daripada peralatan rumah (AC, lampu, pemanas air, dll.)
- **Perkara**: Kawalan baca/tulis + langganan atribut untuk pemantauan perubahan keadaan
- **UPnP**: Penemuan peranti & pemajuan port IGD

Lihat [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` untuk menyemak imbas [SkillsMP](https://skillsmp.comlawHub)](https://skillsmp.comlawHub) kemahiran.
Pasang dan lanjutkan keupayaan uag dengan pantas.

### 🤖 Auto-Pilot (`:auto`)

uag boleh **secara autonomi mengejar matlamat merentasi berbilang LLM pusingan**. Sesuai untuk tugasan yang kompleks dan berbilang langkah yang memerlukan penghalusan berulang.

- **Cara ia berfungsi**: Setiap pusingan mempunyai pertanyaan utama (Langkah A) diikuti dengan penghakiman penyemak (Langkah B) yang memutuskan "SELESAI atau TERUSKAN?"
- **Pembekal yang sama, sama API**: Pertimbangan penyemak menggunakan laluan kod pertanyaan yang sama 
PH-3 termasuk laluan kod pertanyaan yang sama. **Hakim berasingan LLM** (pilihan): Tetapkan `UAGENT_AP_PROVIDER` untuk menggunakan pembekal/model yang berbeza untuk penyemak (cth. gunakan model yang lebih murah untuk menilai).
- **Keluar pada bila-bila masa**: Tekan kekunci `x` untuk berhenti serta-merta, walaupun tindak balas pertengahan. Atau biarkan penyemak membuat keputusan apabila matlamat tercapai.
- **Boleh Dikonfigurasikan**: `--pusingan maksimum N` untuk mengawal belanjawan.

Lihat [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) ## untuk dokumentasi penuh 
 Pengurus

uag boleh menjejaki kemajuan merentas tugasan berbilang fail yang berjalan lama. Apabila LLM memproses berpuluh-puluh fail, `batch_state` mengekalkan senarai fail yang belum selesai, lengkap dan gagal ke cakera. Jika sesi tamat atau pusingan tamat, larian seterusnya disambung semula dari tempat ia berhenti — tiada apa yang hilang.

### 🛡 Human-in-the-Loop

`human_ask` membolehkan LLM berhenti seketika dan meminta pengesahan anda sebelum melakukan operasi yang merosakkan (pemadaman fail, timpa ganti, perintah shell). Anda kekal dalam kawalan.

### 🛑 Sampuk (kekunci c / butang Berhenti)

Hentikan penjanaan respons LLM pada bila-bila masa dan suntikan arahan berhenti kembali ke LLM.

| Antara muka | Bagaimana hendak mengganggu |
|---|---|
| **CLI** | Tekan kekunci `c` semasa penstriman LLM — respons semasa berhenti dan `"Berhenti"` dihantar sebagai mesej pengguna supaya LLM bertindak balas dengan sewajarnya |
| **UI WEB** | Klik butang merah **■ Berhenti** (muncul secara automatik semasa pemprosesan LLM) |
| **Desktop GUI** | Klik butang **■** merah (muncul secara automatik semasa pemprosesan LLM) |

Gangguan berfungsi sebagai "suntikan segera": bukannya hanya menggugurkan, ia menyuapkan `"Berhenti"` kembali ke LLM sebagai mesej pengguna, membolehkannya menyimpulkan atau mengakui gangguan dengan anggun.
`melihat kekunci 
`Press secara automatik [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Automasi Penyemak Imbas & Web Inspektor

Dua pelengkap Playwright
alat berasaskan Automasi pelayar:

### 🕵️ Automasi Penyemak Imbas & Web Inspektor

Dua pelengkap Playwright
alat berasaskan Automasi imbas:
**rights_0
berasaskan pelayar:
*****perkakas berasaskan pelayar sebenar:
*****pelayar-pelayar sebenar — navigasi, klik, isi borang, ekstrak data, kendalikan aliran berbilang halaman. Berfungsi tanpa kepala atau berkepala.
- **playwright_inspector**: Rakam peralihan penyemak imbas, tangkap syot kilat DOM dan tangkapan skrin pada setiap langkah. Berguna untuk menyahpepijat interaksi web atau mengaudit perubahan halaman dari semasa ke semasa.

### 🔄 Pemuatan Alat Dinamik

`katalog_alat` dan `tool_load` membolehkan anda menemui dan mendayakan alatan pada masa jalan.
Tidak perlu memuatkan semuanya pada permulaan — aktifkan hanya apa yang anda perlukan, apabila anda memerlukannya.### 
⏦ Alat

`uuid_gen` dan `slugify` dilaksanakan dalam Rust (melalui PyO3) untuk prestasi.
Ia dimuatkan terus daripada `.pyd` pra-bina — **tiada `pemasangan pip` diperlukan**.

Pemaju luaran juga boleh menghantar alatan berasaskan Rust: letakkan `.pyd`ra di sebelah `.pyd`w `load_rust_pyd()` daripada `uagent.tools.rust_helper` dan
pengguna mendapat alat tersebut tanpa sebarang kebergantungan tambahan. Lihat
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日本語 / Bahasa Inggeris / 简䖇 /中文 /中文 /中斔 /中文한국어 / Español / Français / Русский / dan banyak lagi.
Tetapkan `UAGENT_LANG` untuk bertukar. Lihat [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) untuk menambah tempat baharu.

Terjemahan README ini tersedia dalam [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Pembolehubah Persekitaran Disulitkan

Simpan API kunci dan rahsia dalam `.env.sec.``.env. fail.
Urus dengan `uag_envsec`.

## Konfigurasi & Butiran

- **Pembolehubah persekitaran**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Wizard persediaan**: `python -m __-PH_2⎏edencrypted setup `uag_envsec` — menyulitkan `.env` sebagai `.env.sec`
- **Respons API**: Tetapkan `UAGENT_RESPONSES=1` untuk mod Respons API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Didayakan secara automatik untuk Sakana AI (Fugu).
- **Dokumen pembangun**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Aliran alat**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — cara alatan dihantar ke LLM (topeng genre, katalog_alat, GPT-5.4+ carian alat asli)
- **Petua kecil**:LLM [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Falsafah Projek

uag bercita-cita untuk menjadi **AI anda, pada mesin anda, mengikut syarat anda.**

- Tiada pergantungan SaaS — berjalan secara setempat
- Tiada kunci masuk pembekal — tukar bila-bila masa
- Tiada kunci masuk UI — CLI / GUI / __PH__0
 dengan ciri GUI / __PH__3
 kemahiran

Pengalaman ejen AI percuma, bebas daripada kunci masuk vendor.

### ✨ Cipta Alat Anda Sendiri

Menulis alat baharu untuk uag adalah mudah — buat satu fail `.py` dengan
`TOOL_SPEC` dan `run_tool()`, letakkan ia dalam 
`DUAGTOENT()`, letakkan dalam 

 segera tersedia. Untuk pembangun Rust, hantarkan `.pyd` pra-bina dengan
sifar kebergantungan tambahan untuk pengguna.

Lihat [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
untuk panduan
demi-langkah
## Menyumbang

Sumbangan dialu-alukan! Laporan pepijat, cadangan ciri, penambahbaikan dokumentasi, terjemahan dan permintaan tarik — semuanya dihargai.

- **Isu**: Buka isu GitHub untuk pepijat atau permintaan ciri.
- **Tarik permintaan**: Tolak repo, buat perubahan anda dan serahkan PR. Lihat [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) untuk persediaan dan garis panduan pembangunan.
- **Terjemahan**: README terjemahan dan penambahan tempat dialu-alukan. Lihat [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Alat & Kemahiran**: Pemalam alat baharu dan Kemahiran Ejen boleh disumbangkan melalui pasaran.
 PR
#
e semakan pembangunan
#
e kebergantungan ujian sahaja dahulu. Mereka diketepikan daripada senarai pergantungan masa jalan
:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
````

Jalankan semakan yang sama yang digunakan oleh GitHub Tindakan sebelum menolak:
\`onsh

tests
python -m black --check src tests
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .

````

Untuk lelaran setempat yang lebih pantas, jalankan hanya ujian yang terjejas:

```bash
 tests/<affected_area>
````

Pemeriksaan tambahan apabila berkaitan:

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

After locale (`:po`) edit ons (`:po`) scripts/compile_locales.py`dan`python scripts/po_qc_summary.py\`.

Runtime dasar (perincian dalam [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOPises.md) daripada bantuan §ised.md) `sys.exit`; hos alat menukar alat `SystemExit`/`Pengecualian` kepada rentetan ralat supaya satu alat tidak boleh mematikan proses. Keluar cepat gagal permulaan kekal disengajakan.

## Seni bina dan invarian operasi

Lihat [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) untuk kontrak tahan lama yang meliputi A2A kitaran hayat, konteks I18N, pemasangan pergantungan pilihan, keselamatan alatan, keupayaan pembekal, sempadan kepercayaan OAuth, peristiwa berstruktur penerimaan⎎, dan penerimaan⎎.## Enjin Dasar Perusahaan

Dasar peringkat organisasi untuk alatan, pembekal, bukti kelayakan, MCP pelayan, rangkaian, kemahiran dan pemalam disokong. Tetapkan `UAGENT_POLICY_FILE` kepada fail dasar JSON/YAML; lihat [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) untuk contoh konfigurasi, peranan, pengesahan dan senarai yang dibenarkan.

### Runtime pemulihan dan orkestra

Lihat [RESTART_RECOVERY.md](docs/Y.REMSTART_d) [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) untuk pemulihan yang tahan lama, pelaksanaan sedar kebergantungan, orkestrasi berbilang ejen dan penggunaan A2A dari jauh. [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) untuk penyelarasan pajakan ketua masa jalanan bersama.
