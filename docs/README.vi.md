<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Cổng AI phổ quát</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Môi trường của bạn, sự tự do của bạn.
</p>

<p align="center">
  Thao tác tệp / Tìm kiếm trên web / Tạo và phân tích hình ảnh / Trích xuất PDF & Excel / Kiểm soát IoT / Tích hợp MCP<br>
  24 providers / 3 giao diện người dùng / Thực thi công cụ song song / Agent Skills thị trường
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="README.translations.md">Read this in your language</a>
</p>

______________________________________________________________________

## Tại sao lại là uag?

\*\* Thoát khỏi sự ràng buộc của nhà cung cấp.\*\* Hầu hết trợ lý AI đều ràng buộc bạn với một nhà cung cấp hoặc dịch vụ đám mây cụ thể. uag thì khác.

- **Chạy cục bộ** trên máy của bạn. Dữ liệu của bạn vẫn ở bên bạn (ngoại trừ các lệnh gọi API bạn thực hiện).
- **Quyền tự do của nhà cung cấp**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 21 nhà cung cấp, tất cả đều có thể truy cập từ một giao diện duy nhất. Hoán đổi giữa chúng bằng cách cấu hình lại các biến môi trường — không cần cài đặt lại, không di chuyển.
- **229 công cụ**: I/O tệp, tìm kiếm trên web, tạo hình ảnh, Gmail, quét thiết bị BLE, tích hợp máy chủ MCP — **130 công cụ an toàn song song** (tối đa 8 công cụ thực thi đồng thời qua nhóm luồng, có thể định cấu hình qua `UAGENT_PARALLEL_WORKERS`). Khi LLM thực hiện nhiều lệnh gọi công cụ cùng một lúc, uag sẽ tự động song song chúng.
- **3 UI + A2A**: CLI, GUI, Web và giao thức Agent-to-Agent. Cùng một động cơ, bất kỳ giao diện nào.
- **Kỹ năng đại lý**: Cài đặt các kỹ năng do cộng đồng xây dựng từ thị trường. Mở rộng uag vô tận.

uag là **trợ lý AI theo điều kiện của bạn**. Không bị ràng buộc với nhà cung cấp, không bị ràng buộc với giao diện, không bị ràng buộc với nền tảng.

## Bắt đầu nhanh

```bash
pip install uag
uag
```

Trong lần khởi chạy đầu tiên, trình hướng dẫn thiết lập sẽ hướng dẫn bạn cấu hình nhà cung cấp.
Xem [docs/ENVIRONMENT.md](ENVIRONMENT.md) để biết tất cả các biến môi trường.

## Đặc trưng

### 🧠 Kiến trúc đa nhà cung cấp

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

Tất cả các nhà cung cấp đều có chung bộ công cụ và giao diện. Chuyển đổi bằng cách cài đặt `UAGENT_PROVIDER` — không thay đổi mã, không cài đặt riêng.

### ⚡ Thực thi công cụ song song

Khi LLM yêu cầu nhiều công cụ cùng lúc, uag **tự động song song** chúng.
130 công cụ được đánh dấu `x_parallel_safe` và thực thi đồng thời thông qua `ThreadPoolExecutor` (8 luồng theo mặc định; đặt `UAGENT_PARALLEL_WORKERS` để thay đổi).

**Ví dụ**: Hỏi "Kiểm tra thời tiết ở các thủ đô Bắc Âu" → LLM kích hoạt `search_web` × 5 quốc gia → tất cả 5 tìm kiếm chạy song song → kết quả được thu thập trong một đợt.

Các công cụ chỉ đọc (tìm kiếm tệp, tính toán hàm băm, liệt kê thư mục, dịch thuật, truy vấn DB, v.v.) được song song hóa mạnh mẽ.

### 🧩 Hệ thống plugin (Tương thích với Claude Code)

uagent triển khai **hệ thống plugin tương thích với Claude Code**. Các plugin kết hợp kỹ năng, tác nhân, máy chủ MCP, hook và nhiều thành phần khác vào các thư mục độc lập với manifest `.claude-plugin/plugin.json`.

**Các thành phần được hỗ trợ**: kỹ năng, tác nhân phụ, máy chủ MCP, hook (12 sự kiện vòng đời), lệnh gạch chéo, kiểu đầu ra, userConfig, phụ thuộc, kênh, thị trường

**CLI commands**:

```
:plugin list                         # Liệt kê các plugin đã cài đặt
:plugin install <source> [--scope]
:plugin install <name>@<marketplace>  # Cài đặt từ thị trường
:plugin remove <name>                # Gỡ cài đặt
:plugin enable/disable <name>        # Chuyển đổi
:plugin marketplace add/remove/list  # Quản lý thị trường
:plugin init <name>                  # Tạo cấu trúc plugin mới
```

Xem tài liệu đầy đủ tại [DEVELOP_PLUGIN.md](../src/uagent/docs/DEVELOP_PLUGIN.md).

### 🔄 Phiên liên tục

- **Chuyển đổi nhà cung cấp giữa phiên**: `UAGENT_PROVIDER` — lịch sử hội thoại được giữ nguyên.
- **Tải lại các phiên trước**: `:load <index>` — tiếp tục từ nơi bạn đã dừng lại.

### 🛠 229 Công cụ

| Danh mục | Công cụ |
|---|---|
| **Thao tác tệp** | đọc/ghi/tạo/xóa/tìm kiếm/grep/hash/zip, file_type, parse_eml (tệp .eml) |
| **Web** | tìm nạp_url, search_web, ảnh chụp màn hình, browser_playwright |
| **Truyền thông** | tạo_hình ảnh, phân tích_hình ảnh, img2img, audio_speech, audio_transcribe |
| **Tài liệu** | Trích xuất PDF/PPTX/DOCX/RTF/ODT, trích xuất có cấu trúc Excel |
| **Dự báo** | Dự báo chuỗi thời gian với 9 mô hình (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, v.v.), tự động chọn mô hình, tạo biểu đồ, i18n |
| **Giao tiếp** | gmail_send, gmail_read, bluesky, discord_channel, Team_webhook, **pybitchat** (BLE Mesh) — xem [COMMUNICATION.md](COMMUNICATION.md) và [BITCHAT.md](BITCHAT.md) |
| **IoT** | BACnet、Modbus TCP、OPC UA、SwitchBot（Cloud + BLE）、ECHONET Lite、Matter、UPnP、reverse_geocode |
| **API đám mây** | `aws_api`, `gcp_api`, `azure_api` — AWS, Google Cloud, and Azure API operations; write operations require explicit confirmation |
| **Công cụ dành cho nhà phát triển** | workspace_status, git_ops, python_compile, lint_format, run_tests, db_query, **29 trình điều hướng mã nguồn (dòng idx)** |
| **MCP** | Kết nối với máy chủ MCP bên ngoài, liệt kê các công cụ, thực thi — [OAuth / Proxy guide](MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Giao tiếp giữa các đại lý (với các phiên bản uag khác hoặc máy chủ tương thích với A2A) |
| **Hệ thống** | env vars, thông số kỹ thuật hệ thống, tính toán thời gian, ngày tháng, uuid_gen, slugify, quantities ||
| **Điều hướng nguồn** | **29 công cụ idx** dành cho Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — lấy chỉ mục hàm/lớp hoặc định nghĩa cụ thể mà không cần đọc toàn bộ tệp |

#### Đánh giá và bảo hiểm kho lưu trữ

- `workspace_status`: Báo cáo nhánh không gian làm việc đang hoạt động Git, các thay đổi, trạng thái đồng bộ hóa ngược dòng, thời gian chạy Python và các điểm đánh dấu dự án phổ biến mà không sửa đổi tệp.
- `git_review`: tóm tắt các thay đổi Git, các tệp rủi ro, các ứng cử viên kiểm tra và các phát hiện bí mật mà không để lộ các giá trị bí mật.
- `security_scan`: quét các tệp kho lưu trữ để tìm các bí mật có thể xảy ra và các tệp cấu hình rủi ro.
- `coverage_report`: chạy và chuẩn hóa phạm vi bảo hiểm cho Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift và Dart/Flutter.
- Các phụ thuộc vùng phủ sóng bị thiếu có thể được cài đặt tự động khi yêu cầu thực thi; `dry_run` không bao giờ cài đặt gói.

Xem [Công cụ phân tích kho lưu trữ](REPOSITORY_TOOLS.md) để biết thông số, đầu ra và chi tiết an toàn.

### 🖥 4 Giao diện + Tiện ích mở rộng Mã VS

| Chế độ | Lệnh | Mục đích |
|---|---|---|
| **CLI** | `uag` | Hoạt động dựa trên thiết bị đầu cuối nhanh |
| **GUI** | `uagg` | Giao diện người dùng máy tính để bàn thông qua tkinter |
| **Web** | `uagw` | Truy cập dựa trên trình duyệt |
| **Máy chủ A2A** | `uaga` | Giao thức Agent2Agent cho giao tiếp đa tác nhân |
| **Mã VS** | — | [Tiện ích mở rộng](VSCODE.md) với Bảng trò chuyện, Giải thích, Tái cấu trúc, Sửa lỗi và Chế độ xem dạng cây công cụ |

Xem [VSCODE.md](VSCODE.md) để biết thông tin chi tiết về tiện ích mở rộng VS Code — cài đặt, lệnh, tổ hợp phím và cấu hình.

### 🏠 Kiểm soát thiết bị IoT

- **Vấn đề**: Kiểm tra chỉ đọc cấu trúc liên kết bộ điều khiển/cầu nối/thiết bị

Xem [IOT_USECASE.md](IOT_USECASE.md)

### 🏠 Điều khiển thiết bị IoT

- **BACnet**: Đọc/ghi các thiết bị BACnet/IP (HVAC, hệ thống chiếu sáng, đồng hồ đo điện). Đăng ký COV cho thông báo đẩy
- **Modbus TCP**: Đọc/ghi các thanh ghi giữ/đầu vào và cuộn dây. Giám sát thay đổi dựa trên thăm dò ý kiến
- **OPC UA**: Duyệt qua không gian địa chỉ, đọc/ghi các biến, đăng ký các thay đổi dữ liệu
- **SwitchBot**: Kiểm soát hàng loạt đám mây & quét/kiểm soát BLE. Đăng ký dựa trên thăm dò ý kiến
- **ECHONET Lite**: Khám phá, kiểm soát và đăng ký thông báo INF từ các thiết bị gia dụng (AC, đèn, máy nước nóng, v.v.)
- **Vấn đề**: Kiểm soát đọc/ghi + đăng ký thuộc tính để giám sát thay đổi trạng thái
- **UPnP**: Khám phá thiết bị và chuyển tiếp cổng IGD

Xem [IOT_USECASE.md](IOT_USECASE.md)

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

Xem [README_AUTO.md](README_AUTO.md) để biết tài liệu đầy đủ.

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

Nhấn phím `x` để thoát chế độ tự động điều khiển (xem [README_AUTO.md](README_AUTO.md)).

### 🕵️ Tự động hóa trình duyệt & Trình kiểm tra web

Hai công cụ bổ sung dựa trên Nhà viết kịch:

- **browser_playwright**: Tự động hóa các phiên trình duyệt thực — điều hướng, nhấp chuột, điền biểu mẫu, trích xuất dữ liệu, xử lý các luồng nhiều trang. Hoạt động không có đầu hoặc có đầu.
- **playwright_inspector**: Ghi lại quá trình chuyển đổi trình duyệt, chụp ảnh chụp nhanh DOM và ảnh chụp màn hình ở mỗi bước. Hữu ích cho việc gỡ lỗi các tương tác trên web hoặc kiểm tra các thay đổi của trang theo thời gian.

### 🔄 Đang tải công cụ động

`tool_catalog` và `tool_load` cho phép bạn khám phá và kích hoạt các công cụ trong thời gian chạy.
Không cần tải mọi thứ khi khởi động — chỉ kích hoạt những gì bạn cần, khi bạn cần.

### 🦀 Rust Native Tools

`uuid_gen` và `slugify` được triển khai bằng Rust (thông qua PyO3) để cải thiện hiệu suất.

### 🌐 i18n/L10n

日本語 / Tiếng Anh / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / và hơn thế nữa.
Đặt `UAGENT_LANG` để chuyển đổi. Xem [ADD_LOCALE.md](../src/uagent/docs/DEVELOP_I18N.md) để thêm ngôn ngữ mới.

Bản dịch của README này có sẵn trong [docs/README.translations.md](README.translations.md).

### 🔒 Biến môi trường được mã hóa

Lưu trữ khóa và bí mật API trong `.env.sec` — một tệp `.env` được mã hóa.
Quản lý bằng `uag_envsec`.

## Cấu hình & Chi tiết

- **Biến môi trường**: [docs/ENVIRONMENT.md](ENVIRONMENT.md)
- **Trình hướng dẫn thiết lập**: `python -m uagent.setup_cli`
- **Env được mã hóa**: `uag_envsec` — mã hóa `.env` thành `.env.sec`
- **API phản hồi**: Đặt `UAGENT_RESPONSES=1` cho chế độ API phản hồi (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Tự động kích hoạt cho Sakana AI (Fugu).
- **Tài liệu dành cho nhà phát triển**: [DEVELOP.md](../src/uagent/docs/DEVELOP.md)
- **Tool flow**: [TOOL_FLOW.md](../src/uagent/docs/TOOL_FLOW.md)
- **Mẹo LLM nhỏ**: [SLM_TIPS.md](SLM_TIPS.md)

## Triết lý dự án

uag mong muốn trở thành **AI của bạn, trên máy của bạn, theo điều kiện của bạn.**

- Không phụ thuộc SaaS - chạy cục bộ
- Không khóa nhà cung cấp - chuyển đổi bất cứ lúc nào
- Không khóa giao diện người dùng — CLI / GUI / Web / A2A
- Không khóa tính năng - mở rộng bằng các công cụ và kỹ năng

Trải nghiệm đại lý AI miễn phí, không bị ràng buộc bởi nhà cung cấp.

### ✨ Tạo công cụ của riêng bạn

[vi.md](TOOL_CREATOR_GUIDE.vi.md)
Xem hướng dẫn từng bước tại đây.

## Đóng góp

Mọi đóng góp đều được hoan nghênh! Chúng tôi trân trọng báo cáo lỗi, đề xuất tính năng, cải thiện tài liệu, bản dịch và pull request.

- **Issues**: Mở sự cố GitHub để tìm lỗi hoặc yêu cầu tính năng.
- **Pull request**: Fork kho lưu trữ, thực hiện thay đổi và gửi PR. Xem [DEVELOP.md](../src/uagent/docs/DEVELOP.md) để biết cách thiết lập môi trường phát triển và các hướng dẫn.

Realtime Giọng nói và AEC3

## Realtime chế độ giọng nói hỗ trợ đầu vào/đầu ra loa và micrô song công hoàn toàn. Nếu thiếu phần phụ trợ AEC3, uag sẽ tự động cài đặt pywebrtc-audio.

**Nhà cung cấp thời gian thực**: OpenAI Realtime, Azure OpenAI GPT Realtime, Google Gemini Live, xAI Grok Voice và Amazon Bedrock Nova Sonic. SDK phát trực tuyến hai chiều của Bedrock chỉ được cài đặt tự động khi Bedrock được chọn.

```bat
python scheck.py realtime
```

AEC3 sử dụng tín hiệu micrô thực tế (gần) và âm thanh thực tế được gửi đến loa (xa). Chỉ bật chẩn đoán khi điều tra sự cố âm thanh.

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime hỗ trợ tích hợp Function Calling ở mức giới hạn an toàn. Bộ điều hợp hiện tại tự động hiển thị chức năng get_current_time chỉ đọc. Các công cụ phá hủy và điều khiển thiết bị yêu cầu phải có danh sách cho phép và quy trình xác nhận rõ ràng. Grok thời gian thực sử dụng bộ chuyển đổi riêng và không sử dụng đường dẫn Function Calling dành riêng cho OpenAI này.

## Kiến trúc và bất biến vận hành

Xem [ARCHITECTURE.md](ARCHITECTURE.md) để biết các hợp đồng triển khai lâu dài bao quát vòng đời A2A, ngữ cảnh I18N, cài đặt phần phụ thuộc tùy chọn, an toàn công cụ, khả năng của nhà cung cấp, ranh giới tin cậy OAuth, sự kiện có cấu trúc và xác minh nghiệm thu.

## Enterprise Policy Engine

Enterprise Policy Engine supports organization-level rules for tools, providers, credentials, MCP servers, networks, skills, and plugins. Configure `UAGENT_POLICY_FILE` with a JSON/YAML policy file. See [ENTERPRISE_POLICY.md](ENTERPRISE_POLICY.md) for examples, roles, confirmation, and allowlists.

### Runtime recovery and orchestration

See [RESTART_RECOVERY.md](RESTART_RECOVERY.md) / [DAG_SCHEDULER.md](DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](MULTI_AGENT_RUNTIME.md) for durable recovery, dependency-aware execution, multi-agent orchestration, and remote A2A usage.

See [DISTRIBUTED_COORDINATION.md](DISTRIBUTED_COORDINATION.md) for shared-runtime leader lease coordination.
