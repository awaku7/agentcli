<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Model AI Anda. Peralatan Anda. Lingkungan Anda.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Bahasa lainnya</a></p>

---

**UAG adalah runtime agen AI sumber terbuka yang mengutamakan eksekusi lokal.** UAG menghubungkan model bahasa pilihan Anda dengan alat dan sistem yang digunakan. Kerjakan kode, berkas, browser, layanan, serta perangkat melalui antarmuka yang konsisten tanpa terikat pada satu penyedia model.

| **Pilih model** | **Hubungkan alat nyata** | **Tetap memegang kendali** |
| :--- | :--- | :--- |
| Model cloud dan lokal seperti OpenAI, Claude, Gemini, Grok, Bedrock, dan Ollama | Berkas, kode, web, MCP, Agent Skills, plugin, layanan cloud, dan IoT | Eksekusi lokal, konfirmasi manusia, penyimpanan kredensial, dan kebijakan yang dapat diatur |

> UAG adalah **lapisan eksekusi agen, bukan penyedia model**. Panggilan ke model serta layanan eksternal bergantung pada konfigurasi. Local-first bukan berarti sepenuhnya offline atau seluruh alat terisolasi secara bawaan.

## Mulai cepat
<!-- README-SYNC:quick-start -->

Diperlukan **Python 3.11 atau lebih baru**. Instal UAG dari [PyPI](https://pypi.org/project/uag/) dan jalankan CLI interaktif:

~~~bash
python -m pip install --upgrade uag
uag
~~~

Saat pertama dijalankan, panduan penyiapan membantu memilih penyedia model dan mengatur kredensial. Anda juga bisa memakai variabel lingkungan atau penyimpanan kredensial. Untuk memasang lebih banyak dependensi penyedia dan alat sejak awal:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Lalu coba permintaan berikut:

~~~text
> Apa yang berubah di repositori Git ini? Ringkas risikonya.
> Cari dokumentasi terbaru pustaka ini dan jelaskan langkah migrasinya.
> Periksa berkas-berkas ini dan buat laporan singkat.
> :help
~~~

Pengguna baru dapat membaca panduan instalasi Windows, termasuk Git dan lingkungan virtual, serta referensi konfigurasi: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Antarmuka
<!-- README-SYNC:interfaces -->

Semua cara masuk memakai runtime agen dan registri alat yang sama.

| Antarmuka | Jalankan | Cocok untuk |
| :--- | :--- | :--- |
| **CLI** | `uag` | Terminal dan otomatisasi |
| **Desktop** | `uagg` | Percakapan dalam aplikasi desktop |
| **Web** | `uagw` | Percakapan dan ruang di browser |
| **A2A** | `uaga` | Integrasi antaragen |
| **VS Code** | [Panduan ekstensi](VSCODE.md) | Bekerja bersama kode |

Antarmuka Desktop dan Web memerlukan dependensi tambahan yang tidak termasuk `uag[core,providers,tools]`:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Server Web dapat mencoba memasang FastAPI dan Uvicorn saat mulai. Pemasangan lebih dulu menghindari ketergantungan pada instalasi otomatis. Rincian: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## Apa yang bisa dibuat dengan UAG
<!-- README-SYNC:capabilities -->

| Kemampuan | Yang disediakan UAG |
| :--- | :--- |
| **Alur kerja bebas model** | Ganti penyedia lokal dan cloud melalui `UAGENT_PROVIDER` tanpa menulis ulang alat |
| **Kode dan berkas** | Menjelajahi repositori, memeriksa Git, lint, pengujian, operasi berkas, dan otomatisasi browser |
| **Alat yang dapat diperluas** | Lebih dari 200 alat, penemuan dinamis lewat `tool_catalog` / `tool_load`, alat Python dan Rust khusus |
| **Agen terhubung** | MCP, A2A, plugin kompatibel Claude Code, Agent Skills, dan subagen |
| **Tugas berjalan lama** | Autopilot, pembacaan independen paralel, penjadwalan, pemulihan, dan sesi tersimpan |
| **Melampaui terminal** | Cloud, komunikasi, dokumen, media, suara real-time, dan protokol IoT yang didukung |

### Satu runtime, banyak integrasi
<!-- README-SYNC:integrations -->

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

**Contoh penyedia model yang didukung** tercantum di bawah; pengaturan khusus tersedia dalam panduan lingkungan.

### Sesuaikan dengan skills dan plugin
<!-- README-SYNC:extensions -->

Perluas UAG tanpa mengubah inti. Instal Agent Skills melalui SkillsMP atau ClawHub, sambungkan server MCP, atau muat plugin kompatibel Claude Code yang berisi alat, skills, agen, dan hooks.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Alat khusus dapat menyediakan `TOOL_SPEC` dan `run_tool()`; alat berbasis Rust juga didukung. Lihat panduan: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## Untuk alur kerja nyata
<!-- README-SYNC:workflows -->

### Konteks dan memori
<!-- README-SYNC:context-memory -->

Hasil alat yang besar dapat disimpan sebagai **artefak** agar tidak memenuhi konteks aktif model. Agen mengambil bagian yang diperlukan nanti melalui `artifact_read`. Sesi disimpan dalam SQLite secara bawaan, dengan pencarian riwayat dan pemeriksaan memori secara eksplisit.

- [Context compression](CONTEXT_COMPRESSION.id.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Otomatisasi dan kolaborasi
<!-- README-SYNC:automation -->

UAG mendukung pembacaan independen secara paralel, koordinasi multiagen, pemulihan sesi, dan autopilot untuk pekerjaan beberapa putaran. Mulai dengan `:auto`; tekan **F12** untuk menghentikan jawaban saat ini dan meminta autopilot berhenti.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Keamanan dan observabilitas
<!-- README-SYNC:security -->

Operasi sensitif dapat memerlukan persetujuan `human_ask`. Kredensial dapat disimpan dalam pengelola sistem operasi atau berkas terenkripsi. Antarmuka Web mendukung login OIDC dan kontrol akses setelah dikonfigurasi. Pelacakan serta metrik OpenTelemetry bersifat **opsional**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Kontrol tersebut dapat dikonfigurasi dan **tidak menjamin** setiap alat dijalankan terisolasi dalam sandbox. Baca panduan penerapan dan kebijakan sebelum membuka UAG untuk pengguna atau jaringan yang tidak tepercaya.

### Bahasa, perangkat, dan suara
<!-- README-SYNC:languages -->

UAG menyediakan sumber daya untuk **38 lokal** (bahasa Inggris dan 37 terjemahan), integrasi suara dua arah opsional, serta alat untuk SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP, dan OPC UA.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Dokumentasi
<!-- README-SYNC:documentation -->

Mulailah dari panduan berikut dan pelajari topik secara mendalam:

| Mulai di sini | Pelajari lebih lanjut |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

Anda juga dapat menjelajahi semua dokumentasi dan terjemahan: [Documentation](./) · [Other languages](README.translations.md).

## Pengembangan dan kontribusi
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

Sebelum pull request yang mengubah **kode Python**, jalankan pengujian terkait dan pemeriksaan proyek:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Aturan kontribusi dan panduan pengembang tersedia di bawah. Laporan bug, perbaikan dokumentasi, alat, terjemahan, dan pull request terfokus disambut baik: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Lisensi
<!-- README-SYNC:license -->

UAG tersedia berdasarkan lisensi: [Apache License 2.0](../LICENSE).
