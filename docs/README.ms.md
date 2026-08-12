# uag — Universal AI Gateway

uag ialah ejen AI tempatan yang memberi kebebasan untuk memilih penyedia model, antara muka dan alat.

## Mula dengan pantas

```bash
pip install uag
uag
```

Pada pelancaran pertama, wizard persediaan akan membantu anda mengkonfigurasi penyedia. Lihat [pemboleh ubah persekitaran](ENVIRONMENT.md) untuk semua tetapan.

## Ciri utama

- **24 penyedia**: OpenAI, PFN (PLaMo), Azure, Bedrock, OpenRouter, Ollama, Gemini, Vertex AI, Claude, Grok, NVIDIA, Novita, DeepSeek, Z.AI, HuggingFace, Alibaba Cloud, Moonshot, Xiaomi MiMo, LM Studio, MiniMax, Sakana AI, SAKURA AI Engine, Together AI dan Vercel AI Gateway.
- **222 alat** untuk operasi fail, carian web, imej, audio, dokumen, IoT, MCP, A2A dan pembangunan.
- **API awan**: `aws_api`, `gcp_api`, `azure_api` — AWS, Google Cloud, and Azure API operations; write operations require explicit confirmation.
- **130 alat** ditanda `x_parallel_safe` dan boleh dijalankan secara selari.
- **4 antara muka**: CLI, GUI, Web dan A2A, serta sambungan VS Code.
- Pemuatan alat dinamik, Agent Skills, kesinambungan sesi dan operasi tempatan.

## Alat dan IoT

uag menyokong BACnet, Modbus TCP, OPC UA, SwitchBot, ECHONET Lite, Matter dan UPnP. Alat boleh ditemui dan diaktifkan semasa runtime menggunakan `tool_catalog` dan `tool_load`.

## Dokumentasi

- [Pemboleh ubah persekitaran](ENVIRONMENT.md)
- [Panduan mula pantas](QUICKSTART.md)
- [Komunikasi dan bitchat](COMMUNICATION.md)
- [Kes penggunaan IoT](IOT_USECASE.md)
- [Semua terjemahan README](README.translations.md)

Untuk PFN/PLaMo, gunakan `UAGENT_PROVIDER=pfn` bersama `UAGENT_PFN_API_KEY`, `UAGENT_PFN_BASE_URL` dan `UAGENT_PFN_DEPNAME`.

Lihat [README.md](../README.md) untuk dokumentasi lengkap dalam bahasa Inggeris.
#### Semakan dan liputan repositori

- `git_review`: meringkaskan perubahan Git, fail berisiko, calon ujian dan penemuan rahsia tanpa mendedahkan nilai rahsia.
- `security_scan`: imbas fail repositori untuk kemungkinan rahsia dan fail konfigurasi berisiko.
- `coverage_report`: run dan liputan RusScript/Java, Python Type, Rustrip/Java .NET, C/C++, Ruby, PHP, Swift dan Dart/Flutter.
- Kebergantungan liputan yang hilang boleh dipasang secara automatik apabila pelaksanaan diminta; `dry_run` tidak pernah memasang pakej.

Lihat [Alat Analisis Repositori](REPOSITORY_TOOLS.md) untuk parameter, output dan butiran keselamatan.

