```
██╗   ██╗ █████╗  ██████╗ ███████╗███╗   ██╗████████╗ ██████╗██╗     ██╗
██║   ██║██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██╔════╝██║     ██║
██║   ██║███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ██║     ██║     ██║
██║   ██║██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ██║     ██║     ██║
╚██████╔╝██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ╚██████╗███████╗██║
 ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝╚══════╝╚═╝
```

# uag (Local AI Agent)

uag adalah agen interaktif yang menjalankan **perintah**, memanipulasi **berkas**, dan membaca **berbagai format data** (PDF/PPTX/Excel, dll.) di PC lokal Anda. Aplikasi ini menyediakan tiga antarmuka: CLI, GUI, dan Web.


GitHub: https://github.com/awaku7/agentcli

## Instalasi

Anda dapat memasang `uag` melalui pip:

```bash
pip install uag
```

Setelah instalasi, saat pertama kali menjalankan `uag`, wizard setup interaktif akan otomatis dibuka untuk mengonfigurasi variabel lingkungan Anda. Untuk informasi rinci tentang konfigurasi dan enkripsi, lihat **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**.

## Fitur Utama

- **Perangkat Alat Praktis**: Dilengkapi alat untuk manipulasi berkas, pencarian web, ekstraksi data (PDF/PPTX/Excel), pembuatan gambar, dan analisis, semuanya dapat dijalankan di lingkungan lokal Anda.
- **Dukungan Multi-Provider**: Mendukung OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA.
- **Antarmuka Fleksibel**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **A2A (Server)**: `uaga` / `python -m uagent.a2a.server`
- **MCP (Model Context Protocol)**: Mendukung koneksi ke server alat MCP eksternal.
- **Kelangsungan Sesi**: Menjaga konteks percakapan bahkan saat berpindah provider atau model.
- **Web Inspector**: Menyimpan transisi browser, DOM, dan screenshot secara otomatis menggunakan `playwright_inspector`.
- **Dokumentasi Bawaan**: Akses instan ke dokumentasi internal yang rinci menggunakan perintah `uag docs`.

## Penggunaan

### Memulai dan Keluar
Jalankan `uag` dari terminal Anda untuk memulai. Ketik `:exit` untuk keluar.

### Server A2A (Agent2Agent)
Jalankan server HTTP yang kompatibel dengan A2A:
```bash
uaga
```

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

### Dokumentasi Pengembang dan Internasionalisasi
- **Dokumen Pengembang**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Menambah Locale**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **README Bahasa Lain**: [English](https://github.com/awaku7/agentcli/blob/main/README.md) / [日本語](https://github.com/awaku7/agentcli/blob/main/README.ja.md) / [Deutsch](https://github.com/awaku7/agentcli/blob/main/README.de.md) / [Español](https://github.com/awaku7/agentcli/blob/main/README.es.md) / [Français](https://github.com/awaku7/agentcli/blob/main/README.fr.md) / [Italiano](https://github.com/awaku7/agentcli/blob/main/README.it.md) / [한국어](https://github.com/awaku7/agentcli/blob/main/README.ko.md) / [Português](https://github.com/awaku7/agentcli/blob/main/README.pt_BR.md) / [Русский](https://github.com/awaku7/agentcli/blob/main/README.ru.md) / [ไทย](https://github.com/awaku7/agentcli/blob/main/README.th.md) / [简体中文](https://github.com/awaku7/agentcli/blob/main/README.zh_CN.md) / [繁體中文](https://github.com/awaku7/agentcli/blob/main/README.zh_TW.md) / [Polski](https://github.com/awaku7/agentcli/blob/main/README.pl.md) / [Tiếng Việt](https://github.com/awaku7/agentcli/blob/main/README.vi.md) / [Bahasa Indonesia](https://github.com/awaku7/agentcli/blob/main/README.id.md)
