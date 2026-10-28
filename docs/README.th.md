<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>โมเดล AI ของคุณ เครื่องมือของคุณ สภาพแวดล้อมของคุณ</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">ภาษาอื่น</a></p>

---

**UAG เป็นรันไทม์เอเจนต์ AI แบบโอเพนซอร์สที่ให้ความสำคัญกับการทำงานในเครื่อง** เชื่อมต่อโมเดลภาษาที่คุณเลือกเข้ากับเครื่องมือและระบบที่ใช้งานจริง จัดการโค้ด ไฟล์ เบราว์เซอร์ บริการ และอุปกรณ์ผ่านส่วนติดต่อเดียว โดยไม่ต้องผูกขั้นตอนการทำงานไว้กับผู้ให้บริการโมเดลรายเดียว

| **เลือกโมเดลเอง** | **เชื่อมต่อเครื่องมือจริง** | **ควบคุมได้ด้วยตนเอง** |
| :--- | :--- | :--- |
| โมเดลบนคลาวด์และในเครื่อง เช่น OpenAI, Claude, Gemini, Grok, Bedrock และ Ollama | ไฟล์ โค้ด เว็บ MCP Agent Skills ปลั๊กอิน คลาวด์ และ IoT | การทำงานในเครื่อง การยืนยันโดยมนุษย์ การเก็บข้อมูลรับรอง และนโยบายที่กำหนดได้ |

> UAG เป็น**ชั้นการทำงานของเอเจนต์ ไม่ใช่ผู้ให้บริการโมเดล** การเรียกใช้โมเดลและบริการภายนอกขึ้นอยู่กับการตั้งค่า การให้ความสำคัญกับการทำงานในเครื่องไม่ได้หมายความว่าจะออฟไลน์ทั้งหมดหรือแยกทุกเครื่องมือโดยอัตโนมัติ

## เริ่มต้นอย่างรวดเร็ว
<!-- README-SYNC:quick-start -->

ต้องใช้ **Python 3.11 หรือใหม่กว่า** ติดตั้ง UAG จาก [PyPI](https://pypi.org/project/uag/) แล้วเปิด CLI แบบโต้ตอบ:

~~~bash
python -m pip install --upgrade uag
uag
~~~

เมื่อเปิดครั้งแรก ตัวช่วยตั้งค่าจะช่วยเลือกผู้ให้บริการและกำหนดข้อมูลรับรอง คุณยังใช้ตัวแปรสภาพแวดล้อมหรือที่เก็บข้อมูลรับรองได้ หากต้องการติดตั้งการพึ่งพาของโมเดลและเครื่องมือเพิ่มเติมล่วงหน้า ให้ใช้:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

จากนั้นลองป้อนคำสั่งต่อไปนี้:

~~~text
> มีอะไรเปลี่ยนแปลงในที่เก็บ Git นี้บ้าง สรุปความเสี่ยงด้วย
> ค้นหาเอกสารล่าสุดของไลบรารีนี้และอธิบายขั้นตอนย้ายระบบ
> ตรวจสอบไฟล์เหล่านี้และจัดทำรายงานสั้น ๆ
> :help
~~~

ผู้เริ่มต้นควรอ่านคู่มือติดตั้ง Windows ซึ่งรวมขั้นตอน Git และสภาพแวดล้อมเสมือน ตลอดจนเอกสารการตั้งค่า: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## ส่วนติดต่อผู้ใช้
<!-- README-SYNC:interfaces -->

ทุกช่องทางใช้รันไทม์เอเจนต์และทะเบียนเครื่องมือเดียวกัน

| ส่วนติดต่อ | เริ่มด้วย | เหมาะสำหรับ |
| :--- | :--- | :--- |
| **CLI** | `uag` | งานเทอร์มินัลและระบบอัตโนมัติ |
| **Desktop** | `uagg` | สนทนาในแอปเดสก์ท็อป |
| **Web** | `uagw` | สนทนาและห้องในเบราว์เซอร์ |
| **A2A** | `uaga` | เชื่อมต่อระหว่างเอเจนต์ |
| **VS Code** | [คู่มือส่วนขยาย](VSCODE.md) | ทำงานควบคู่กับโค้ด |

ส่วนติดต่อ Desktop และ Web ต้องติดตั้งแพ็กเกจเพิ่มเติม ซึ่งไม่รวมอยู่ใน `uag[core,providers,tools]`:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

เว็บเซิร์ฟเวอร์อาจพยายามติดตั้ง FastAPI และ Uvicorn เมื่อเริ่มทำงาน การติดตั้งไว้ก่อนช่วยเลี่ยงการพึ่งพาการติดตั้งอัตโนมัติ รายละเอียด: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## สิ่งที่สร้างได้ด้วย UAG
<!-- README-SYNC:capabilities -->

| ความสามารถ | สิ่งที่ UAG มีให้ |
| :--- | :--- |
| **เวิร์กโฟลว์ไม่ขึ้นกับโมเดล** | เปลี่ยนโมเดลในเครื่องหรือบนคลาวด์ด้วย `UAGENT_PROVIDER` โดยไม่ต้องเขียนเครื่องมือใหม่ |
| **โค้ดและไฟล์** | สำรวจที่เก็บโค้ด ตรวจ Git ตรวจรูปแบบ ทดสอบ จัดการไฟล์ และควบคุมเบราว์เซอร์อัตโนมัติ |
| **เครื่องมือที่ขยายได้** | เครื่องมือกว่า 200 รายการ ค้นหาแบบไดนามิกด้วย `tool_catalog` / `tool_load` และเครื่องมือ Python หรือ Rust ที่กำหนดเอง |
| **เอเจนต์เชื่อมต่อกัน** | MCP, A2A, ปลั๊กอินที่เข้ากันได้กับ Claude Code, Agent Skills และเอเจนต์ย่อย |
| **งานที่ใช้เวลานาน** | Autopilot การอ่านอิสระแบบขนาน การตั้งเวลา การกู้คืน และเซสชันถาวร |
| **มากกว่าเทอร์มินัล** | คลาวด์ การสื่อสาร เอกสาร สื่อ เสียงแบบเรียลไทม์ และโปรโตคอล IoT ที่รองรับ |

### รันไทม์เดียว เชื่อมต่อได้หลายระบบ
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

**ตัวอย่างผู้ให้บริการโมเดลที่รองรับ** อยู่ด้านล่าง การตั้งค่าเฉพาะดูได้ในเอกสารสภาพแวดล้อม

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

[ENVIRONMENT.md](ENVIRONMENT.md)

### ปรับแต่งด้วยทักษะและปลั๊กอิน
<!-- README-SYNC:extensions -->

ขยาย UAG ได้โดยไม่ต้องแก้ไขแกนหลัก ติดตั้ง Agent Skills จาก SkillsMP หรือ ClawHub เชื่อมต่อเซิร์ฟเวอร์ MCP หรือโหลดปลั๊กอินที่เข้ากันได้กับ Claude Code ซึ่งมีเครื่องมือ ทักษะ เอเจนต์ และ hooks

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

เครื่องมือที่สร้างเองสามารถมี `TOOL_SPEC` และ `run_tool()` และยังรองรับเครื่องมือที่พัฒนาด้วย Rust ดูคู่มือ: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## ออกแบบมาสำหรับงานจริง
<!-- README-SYNC:workflows -->

### บริบทและหน่วยความจำ
<!-- README-SYNC:context-memory -->

ผลลัพธ์เครื่องมือขนาดใหญ่สามารถเก็บเป็น **Artifacts** แทนการเติมบริบทที่ใช้งานอยู่ของโมเดล แล้วเรียกดูเฉพาะส่วนสำคัญด้วย `artifact_read` เซสชันจะบันทึกใน SQLite เป็นค่าเริ่มต้น พร้อมค้นหาประวัติและตรวจสอบหน่วยความจำอย่างชัดเจน

- [Context compression](CONTEXT_COMPRESSION.th.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### ระบบอัตโนมัติและการทำงานร่วมกัน
<!-- README-SYNC:automation -->

UAG รองรับการอ่านอิสระแบบขนาน การประสานงานหลายเอเจนต์ การกู้คืนเซสชัน และ Autopilot สำหรับงานหลายรอบ เริ่มด้วย `:auto` และกด **F12** เพื่อขัดจังหวะคำตอบปัจจุบันและขอให้หยุด Autopilot

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### ความปลอดภัยและการสังเกตการณ์
<!-- README-SYNC:security -->

การดำเนินการที่ละเอียดอ่อนสามารถตั้งค่าให้ยืนยันด้วย `human_ask` ข้อมูลรับรองเก็บได้ในระบบจัดการของระบบปฏิบัติการหรือไฟล์เข้ารหัส Web รองรับการเข้าสู่ระบบ OIDC และควบคุมการเข้าถึงเมื่อกำหนดค่าแล้ว การติดตามและตัวชี้วัด OpenTelemetry เป็น**ทางเลือก**

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

มาตรการเหล่านี้กำหนดค่าได้ แต่**ไม่รับประกัน**ว่าเครื่องมือใด ๆ จะถูกแยกไว้ใน sandbox โปรดอ่านคู่มือการปรับใช้และนโยบายก่อนเปิด UAG ให้ผู้ใช้หรือเครือข่ายที่ไม่เชื่อถือ

### ภาษา อุปกรณ์ และเสียง
<!-- README-SYNC:languages -->

UAG มีทรัพยากรสำหรับ **38 ภาษาและภูมิภาค** (อังกฤษและคำแปลอีก 37 ภาษา) การเชื่อมต่อเสียงสองทางแบบเลือกใช้ และเครื่องมือสำหรับ SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP และ OPC UA

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## เอกสาร
<!-- README-SYNC:documentation -->

เริ่มจากคู่มือเหล่านี้ แล้วศึกษาเพิ่มเติมตามหัวข้อที่สนใจ:

| เริ่มต้นที่นี่ | เรียนรู้เพิ่มเติม |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

สามารถดูเอกสารทั้งหมดและคำแปลภาษาอื่นได้ด้วย: [Documentation](./) · [Other languages](README.translations.md).

## การพัฒนาและการมีส่วนร่วม
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

ก่อนส่ง pull request ที่แก้ไข **โค้ด Python** ให้เรียกใช้การทดสอบและตรวจสอบโครงการที่เกี่ยวข้อง:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

อ่านข้อกำหนดการมีส่วนร่วมและคู่มือผู้พัฒนาได้ด้านล่าง ยินดีรับรายงานบั๊ก การปรับปรุงเอกสาร เครื่องมือ คำแปล และ pull request ที่มีขอบเขตชัดเจน: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## สัญญาอนุญาต
<!-- README-SYNC:license -->

UAG เผยแพร่ภายใต้สัญญาอนุญาต: [Apache License 2.0](../LICENSE).
