<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Gerbang AI Universal</h1>

<p align="center">
  <b>U</b>universal <b>A</b>I <b>G</b>ateway — Lingkungan Anda, kebebasan Anda.
</p>

<p align="center">
  Operasi file / Pencarian web / Pembuatan & analisis gambar / Ekstraksi PDF & Excel / Kontrol IoT / Integrasi MCP<br>
  15+ penyedia / 3 UI / Eksekusi alat paralel / Pasar Keterampilan Agen
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Baca ini dalam bahasa Anda</a>
</p>

---

## Kenapa harus?

**Bebaskan diri dari penguncian vendor.** Sebagian besar asisten AI mengikat Anda ke penyedia atau layanan cloud tertentu. uag berbeda.

- **Berjalan secara lokal** di mesin Anda. Data Anda tetap bersama Anda (kecuali panggilan API yang Anda lakukan).
- **Kebebasan penyedia**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock... 15+ penyedia, semuanya dapat diakses dari satu antarmuka. Bertukar di antara keduanya dengan mengonfigurasi ulang variabel lingkungan — tanpa instalasi ulang, tanpa migrasi.
- **131 alat**: I/O file, pencarian web, pembuatan gambar, pemindaian perangkat BLE, integrasi server MCP — dan **76 di antaranya berjalan secara paralel**. Saat LLM mengaktifkan beberapa panggilan alat sekaligus, uag secara otomatis mengeksekusinya melalui kumpulan thread.
- **4 UI + A2A**: CLI, GUI, Web, dan protokol Agen-ke-Agen. Mesin yang sama, antarmuka apa pun.
- **Siap IoT**: SwitchBot, ECHONET Lite, Matter, UPnP — kendalikan perangkat rumah Anda melalui AI.
- **Keterampilan Agen**: Instal keterampilan yang dibangun komunitas dari pasar. Perpanjang uag tanpa henti.

uag adalah **asisten AI sesuai keinginan Anda**. Tidak terikat pada penyedia, tidak terikat pada antarmuka, tidak terikat pada platform.

## Mulai Cepat

```bash
pip install uag
uag
```

Pada peluncuran pertama, wizard pengaturan memandu Anda melalui konfigurasi penyedia.
Lihat [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) untuk semua variabel lingkungan.

## Fitur

### 🧠 Arsitektur Multi-Penyedia

OpenAI / Azure / Batuan Dasar / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax

Semua penyedia berbagi perangkat dan antarmuka yang sama. Beralih berdasarkan pengaturan `UAGENT_PROVIDER` — tidak ada perubahan kode, tidak ada instalasi terpisah.

### ⚡ Eksekusi Alat Paralel

Saat LLM meminta beberapa alat secara bersamaan, uag **secara otomatis memparalelkannya**.
76 alat ditandai `x_parallel_safe` dan dieksekusi secara bersamaan melalui `ThreadPoolExecutor` 4-thread.

**Contoh**: Tanyakan "Periksa cuaca di ibu kota Nordik" → LLM mengaktifkan `search_web` × 5 negara → kelima penelusuran dijalankan secara paralel → hasil dikumpulkan dalam satu kelompok.

Alat read-only (pencarian file, penghitungan hash, daftar direktori, terjemahan, kueri DB, dll.) diparalelkan secara agresif.

### 🔄 Kontinuitas Sesi

- **Ganti penyedia di tengah sesi** dengan `UAGENT_PROVIDER` — riwayat percakapan dipertahankan.
- **Muat ulang sesi sebelumnya** dengan `:load <index>` — lanjutkan dari bagian terakhir yang Anda tinggalkan.
- **Caching hasil alat** menghindari eksekusi ulang yang berlebihan ketika panggilan alat yang sama diulang.

### 🛠 131 Alat

| Kategori | Alat |
|---|---|
| **Operasi File** | baca/tulis/buat/hapus/pencarian/grep/hash/zip |
| **Jaringan** | ambil_url, cari_web, tangkapan layar, browser_playwright |
| **Media** | menghasilkan_gambar, menganalisis_gambar, img2img, audio_speech, audio_transkripsikan |
| **Dokumen** | Ekstraksi PDF/PPTX/DOCX/RTF/ODT, ekstraksi terstruktur Excel |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Materi, UPnP |
| **Alat Pengembang** | git_ops, python_compile, lint_format, run_tests, db_query, **13 idx tools** |
| **MCP** | Hubungkan ke server MCP eksternal, daftar alat, jalankan |
| **A2A** | Komunikasi agen-ke-agen (dengan instans uag lain atau server yang kompatibel dengan A2A) |
| **Sistem** | env vars, spesifikasi sistem, waktu, perhitungan tanggal |

### 🖥 3 Antarmuka + A2A + VS Code

| Modus | Perintah | Tujuan |
|---|---|---|
| **KLI** | `uag` | Pengoperasian cepat berbasis terminal |
| **GUI** | `uagg` | UI Desktop melalui tkinter |
| **Jaringan** | `uagw` | Akses berbasis browser |
| **Server A2A** | `uaga` | Protokol Agent2Agent untuk komunikasi multi-agen |
| **VS Code** | — | Extension (Chat Panel, Explain, Refactor, Fix Error, Tools Tree View) — see [VSCODE.md](VSCODE.md) |

### 🏠 Kontrol Perangkat IoT

- **SwitchBot**: Kontrol batch cloud & pemindaian/kontrol BLE
- **ECHONET Lite**: Temukan dan kendalikan peralatan rumah tangga (AC, lampu, pemanas air, dll.) di jaringan lokal
- **Materi**: Pemeriksaan topologi pengontrol/jembatan/perangkat hanya-baca
- **UPnP**: Penemuan perangkat & penerusan port IGD

Lihat [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 Pasar Keterampilan Agen

`:skills mp_search` untuk menelusuri [SkillsMP](https://skillsmp.com) dan [ClawHub](https://clawhub.ai) untuk keterampilan komunitas.
Instal dan perluas kemampuan uag dengan cepat.

### 🧩 Manajer Status Batch

uag dapat melacak kemajuan tugas multi-file yang berjalan lama. Saat LLM memproses lusinan file, `batch_state` menyimpan daftar file yang tertunda, selesai, dan gagal ke disk. Jika sesi berakhir atau putaran habis, putaran berikutnya dilanjutkan dari titik berhentinya — tidak ada yang hilang.

### 🛡 Manusia dalam Lingkaran

`human_ask` memungkinkan LLM berhenti sejenak dan meminta konfirmasi Anda sebelum melakukan operasi destruktif (penghapusan file, penimpaan, perintah shell). Anda tetap memegang kendali.

### 🕵️ Otomatisasi Browser & Inspektur Web

Dua alat berbasis Penulisan Drama yang saling melengkapi:

- **browser_playwright**: Mengotomatiskan sesi browser sebenarnya — menavigasi, mengklik, mengisi formulir, mengekstrak data, menangani alur multi-halaman. Bekerja tanpa kepala atau berkepala.
- **playwright_inspector**: Rekam transisi browser, ambil cuplikan DOM dan tangkapan layar di setiap langkah. Berguna untuk men-debug interaksi web atau mengaudit perubahan halaman seiring waktu.

### 🔄 Pemuatan Alat Dinamis

`tool_catalog` dan `tool_load` memungkinkan Anda menemukan dan mengaktifkan alat saat runtime.
Tidak perlu memuat semuanya saat startup — aktifkan hanya yang Anda perlukan, saat Anda membutuhkannya.

### 🌐 i18n / L10n

日本語 / Inggris / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / dan masih banyak lagi.
Setel `UAGENT_LANG` untuk beralih. Lihat [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) untuk menambahkan lokal baru.

Terjemahan README ini tersedia di [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Variabel Lingkungan Terenkripsi

Simpan kunci dan rahasia API di `.env.sec` — file `.env` terenkripsi.
Kelola dengan `uag_envsec`.

## Konfigurasi & Detail

- **Variabel lingkungan**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **Wizard penyiapan**: `python -m uagent.setup_cli`
- **Env terenkripsi**: `uag_envsec` — mengenkripsi `.env` sebagai `.env.sec`
- **Responses API**: Setel `UAGENT_RESPONSES=1` untuk mode Responses API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/LM Studio)
- **Dokumen pengembang**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Tips LLM kecil**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Filosofi Proyek

uag bercita-cita menjadi **AI Anda, di mesin Anda, sesuai keinginan Anda.**

- Tidak ada ketergantungan SaaS — berjalan secara lokal
- Tidak ada penguncian penyedia — beralih kapan saja
- Tidak ada penguncian UI — CLI / GUI / Web / A2A
- Tidak ada penguncian fitur — perluas dengan alat dan keterampilan

Pengalaman agen AI gratis, bebas dari penguncian vendor.