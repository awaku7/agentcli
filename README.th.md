<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (เอเจนต์ AI แบบโลคัล)

uag เป็นเอเจนต์แบบโต้ตอบที่สามารถรัน **คำสั่ง**, จัดการ **ไฟล์**, และอ่าน **ข้อมูลรูปแบบต่างๆ** (PDF/PPTX/Excel และอื่นๆ) บนเครื่อง PC ของคุณ โดยมีอินเทอร์เฟซให้เลือก 3 แบบ: CLI, GUI และ Web

GitHub: https://github.com/awaku7/agentcli

## การติดตั้ง

คุณสามารถติดตั้ง `uag` ผ่าน pip:

```bash
pip install uag
```

หลังจากติดตั้งแล้ว การรัน `uag` ครั้งแรกจะเริ่ม **ตัวช่วยตั้งค่าแบบโต้ตอบ** โดยอัตโนมัติเพื่อกำหนดค่าตัวแปรสภาพแวดล้อมของคุณ สำหรับข้อมูลโดยละเอียดเกี่ยวกับการตั้งค่าและการเข้ารหัส โปรดดูที่ **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**

## คุณสมบัติหลัก

- **ชุดเครื่องมือที่ใช้งานได้จริง**: มาพร้อมเครื่องมือจัดการไฟล์, ค้นหาเว็บ, ดึงข้อมูล (PDF/PPTX/Excel), สร้างและวิเคราะห์รูปภาพ ซึ่งทั้งหมดทำงานบนเครื่องของคุณโดยตรง
- **รองรับผู้ให้บริการหลายราย**: รองรับ OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA
- **อินเทอร์เฟซที่ยืดหยุ่น**: 
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
- **MCP (Model Context Protocol)**: รองรับการเชื่อมต่อกับเซิร์ฟเวอร์เครื่องมือ MCP ภายนอก
- **ความต่อเนื่องของเซสชัน**: รักษาบริบทการสนทนาแม้ว่าจะเปลี่ยนผู้ให้บริการหรือโมเดล
- **Web Inspector**: บันทึกการเปลี่ยนหน้าเว็บ, DOM และภาพหน้าจอโดยอัตโนมัติด้วย `playwright_inspector`
- **เอกสารในตัว**: เข้าถึงเอกสารรายละเอียดภายในได้ทันทีด้วยคำสั่ง `uag docs`

## วิธีใช้งาน

### การเริ่มและออก
รัน `uag` จากเทอร์มินัลเพื่อเริ่มใช้งาน พิมพ์ `:exit` เพื่อออก

### เซิร์ฟเวอร์ A2A (Agent2Agent)
คุณสามารถรันเซิร์ฟเวอร์ HTTP ที่รองรับ A2A แยกต่างหากจากอินเทอร์เฟซปกติได้
```bash
uaga
# หรือ python -m uagent.a2a.server
```

### หมายเหตุเกี่ยวกับ Responses API

หากตั้งค่า `UAGENT_RESPONSES=1` จะใช้ Responses API สำหรับผู้ให้บริการที่รองรับ: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI ใช้เส้นทาง API แบบเนทีฟของตนเองและไม่อยู่ในขอบเขตของ Responses API.
สำหรับผู้ให้บริการรายอื่น uag จะย้อนกลับไปใช้เส้นทางเฉพาะของผู้ให้บริการหรือ chat-completions.

ดู [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) สำหรับการตั้งค่า `UAGENT_A2A_*` เช่น การยืนยันตัวตน โฮสต์ พอร์ต การรีโหลด URL ฐานสาธารณะ จำนวนงานพร้อมกัน และเอนจิน

### เคล็ดลับที่มีประโยชน์ (ความต่อเนื่องและการควบคุม)
- `:tools`: แสดงรายการเครื่องมือที่โหลดอยู่
- `:logs [n]`: แสดงบันทึกเซสชัน (ระบุจำนวนรายการด้วย `n`)
- `:load <index>`: โหลดเซสชันเก่าเพื่อสนทนาต่อ
- `:skills`: เลือกและโหลด Agent Skills (บทบาทหรือคำแนะนำเพิ่มเติม)
- `:shrink [n]`: จัดระเบียบประวัติเพื่อให้เหลือเพียง `n` ข้อความล่าสุดเพื่อประหยัดโทเค็น

## การตั้งค่าและรายละเอียด

### ตัวแปรสภาพแวดล้อมและการตั้งค่า
สำหรับการตั้งค่าโดยละเอียด (API key, ภาษาที่แสดง `UAGENT_LANG`, การตั้งค่าการย่อประวัติ ฯลฯ) โปรดดูที่ **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**
- **การตั้งค่า**: กำหนดค่าแบบโต้ตอบผ่าน `python -m uagent.setup_cli`
- **การเข้ารหัส**: เข้ารหัสไฟล์ `.env` ของคุณอย่างปลอดภัยด้วยเครื่องมือ `uag_envsec`
- **อัปเดต**: ใช้ `uag_envsec add --file .env.sec --key NAME --value VALUE` เพื่อเพิ่มหรืออัปเดตตัวแปรในไฟล์ที่เข้ารหัสอยู่แล้ว

### สำหรับนักพัฒนาและการรองรับหลายภาษา
- **เอกสารนักพัฒนา**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **การเพิ่มภาษาใหม่**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **README ในภาษาอื่น**: [English](https://github.com/awaku7/agentcli/blob/main/README.md) / [日本語](https://github.com/awaku7/agentcli/blob/main/README.ja.md) / [Deutsch](https://github.com/awaku7/agentcli/blob/main/README.de.md) / [Español](https://github.com/awaku7/agentcli/blob/main/README.es.md) / [Français](https://github.com/awaku7/agentcli/blob/main/README.fr.md) / [Italiano](https://github.com/awaku7/agentcli/blob/main/README.it.md) / [한국어](https://github.com/awaku7/agentcli/blob/main/README.ko.md) / [Português](https://github.com/awaku7/agentcli/blob/main/README.pt_BR.md) / [Русский](https://github.com/awaku7/agentcli/blob/main/README.ru.md) / [ไทย](https://github.com/awaku7/agentcli/blob/main/README.th.md) / [简体中文](https://github.com/awaku7/agentcli/blob/main/README.zh_CN.md) / [繁體中文](https://github.com/awaku7/agentcli/blob/main/README.zh_TW.md) / [Polski](https://github.com/awaku7/agentcli/blob/main/README.pl.md) / [Tiếng Việt](https://github.com/awaku7/agentcli/blob/main/README.vi.md) / [Bahasa Indonesia](https://github.com/awaku7/agentcli/blob/main/README.id.md) / [العربية](https://github.com/awaku7/agentcli/blob/main/README.ar.md) / [हिन्दी](https://github.com/awaku7/agentcli/blob/main/README.hi.md) / [Português](https://github.com/awaku7/agentcli/blob/main/README.pt.md) / [Svenska](https://github.com/awaku7/agentcli/blob/main/README.sv.md) / [Norsk bokmål](https://github.com/awaku7/agentcli/blob/main/README.nb.md)
