# CARA PENGGUNAAN (Pilihan baris perintah)

Dokumen ini menerangkan pilihan baris perintah yang tersedia untuk titik masuk uag.

______________________________________________________________________

## Titik kemasukan

| Perintah | Modul Python | Antara muka |
|---|---|---|
| `uag` | `python -m uagent` | CLI (gelung stdin) |
| `uagg` | `python -m uagent.gui` | GUI (tkinter) |
| `uagw` | `python -m uagent.web` | Web server (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | A2A HTTP pelayan |

______________________________________________________________________

## CLI pilihan permulaan (`uag`)

### `--workdir` / `-C <path>`

Direktori kerja. Jika tidak ditetapkan, ia akan menggunakan semulaubah `UAGENT_WORKDIR`, kemudian direktori semasa.
Direktori akan diwujudkan jika ia tidak wujud.

### `--tool-genre-mask <int>`

Bitmask genre alat. Apabila disediakan, paparan interaktif untuk pemilihan genre akan diabaikan.

| Bit | Genre | Deskripsi |
|-----|-------|-------------|
| 1 | basic | Alat fail/perbualan asas |
| 2 | comm | Alat komunikasi (Bluesky, Teams) |
| 4 | office | Alat suite pejabat (Excel, PDF, PPTX) |
| 8 | devel | Alat pembangunan (git, lint, compile) |
| 16 | iot | Alat peranti IoT (SwitchBot, ECHONET, Matter, UPnP) |
| 32 | exec | Alat pelaksanaan arahan |
| 64 | external | Alat pemalam luaran |
| 128 | media | Penghasilan dan analisis imej/audio |
| 256 | file | Alat pengurusan fail |
| 512 | index | Alat navigasi sumber/indeks |
| 1024 | dev | Alat pembangun dan repositori |
| 2048 | web | Alat web dan pelayar |
| 4096 | utiliti | Alat utiliti dan sokongan |
| 8191 | semua | Semua alat |

Contoh:

```
uag --tool-genre-mask 1 # asas sahaja
uag --tool-genre-mask 9 # asas + pembangunan (1 + 8)
uag --tool-genre-mask 8191    # semua alat
```

### `--use-tool` / `--no-use-tool`

Mengaktifkan atau menyahaktifkan penghantaran definisi alat kepada LLM. Menimpa pembolehubah persekitaran `UAGENT_USE_TOOL`.

- `--use-tool` memaksa penghantaran alat dihidupkan.
- `--no-use-tool` memaksa penghantaran alat dimatikan.

Apabila dilumpuhkan, LLM tidak menerima sebarang definisi alat dan tidak dapat memanggil mana-mana alat.

### `--computer-use` / `--no-computer-use`

Memperoleh atau melumpuhkan Computer Use. Menimpa pembolehubah persekitaran `UAGENT_COMPUTER_USE`.

### `--inject-message` / `-M <mesej>`

Menyuntik mesej ke dalam LLM semasa permulaan dan keluar selepas selesai. Ini bermaksud `--non-interactive`.

### `--embedded`

Mod terbenam untuk penyebaran yang terhad atau sensitif terhadap kebolehulangan.

- Mematikan stor sesi.
- Menyembunyikan alat pengurusan (`tool_catalog`, `tool_load`, `unload_tool`) melainkan dinyahaktifkan secara eksplisit.
- Mengabaikan `--tool-genre-mask`; gunakan `--enable-tool` untuk memuatkan alat secara eksplisit.

### `--enable-tool <name>`

Memuat alat secara eksplisit semasa permulaan. Pilihan ini boleh diulang, dan nama yang dipisahkan dengan koma juga diterima.

```

Susunan yang dinyatakan dikekalkan dan tercermin dalam susunan alat yang dipersembahkan kepada LLM --embedded --enable-tool handle_mcp_v2,human_ask
```

Susunan yang dinyatakan dikekalkan dan tercermin dalam susunan alat yang dibentangkan kepada LLM. Alat yang diaktifkan secara eksplisit dikunci daripada pelupusan automatik.

### `--plugin-dir <path>`

Memuatkan pemalam daripada direktori yang dinyatakan. Pilihan ini boleh diulang.

______________________________________________________________________

## Pilihan hanya untuk CLI

### `--inject-message-auto <goal-options>`

Memulakan auto-pilot daripada matlamat suntikan tidak interaktif. Nilai ini menggunakan pilihan yang sama seperti `:auto`; petik nilai lengkap apabila ia mengandungi pilihan.

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sort the items --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sort the items --infinite"
```

Mod normal menggunakan laluan pertimbangan penilai. Tetapkan `UAGENT_AUTO_SENTINEL=1` untuk menyertai mod sentinel LLM tunggal. Dalam mod itu, sasaran LLM mesti menamatkan setiap respons dengan tepat salah satu daripada:

- `<AUTO_CONTINUE>` — jalankan pusingan lain
- `<AUTO_COMPLETE>` — tamat dengan jayanya

Penanda yang hilang atau tidak sah menghentikan pemandu automatik dengan selamat. Ini masih menjalankan target LLM; ia hanya mengelakkan panggilan LLM pemeriksa tambahan.

### `--non-interactive`

Mod tidak interaktif. Tidak memulakan gelung stdin. Jika laluan fail diberikan sebagai hujah berposisi, ia diproses dan program akan keluar serta-merta.

```
uag --non-interaktif README.md
uag --non-interaktif --workdir /tmp/project
```

______________________________________________________________________

## Pilihan pelayan web (`uagw`)

### `--host <alamat>`

Mengikat alamat untuk pelayan Web (lalai: `127.0.0.1`, boleh diatasi oleh `UAGENT_WEB_HOST`).

Secara lalai, pelayan Web mendengar pada localhost sahaja (`127.0.0.1`). Untuk membolehkannya diakses dari mesin lain di rangkaian, gunakan `--host 0.0.0.0`.

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <int>`

Pilih genre alat menggunakan bitmask yang sama seperti yang diterangkan di atas. Apabila ditetapkan, prompt genre interaktif akan diabaikan.

### `--use-tool` / `--no-use-tool`

Mengaktifkan atau menyahaktifkan penghantaran definisi alat ke LLM. Mengatasi `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Mengaktifkan atau menyahaktifkan Computer Use. Mengatasi `UAGENT_COMPUTER_USE`.

### `--no-frontend`

Jalankan hanya API tanpa templat HTML atau fail frontend statik.

### `--embedded`

Mematikan stor sesi dan menyembunyikan alat pengurusan (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Pilihan pelayan A2A (`uaga`)

### `--host <alamat>`

Alamat sambungan untuk pelayan A2A HTTP (lalai: `0.0.0.0`, boleh diubah oleh `UAGENT_A2A_HOST`).

### `--port <nombor>`

Nombor port untuk pelayan A2A HTTP (lalai: `8765`, boleh diubah oleh `UAGENT_A2A_PORT`).

### `--reload`

Mengaktifkan pemuatan semula panas untuk perubahan kod (laluan lalai: dimatikan, boleh diubah oleh `UAGENT_A2A_RELOAD`).

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <int>`

Pilih genre alat menggunakan bitmask yang sama seperti yang diterangkan di atas. Apabila ditetapkan, prompt genre interaktif akan diabaikan.

### `--use-tool` / `--no-use-tool`

Aktifkan atau nyahaktifkan penghantaran definisi alat ke LLM. Mengatasi `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Mengaktifkan atau menyahaktifkan Computer Use. Menimpa `UAGENT_COMPUTER_USE`.

### `--embedded`

Menyahaktifkan stor sesi dan menyembunyikan alat pengurusan alat (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Pembolehubah persekitaran berkaitan

| Pembolehubah | Deskripsi |
|---|---|
| `UAGENT_PROVIDER` | Nama penyedia LLM (diperlukan semasa permulaan) |
| `UAGENT_*_API_KEY` | Kunci untuk penyedia yang dipilih |
| `UAGENT_WORKDIR` | Direktori kerja lalai |
| `UAGENT_WEB_HOST` | Alamat ikatan pelayan web (lalai: `127.0.0.1`) |
| `UAGENT_A2A_HOST` | Alamat ikatan pelayan A2A (lalai: `0.0.0.0`) |
| `UAGENT_A2A_PORT` | Pelabuhan pelayan A2A (lalai: `8765`) |
| `UAGENT_A2A_RELOAD` | Aktifkan pemuatan semula panas A2A secara lalai |
| `UAGENT_USE_TOOL` | Lumpuhkan alat apabila ditetapkan kepada `0`, `false`, `no`, atau `off` |
| `UAGENT_COMPUTER_USE` | Aktifkan atau lumpuhkan Computer Use secara lalai |
| `UAGENT_SESSION_STORE` | Aktifkan atau lumpuhkan stor sesi; Mod terbenam memaksa `0` |
| `UAGENT_PLUGIN_DIRS` | Direktori carian pemalam tambahan |
| `UAGENT_AUTO_SENTINEL` | Pilih untuk mod sentinel auto-pilot LLM tunggal apabila ditetapkan kepada `1` |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | Bilangan maksimum panggilan alat segar berturut-turut (lalai: `100`) |
| `UAGENT_MAX_TOOL_ROUNDS` | Bilangan pusingan LLM/alat maksimum bagi setiap operasi pengguna (lalai: `200`) |
| `UAGENT_SHRINK_CNT` | Ambang pengecutan automatik pilihan dalam mesej (`0`/tidak ditetapkan = dilumpuhkan) |
| `UAGENT_SHRINK_KEEP_LAST` | Mesej untuk disimpan selepas penyusutan (lalai: `20`) |
| `UAGENT_LANG` | Bahasa antara muka (`ja`, `en`, dan lain-lain) |

Untuk senarai penuh pembolehubah persekitaran, lihat [ENVIRONMENT.md](ENVIRONMENT.md).

______________________________________________________________________

## Contoh

### Permulaan minimum dengan OpenAI

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### Ollama tempatan dengan alat asas sahaja

```
set UAGENT_PROVIDER=ollama
set UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### Pelayan web pada semua antara muka

```
set UAGENT_WEB_HOST=0.0.0.0
uagw
```

atau

```
uagw --host 0.0.0.0
```

### A2A pelayan pada localhost dengan port tersuai

```
uaga --host 127.0.0.1 --port 8080
```

### Lumpuhkan alat untuk model kecil

```
uag --no-use-tool --tool-genre-mask 1
```

### Pemprosesan fail tidak interaktif

```
uag --non-interactive README.md
```
