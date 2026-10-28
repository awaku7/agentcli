<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Model AI anda. Alat anda. Persekitaran anda.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Bahasa lain</a></p>

---

**UAG ialah persekitaran pelaksanaan ejen AI sumber terbuka yang mengutamakan operasi setempat.** Ia menghubungkan model bahasa pilihan anda dengan alat dan sistem yang anda gunakan. Urus kod, fail, pelayar, perkhidmatan dan peranti melalui antara muka yang konsisten tanpa terikat kepada satu penyedia model.

| **Pilih model anda** | **Sambungkan alat sebenar** | **Kekalkan kawalan** |
| :--- | :--- | :--- |
| Model awan dan setempat seperti OpenAI, Claude, Gemini, Grok, Bedrock dan Ollama | Fail, kod, web, MCP, Agent Skills, pemalam, awan dan IoT | Pelaksanaan setempat, pengesahan manusia, penyimpanan bukti kelayakan dan dasar yang boleh ditetapkan |

> UAG ialah **lapisan pelaksanaan ejen, bukan penyedia model**. Panggilan kepada model dan perkhidmatan luaran bergantung pada tetapan. Keutamaan setempat tidak bererti operasi luar talian sepenuhnya atau semua alat diasingkan secara lalai.

## Mula pantas
<!-- README-SYNC:quick-start -->

Memerlukan **Python 3.11 atau lebih baharu**. Pasang UAG daripada [PyPI](https://pypi.org/project/uag/) dan jalankan CLI interaktif:

~~~bash
python -m pip install --upgrade uag
uag
~~~

Pada pelancaran pertama, panduan persediaan membantu memilih penyedia model dan menetapkan bukti kelayakan. Anda juga boleh menggunakan pemboleh ubah persekitaran atau stor kelayakan. Untuk memasang lebih banyak kebergantungan penyedia dan alat terlebih dahulu:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Kemudian cuba permintaan berikut:

~~~text
> Apakah perubahan dalam repositori Git ini? Ringkaskan risikonya.
> Cari dokumentasi terkini untuk pustaka ini dan terangkan langkah migrasi.
> Periksa fail-fail ini dan hasilkan laporan ringkas.
> :help
~~~

Pengguna baharu boleh membaca panduan pemasangan Windows termasuk Git dan persekitaran maya, serta rujukan konfigurasi: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Antara muka
<!-- README-SYNC:interfaces -->

Semua pintu masuk menggunakan masa jalan ejen dan daftar alat yang sama.

| Antara muka | Mulakan | Sesuai untuk |
| :--- | :--- | :--- |
| **CLI** | `uag` | Terminal dan automasi |
| **Desktop** | `uagg` | Perbualan dalam aplikasi desktop |
| **Web** | `uagw` | Perbualan dan bilik dalam pelayar |
| **A2A** | `uaga` | Integrasi antara ejen |
| **VS Code** | [Panduan sambungan](VSCODE.md) | Bekerja bersama kod |

Desktop dan Web memerlukan kebergantungan tambahan yang tidak disertakan dalam `uag[core,providers,tools]`:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Pelayan Web boleh cuba memasang FastAPI dan Uvicorn ketika bermula. Pemasangan awal mengelakkan pergantungan pada pemasangan automatik. Butiran: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## Perkara yang boleh dilakukan dengan UAG
<!-- README-SYNC:capabilities -->

| Keupayaan | Yang disediakan oleh UAG |
| :--- | :--- |
| **Aliran kerja bebas model** | Tukar penyedia awan atau setempat melalui `UAGENT_PROVIDER` tanpa menulis semula alat |
| **Kod dan fail** | Navigasi repositori, semakan Git, lint, ujian, operasi fail dan automasi pelayar |
| **Alat boleh diperluas** | Lebih 200 alat, penemuan dinamik melalui `tool_catalog` / `tool_load`, alat Python dan Rust tersuai |
| **Ejen bersambung** | MCP, A2A, pemalam serasi Claude Code, Agent Skills dan subejen |
| **Tugas jangka panjang** | Autopilot, bacaan bebas secara selari, jadual, pemulihan dan sesi kekal |
| **Melebihi terminal** | Awan, komunikasi, dokumen, media, suara masa nyata dan protokol IoT yang disokong |

### Satu masa jalan, pelbagai integrasi
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

**Contoh penyedia model yang disokong** terdapat di bawah. Tetapan khusus dijelaskan dalam rujukan persekitaran.

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

[ENVIRONMENT.md](ENVIRONMENT.md)

### Sesuaikan dengan kemahiran dan pemalam
<!-- README-SYNC:extensions -->

Luaskan UAG tanpa mengubah terasnya. Pasang Agent Skills daripada SkillsMP atau ClawHub, sambungkan pelayan MCP atau muatkan pemalam serasi Claude Code yang mengandungi alat, kemahiran, ejen dan hooks.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Alat tersuai boleh menyediakan `TOOL_SPEC` dan `run_tool()`; alat berasaskan Rust turut disokong. Rujuk panduan: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## Untuk aliran kerja sebenar
<!-- README-SYNC:workflows -->

### Konteks dan memori
<!-- README-SYNC:context-memory -->

Hasil alat yang besar boleh disimpan sebagai **artifak** agar tidak memenuhi konteks aktif model. Ejen boleh mendapatkan semula bahagian berkaitan melalui `artifact_read`. Sesi disimpan dalam SQLite secara lalai, termasuk carian sejarah dan semakan memori secara jelas.

- [Context compression](CONTEXT_COMPRESSION.ms.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Automasi dan kerjasama
<!-- README-SYNC:automation -->

UAG menyokong bacaan bebas selari, penyelarasan pelbagai ejen, pemulihan sesi dan autopilot untuk kerja beberapa pusingan. Mulakan dengan `:auto`; tekan **F12** untuk menghentikan jawapan semasa dan meminta autopilot berhenti.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Keselamatan dan kebolehcerapan
<!-- README-SYNC:security -->

Operasi sensitif boleh memerlukan pengesahan `human_ask`. Bukti kelayakan boleh disimpan dalam pengurus sistem pengendalian atau fail tersulit. Antara muka Web menyokong log masuk OIDC dan kawalan akses apabila dikonfigurasi. Jejak dan metrik OpenTelemetry adalah **pilihan**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Kawalan ini boleh ditetapkan tetapi **tidak menjamin** semua pelaksanaan alat diasingkan dalam sandbox. Baca panduan penggunaan dan dasar sebelum membuka UAG kepada pengguna atau rangkaian yang tidak dipercayai.

### Bahasa, peranti dan suara
<!-- README-SYNC:languages -->

UAG menyediakan sumber untuk **38 lokal** (bahasa Inggeris dan 37 terjemahan), integrasi suara dua hala pilihan, serta alat untuk SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP dan OPC UA.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Dokumentasi
<!-- README-SYNC:documentation -->

Mulakan dengan panduan berikut sebelum meneroka butiran:

| Mula di sini | Ketahui lanjut |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

Anda juga boleh melayari semua dokumen dan terjemahan: [Documentation](./) · [Other languages](README.translations.md).

## Pembangunan dan sumbangan
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

Sebelum pull request yang mengubah **kod Python**, jalankan ujian dan semakan projek yang berkaitan:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Peraturan sumbangan dan panduan pembangun tersedia di bawah. Laporan pepijat, penambahbaikan dokumentasi, alat, terjemahan dan pull request berfokus amat dialu-alukan: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Lesen
<!-- README-SYNC:license -->

UAG diedarkan di bawah lesen: [Apache License 2.0](../LICENSE).
