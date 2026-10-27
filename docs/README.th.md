<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  เอเจนต์ภายในเครื่องหนึ่งตัว โมเดลใดก็ได้ เครื่องมือใดก็ได้ สภาพแวดล้อมของคุณ กฎของคุณ
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI status"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI version"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="https://github.com/awaku7/agentcli/blob/main/LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="PyPI Downloads"></a>
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a> ·
  <a href="https://pypi.org/project/uag/">PyPI</a> ·
  <a href="https://github.com/awaku7/agentcli/discussions">Discussions</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Translations</a>
</p>

______________________________________________________________________

**เหตุใดจึงเป็น uag?**

uag คือเอเจนต์ AI แบบ local-first ที่เชื่อมต่อโมเดลที่คุณต้องการเข้ากับเครื่องมือที่คุณใช้งานจริง
มอบ runtime เดียวที่ขยายได้สำหรับไฟล์ เบราว์เซอร์ codebase การสื่อสาร Cloud API
อุปกรณ์ IoT เซิร์ฟเวอร์ MCP และเวิร์กโฟลว์แบบหลายเอเจนต์

- **อิสระในการเลือก Provider** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek และอื่น ๆ
- **การทำงานแบบ Local-first** — runtime ของเอเจนต์และการเรียกใช้เครื่องมืออยู่บนเครื่องของคุณ มีเพียง API call ที่คุณเลือกเท่านั้นที่ออกจากเครื่อง
- **ชั้นเครื่องมือเดียว** — เครื่องมือชุดเดียวกันทำงานได้จาก CLI, desktop GUI, web UI, VS Code และ A2A
- **ออกแบบมาเพื่อทำงานขนาน** — การดำเนินการแบบอ่านอย่างเดียวที่เป็นอิสระต่อกันสามารถทำงานพร้อมกันได้
- **ขยายได้** — เพิ่มเครื่องมือ ปลั๊กอิน Agent Skills เซิร์ฟเวอร์ MCP และเครื่องมือที่ทำงานด้วย Rust ได้โดยไม่ต้องเปลี่ยน core
- **คำนึงถึงความปลอดภัย** — การดำเนินการที่ทำลายข้อมูล ข้อมูลรับรอง การควบคุมอุปกรณ์ และการเขียนผ่านเครือข่ายรองรับการยืนยันและการควบคุมนโยบายอย่างชัดเจน

> **กล่าวโดยสรุป:** uag คือ control plane ระหว่างโมเดล AI กับสภาพแวดล้อมจริงของคุณ

> **🧠 ผลลัพธ์ของเครื่องมือที่คำนึงถึงบริบท** — ผลลัพธ์ของเครื่องมือขนาดใหญ่จะถูกเก็บไว้นอกบริบทของโมเดลที่กำลังทำงานอยู่ เมื่อเป็นไปได้ uag เก็บผลลัพธ์เหล่านั้นไว้ในรูปแบบ Artifacts และส่งตัวอย่างที่จำกัดพร้อมการอ้างอิง Artifact ที่เสถียรไปยังโมเดลแทน วิธีนี้สามารถลดจำนวนโทเค็นอินพุตที่จำเป็นสำหรับรอบการสนทนาถัดไปได้อย่างมีนัยสำคัญ เมื่อเครื่องมือสร้างผลลัพธ์ที่มีขนาดใหญ่
> [คู่มือการบีบอัดบริบทฉบับละเอียด](CONTEXT_COMPRESSION.th.md)

## เริ่มต้นอย่างรวดเร็ว

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

การเปิดใช้งานครั้งแรกจะแสดง setup wizard เพื่อช่วยกำหนดค่า provider และจัดเก็บการตั้งค่าที่เลือกไว้
ในสภาพแวดล้อมภายในเครื่องของคุณ

สำหรับกลุ่มฟีเจอร์ทั่วไป:

```bash
python -m pip install "uag[core,providers,tools]"
```

> การผสานรวมเฉพาะแพลตฟอร์มเป็นตัวเลือก ติดตั้งเฉพาะสิ่งที่ระบบปฏิบัติการของคุณต้องใช้ ดู

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## อินเทอร์เฟซ

| อินเทอร์เฟซ | คำสั่ง | เหมาะสำหรับ |
|---|---|---|
| **CLI** | `uag` | งานที่รวดเร็วและใช้คีย์บอร์ดเป็นหลัก |
| **Desktop GUI** | `uagg` | ประสบการณ์เดสก์ท็อปแบบ native |
| **Web UI** | `uagw` | การเข้าถึงผ่านเบราว์เซอร์ |
| **A2A server** | `uaga` | การสื่อสารระหว่างเอเจนต์ |
| **VS Code** | Extension | อธิบาย รีแฟกเตอร์ แก้ไข และเรียกดูเครื่องมือในเอดิเตอร์ |

อินเทอร์เฟซทั้งหมดใช้การกำหนดค่า provider ทะเบียนเครื่องมือ กฎความปลอดภัย และข้อมูลเซสชันร่วมกัน

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## สิ่งที่คุณสร้างได้

อะแดปเตอร์ provider รองรับ runtime แบบ hosted และ local รวมถึง:

**OpenAI · Meta Model API · Anthropic · Google Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · OpenRouter · Ollama · llama.cpp · Grok · DeepSeek · NVIDIA · Hugging Face · Alibaba Cloud · Moonshot · Xiaomi MiMo · LM Studio · MiniMax · Sakana AI · SAKURA AI Engine · Together AI · Vercel AI Gateway · PFN/PLaMo · Z.AI · Novita**

เปลี่ยน provider ด้วย `UAGENT_PROVIDER` โดยเครื่องมือและอินเทอร์เฟซของคุณไม่เปลี่ยนแปลง

**ทำงานกับสภาพแวดล้อมของคุณ**

- อ่าน สร้าง แก้ไข ค้นหา คำนวณ hash จัดเก็บถาวร และตรวจสอบไฟล์
- รีวิวการเปลี่ยนแปลงของ Git สแกนหา secrets รันทดสอบ lint คอมไพล์ และวัด coverage
- นำทาง codebase ขนาดใหญ่ที่ใช้ Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA และภาษาอื่น ๆ
- ทำงานอัตโนมัติกับเบราว์เซอร์ด้วย Playwright รวมถึงเวิร์กโฟลว์หลายหน้าและการดาวน์โหลด

**เชื่อมต่อบริการและอุปกรณ์**

- **MCP** — เชื่อมต่อเซิร์ฟเวอร์เครื่องมือภายนอก รวมถึงบริการที่รองรับ OAuth
- **A2A** — ประสานงานกับเอเจนต์และเซิร์ฟเวอร์ที่เข้ากันได้อื่น ๆ
- **Cloud** — เข้าถึง AWS, Google Cloud และ Azure API พร้อมการยืนยันสำหรับการเขียน
- **Communication** — Gmail, Bluesky, Discord, Microsoft Teams และ pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA และ UPnP
- **Media** — สร้าง/แก้ไขภาพ ถอดเสียง/สังเคราะห์เสียง ถ่ายภาพจากกล้อง และ QR codes
- **Documents** — วิเคราะห์ PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL และ log

**IoT และการควบคุมโลกจริง**

- **SwitchBot** — การค้นพบผ่าน Cloud และ BLE สถานะ การควบคุม การทำเป็นชุด และ subscriptions
- **ECHONET Lite** — ค้นหาและควบคุมเครื่องใช้ไฟฟ้าภายในบ้านของญี่ปุ่น รวมถึงการแจ้งเตือน INF
- **Matter** — endpoints, clusters, attributes, ประวัติสถานะ subscriptions และการควบคุม
- **BACnet / Modbus TCP / OPC UA** — การอ่าน เขียน เรียกดู และตรวจสอบระบบอัตโนมัติในอุตสาหกรรมและอาคาร
- **UPnP** — การค้นพบอุปกรณ์ สถานะ WAN และการจัดการ router port-mapping

### ตำแหน่งของ uag

uag อยู่ระหว่างผู้คนและอินเทอร์เฟซด้านหนึ่ง กับโมเดล เครื่องมือ และระบบในโลกจริงอีกด้านหนึ่ง
uag ประสานการสนทนา เลือกความสามารถ ใช้กฎความปลอดภัย และทำให้เวิร์กโฟลว์กลับมาทำต่อได้

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### ปลั๊กอิน Agent Skills และ marketplaces

เปลี่ยน uag ให้เป็นเอเจนต์เฉพาะทางได้โดยไม่ต้อง fork core:

- ติดตั้ง **ปลั๊กอินที่เข้ากันได้กับ Claude Code** จากไดเรกทอรี ZIP Git repository HTTP source หรือ marketplace
- รวม skills, sub-agents, MCP servers, hooks, slash commands, output styles, dependencies และ channels
- เรียกดูความสามารถจากชุมชนผ่าน [SkillsMP](https://skillsmp.com) และ [ClawHub](https://clawhub.ai)
- เพิ่ม skills และเครื่องมือส่วนตัวขององค์กรภายในเครื่องผ่าน `UAGENT_EXTERNAL_TOOLS_DIR`

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

ดู [Plugin Development Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md)

- **เครื่องมือมากกว่า 200 รายการ** สำหรับไฟล์ เว็บ มีเดีย เอกสาร โค้ด Cloud การสื่อสาร และ IoT
- **การค้นพบและโหลดแบบไดนามิก** — ใช้ `tool_catalog` เพื่อค้นหาความสามารถ และ `tool_load` เพื่อเปิดใช้เฉพาะเมื่อจำเป็น
- **ความอัจฉริยะด้านโค้ด** — `code_map`, ตัวนำทาง `idx` เฉพาะภาษา การรีวิว Git การรันทดสอบ linting การคอมไพล์ และ coverage
- **ปลั๊กอินที่เข้ากันได้กับ Claude Code** พร้อม skills, agents, MCP servers, hooks, commands และ marketplaces
- **Agent Skills** จาก SkillsMP และ ClawHub
- **เครื่องมือ Python แบบกำหนดเอง** ด้วย `TOOL_SPEC` และ `run_tool()`
- **เครื่องมือที่ทำงานด้วย Rust** สำหรับ native extension น้ำหนักเบา

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## สร้างขึ้นเพื่อเวิร์กโฟลว์จริง

### 🧠 ผลลัพธ์ของเครื่องมือที่คำนึงถึงบริบท

ผลลัพธ์ของเครื่องมือขนาดใหญ่จะถูกเก็บไว้นอกบริบทของโมเดลที่กำลังทำงานอยู่ เมื่อเป็นไปได้ uag เก็บผลลัพธ์เหล่านั้นไว้ในรูปแบบ Artifacts และส่งตัวอย่างที่จำกัดพร้อมการอ้างอิง Artifact ที่เสถียรไปยังโมเดลแทน วิธีนี้สามารถลดจำนวนโทเค็นอินพุตที่จำเป็นสำหรับรอบการสนทนาถัดไปได้อย่างมีนัยสำคัญ เมื่อเครื่องมือสร้างผลลัพธ์ที่มีขนาดใหญ่

กลับไปสนทนาต่อจากครั้งก่อนด้วย `:load <index>` ผลลัพธ์เครื่องมือสามารถแคชได้ และสามารถเปลี่ยน provider ได้
โดยไม่ต้องสร้างแอปพลิเคชันใหม่

[Context compression](CONTEXT_COMPRESSION.th.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Auto-pilot

ใช้ `:auto` สำหรับงานหลายรอบพร้อมโมเดล reviewer เสริม กำหนดขีดจำกัดรอบด้วย `--max-rounds N`
กด **F12** เพื่อหยุด auto-pilot หรือ **F12** เพื่อหยุดการตอบกลับปัจจุบัน

การดำเนินการแบบอ่านอย่างเดียวที่เป็นอิสระต่อกันจะทำงานพร้อมกันเมื่อปลอดภัย การค้นหาเว็บ การตรวจสอบไฟล์
การวิเคราะห์ repository และงานลักษณะเดียวกันสามารถทำเสร็จพร้อมกันได้ด้วย worker pool ที่กำหนดค่าได้
(`UAGENT_PARALLEL_WORKERS`) ส่วนการเขียนยังคงทำเป็นลำดับหรือต้องมีการยืนยัน

ความต่อเนื่องของเซสชัน การแคชผลลัพธ์เครื่องมือ สถานะ batch การกู้คืนหลังเริ่มระบบใหม่ การจัดตาราง DAG และ
การประสานงานหลายเอเจนต์ทำให้งานซับซ้อนกลับมาทำต่อได้แทนที่จะทำได้เพียงครั้งเดียว

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 เป็นส่วนตัว รองรับหลายภาษา และตระหนักถึงนโยบาย

`human_ask` จะหยุดก่อนการดำเนินการที่มีความอ่อนไหว การลบไฟล์ การเขียนทับ shell commands การควบคุมอุปกรณ์
การดำเนินการกับข้อมูลรับรอง และการเขียนผ่านเครือข่ายสามารถอยู่ภายใต้กฎการยืนยันและนโยบายได้

ใช้ credential store แทนการใส่ secrets ที่มีอายุยาวไว้ใน prompt:

เว็บ UI มีการเข้าสู่ระบบ OIDC โดยใช้ Authorization Code + PKCE, โทเค็น ID ที่ได้รับการยืนยัน, เซสชันฝั่งเซิร์ฟเวอร์ และการควบคุมการเข้าถึงโปรเจกต์/ห้อง การอ้างสิทธิ์กลุ่ม Microsoft Entra ID ที่ได้รับการยืนยันสามารถนำมาใช้กับนโยบายการเข้าถึงที่อิงกับไดเรกทอรีได้เมื่อมีการกำหนดค่า การติดตั้ง Windows Active Directory, OAuth และ trusted-proxy สามารถรวมเข้าด้วยกันผ่านอะแดปเตอร์ตัวตนที่ได้รับการยืนยันอย่างชัดเจน; Windows AD ต้องการตัวตรวจสอบ Kerberos/Negotiate เฉพาะสำหรับการติดตั้งและไม่ได้เปิดใช้งานโดยค่าเริ่มต้น

uag รวมการติดตาม OpenTelemetry ที่เป็นกลางของผู้ให้บริการและการวัดสำหรับ Agent, LLM, เครื่องมือ, Context, Memory และการดำเนินการดึงข้อมูล ความสามารถในการสังเกตถูกปิดใช้งานตามค่าเริ่มต้น

การให้ความสำคัญกับการทำงานในเครื่องไม่ได้หมายความว่า UAG จะทำงานแบบออฟไลน์ทั้งหมดหรือแยกการทำงานของทุกเครื่องมือโดยค่าเริ่มต้น การเรียกใช้โมเดลและบริการภายนอกขึ้นอยู่กับการกำหนดค่า

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 การแปลหลายภาษา

- `translate_text` รองรับ Google Translate และไคลเอนต์ DeepL Python อย่างเป็นทางการผ่าน `provider=auto`, `provider=deepl`, หรือ `provider=google`.
- การกำหนดเครื่องมือมีพร้อมใน 37 ภาษาท้องถิ่นบวกกับภาษาอังกฤษ (รวม 38 ภาษา) โดยรักษาตัวแทนและตัวระบุทางเทคนิคไว้

รองรับเสียงแบบ full-duplex ผ่าน OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live
และ Bedrock Nova Sonic พร้อมการยกเลิกเสียงสะท้อน AEC3 แบบเลือกใช้ และการเรียกใช้ฟังก์ชันแบบเรียลไทม์ที่จำกัดด้วยความปลอดภัย

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## เอกสารประกอบ

| หัวข้อ | เอกสาร |
|---|---|
| Environment variables | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Architecture and invariants | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Repository tools | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| IoT use cases | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Communication tools | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Auto-pilot | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| VS Code extension | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Developer guide | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Tool flow | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## การพัฒนาและการมีส่วนร่วม

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

เรียกใช้การตรวจสอบก่อนส่ง PR:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

สำหรับเวิร์กโฟลว์การพัฒนาเต็มรูปแบบ ดู [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)

ยินดีรับรายงานข้อบกพร่อง แนวคิดฟีเจอร์ การปรับปรุงเอกสาร คำแปล เครื่องมือ skills และ pull requests
โปรดเปิด issue หรือ discussion ก่อนการเปลี่ยนแปลงขนาดใหญ่ อ่าน [Developer Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
และเรียกใช้การตรวจสอบข้างต้นก่อนส่ง pull request

## ใบอนุญาต

เผยแพร่ภายใต้ [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE)
