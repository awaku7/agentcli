<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — เกตเวย์ AI สากล</h1>

<p align="center">
 <b>U</b>niversal <b>A</b>I <b>G</b>ateway — สภาพแวดล้อมของคุณ อิสรภาพของคุณ
</p>

<p align="center">
 การดำเนินการไฟล์ / การค้นหาเว็บ / การสร้างและการวิเคราะห์รูปภาพ / การแยก PDF และ Excel / การควบคุม IoT / MCP การบูรณาการ<br>
 ผู้ให้บริการ 24 ราย / 3 UIs / การดำเนินการใช้เครื่องมือแบบขนาน / ทักษะของตัวแทน ตลาด
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a href="https://pypi.org/project/uag/">PyPI</a>
 ·
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">อ่านสิ่งนี้ในภาษาของคุณ</a>
</p>

______________________________________________________________________

## ทำไม uag?

**หลุดพ้นจากการล็อคอินของผู้ขาย** ผู้ช่วย AI ส่วนใหญ่ผูกคุณไว้กับผู้ให้บริการเฉพาะหรือบริการคลาวด์ uag แตกต่าง

- **ทำงานภายในเครื่อง** บนเครื่องของคุณ ข้อมูลของคุณจะอยู่กับคุณ (ยกเว้นการโทร API ครั้ง)
- **เสรีภาพของผู้ให้บริการ**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... ผู้ให้บริการ 24 ราย เข้าถึงได้จากอินเทอร์เฟซเดียว สลับระหว่างกันโดยการกำหนดค่าตัวแปรสภาพแวดล้อมใหม่ — ไม่ต้องติดตั้งใหม่ ไม่มีการย้าย
- **เครื่องมือ 222 รายการ**: ไฟล์ I/O, การค้นหาเว็บ, การสร้างภาพ, Gmail, การสแกนอุปกรณ์ BLE, การรวมเซิร์ฟเวอร์ MCP — **130 รายการถูกทำเครื่องหมายแบบคงที่ว่าปลอดภัยแบบขนาน** (สูงสุด 8 รายการดำเนินการพร้อมกันผ่านกลุ่มเธรด กำหนดค่าได้ผ่าน `UAGENT_PARALLEL_WORKERS`) เมื่อ LLM เรียกใช้เครื่องมือหลายรายการพร้อมกัน uag จะทำการขนานเครื่องมือเหล่านั้นโดยอัตโนมัติ
- **3 UI + A2A**: CLI, GUI, เว็บ และโปรโตคอล Agent-to-Agent เครื่องยนต์เดียวกัน ทุกอินเทอร์เฟซ
- **IoT พร้อม**: SwitchBot, ECHONET Lite, Matter, UPnP — ควบคุมอุปกรณ์ในบ้านของคุณผ่าน AI
- **ทักษะของตัวแทน**: ติดตั้งทักษะที่สร้างโดยชุมชนจากตลาดกลาง ขยาย uag อย่างไม่มีที่สิ้นสุด

uag คือ **ผู้ช่วย AI ของคุณตามเงื่อนไขของคุณ** ไม่เชื่อมโยงกับผู้ให้บริการ, ไม่เชื่อมโยงกับอินเทอร์เฟซ, ไม่เชื่อมโยงกับแพลตฟอร์ม

## Quick Start

```bash
pip install uag
uag
```

เมื่อเปิดใช้งานครั้งแรก วิซาร์ดการตั้งค่าจะนำคุณผ่านการกำหนดค่าผู้ให้บริการ
ดู [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) สำหรับทุกสภาพแวดล้อม ตัวแปร

## การใช้คอมพิวเตอร์

การใช้คอมพิวเตอร์เป็นแบบเลือกใช้และรองรับทั้งรันไทม์เบราว์เซอร์ Playwright ที่มองเห็นได้
และรันไทม์บนเดสก์ท็อป เมื่อเปิดใช้งาน รันไทม์ทั้งสองจะถูกสร้างและลงทะเบียน
รันไทม์ที่เลือกจะถูกควบคุมโดย `UAGENT_COMPUTER_ENVIRONMENT`:

```bat
set UAGENT_COMPUTER_USE=1
set UAGENT_COMPUTER_ENVIRONMENT=browser
```

ใช้ `desktop` เพื่อเลือกรันไทม์เดสก์ท็อป OS แทน ทรัพยากรรันไทม์จะถูก
ปิดพร้อมกันเมื่อออกปกติ `Ctrl-C` และการปิดกระบวนการ ตั้งค่า
`UAGENT_COMPUTER_HEADLESS=1` สำหรับ CI ที่ใช้เบราว์เซอร์หรือการทดสอบควัน
ดู [docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
สำหรับรายละเอียดการบูรณาการและความปลอดภัย

## เสียงเรียลไทม์และ AEC3

โหมดเสียงเรียลไทม์รองรับ OpenAI เรียลไทม์, Azure OpenAI GPT เรียลไทม์, xAI Grok เสียง API, Google Gemini Multimodal Live API และ Amazon Bedrock Nova Sonic พร้อมไมโครโฟนฟูลดูเพล็กซ์และ I/O ลำโพง แบ็กเอนด์ AEC3 `pywebrtc-audio` ที่จำเป็นได้รับการติดตั้งโดยอัตโนมัติ และ SDK สตรีมมิ่งแบบสองทิศทางเสริมของ Bedrock จะถูกติดตั้งโดยอัตโนมัติเฉพาะเมื่อผู้ให้บริการ Bedrock ถูกเลือก:

```bash
python scheck.py realtime
```

ไปป์ไลน์ AEC3 รับสัญญาณไมโครโฟนจริง (`ใกล้`) และเสียงที่ส่งไปยังลำโพงจริง (`ไกล`) เพื่อให้ผู้ช่วยสามารถ ฟังขณะพูด เปิดใช้งานการวินิจฉัยเฉพาะเมื่อตรวจสอบปัญหาเกี่ยวกับเสียง:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime รองรับการรวมการเรียกฟังก์ชันที่จำกัดความปลอดภัย อะแดปเตอร์เรียลไทม์ปัจจุบันเปิดเผย `get_current_time` แบบอ่านอย่างเดียวโดยอัตโนมัติ เครื่องมือทำลายล้างและการควบคุมอุปกรณ์จะไม่ถูกเปิดเผยหากไม่มีรายการที่อนุญาตและขั้นตอนการยืนยันที่ชัดเจน Grok เรียลไทม์ใช้อะแดปเตอร์แยกต่างหากและไม่ได้ใช้เส้นทางการเรียกใช้ฟังก์ชันเฉพาะ OpenAI นี้

## คุณสมบัติ

### 🧠 สถาปัตยกรรมหลายผู้ให้บริการ

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / AI ร่วมกัน / Vercel AI Gateway
ผู้ให้บริการทั้งหมดใช้ชุดเครื่องมือและอินเทอร์เฟซเดียวกัน สลับโดยการตั้งค่า `UAGENT_PROVIDER` — ไม่มีการเปลี่ยนแปลงโค้ด ไม่มีการติดตั้งแยกกัน

#### Ollama และ llama.cpp

Ollama และ llama.cpp เป็นผู้ให้บริการที่แยกจากกัน Ollama ใช้บริการและการจัดการโมเดลของตัวเอง ในขณะที่ `llama.cpp` เชื่อมต่อกับปลายทางที่เข้ากันได้กับ `llama-server` OpenAI:

```bash
# Ollama
UAGENT_PROVIDER=ollama
UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
UAGENT_OLLAMA_DEPNAME=llama3.1
# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY=dummy
```

ผู้ให้บริการ llama.cpp ใช้การแชท เส้นทางที่เข้ากันได้กับความสำเร็จ เก็บ `UAGENT_RESPONSES=0` ไว้เว้นแต่จะมีการกำหนดค่าพร็อกซีที่เข้ากันได้

### ⚡ Parallel Tool Execution

เมื่อ LLM ร้องขอเครื่องมือหลายรายการพร้อมกัน uag **จะขนานกันโดยอัตโนมัติ** เครื่องมือเหล่านั้น
เครื่องมือ 130 รายการจะถูกทำเครื่องหมายแบบคงที่ `x_parallel_safe` และดำเนินการพร้อมกันผ่าน `ThreadPoolExecutor` (8 เธรดตามค่าเริ่มต้น ตั้งค่า `UAGENT_PARALLEL_WORKERS` ที่จะเปลี่ยน)
**ตัวอย่าง**: ถาม "ตรวจสอบสภาพอากาศในเมืองหลวงของนอร์ดิก" → LLM เรียกใช้ `search_web` × 5 ประเทศ → การค้นหาทั้ง 5 รายการทำงานพร้อมกัน → ผลลัพธ์ที่รวบรวมในชุดเดียว
จำนวนปัจจุบันขึ้นอยู่กับโมดูลเครื่องมือที่กำหนด `TOOL_SPEC` (ปัจจุบัน 222 รวมถึงเครื่องมือที่ขึ้นสนิม 2 รายการใน `src/uagent/tools_rust/`) `http_request` ใช้ความปลอดภัยที่คำนึงถึงวิธีการ: การเรียก `GET`/`HEAD`/`OPTIONS` อาจทำงานแบบขนาน ในขณะที่วิธีการเขียนยังคงเป็นแบบอนุกรม
เครื่องมือแบบอ่านอย่างเดียว (การค้นหาไฟล์ การคำนวณแฮช รายการไดเร็กทอรี การแปล การสืบค้น DB ฯลฯ) จะถูกขนานอย่างมาก

### 🧩 ระบบปลั๊กอิน (เข้ากันได้กับโค้ด Claude)

uagent ใช้ปลั๊กอินที่เข้ากันได้กับโค้ด **Claude ระบบ**. ปลั๊กอินรวมทักษะ เอเจนต์ เซิร์ฟเวอร์ MCP ฮุค และอื่นๆ ไว้ในไดเร็กทอรีที่มีอยู่ในตัวเองด้วยรายการ `.claude-plugin/plugin.json`
**ส่วนประกอบที่รองรับ**: ทักษะ เอเจนต์ย่อย เซิร์ฟเวอร์ MCP ฮุค (12 เหตุการณ์รอบการใช้งาน) คำสั่ง Slash รูปแบบเอาต์พุต การกำหนดค่าผู้ใช้ การขึ้นต่อกัน แชนเนล ตลาดกลาง
**CLI คำสั่ง**:

```
:รายการปลั๊กอิน # รายการปลั๊กอินที่ติดตั้ง
:ปลั๊กอินติดตั้ง <แหล่งที่มา> [--ขอบเขต] # ติดตั้ง (dir/zip/git/http)
:ปลั๊กอินติดตั้ง <name>@<marketplace> # ติดตั้งจากตลาดกลาง
:ปลั๊กอินลบ <ชื่อ> # ถอนการติดตั้ง
:ปลั๊กอินเปิดใช้งาน/ปิดการใช้งาน <ชื่อ> # สลับ
:ปลั๊กอินตลาดเพิ่ม/ลบ/รายการ # จัดการ Marketplaces
:plugin init <name> # Scaffold new Plug
```

ดู [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) สำหรับเอกสารฉบับเต็ม

### 🔄 Session Continuity

- **สลับผู้ให้บริการระหว่างเซสชัน** ด้วย `UAGENT_PROVIDER` — ประวัติการสนทนาคือ เก็บรักษาไว้
- **โหลดเซสชันที่ผ่านมา** ด้วย `:load <index>` — ดำเนินการต่อจากจุดที่คุณค้างไว้
- **การแคชผลลัพธ์ของเครื่องมือ** หลีกเลี่ยงการดำเนินการซ้ำซ้อนเมื่อมีการเรียกใช้เครื่องมือเดียวกันซ้ำ

### 🛠 229 Tools

| หมวดหมู่ | เครื่องมือ |
|---|---|
| **การทำงานของไฟล์** | อ่าน/เขียน/สร้าง/ลบ/ค้นหา/grep/hash/zip, file_type, parse_eml (ไฟล์ .eml), `path_alias` |
| **เว็บ** | fetch_url, search_web, ภาพหน้าจอ, browser_playwright, `url_alias`, `public_transit_route` ([คำแนะนำ](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **สื่อ** | Generate_image, analy_image, img2img, audio_speech, audio_transcribe |
| **เอกสาร** | การสกัด PDF/PPTX/DOCX/RTF/ODT, การสกัดแบบมีโครงสร้าง Excel |
| **พยากรณ์** | การคาดการณ์อนุกรมเวลาด้วยโมเดล 9 แบบ (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM ฯลฯ) การเลือกโมเดลอัตโนมัติ การสร้างพล็อต i18n |
| **การสื่อสาร** | gmail_send, gmail_read, bluesky, discord_channel, team_webhook, **pybitchat** (BLE Mesh) — ดู [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) และ [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **ไอโอที** | SwitchBot (คลาวด์ + BLE), ECHONET Lite, สสาร, UPnP, Reverse_geocode |
| **Cloud API** | `aws_api`, `gcp_api`, `azure_api` — การดำเนินการ AWS ทั่วไป, Google Cloud และ Azure API; การดำเนินการเขียนต้องมีการยืนยันอย่างชัดเจน |
| **เครื่องมือสำหรับการพัฒนา** | workspace_status, git_ops, git_review, security_scan, Coverage_report, python_compile, lint_format, run_tests, db_query, **ตัวนำทางซอร์สโค้ด 29 ตัว (ตระกูล idx)** |
| **MCP** | เชื่อมต่อกับเซิร์ฟเวอร์ MCP ภายนอก แสดงรายการเครื่องมือ ดำเนินการ — [คำแนะนำ OAuth / พร็อกซี](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | การสื่อสารระหว่างตัวแทนถึงตัวแทน (กับอินสแตนซ์ uag อื่นๆ หรือเซิร์ฟเวอร์ที่เข้ากันได้กับ A2A) |
| **ระบบ** | env vars, ข้อมูลจำเพาะของระบบ, เวลา, การคำนวณวันที่, [ปริมาณ](docs/QUANTITIES.md), [geodesic_distance](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **การนำทางที่มา** | **เครื่องมือ idx 29 รายการ** สำหรับ Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — รับฟังก์ชัน/ดัชนีคลาสหรือคำจำกัดความเฉพาะโดยไม่ต้องอ่านทั้งไฟล์ |

#### การตรวจสอบพื้นที่เก็บข้อมูลและความครอบคลุม

- `workspace_status`: รายงานสาขา Git ของพื้นที่ทำงานที่ใช้งานอยู่ การเปลี่ยนแปลง สถานะการซิงค์อัปสตรีม รันไทม์ Python และทั่วไป เครื่องหมายโครงการโดยไม่ต้องแก้ไขไฟล์
- `git_review`: สรุปการเปลี่ยนแปลง Git ไฟล์ที่มีความเสี่ยง ผู้สมัครทดสอบ และการค้นพบความลับโดยไม่เปิดเผยค่าที่เป็นความลับ
- `security_scan`: สแกนไฟล์ที่เก็บเพื่อค้นหาความลับที่เป็นไปได้และไฟล์การกำหนดค่าที่มีความเสี่ยง
- `coverage_report`: เรียกใช้และทำให้การครอบคลุมเป็นปกติสำหรับ Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift และ Dart/Flutter
- การพึ่งพาความครอบคลุมที่ขาดหายไปสามารถติดตั้งได้โดยอัตโนมัติเมื่อมีการร้องขอการดำเนินการ `dry_run` ไม่เคยติดตั้งแพ็คเกจ
  ดู [Repository Analysis Tools](docs/REPOSITORY_TOOLS.md) สำหรับพารามิเตอร์ เอาต์พุต และรายละเอียดด้านความปลอดภัย
  ดู [Path and URL aliases](docs/PATH_URL_ALIASES.md) สำหรับการย่อพาธของไฟล์ที่ซ้ำกันและ URL ในอาร์กิวเมนต์ของเครื่องมือ

### 🖥 4 Interfaces + VS Code Extension

| โหมด | คำสั่ง | วัตถุประสงค์ |
|---|---|---|
| **คลี** | `uag` | การทำงานบนเทอร์มินัลที่รวดเร็ว |
| **กุย** | `อูกก` | UI เดสก์ท็อปผ่าน tkinter |
| **เว็บ** | `อู้วว` | การเข้าถึงผ่านเบราว์เซอร์ |
| **A2A เซิร์ฟเวอร์** | `อูก้า` | โปรโตคอล Agent2Agent สำหรับการสื่อสารหลายตัวแทน |
| **รหัส VS** | — | [ส่วนขยาย](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) พร้อมด้วย Chat Panel, Explain, Refactor, Fix Error และ Tools Tree View |
ดู [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) สำหรับรายละเอียดเกี่ยวกับส่วนขยาย VS Code — การติดตั้ง คำสั่ง การผูกคีย์ และ การกำหนดค่า

### 🏠 การควบคุมอุปกรณ์ IoT

- **BACnet**: อ่าน/เขียนอุปกรณ์ BACnet/IP (HVAC, ไฟส่องสว่าง, มิเตอร์ไฟฟ้า) การสมัครสมาชิก COV สำหรับการแจ้งเตือนแบบพุช
- **Modbus TCP**: อ่าน/เขียนการถือครอง/การลงทะเบียนอินพุตและคอยส์ การตรวจสอบการเปลี่ยนแปลงตามการสำรวจ
- **OPC UA**: เรียกดูพื้นที่ที่อยู่ อ่าน/เขียนตัวแปร สมัครรับการเปลี่ยนแปลงข้อมูล
- **SwitchBot**: การควบคุมแบตช์ระบบคลาวด์ & การสแกน/การควบคุม BLE การสมัครสมาชิกตามการสำรวจความคิดเห็น
- **ECHONET Lite**: ค้นหา ควบคุม และสมัครรับการแจ้งเตือน INF จากเครื่องใช้ภายในบ้าน (AC, ไฟ, เครื่องทำน้ำอุ่น ฯลฯ)
- **เรื่อง**: การควบคุมการอ่าน/เขียน + การสมัครสมาชิกแอตทริบิวต์สำหรับการตรวจสอบการเปลี่ยนแปลงสถานะ
- **UPnP**: การค้นพบอุปกรณ์และการส่งต่อพอร์ต IGD
  ดู [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` เพื่อเรียกดู [SkillsMP](https://skillsmp.com) และ [ClawHub](https://clawhub.ai) เพื่อดูทักษะของชุมชน
ติดตั้งและขยาย ขีดความสามารถของ uag ได้ทันที

### 🤖 นักบินอัตโนมัติ (`:อัตโนมัติ`)

uag สามารถ **ไล่ตามเป้าหมายโดยอัตโนมัติในหลาย LLM รอบ** เหมาะสำหรับงานที่ซับซ้อนหลายขั้นตอนที่ต้องการการปรับแต่งซ้ำๆ

- **วิธีการทำงาน**: แต่ละรอบมีคำถามหลัก (ขั้นตอน A) ตามด้วยการตัดสินของผู้ตรวจสอบ (ขั้นตอน B) ที่ตัดสินใจว่า "เสร็จสมบูรณ์หรือดำเนินการต่อ"
- **ผู้ให้บริการรายเดียวกัน API**: การตัดสินของผู้ตรวจสอบใช้เส้นทางโค้ดที่เหมือนกันเป็นคำถามหลัก — รวมถึงคำตอบ API สนับสนุน
- **ผู้พิพากษาแยกต่างหาก LLM** (ตัวเลือก): ตั้งค่า `UAGENT_AP_PROVIDER` เพื่อใช้ ผู้ให้บริการ/รุ่นอื่นสำหรับผู้ตรวจสอบ (เช่น ใช้รุ่นที่ถูกกว่าในการตัดสิน)
- **ออกเมื่อใดก็ได้**: กดปุ่ม `x` เพื่อหยุดทันที แม้จะตอบกลับกลางคันก็ตาม หรือให้ผู้ตรวจสอบตัดสินใจว่าเมื่อใดจะบรรลุเป้าหมาย
- **กำหนดค่าได้**: `--max-rounds N` เพื่อควบคุมงบประมาณ
  ดู [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) สำหรับเอกสารฉบับเต็ม

### 🧩 Batch State Manager

uag สามารถติดตามความคืบหน้าได้ งานหลายไฟล์ที่ใช้เวลานาน เมื่อ LLM ประมวลผลไฟล์หลายสิบไฟล์ `batch_state` จะยังคงอยู่ในรายการไฟล์ที่รอดำเนินการ เสร็จสมบูรณ์ และล้มเหลวในดิสก์ หากเซสชันสิ้นสุดลงหรือหมดเวลา การเรียกใช้ครั้งถัดไปจะดำเนินการต่อจากจุดที่หยุดไว้ — ไม่มีอะไรสูญหาย

### 🛡 Human-in-the-Loop

`human_ask` อนุญาตให้ LLM หยุดชั่วคราวและขอการยืนยันของคุณก่อนที่จะดำเนินการทำลายล้าง (การลบไฟล์ เขียนทับ คำสั่งเชลล์) คุณควบคุมได้

### 🛑 ขัดจังหวะ (ปุ่ม c / หยุด)

หยุดการสร้างการตอบสนอง LLM ได้ตลอดเวลา และป้อนคำสั่งหยุดกลับไปที่ LLM.
| อินเตอร์เฟซ | วิธีการขัดจังหวะ |
|---|---|
| **คลี** | กดปุ่ม `c` ระหว่างการสตรีม LLM — การตอบกลับปัจจุบันจะหยุดลง และ `"หยุด"` จะถูกส่งเป็นข้อความผู้ใช้ ดังนั้น LLM จะตอบกลับตามนั้น |
| **เว็บ UI** | คลิกปุ่มสีแดง **■ หยุด** (ปรากฏขึ้นโดยอัตโนมัติระหว่างการประมวลผล LLM) |
| \*\* GUI เดสก์ท็อป \*\* | คลิกปุ่ม **■** สีแดง (ปรากฏขึ้นโดยอัตโนมัติระหว่างการประมวลผล LLM) |
อินเทอร์รัปต์ทำงานเป็น "การแทรกพร้อมท์": แทนที่จะยกเลิกเพียงแต่อินเทอร์รัปต์จะป้อน `"หยุด"` กลับไปที่ LLM เป็นข้อความผู้ใช้ เพื่อให้สามารถสรุปหรือรับทราบการขัดจังหวะได้อย่างสวยงาม
กดปุ่ม `x` เพื่อออกจากโหมดนำร่องอัตโนมัติ (ดู [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Browser Automation & Web Inspector

เครื่องมือเสริม Playwright สองเครื่องมือ:

- **browser_playwright**: ทำให้เซสชันเบราว์เซอร์จริงเป็นอัตโนมัติ — นำทาง คลิก กรอกแบบฟอร์ม แยกข้อมูล จัดการโฟลว์หลายหน้า ทำงานแบบไม่มีหัวหรือหัวขาด
- **playwright_inspector**: บันทึกการเปลี่ยนเบราว์เซอร์ จับภาพสแนปชอต DOM และภาพหน้าจอในแต่ละขั้นตอน มีประโยชน์สำหรับการดีบักการโต้ตอบบนเว็บหรือตรวจสอบการเปลี่ยนแปลงเพจเมื่อเวลาผ่านไป

### 🔄 การโหลดเครื่องมือแบบไดนามิก

`tool_catalog` และ `tool_load` ช่วยให้คุณค้นพบและเปิดใช้งานเครื่องมือในขณะรันไทม์
ไม่จำเป็นต้องโหลดทุกอย่างเมื่อเริ่มต้น — เปิดใช้งานเฉพาะสิ่งที่คุณต้องการเมื่อคุณต้องการเท่านั้น

### ปู Rust Native Tools

`uuid_gen` และ `slugify` ได้รับการปรับใช้ใน Rust (ผ่าน PyO3) เพื่อประสิทธิภาพ
โหลดโดยตรงจาก `.pyd` ที่สร้างไว้ล่วงหน้า — \*\*ไม่จำเป็นต้องติดตั้ง pip`**. นักพัฒนาภายนอกยังสามารถจัดส่งเครื่องมือที่ใช้ Rust ได้: วาง `.pyd`ถัดจาก  wrapper`.py`ใช้`load_rust_pyd()`จาก`uagent.tools.rust_helper\` และ
ผู้ใช้จะได้รับเครื่องมือโดยไม่ต้องทำอะไรเพิ่มเติม การพึ่งพาอาศัยกัน ดู
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日本語 / อังกฤษ / 简体中文 / 繁體中文 / เกาหลี / Español / Français / Русский / และอื่นๆ
ตั้งค่า `UAGENT_LANG` เพื่อสลับ ดู [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) เพื่อเพิ่มสถานที่ใหม่
คำแปลของ README นี้มีอยู่ใน [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 ตัวแปรสภาพแวดล้อมที่เข้ารหัส

จัดเก็บคีย์ API และข้อมูลลับใน `.env.sec` — ไฟล์ `.env` ที่เข้ารหัส
จัดการด้วย `uag_envsec`.

## การกำหนดค่าและรายละเอียด

- **ตัวแปรสภาพแวดล้อม**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **วิซาร์ดการตั้งค่า**: `python -m uagent.setup_cli`
- **env ที่เข้ารหัส**: `uag_envsec` — เข้ารหัส `.env` เป็น `.env.sec`
- **Responses API**: ตั้งค่า `UAGENT_RESPONSES=1` สำหรับการตอบกลับ API โหมด (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI) เปิดใช้งานอัตโนมัติสำหรับ Sakana AI (Fugu).
- **เอกสารสำหรับนักพัฒนา**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **การไหลของเครื่องมือ**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — วิธีการส่งเครื่องมือไปยัง LLM (มาสก์ประเภท, tool_catalog, GPT-5.4+ เนทีฟ tool_search)
- **เคล็ดลับเล็กๆ น้อยๆ LLM**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## ปรัชญาโครงการ

uag ปรารถนาที่จะเป็น **AI ของคุณบนเครื่องของคุณ ตามเงื่อนไขของคุณ**

- ไม่มีการพึ่งพา SaaS — ทำงานภายในเครื่อง
- ไม่มีการล็อคอินของผู้ให้บริการ — สลับได้ตลอดเวลา
- ไม่มีการล็อคอิน UI — CLI / GUI / Web / A2A
- ไม่มีการล็อคอินคุณสมบัติ — ขยายด้วยเครื่องมือและทักษะ

ประสบการณ์ตัวแทน AI ฟรี ฟรีจากผู้ขาย ล็อคอิน

### ✨ สร้างเครื่องมือของคุณเอง

การเขียนเครื่องมือใหม่สำหรับ uag นั้นตรงไปตรงมา — สร้างไฟล์ `.py` ไฟล์เดียวด้วย
`TOOL_SPEC` และ `run_tool()` แล้ววางไว้ใน `UAGENT_EXTERNAL_TOOLS_DIR` และ
จะพร้อมใช้งานทันที สำหรับนักพัฒนา Rust ให้จัดส่ง `.pyd` ที่สร้างไว้ล่วงหน้าพร้อม
การพึ่งพาเพิ่มเติมเป็นศูนย์สำหรับผู้ใช้

ดู [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
สำหรับคำแนะนำทีละขั้นตอน

## มีส่วนร่วม

ยินดีต้อนรับการมีส่วนร่วม! รายงานข้อบกพร่อง คำแนะนำคุณลักษณะ การปรับปรุงเอกสาร การแปล และคำขอดึง — ชื่นชมทั้งหมด

- **ปัญหา**: เปิดปัญหา GitHub สำหรับข้อบกพร่องหรือคำขอคุณลักษณะ
- **คำขอดึง**: แยก repo ทำการเปลี่ยนแปลง และส่ง PR ดู [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) สำหรับการตั้งค่าและแนวทางการพัฒนา
- **การแปล**: ยินดีรับการแปล README และการเพิ่มสถานที่ ดู [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **เครื่องมือและทักษะ**: สามารถสนับสนุนปลั๊กอินเครื่องมือใหม่และทักษะของตัวแทนผ่านทางตลาดกลางได้

### การตรวจสอบการพัฒนา (ก่อน PR)

ติดตั้งการทดสอบเท่านั้น การพึ่งพาอาศัยกันก่อน พวกมันจะถูกกันไม่ให้อยู่ในรายการรันไทม์
การพึ่งพา:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
```

รันการตรวจสอบเดียวกันกับที่ใช้โดย GitHub Actions ก่อนที่จะกด:

```bash
python -m ruff check src tests
python -m black --check src tests
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .
```

เพื่อการวนซ้ำในเครื่องที่เร็วขึ้น ให้รันเฉพาะการทดสอบที่ได้รับผลกระทบเท่านั้น:

```bash
pytest -q tests/<affected_area>
```

การตรวจสอบเพิ่มเติมเมื่อเกี่ยวข้อง:

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

หลังจากแก้ไข locale (`.po`): `python scripts/compile_locales.py` และ `python scripts/po_qc_summary.py`.

นโยบายรันไทม์ (รายละเอียดใน [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) §6.1): ผู้ช่วยเหลือเพิ่มแทน `sys.exit`; โฮสต์เครื่องมือเปลี่ยนเครื่องมือ `SystemExit`/`Exception` เป็นสตริงข้อผิดพลาด ดังนั้นเครื่องมือเดียวจึงไม่สามารถฆ่ากระบวนการได้ การออกอย่างรวดเร็วเมื่อล้มเหลวยังคงเป็นเจตนา

## สถาปัตยกรรมและค่าคงที่ในการปฏิบัติงาน

ดู [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) สำหรับสัญญาที่คงทนซึ่งครอบคลุมวงจรการใช้งาน A2A, บริบท I18N, การติดตั้งการพึ่งพาเพิ่มเติม, ความปลอดภัยของเครื่องมือ, ความสามารถของผู้ให้บริการ, ขอบเขตความน่าเชื่อถือของ OAuth, เหตุการณ์ที่มีโครงสร้าง และการตรวจสอบการยอมรับ

## Enterprise Policy Engine

รองรับนโยบายระดับองค์กรสำหรับเครื่องมือ ผู้ให้บริการ ข้อมูลรับรอง เซิร์ฟเวอร์ MCP เครือข่าย ทักษะ และปลั๊กอิน ตั้งค่า `UAGENT_POLICY_FILE` เป็นไฟล์นโยบาย JSON/YAML ดู [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) สำหรับตัวอย่างการกำหนดค่า บทบาท การยืนยัน และรายการที่อนุญาต

### Runtime recovery and orchestration

ดู [RESTART_RECOVERY.md](docs/RESTART_RECOVERY.md) / [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) เพื่อการกู้คืนที่คงทน การดำเนินการที่คำนึงถึงการพึ่งพา การประสานหลายเอเจนต์ และการใช้งาน A2A ระยะไกล

ดู [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) สำหรับการประสานงานการเช่าผู้นำรันไทม์ที่ใช้ร่วมกัน
