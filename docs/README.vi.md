<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Cổng AI phổ quát</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Your environment, your freedom.
</p>

<p align="center">
  File ops / Web search / Image generation &amp; analysis / PDF &amp; Excel extraction / IoT control / MCP integration<br>
  15+ providers / 3 UIs / Parallel tool execution / Agent Skills marketplace
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

---

## Tại sao lại là uag?

** Thoát khỏi sự ràng buộc của nhà cung cấp.** Hầu hết trợ lý AI đều ràng buộc bạn với một nhà cung cấp hoặc dịch vụ đám mây cụ thể. uag thì khác.

- **Chạy cục bộ** trên máy của bạn. Dữ liệu của bạn vẫn ở bên bạn (ngoại trừ các lệnh gọi API bạn thực hiện).
- **Quyền tự do của nhà cung cấp**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... Hơn 15 nhà cung cấp, tất cả đều có thể truy cập từ một giao diện duy nhất. Hoán đổi giữa chúng bằng cách cấu hình lại các biến môi trường — không cần cài đặt lại, không di chuyển.
- **131 công cụ**: I/O tệp, tìm kiếm trên web, tạo hình ảnh, Gmail, quét thiết bị BLE, tích hợp máy chủ MCP — **76 công cụ an toàn song song** (tối đa 8 công cụ thực thi đồng thời qua nhóm luồng, có thể định cấu hình qua `UAGENT_PARALLEL_WORKERS`). Khi LLM thực hiện nhiều lệnh gọi công cụ cùng một lúc, uag sẽ tự động song song chúng.
- **3 UI + A2A**: CLI, GUI, Web và giao thức Agent-to-Agent. Cùng một động cơ, bất kỳ giao diện nào.
- **Sẵn sàng cho IoT**: SwitchBot, ECHONET Lite, Matter, UPnP — điều khiển các thiết bị trong nhà của bạn thông qua AI.
- **Kỹ năng đại lý**: Cài đặt các kỹ năng do cộng đồng xây dựng từ thị trường. Mở rộng uag vô tận.

uag là **trợ lý AI theo điều kiện của bạn**. Không bị ràng buộc với nhà cung cấp, không bị ràng buộc với giao diện, không bị ràng buộc với nền tảng.

## Bắt đầu nhanh

```bash
pip install uag
uag
```

Trong lần khởi chạy đầu tiên, trình hướng dẫn thiết lập sẽ hướng dẫn bạn cấu hình nhà cung cấp.
Xem [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) để biết tất cả các biến môi trường.

## Đặc trưng

### 🧠 Kiến trúc đa nhà cung cấp

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI (Fugu)**

Tất cả các nhà cung cấp đều có chung bộ công cụ và giao diện. Chuyển đổi bằng cách cài đặt `UAGENT_PROVIDER` — không thay đổi mã, không cài đặt riêng.

### ⚡ Thực thi công cụ song song

Khi LLM yêu cầu nhiều công cụ cùng lúc, uag **tự động song song** chúng.
76 công cụ được đánh dấu `x_parallel_safe` và thực thi đồng thời thông qua `ThreadPoolExecutor` (8 luồng theo mặc định; đặt `UAGENT_PARALLEL_WORKERS` để thay đổi).

**Ví dụ**: Hỏi "Kiểm tra thời tiết ở các thủ đô Bắc Âu" → LLM kích hoạt `search_web` × 5 quốc gia → tất cả 5 tìm kiếm chạy song song → kết quả được thu thập trong một đợt.

Các công cụ chỉ đọc (tìm kiếm tệp, tính toán hàm băm, liệt kê thư mục, dịch thuật, truy vấn DB, v.v.) được song song hóa mạnh mẽ.

### 🔄 Phiên liên tục

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 131 Công cụ

| Danh mục | Công cụ |
|---|---|
| **Thao tác tệp** | đọc/ghi/tạo/xóa/tìm kiếm/grep/hash/zip, parse_eml (tệp .eml) |
| **Web** | tìm nạp_url, search_web, ảnh chụp màn hình, browser_playwright |
| **Truyền thông** | tạo_hình ảnh, phân tích_hình ảnh, img2img, audio_speech, audio_transcribe |
| **Tài liệu** | Trích xuất PDF/PPTX/DOCX/RTF/ODT, trích xuất có cấu trúc Excel |
| **Giao tiếp** | gmail_send, gmail_read, bluesky, discord_channel, Team_webhook — xem [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| **IoT** | SwitchBot (Đám mây + BLE), ECHONET Lite, Matter, UPnP |
| **Công cụ dành cho nhà phát triển** | git_ops, python_compile, lint_format, run_tests, db_query, **13 trình điều hướng mã nguồn (dòng idx)** |
| **MCP** | Kết nối với máy chủ MCP bên ngoài, liệt kê các công cụ, thực thi |
| **A2A** | Giao tiếp giữa các đại lý (với các phiên bản uag khác hoặc máy chủ tương thích với A2A) |
| **Hệ thống** | env vars, thông số kỹ thuật hệ thống, tính toán thời gian, ngày tháng |
| **Điều hướng nguồn** | **13 công cụ idx** dành cho Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL — lấy chỉ mục hàm/lớp hoặc định nghĩa cụ thể mà không cần đọc toàn bộ tệp |

### 🖥 4 Giao diện + Tiện ích mở rộng Mã VS

| Chế độ | Lệnh | Mục đích |
|---|---|---|
| **CLI** | `uag` | Hoạt động dựa trên thiết bị đầu cuối nhanh |
| **GUI** | `uagg` | Giao diện người dùng máy tính để bàn thông qua tkinter |
| **Web** | `uagw` | Truy cập dựa trên trình duyệt |
| **Máy chủ A2A** | `uaga` | Giao thức Agent2Agent cho giao tiếp đa tác nhân |
| **Mã VS** | — | [Tiện ích mở rộng](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) với Bảng trò chuyện, Giải thích, Tái cấu trúc, Sửa lỗi và Chế độ xem dạng cây công cụ |

Xem [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) để biết thông tin chi tiết về tiện ích mở rộng VS Code — cài đặt, lệnh, tổ hợp phím và cấu hình.

### 🏠 Kiểm soát thiết bị IoT

- **SwitchBot**: Kiểm soát hàng loạt đám mây & quét/điều khiển BLE
- **ECHONET Lite**: Khám phá và điều khiển các thiết bị gia dụng (AC, đèn, máy nước nóng, v.v.) trên mạng cục bộ
- **Vấn đề**: Kiểm tra chỉ đọc cấu trúc liên kết bộ điều khiển/cầu nối/thiết bị
- **UPnP**: Phát hiện thiết bị & chuyển tiếp cổng IGD

Xem [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 Thị trường kỹ năng đại lý

`:skills mp_search` để duyệt qua [SkillsMP](https://skillsmp.com) và [ClawHub](https://clawhub.ai) để tìm kiếm các kỹ năng cộng đồng.
Cài đặt và mở rộng khả năng của uag một cách nhanh chóng.

### 🤖 Tự động điều khiển (`:auto`)

uag có thể **tự động theo đuổi mục tiêu qua nhiều vòng LLM**. Hoàn hảo cho các nhiệm vụ phức tạp, nhiều bước cần tinh chỉnh lặp đi lặp lại.

- **Cách thức hoạt động**: Mỗi vòng có một truy vấn chính (Bước A) theo sau là đánh giá của người đánh giá (Bước B) để quyết định "HOÀN THÀNH hay TIẾP TỤC?"
- **Cùng nhà cung cấp, cùng API**: Đánh giá của người đánh giá sử dụng đường dẫn mã giống hệt nhau làm truy vấn chính — bao gồm hỗ trợ API phản hồi.
- **Thẩm phán LLM riêng** (tùy chọn): Đặt `UAGENT_AP_PROVIDER` để sử dụng nhà cung cấp/mô hình khác cho người đánh giá (ví dụ: sử dụng mô hình rẻ hơn để đánh giá).
- **Thoát bất cứ lúc nào**: Nhấn phím `x` để dừng ngay lập tức, kể cả khi đang phản hồi. Hoặc để người đánh giá quyết định khi nào đạt được mục tiêu.
- **Có thể định cấu hình**: `--max-rounds N` để kiểm soát ngân sách.

Xem [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md) để biết tài liệu đầy đủ.

### 🧩 Quản lý trạng thái hàng loạt

uag có thể theo dõi tiến trình trên các tác vụ nhiều tệp chạy dài. Khi LLM xử lý hàng chục tệp, `batch_state` vẫn duy trì danh sách các tệp đang chờ xử lý, đã hoàn thành và không thành công vào đĩa. Nếu phiên kết thúc hoặc hết thời gian, lượt chạy tiếp theo sẽ tiếp tục từ nơi phiên đã dừng — không có gì bị mất.

### 🛡 Con người trong vòng lặp

`human_ask` cho phép LLM tạm dừng và yêu cầu bạn xác nhận trước khi thực hiện các thao tác phá hoại (xóa tệp, ghi đè, lệnh shell). Bạn luôn kiểm soát.

### 🛑 Ngắt (phím c / Nút dừng)

Dừng việc tạo phản hồi LLM bất cứ lúc nào và đưa lệnh dừng trở lại LLM.

| Giao diện | Cách ngắt lời |
|---|---|
| **CLI** | Nhấn phím `c` trong khi phát trực tuyến LLM — phản hồi hiện tại dừng và `"Dừng"` được gửi dưới dạng tin nhắn người dùng để LLM phản hồi tương ứng |
| **Giao diện người dùng WEB** | Nhấp vào nút **■ Dừng** màu đỏ (tự động xuất hiện trong quá trình xử lý LLM) |
| **Giao diện máy tính để bàn** | Nhấp vào nút **■** màu đỏ (tự động xuất hiện trong quá trình xử lý LLM) |

Ngắt hoạt động như "chèn nhắc": thay vì chỉ hủy bỏ, nó đưa `"Dừng"` trở lại LLM dưới dạng thông báo người dùng, cho phép LLM kết luận hoặc thừa nhận sự gián đoạn một cách khéo léo.

Nhấn phím `x` để thoát chế độ tự động điều khiển (xem [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md)).

### 🕵️ Tự động hóa trình duyệt & Trình kiểm tra web

Hai công cụ bổ sung dựa trên Nhà viết kịch:

- **browser_playwright**: Tự động hóa các phiên trình duyệt thực — điều hướng, nhấp chuột, điền biểu mẫu, trích xuất dữ liệu, xử lý các luồng nhiều trang. Hoạt động không có đầu hoặc có đầu.
- **playwright_inspector**: Ghi lại quá trình chuyển đổi trình duyệt, chụp ảnh chụp nhanh DOM và ảnh chụp màn hình ở mỗi bước. Hữu ích cho việc gỡ lỗi các tương tác trên web hoặc kiểm tra các thay đổi của trang theo thời gian.

### 🔄 Đang tải công cụ động

`tool_catalog` và `tool_load` cho phép bạn khám phá và kích hoạt các công cụ trong thời gian chạy.
Không cần tải mọi thứ khi khởi động — chỉ kích hoạt những gì bạn cần, khi bạn cần.

### 🌐 i18n/L10n

日本語 / Tiếng Anh / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / và hơn thế nữa.
Đặt `UAGENT_LANG` để chuyển đổi. Xem [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) để thêm ngôn ngữ mới.

Bản dịch của README này có sẵn trong [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Biến môi trường được mã hóa

Lưu trữ khóa và bí mật API trong `.env.sec` — một tệp `.env` được mã hóa.
Quản lý bằng `uag_envsec`.

## Cấu hình & Chi tiết

- **Biến môi trường**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **Trình hướng dẫn thiết lập**: `python -m uagent.setup_cli`
- **Env được mã hóa**: `uag_envsec` — mã hóa `.env` thành `.env.sec`
- **API phản hồi**: Đặt `UAGENT_RESPONSES=1` cho chế độ API phản hồi (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Tự động kích hoạt cho Sakana AI (Fugu).
- **Tài liệu dành cho nhà phát triển**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Mẹo LLM nhỏ**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Triết lý dự án

uag mong muốn trở thành **AI của bạn, trên máy của bạn, theo điều kiện của bạn.**

- Không phụ thuộc SaaS - chạy cục bộ
- Không khóa nhà cung cấp - chuyển đổi bất cứ lúc nào
- Không khóa giao diện người dùng — CLI / GUI / Web / A2A
- Không khóa tính năng - mở rộng bằng các công cụ và kỹ năng

Trải nghiệm đại lý AI miễn phí, không bị ràng buộc bởi nhà cung cấp.
