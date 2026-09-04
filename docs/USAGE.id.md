# PENGGUNAAN (Opsi baris perintah)

Dokumen ini menjelaskan opsi baris perintah yang tersedia untuk titik masuk uag.

______________________________________________________________________

## Titik masuk

| Perintah | Modul Python | Antarmuka |
|---|---|---|
| `uag` | `python -m uagent` | CLI (loop stdin) |
| `uagg` | `python -m uagent.gui` | GUI (tkinter) |
| `uagw` | `python -m uagent.web` | Server web (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | server A2A HTTP |

______________________________________________________________________

## Opsi startup CLI (`uag`)

### `--workdir` / `-C <path>`

Direktori kerja. Jika tidak ditentukan, akan menggunakan variabel lingkungan `UAGENT_WORKDIR` sebagai cadangan, lalu direktori saat ini.
Direktori akan dibuat jika belum ada.

### `--tool-genre-mask <int>`

Bitmask genre alat. Jika ditentukan, prompt pemilihan genre interaktif akan dilewati.

| Bit | Genre | Deskripsi |
|-----|-------|-------------|
| 1 | basic | Alat file/obrolan esensial |
| 2 | comm | Alat komunikasi (Bluesky, Teams) |
| 4 | office | Alat suite kantor (Excel, PDF, PPTX) |
| 8 | devel | Alat pengembangan (git, lint, compile) |
| 16 | iot | Alat perangkat IoT (SwitchBot, ECHONET, Matter, UPnP) |
| 32 | exec | Alat eksekusi perintah |
| 64 | external | Alat plugin eksternal |
| 128 | media | Pembuatan dan analisis gambar/audio |
| 256 | file | Alat pengelolaan berkas |
| 512 | index | Alat navigasi sumber/indeks |
| 1024 | dev | Alat pengembang dan repositori |
| 2048 | web | Alat web dan peramban |
| 4096 | utility | Alat utilitas dan dukungan |
| 8191 | all | Semua alat |

Contoh:

```
uag --tool-genre-mask 1 # hanya dasar
uag --tool-genre-mask 9 # dasar + pengembangan (1 + 8)
uag --tool-genre-mask 8191    # semua alat
```

### `--use-tool` / `--no-use-tool`

Mengaktifkan atau menonaktifkan pengiriman definisi alat ke LLM. Menggantikan variabel lingkungan `UAGENT_USE_TOOL`.

- `--use-tool` memaksa pengiriman alat diaktifkan.
- `--no-use-tool` memaksa pengiriman alat dinonaktifkan.

Saat dinonaktifkan, LLM tidak menerima definisi alat apa pun dan tidak dapat memanggil alat apa pun.

### `--computer-use` / `--no-computer-use`

Mengaktifkan atau menonaktifkan Penggunaan Komputer. Menggantikan variabel lingkungan `UAGENT_COMPUTER_USE`.

### `--inject-message` / `-M <message>`

Menyisipkan pesan ke dalam LLM saat startup dan keluar setelah selesai. Ini menyiratkan `--non-interactive`.

### `--embedded`

Mode tertanam untuk penerapan yang terkendala atau sensitif terhadap reproduktifitas.

- Menonaktifkan penyimpanan sesi.
- Menyembunyikan alat manajemen alat (`tool_catalog`, `tool_load`, `unload_tool`) kecuali diaktifkan secara eksplisit.
- Mengabaikan `--tool-genre-mask`; gunakan `--enable-tool` untuk memuat alat secara eksplisit.

### `--enable-tool <nama>`

Memuat alat secara eksplisit saat startup. Opsi ini dapat diulang, dan nama yang dipisahkan dengan koma juga diterima.

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

Urutan yang ditentukan akan dipertahankan dan tercermin dalam urutan alat yang ditampilkan ke LLM. Alat yang diaktifkan secara eksplisit akan dikunci agar tidak dimuat ulang secara otomatis.

### `--plugin-dir <path>`

Memuat plugin dari direktori yang ditentukan. Opsi ini dapat diulang.

______________________________________________________________________

## Opsi khusus CLI

### `--inject-message-auto <goal-options>`

Mulai autopilot dari tujuan yang disuntikkan secara non-interaktif. Nilai ini menggunakan opsi yang sama seperti `:auto`; masukkan nilai lengkapnya dalam tanda kutip jika berisi opsi.

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Urutkan item --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Urutkan item --infinite"
```

Mode normal menggunakan jalur penilaian peninjau. Tetapkan `UAGENT_AUTO_SENTINEL=1` untuk memilih mode sentinel tunggal LLM. Dalam mode tersebut, target LLM harus mengakhiri setiap respons dengan tepat salah satu dari:

- `<AUTO_CONTINUE>` — jalankan putaran lain
- `<AUTO_COMPLETE>` — selesaikan dengan sukses

Penanda yang hilang atau tidak valid akan menghentikan autopilot dengan aman. Target LLM ini tetap dijalankan; opsi ini hanya menghindari panggilan tambahan ke peninjau LLM.

### `--non-interactive`

Mode non-interaktif. Tidak memulai loop stdin. Jika jalur berkas diberikan sebagai argumen posisional, jalur tersebut akan diproses dan program akan segera keluar.

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Opsi server web (`uagw`)

### `--host <address>`

Alamat pengikatan untuk server web (default: `127.0.0.1`, dapat diganti dengan `UAGENT_WEB_HOST`).

Secara default, server web hanya mendengarkan pada localhost (`127.0.0.1`). Untuk membuatnya dapat diakses dari mesin lain di jaringan, gunakan `--host 0.0.0.0`.

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <int>`

Pilih genre alat menggunakan bitmask yang sama seperti yang dijelaskan di atas. Jika ditentukan, prompt genre interaktif akan dilewati.

### `--use-tool` / `--no-use-tool`

Aktifkan atau nonaktifkan pengiriman definisi alat ke LLM. Menggantikan `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Mengaktifkan atau menonaktifkan Penggunaan Komputer. Menggantikan `UAGENT_COMPUTER_USE`.

### `--no-frontend`

Menjalankan API saja tanpa templat HTML atau berkas frontend statis.

### `--embedded`

Menonaktifkan penyimpanan sesi dan menyembunyikan alat manajemen (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Opsi server A2A (`uaga`)

### `--host <address>`

Alamat yang diikat untuk server A2A HTTP (default: `0.0.0.0`, dapat diganti dengan `UAGENT_A2A_HOST`).

### `--port <nomor>`

Nomor port untuk server A2A HTTP (default: `8765`, dapat diganti dengan `UAGENT_A2A_PORT`).

### `--reload`

Aktifkan pemuatan ulang otomatis saat terjadi perubahan kode (default: nonaktif, dapat diganti dengan `UAGENT_A2A_RELOAD`).

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <int>`

Pilih genre alat menggunakan bitmask yang dijelaskan di atas. Jika ditentukan, prompt genre interaktif akan dilewati.

### `--use-tool` / `--no-use-tool`

Aktifkan atau nonaktifkan pengiriman definisi alat ke LLM. Menggantikan `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Mengaktifkan atau menonaktifkan Penggunaan Komputer. Menggantikan `UAGENT_COMPUTER_USE`.

### `--embedded`

Menonaktifkan penyimpanan sesi dan menyembunyikan alat manajemen alat (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Variabel lingkungan terkait

| Variabel | Deskripsi |
|---|---|
| `UAGENT_PROVIDER` | Nama penyedia `LLM` (diperlukan saat startup) |
| `UAGENT_*_API_KEY` | Kunci penyedia yang dipilih (API) |
| `UAGENT_WORKDIR` | Direktori kerja default |
| `UAGENT_WEB_HOST` | Alamat bind server web (default: `127.0.0.1`) |
| `UAGENT_A2A_HOST` | Alamat pengikatan server A2A (default: `0.0.0.0`) |
| `UAGENT_A2A_PORT` | Port server A2A (default: `8765`) |
| `UAGENT_A2A_RELOAD` | Aktifkan pemuatan ulang panas (hot reload) A2A secara default |
| `UAGENT_USE_TOOL` | Nonaktifkan alat jika diatur ke `0`, `false`, `no`, atau `off` |
| `UAGENT_COMPUTER_USE` | Aktifkan atau nonaktifkan Penggunaan Komputer secara default |
| `UAGENT_SESSION_STORE` | Aktifkan atau nonaktifkan penyimpanan sesi; Mode tertanam memaksa nilai `0` |
| `UAGENT_PLUGIN_DIRS` | Direktori pencarian plugin tambahan |
| `UAGENT_AUTO_SENTINEL` | Aktifkan mode pengawas autopilot tunggal LLM jika diatur ke `1` |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | Jumlah maksimum panggilan alat baru berturut-turut (default: `100`) |
| `UAGENT_MAX_TOOL_ROUNDS` | Batas maksimum putaran LLM/alat per operasi pengguna (default: `200`) |
| `UAGENT_SHRINK_CNT` | Ambang batas pengecilan otomatis opsional dalam pesan (`0`/tidak diatur = dinonaktifkan) |
| `UAGENT_SHRINK_KEEP_LAST` | Jumlah pesan yang akan disimpan setelah penyusutan (default: `20`) |
| `UAGENT_LANG` | Bahasa antarmuka (`ja`, `en`, dll.) |

Untuk daftar lengkap variabel lingkungan, lihat [ENVIRONMENT.md](ENVIRONMENT.md).

______________________________________________________________________

## Contoh

### Pengaturan awal minimal dengan OpenAI

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### Ollama lokal dengan hanya alat-alat dasar

```
set UAGENT_PROVIDER=ollama
set UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### Server web di semua antarmuka

```
set UAGENT_WEB_HOST=0.0.0.0
uagw
```

atau

```
uagw --host 0.0.0.0
```

### Server A2A di localhost dengan port khusus

```
uaga --host 127.0.0.1 --port 8080
```

### Menonaktifkan alat untuk model kecil

```
uag --no-use-tool --tool-genre-mask 1
```

### Pemrosesan berkas non-interaktif

```
uag --non-interactive README.md
```
