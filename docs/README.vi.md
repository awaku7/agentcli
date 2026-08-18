\<palign="center">
<img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">

</p>

\<h1align="center">uag — Cổng AI phổ quát</h1>

\<palign="center">
<b>U</b>niversal <b>A</b>I <b>G</b>ateway — Môi trường của bạn, sự tự do của bạn.

</p>

\<palign="center">
Hoạt động tệp / Tìm kiếm trên web / Tạo và phân tích hình ảnh / Trích xuất PDF & Excel / Kiểm soát IoT / Tích hợp MCP<br>
24 nhà cung cấp / 3 giao diện người dùng / Thực thi công cụ song song / Thị trường kỹ năng của đại lý

</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a href="https://pypi.org/project/uag/">PyPI</a>
 ·
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Đọc phần này trong trang của bạn ngôn ngữ</a>
</p>

______________________________________________________________________

## Tại sao uag?

**Thoát khỏi sự ràng buộc của nhà cung cấp.** Hầu hết trợ lý AI đều ràng buộc bạn với một nhà cung cấp hoặc dịch vụ đám mây cụ thể. uag thì khác.

- **Chạy cục bộ** trên máy của bạn. Dữ liệu của bạn vẫn được lưu giữ bên bạn (ngoại trừ API cuộc gọi bạn thực hiện).
- **Quyền tự do của nhà cung cấp**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 nhà cung cấp, tất cả đều có thể truy cập được từ một giao diện duy nhất. Hoán đổi giữa chúng bằng cách định cấu hình lại các biến môi trường — không cài đặt lại, không di chuyển.
- **222 công cụ**: I/O tệp, tìm kiếm trên web, tạo hình ảnh, Gmail, quét thiết bị BLE, MCP tích hợp máy chủ — **130 được đánh dấu tĩnh là an toàn song song** (tối đa 8 công cụ thực thi đồng thời thông qua nhóm luồng, có thể định cấu hình qua `UAGENT_PARALLEL_WORKERS`). Khi LLM thực hiện nhiều lệnh gọi công cụ cùng một lúc, uag sẽ tự động song song hóa chúng.
- **3 UI + A2A**: CLI, GUI, Web và giao thức Agent-to-Agent. Cùng một công cụ, mọi giao diện.
- **IoT sẵn sàng**: SwitchBot, ECHONET Lite, Matter, UPnP — điều khiển các thiết bị trong nhà của bạn thông qua AI.
- **Kỹ năng đại lý**: Cài đặt các kỹ năng do cộng đồng xây dựng từ thị trường. Mở rộng uag vô tận.

uag là **trợ lý AI theo điều kiện của bạn**. Không bị ràng buộc với nhà cung cấp, không bị ràng buộc với giao diện, không bị ràng buộc với nền tảng.

## Bắt đầu nhanh

```bash
pip install uag
uag
```

Trong lần khởi chạy đầu tiên, trình hướng dẫn thiết lập sẽ hướng dẫn bạn cách cấu hình nhà cung cấp.
Xem [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) để biết tất cả các biến môi trường.

## Sử dụng máy tính

Sử dụng máy tính được chọn tham gia và hỗ trợ cả thời gian chạy trình duyệt Playwright hiển thị
và thời gian chạy trên máy tính để bàn. Khi được bật, cả hai thời gian chạy đều được tạo và đăng ký;

```bat
set UAGENT_COMPUTER_USE=1
```

Sử dụng `desktop` để chọn thời gian chạy máy tính để bàn của hệ điều hành thay thế. Các tài nguyên thời gian chạy
được đóng lại với nhau khi thoát thông thường, `Ctrl-C` và tắt quy trình. Đặt
`UAGENT_COMPUTER_HEADLESS=1` để kiểm tra CI hoặc khói dựa trên trình duyệt.
Xem [docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
để biết chi tiết về tích hợp và an toàn.

## Giọng nói thời gian thực và AEC3

Chế độ giọng nói thời gian thực hỗ trợ OpenAI Thời gian thực, Azure OpenAI GPT Thời gian thực, xAI Grok Giọng nói API, Google Gemini Multimodal Live API và Amazon Bedrock Nova Sonic với I/O loa và micrô song công hoàn toàn. Phần phụ trợ `pywebrtc-audio` AEC3 bắt buộc được cài đặt tự động và SDK phát trực tuyến hai chiều tùy chọn của Bedrock chỉ được cài đặt tự động khi nhà cung cấp Bedrock được chọn:

```bash
python scheck.py realtime
```

Đường dẫn AEC3 nhận được tín hiệu micrô thực tế (`gần`) và âm thanh thực sự được truyền đến loa (`xa`) để trợ lý có thể nghe trong khi nói. Chỉ bật chẩn đoán khi điều tra sự cố âm thanh:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Gọi hàm theo thời gian thực

OpenAI Thời gian thực hỗ trợ tích hợp Gọi hàm ở giới hạn an toàn. Bộ điều hợp thời gian thực hiện tại tự động hiển thị `get_current_time` chỉ đọc. Các công cụ phá hủy và điều khiển thiết bị sẽ không bị lộ nếu không có danh sách cho phép và quy trình xác nhận rõ ràng. Grok thời gian thực sử dụng bộ điều hợp riêng và không sử dụng đường dẫn gọi hàm dành riêng cho OpenAI này.

## Tính năng

### 🧠 Kiến trúc đa nhà cung cấp

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway
Tất cả các nhà cung cấp đều có chung bộ công cụ và giao diện. Chuyển đổi bằng cách cài đặt `UAGENT_PROVIDER` — không thay đổi mã, không cài đặt riêng.

#### Ollama và llama.cpp

Ollama và llama.cpp là các nhà cung cấp riêng biệt. Ollama sử dụng dịch vụ và quản lý mô hình của riêng mình, trong khi `llama.cpp` kết nối với điểm cuối tương thích với `llama-server` OpenAI:
\`\`bash

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
Nhà cung cấp llama.cpp sử dụng đường dẫn tương thích với Hoàn thành trò chuyện. Giữ `UAGENT_RESPONSES=0` trừ khi proxy tương thích được định cấu hình.
### ⚡ Thực thi công cụ song song
Khi LLM yêu cầu nhiều công cụ cùng lúc, uag **tự động song song** chúng.
130 công cụ được đánh dấu tĩnh `x_parallel_safe` và thực thi đồng thời thông qua `ThreadPoolExecutor` (8 luồng theo mặc định; được đặt `UAGENT_PARALLEL_WORKERS` để thay đổi).
**Ví dụ**: Hỏi "Kiểm tra thời tiết ở các thủ đô Bắc Âu" → LLM kích hoạt `search_web` × 5 quốc gia → tất cả 5 tìm kiếm chạy song song → kết quả được thu thập trong một đợt.
Số lượng hiện tại dựa trên các mô-đun công cụ xác định `TOOL_SPEC` (hiện tại là 222, bao gồm 2 công cụ được hỗ trợ bởi Rust trong `src/uagent/tools_rust/`). `http_request` sử dụng tính năng an toàn nhạy cảm với phương thức: lệnh gọi `GET`/`HEAD`/`OPTIONS` có thể chạy song song, trong khi phương thức ghi vẫn duy trì nối tiếp.
Các công cụ chỉ đọc (tìm kiếm tệp, tính toán băm, danh sách thư mục, dịch thuật, truy vấn DB, v.v.) được song song hóa mạnh mẽ.
### 🧩 Hệ thống plugin (Claude Tương thích mã)
uagent triển khai **Claude Hệ thống plugin tương thích với mã**. Các plugin kết hợp các kỹ năng, tác nhân, máy chủ MCP, hook và nhiều thứ khác vào các thư mục độc lập với tệp kê khai `.claude-plugin/plugin.json`.
**Các thành phần được hỗ trợ**: Kỹ năng, Tác nhân phụ, máy chủ MCP, Hook (12 sự kiện trong vòng đời), Lệnh gạch chéo, Kiểu đầu ra, cấu hình người dùng, Phần phụ thuộc, Kênh, Thị trường
**CLI lệnh**:
```

:danh sách plugin # Liệt kê các plugin đã cài đặt
:cài đặt plugin <source> [--scope] # Cài đặt (dir/zip/git/http)
:plugin install <name>@<marketplace> # Cài đặt từ Marketplace
:plugin xóa <name> # Gỡ cài đặt
:bật/tắt plugin <name> # Toggle
:plugin Marketplace thêm/xóa/danh sách # Quản lý Marketplace
:plugin init <name> # Plugin mới của giàn giáo

````
Xem [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) để có tài liệu đầy đủ.
### 🔄 Tính liên tục của phiên
- **Chuyển đổi nhà cung cấp giữa phiên** với `UAGENT_PROVIDER` — lịch sử hội thoại được giữ nguyên.
- **Tải lại các phiên trước** với `:load <index>` — tiếp tục từ nơi bạn đã dừng lại.
- **Bộ nhớ đệm kết quả công cụ** tránh việc thực thi lại dư thừa khi lệnh gọi công cụ tương tự lặp lại.
### 🛠 229 Tools
| Danh mục | Công cụ |
|---|---|
| **Thao tác tệp** | đọc/ghi/tạo/xóa/tìm kiếm/grep/hash/zip, file_type, parse_eml (tệp .eml), `path_alias` |
| **Web** | tìm nạp_url, search_web, ảnh chụp màn hình, browser_playwright, `url_alias`, `public_transit_route` ([guide](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **Truyền thông** | tạo_hình ảnh, phân tích_hình ảnh, img2img, audio_speech, audio_transcribe |
| **Tài liệu** | Trích xuất PDF/PPTX/DOCX/RTF/ODT, trích xuất có cấu trúc Excel |
| **Dự báo** | Dự báo chuỗi thời gian với 9 mô hình (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, v.v.), lựa chọn mô hình tự động, tạo cốt truyện, i18n |
| **Giao tiếp** | gmail_send, gmail_read, bluesky, discord_channel, Team_webhook, **pybitchat** (BLE Mesh) — xem [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) và [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP, Reverse_geocode |
| **API đám mây** | `aws_api`, `gcp_api`, `azure_api` — các hoạt động chung của AWS, Google Cloud và Azure API; thao tác ghi yêu cầu xác nhận rõ ràng |
| **Công cụ dành cho nhà phát triển** | không gian làm việc_status, git_ops, git_review, security_scan, cover_report, python_compile, lint_format, run_tests, db_query, **29 trình điều hướng mã nguồn (dòng idx)** |
| **MCP** | Kết nối với máy chủ MCP bên ngoài, liệt kê các công cụ, thực thi — [Hướng dẫn OAuth / Proxy](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Giao tiếp giữa đại lý với đại lý (với các phiên bản uag khác hoặc máy chủ tương thích A2A) |
| **Hệ thống** | env vars, thông số hệ thống, tính toán ngày, giờ, [số lượng](docs/QUANTITIES.md), [geodesic_distance](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **Điều hướng nguồn** | **29 công cụ idx** cho Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — lấy chỉ mục hàm/lớp hoặc định nghĩa cụ thể mà không cần đọc toàn bộ tệp |
#### Đánh giá và bao quát kho lưu trữ
- `workspace_status`: báo cáo nhánh Git của không gian làm việc đang hoạt động, các thay đổi, trạng thái đồng bộ ngược dòng, thời gian chạy Python và các dấu hiệu dự án phổ biến mà không cần sửa đổi tệp.
- `git_review`: tóm tắt các thay đổi Git, tệp rủi ro, kiểm tra ứng viên và phát hiện bí mật mà không để lộ giá trị bí mật.
- `security_scan`: quét các tệp kho lưu trữ để tìm bí mật có thể xảy ra và tệp cấu hình rủi ro.
- `coverage_report`: chạy và chuẩn hóa phạm vi bảo hiểm cho Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift và Dart/Flutter.
- Các phụ thuộc vùng phủ sóng bị thiếu có thể được cài đặt tự động khi yêu cầu thực thi; `dry_run` không bao giờ cài đặt gói.
Xem [Công cụ phân tích kho lưu trữ](docs/REPOSITORY_TOOLS.md) để biết thông số, đầu ra và chi tiết an toàn.
Xem [Bí danh đường dẫn và URL](docs/PATH_URL_ALIASES.md) để rút ngắn đường dẫn tệp và URL lặp lại trong đối số công cụ.
### 🖥 4 Giao diện + Phần mở rộng mã VS
| Chế độ | Lệnh | Mục đích |
|---|---|---|
| **CLI** | `uag` | Hoạt động dựa trên thiết bị đầu cuối nhanh |
| **GUI** | `uagg` | Giao diện người dùng máy tính để bàn thông qua tkinter |
| **Web** | `uagw` | Truy cập dựa trên trình duyệt |
| **A2A Máy chủ** | `uaga` | Giao thức Agent2Agent cho giao tiếp đa tác nhân |
| **Mã VS** | — | [Tiện ích mở rộng](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) với Bảng trò chuyện, Giải thích, Tái cấu trúc, Sửa lỗi và Chế độ xem dạng cây công cụ |
Xem [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) để biết thông tin chi tiết về tiện ích mở rộng VS Code — cài đặt, lệnh, tổ hợp phím và cấu hình.
### 🏠 Điều khiển thiết bị IoT
- **BACnet**: Đọc/ghi các thiết bị BACnet/IP (HVAC, hệ thống chiếu sáng, đồng hồ đo điện). Đăng ký COV để nhận thông báo đẩy
- **Modbus TCP**: Đọc/ghi giữ/nhập các thanh ghi và cuộn dây. Giám sát thay đổi dựa trên thăm dò
- **OPC UA**: Duyệt không gian địa chỉ, đọc/ghi các biến, đăng ký thay đổi dữ liệu
- **SwitchBot**: Kiểm soát hàng loạt đám mây & quét/điều khiển BLE. Đăng ký dựa trên thăm dò
- **ECHONET Lite**: Khám phá, kiểm soát và đăng ký thông báo INF từ các thiết bị gia dụng (AC, đèn, máy nước nóng, v.v.)
- **Vấn đề**: Kiểm soát đọc/ghi + đăng ký thuộc tính để giám sát thay đổi trạng thái
- **UPnP**: Khám phá thiết bị & chuyển tiếp cổng IGD
Xem [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)
### 🎯 Chợ kỹ năng đại lý
`:skills mp_search` để duyệt qua [SkillsMP](https://skillsmp.com) và [ClawHub](https://clawhub.ai) để biết các kỹ năng cộng đồng.
Cài đặt và mở rộng Khả năng của uag một cách nhanh chóng.
### 🤖 Auto-Pilot (`:auto`)
uag có thể **tự động theo đuổi mục tiêu trong nhiều LLM vòng**. Hoàn hảo cho các nhiệm vụ phức tạp, nhiều bước cần tinh chỉnh lặp đi lặp lại.
- **Cách hoạt động**: Mỗi vòng có một truy vấn chính (Bước A), theo sau là phán đoán của người đánh giá (Bước B) quyết định "HOÀN THÀNH hay TIẾP TỤC?"
- **Cùng một nhà cung cấp, giống API**: Phán quyết của người đánh giá sử dụng đường dẫn mã giống hệt như truy vấn chính — bao gồm Phản hồi API hỗ trợ.
- **Thẩm phán riêng LLM** (tùy chọn): Đặt `UAGENT_AP_PROVIDER` để sử dụng một nhà cung cấp/mô hình khác cho người đánh giá (ví dụ: sử dụng mô hình rẻ hơn để đánh giá).
- **Thoát bất cứ lúc nào**: Nhấn phím F11 để dừng ngay lập tức, kể cả khi đang phản hồi. Hoặc để người đánh giá quyết định khi nào đạt được mục tiêu.
- **Có thể định cấu hình**: `--max-rounds N` để kiểm soát ngân sách.
Xem [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) để có tài liệu đầy đủ.
### 🧩 Batch State Manager
uag có thể theo dõi tiến trình trong thời gian dài nhiệm vụ nhiều tập tin. Khi LLM xử lý hàng chục tệp, `batch_state` vẫn giữ nguyên danh sách các tệp đang chờ xử lý, đã hoàn thành và không thành công vào đĩa. Nếu phiên kết thúc hoặc hết thời gian, lần chạy tiếp theo sẽ tiếp tục từ nơi nó đã dừng — không có gì bị mất.
### 🛡 Human-in-the-Loop
`human_ask` cho phép LLM tạm dừng và yêu cầu bạn xác nhận trước khi thực hiện các thao tác phá hoại (xóa tệp, ghi đè, lệnh shell). Bạn luôn nắm quyền kiểm soát.
### 🛑 Ngắt (phím c / Nút dừng)
Dừng tạo phản hồi LLM bất cứ lúc nào và đưa lệnh dừng trở lại LLM.
| Giao diện | Cách ngắt lời |
|---|---|
| **CLI** | Nhấn phím F12 trong khi phát trực tuyến LLM — phản hồi hiện tại dừng và `"Dừng"` được gửi dưới dạng tin nhắn người dùng để LLM phản hồi tương ứng |
| **Giao diện người dùng WEB** | Nhấp vào nút **■ Dừng** màu đỏ (tự động xuất hiện trong quá trình xử lý LLM) |
| **Giao diện máy tính để bàn** | Nhấp vào nút **■** màu đỏ (tự động xuất hiện trong quá trình xử lý LLM) |
Ngắt hoạt động như "nhắc nhở": thay vì chỉ hủy bỏ, nó sẽ đưa `"Dừng"` trở lại LLM dưới dạng thông báo người dùng, cho phép nó kết thúc hoặc xác nhận sự gián đoạn một cách duyên dáng.
Nhấn phím F11 để thoát chế độ tự động điều khiển (xem [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).
### 🕵️ Tự động hóa trình duyệt và Thanh tra web
Hai công cụ bổ sung dựa trên Playwright:
- **browser_playwright**: Tự động hóa các phiên trình duyệt thực — điều hướng, nhấp chuột, điền vào biểu mẫu, trích xuất dữ liệu, xử lý các luồng nhiều trang. Hoạt động không có đầu hoặc có đầu.
- **playwright_inspector**: Ghi lại quá trình chuyển đổi trình duyệt, chụp ảnh chụp nhanh DOM và ảnh chụp màn hình ở mỗi bước. Hữu ích để gỡ lỗi các tương tác trên web hoặc kiểm tra các thay đổi của trang theo thời gian.
### 🔄 Tải công cụ động
`tool_catalog` và `tool_load` cho phép bạn khám phá và kích hoạt các công cụ trong thời gian chạy.
Không cần tải mọi thứ khi khởi động — chỉ kích hoạt những gì bạn cần, khi bạn cần.
### 🦀 Rust Native Tools
`uuid_gen` và `slugify` được triển khai trong Rust (thông qua PyO3) cho hiệu suất.
Chúng tải trực tiếp từ `.pyd` dựng sẵn — **không cần `pip install`**.
Các nhà phát triển bên ngoài cũng có thể cung cấp các công cụ dựa trên Rust: đặt `.pyd` bên cạnh 
wrapper `.py`, sử dụng `load_rust_pyd()` từ `uagent.tools.rust_helper` và
người dùng nhận được công cụ mà không cần bất kỳ sự phụ thuộc bổ sung nào. Xem
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).
### 🌐 i18n / L10n
日本語 / English / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / và hơn thế nữa.
Đặt `UAGENT_LANG` để chuyển đổi. Xem [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) để thêm ngôn ngữ mới.
Bản dịch của README này có sẵn ở [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).
### 🔒 Biến môi trường được mã hóa
Lưu trữ API khóa và bí mật trong `.env.sec` — một tệp `.env` được mã hóa.
Quản lý bằng `uag_envsec`.
## Cấu hình & Chi tiết

- **Biến môi trường**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Trình hướng dẫn thiết lập**: `python -m uagent.setup_cli`
- **Env được mã hóa**: `uag_envsec` — mã hóa `.env` dưới dạng `.env.sec`
- **Phản hồi API**: Đặt `UAGENT_RESPONSES=1` cho chế độ Phản hồi API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Tự động kích hoạt cho Sakana AI (Fugu).
- **Tài liệu dành cho nhà phát triển**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Luồng công cụ**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — cách các công cụ được gửi tới LLM (mặt nạ thể loại, tool_catalog, GPT-5.4+ công cụ gốc_search)
- **Mẹo nhỏ LLM**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Triết lý dự án

uag mong muốn trở thành **AI của bạn, trên máy của bạn, theo điều kiện của bạn.**

- Không phụ thuộc vào SaaS — chạy cục bộ
- Không khóa nhà cung cấp — chuyển đổi bất cứ lúc nào
- Không khóa giao diện người dùng — CLI / GUI / Web / A2A
- Không khóa tính năng — mở rộng với các công cụ và kỹ năng

Trải nghiệm tác nhân AI miễn phí, miễn phí từ nhà cung cấp lock-in.

### ✨ Tạo công cụ của riêng bạn

Viết một công cụ mới cho uag rất đơn giản — tạo một tệp `.py` duy nhất với
`TOOL_SPEC` và `run_tool()`, đặt nó vào `UAGENT_EXTERNAL_TOOLS_DIR` và
nó có sẵn ngay lập tức. Đối với các nhà phát triển Rust, hãy gửi `.pyd` dựng sẵn mà
không có phần phụ thuộc bổ sung nào cho người dùng.

Xem [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
để biết hướng dẫn từng bước.

## Đóng góp

Hoan nghênh đóng góp! Báo cáo lỗi, đề xuất tính năng, cải tiến tài liệu, bản dịch và yêu cầu kéo — tất cả đều được đánh giá cao.

- **Vấn đề**: Mở một vấn đề GitHub về lỗi hoặc yêu cầu tính năng.
- **Yêu cầu kéo**: Phân nhánh kho lưu trữ, thực hiện các thay đổi của bạn và gửi PR. Xem [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) để biết hướng dẫn và thiết lập phát triển.
- **Bản dịch**: Hoan nghênh các bản dịch README và bổ sung ngôn ngữ. Xem [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Công cụ & Kỹ năng**: Các plugin công cụ mới và Kỹ năng của đặc vụ có thể được đóng góp thông qua thị trường.

### Kiểm tra phát triển (trước PR)

Trước tiên hãy cài đặt các phần phụ thuộc chỉ dành cho thử nghiệm. Chúng được giữ ngoài thời gian chạy
danh sách phụ thuộc:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
````

Chạy các kiểm tra tương tự được sử dụng bởi GitHub Hành động trước khi đẩy:

```bash
python -m ruff check src tests
python -m black --check src test
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .
```

Để lặp lại cục bộ nhanh hơn, chỉ chạy các thử nghiệm bị ảnh hưởng:

```bash
pytest -q test/<affected_area>
```

Kiểm tra bổ sung khi có liên quan:

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

Sau khi chỉnh sửa ngôn ngữ (`.po`): `python scripts/compile_locales.py` và `python scripts/po_qc_summary.py`.

Chính sách thời gian chạy (chi tiết trong [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) §6.1): người trợ giúp gây quỹ thay vì `sys.exit`; máy chủ công cụ biến công cụ `SystemExit`/`Exception` thành các chuỗi lỗi để một công cụ duy nhất không thể giết chết tiến trình. Việc thoát nhanh khi khởi động vẫn có chủ ý.

## Các bất biến về kiến ​​trúc và vận hành

Xem [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) để biết các hợp đồng lâu dài bao gồm vòng đời A2A, bối cảnh I18N, cài đặt phụ thuộc tùy chọn, an toàn công cụ, khả năng của nhà cung cấp, ranh giới tin cậy OAuth, sự kiện có cấu trúc và xác minh chấp nhận.

## Công cụ chính sách doanh nghiệp

Các chính sách cấp tổ chức dành cho công cụ, nhà cung cấp, thông tin xác thực, máy chủ MCP, mạng, kỹ năng và plugin được hỗ trợ. Đặt `UAGENT_POLICY_FILE` thành tệp chính sách JSON/YAML; xem [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) để biết ví dụ về cấu hình, vai trò, xác nhận và danh sách cho phép.

### Khôi phục và điều phối thời gian chạy

Xem [RESTART_RECOVERY.md](docs/RESTART_RECOVERY.md) / [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) để phục hồi lâu dài, thực thi nhận thức phụ thuộc, điều phối nhiều tác nhân và sử dụng A2A từ xa.

Xem [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) để phối hợp cho thuê người lãnh đạo trong thời gian chạy chung.
