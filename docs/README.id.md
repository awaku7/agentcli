<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (Local AI Agent)

uag adalah agen interaktif yang menjalankan **perintah**, memanipulasi **berkas**, dan membaca **berbagai format data** (PDF/PPTX/Excel, dll.) di PC lokal Anda. Aplikasi ini menyediakan tiga antarmuka: CLI, GUI, dan Web.

uag dibuat untuk **membebaskan Anda dari aplikasi yang terkunci pada vendor**: gunakan antarmuka yang sesuai dengan alur kerja Anda, ganti penyedia, dan tetap kendalikan lingkungan Anda.

GitHub: https://github.com/awaku7/agentcli

## Instalasi

Anda dapat memasang `uag` melalui pip:

```bash
pip install uag
```

Setelah instalasi, saat pertama kali menjalankan `uag`, wizard setup interaktif akan otomatis dibuka untuk mengonfigurasi variabel lingkungan Anda. Untuk informasi rinci tentang konfigurasi dan enkripsi, lihat **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**.

## Fitur Utama

- **Perangkat Alat Praktis**: Dilengkapi alat untuk manipulasi berkas, pencarian web, ekstraksi data (PDF/PPTX/Excel), pembuatan gambar, dan analisis, semuanya dapat dijalankan di lingkungan lokal Anda.
- **Dukungan Multi-Provider**: Mendukung OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / Moonshot AI.
- **Antarmuka Fleksibel**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **A2A (Server)**: `uaga` / `python -m uagent.a2a.server`
- **MCP (Model Context Protocol)**: Mendukung koneksi ke server alat MCP eksternal.
- **Kelangsungan Sesi**: Menjaga konteks percakapan bahkan saat berpindah provider atau model.
- **Web Inspector**: Menyimpan transisi browser, DOM, dan screenshot secara otomatis menggunakan `playwright_inspector`.
- **Dokumentasi Bawaan**: Akses instan ke dokumentasi internal yang rinci menggunakan perintah `uag docs`.
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

## Penggunaan

### Memulai dan Keluar

Jalankan `uag` dari terminal Anda untuk memulai. Ketik `:exit` untuk keluar.

### Server A2A (Agent2Agent)

Jalankan server HTTP yang kompatibel dengan A2A:

```bash
uaga
```

### Catatan tentang Responses API

Jika Anda menetapkan `UAGENT_RESPONSES=1`, Responses API digunakan untuk penyedia yang didukung: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI menggunakan jalur API bawaan mereka dan tidak tercakup oleh Responses API.
Untuk penyedia lain, uag kembali ke jalur khusus penyedia atau alur chat-completions.

Lihat [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) untuk pengaturan `UAGENT_A2A_*` seperti autentikasi, host, port, reload, URL dasar publik, konkurensi, dan engine.

### Tips Praktis (Kelangsungan dan Kontrol)

- `:tools`: Menampilkan daftar alat yang dimuat.
- `:logs [n]`: Menampilkan log sesi (`n` untuk menentukan jumlah entri).
- `:load <index>`: Memuat sesi sebelumnya untuk melanjutkan percakapan.
- `:skills`: Memilih dan memuat Agent Skills (peran atau instruksi tambahan).
- `:shrink [n]`: Menyusun riwayat agar hanya menyimpan `n` pesan terakhir untuk menghemat token.

## Konfigurasi dan Rincian

### Variabel Lingkungan dan Setup

Untuk pengaturan rinci (kunci API, bahasa tampilan `UAGENT_LANG`, pengaturan penyusutan riwayat, dll.), lihat **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**.

- **Setup**: Konfigurasikan secara interaktif melalui `python -m uagent.setup_cli`.
- **Enkripsi**: Enkripsi file `.env` Anda secara aman menggunakan alat `uag_envsec`.
- **Pembaruan**: Gunakan `uag_envsec add --file .env.sec --key NAME --value VALUE` untuk menambah atau memperbarui variabel dalam file terenkripsi yang sudah ada.

### Dokumentasi Pengembang dan Internasionalisasi

- **Dokumen Pengembang**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Menambah Locale**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **README Bahasa Lain**: [`docs/README.translations.md`](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)
