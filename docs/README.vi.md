<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="logo uag" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Cổng AI Toàn năng</strong><br>
  Một agent cục bộ. Mọi mô hình. Mọi công cụ. Môi trường của bạn, quy tắc của bạn.
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="trạng thái CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="phiên bản PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="các phiên bản Python"></a>
  <a href="https://github.com/awaku7/agentcli/blob/main/LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="Giấy phép"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="PyPI Downloads"></a>
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a> ·
  <a href="https://pypi.org/project/uag/">PyPI</a> ·
  <a href="https://github.com/awaku7/agentcli/discussions">Thảo luận</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Bản dịch</a>
</p>

______________________________________________________________________

**Tại sao chọn uag?**

uag là một agent AI ưu tiên cục bộ, kết nối mô hình bạn ưa thích với những công cụ bạn thực sự sử dụng.
Nó cung cấp cho bạn một runtime duy nhất, có thể mở rộng, dành cho tệp, trình duyệt, codebase, giao tiếp, API đám mây,
thiết bị IoT, máy chủ MCP và các quy trình làm việc đa agent.

- **Tự do lựa chọn provider** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek và nhiều hơn nữa.
- **Thực thi ưu tiên cục bộ** — runtime agent và việc thực thi công cụ ở lại trên máy của bạn; chỉ các lệnh gọi API bạn chọn mới rời khỏi máy.
- **Một lớp công cụ** — cùng những công cụ đó hoạt động từ CLI, GUI máy tính, web UI, VS Code và A2A.
- **Thiết kế cho xử lý song song** — các thao tác độc lập, chỉ đọc có thể chạy đồng thời.
- **Có thể mở rộng** — thêm công cụ, plugin, Agent Skills, máy chủ MCP và công cụ chạy trên Rust mà không cần thay đổi lõi.
- **Nhận biết an toàn** — các hành động phá hủy, thông tin xác thực, điều khiển thiết bị và thao tác ghi qua mạng hỗ trợ xác nhận rõ ràng cùng các kiểm soát chính sách.

> **Tóm lại:** uag là mặt phẳng điều khiển nằm giữa các mô hình AI và môi trường thực tế của bạn.

> **🧠 Kết quả của công cụ dựa trên ngữ cảnh** — Khi có thể, các kết quả có dung lượng lớn của công cụ sẽ được loại trừ khỏi ngữ cảnh mô hình đang hoạt động. uag lưu trữ chúng dưới dạng Artifacts và thay vào đó, truyền cho mô hình một bản xem trước có giới hạn kèm theo tham chiếu Artifact ổn định. Điều này có thể giảm đáng kể số lượng token đầu vào cần thiết cho các lượt tiếp theo khi công cụ tạo ra kết quả có dung lượng lớn.
> [Hướng dẫn chi tiết về nén ngữ cảnh](CONTEXT_COMPRESSION.vi.md)

## Bắt đầu nhanh

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

Lần khởi chạy đầu tiên sẽ mở trình hướng dẫn thiết lập. Trình hướng dẫn giúp cấu hình một provider và lưu các cài đặt đã chọn
vào môi trường cục bộ của bạn.

Đối với các nhóm tính năng phổ biến:

```bash
python -m pip install "uag[core,providers,tools]"
```

> Các tích hợp nền tảng là tùy chọn. Chỉ cài đặt những gì hệ điều hành của bạn cần; xem

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Các giao diện

| Giao diện | Lệnh | Phù hợp nhất cho |
|---|---|---|
| **CLI** | `uag` | Công việc nhanh, ưu tiên bàn phím |
| **GUI máy tính** | `uagg` | Trải nghiệm máy tính native |
| **Web UI** | `uagw` | Truy cập qua trình duyệt |
| **Máy chủ A2A** | `uaga` | Giao tiếp agent với agent |
| **VS Code** | Extension | Giải thích, tái cấu trúc, sửa lỗi và duyệt công cụ trong trình soạn thảo |

Tất cả giao diện dùng chung cấu hình provider, registry công cụ, quy tắc an toàn và dữ liệu phiên.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## Bạn có thể tạo gì

Các adapter provider bao phủ runtime lưu trữ và cục bộ, bao gồm:

- Đọc, tạo, chỉnh sửa, tìm kiếm, băm, lưu trữ và kiểm tra tệp
- Rà soát thay đổi Git, quét thông tin bí mật, chạy kiểm thử, lint, biên dịch và đo độ bao phủ
- Điều hướng các codebase Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA lớn và các codebase khác
- Tự động hóa trình duyệt bằng Playwright, bao gồm quy trình nhiều trang và tải xuống

- **MCP** — kết nối các máy chủ công cụ bên ngoài, bao gồm các dịch vụ hỗ trợ OAuth
- **A2A** — phối hợp với các agent và máy chủ tương thích khác
- **Cloud** — truy cập API AWS, Google Cloud và Azure với xác nhận cho thao tác ghi
- **Communication** — Gmail, Bluesky, Discord, Microsoft Teams và pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA và UPnP
- **Media** — tạo/chỉnh sửa hình ảnh, chuyển âm thanh thành văn bản/giọng nói, chụp camera và mã QR
- **Documents** — phân tích PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL và log

- **SwitchBot** — khám phá Cloud và BLE, trạng thái, điều khiển, xử lý theo lô và subscription
- **ECHONET Lite** — khám phá và điều khiển thiết bị gia dụng Nhật Bản, bao gồm thông báo INF
- **Matter** — endpoint, cluster, thuộc tính, lịch sử trạng thái, subscription và điều khiển
- **BACnet / Modbus TCP / OPC UA** — đọc, ghi, duyệt và giám sát tự động hóa công nghiệp và tòa nhà
- **UPnP** — khám phá thiết bị, trạng thái WAN và quản lý ánh xạ cổng router

### Vị trí của uag

Một phía, uag nằm giữa con người và các giao diện; phía kia là các mô hình, công cụ và hệ thống thế giới thực.
Nó điều phối cuộc hội thoại, lựa chọn khả năng, áp dụng các quy tắc an toàn và giữ cho quy trình có thể tiếp tục.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Plugin, Agent Skills và marketplace

Biến uag thành một agent chuyên dụng mà không cần fork phần lõi:

- Cài đặt **plugin tương thích Claude Code** từ thư mục, ZIP, repository Git, nguồn HTTP hoặc marketplace
- Đóng gói skill, sub-agent, máy chủ MCP, hook, slash command, kiểu đầu ra, dependency và channel
- Duyệt các khả năng cộng đồng từ [SkillsMP](https://skillsmp.com) và [ClawHub](https://clawhub.ai)
- Thêm skill và công cụ riêng của tổ chức cục bộ thông qua `UAGENT_EXTERNAL_TOOLS_DIR`

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

Xem [Hướng dẫn phát triển Plugin](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **Hơn 200 công cụ** cho tệp, web, phương tiện, tài liệu, code, đám mây, giao tiếp và IoT
- **Khám phá và tải động** — dùng `tool_catalog` để tìm khả năng và `tool_load` để chỉ bật chúng khi cần
- **Tình báo code** — `code_map`, các trình điều hướng `idx` theo ngôn ngữ, rà soát Git, thực thi kiểm thử, lint, biên dịch và đo độ bao phủ
- **Plugin tương thích với Claude Code** cùng skills, agents, máy chủ MCP, hooks, commands và marketplace
- **Agent Skills** từ SkillsMP và ClawHub
- **Công cụ Python tùy chỉnh** với `TOOL_SPEC` và `run_tool()`
- **Công cụ chạy trên Rust** cho các phần mở rộng native nhẹ

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Được xây dựng cho quy trình làm việc thực tế

### 🧠 Kết quả của công cụ dựa trên ngữ cảnh

Khi có thể, các kết quả có dung lượng lớn của công cụ sẽ được loại trừ khỏi ngữ cảnh mô hình đang hoạt động. uag lưu trữ chúng dưới dạng Artifacts và thay vào đó, truyền cho mô hình một bản xem trước có giới hạn kèm theo tham chiếu Artifact ổn định. Điều này có thể giảm đáng kể số lượng token đầu vào cần thiết cho các lượt tiếp theo khi công cụ tạo ra kết quả có dung lượng lớn.

Tiếp tục các cuộc hội thoại trước bằng `:load <index>`. Kết quả công cụ có thể được lưu vào bộ nhớ đệm và provider có thể được thay đổi
mà không cần xây dựng lại ứng dụng.

[Context compression](CONTEXT_COMPRESSION.vi.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Auto-pilot

Dùng `:auto` cho công việc nhiều vòng với một mô hình reviewer tùy chọn. Đặt giới hạn vòng bằng `--max-rounds N`.
Nhấn **F12** để dừng auto-pilot hoặc **F12** để dừng phản hồi hiện tại.

Các thao tác độc lập, chỉ đọc sẽ chạy đồng thời khi an toàn. Tìm kiếm web, kiểm tra tệp,
phân tích repository và các tác vụ tương tự có thể hoàn tất song song với một pool worker có thể cấu hình
(`UAGENT_PARALLEL_WORKERS`). Các thao tác ghi vẫn được tuần tự hóa hoặc yêu cầu xác nhận.

Tính liên tục của phiên, bộ nhớ đệm kết quả công cụ, trạng thái theo lô, khôi phục sau khởi động lại, lập lịch DAG và
điều phối đa agent giúp các công việc phức tạp có thể tiếp tục thay vì chỉ chạy một lần.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Riêng tư, đa ngôn ngữ và nhận biết chính sách

`human_ask` tạm dừng trước các hành động nhạy cảm. Việc xóa tệp, ghi đè, lệnh shell, điều khiển thiết bị,
thao tác thông tin xác thực và ghi qua mạng có thể được quản lý bằng quy tắc xác nhận và chính sách.

Sử dụng kho thông tin xác thực thay vì đặt các bí mật có thời hạn dài trong prompt:

Giao diện Web bao gồm đăng nhập OIDC sử dụng Authorization Code + PKCE, token ID đã được xác minh, phiên phía máy chủ và kiểm soát truy cập dự án/phòng. Các yêu cầu nhóm Microsoft Entra ID đã được xác minh có thể cung cấp chính sách truy cập dựa trên thư mục khi được cấu hình. Các triển khai Windows Active Directory, OAuth và trusted-proxy có thể tích hợp thông qua bộ điều hợp nhận dạng đã được xác minh rõ ràng; Windows AD yêu cầu bộ xác minh Kerberos/Negotiate riêng cho triển khai và không được bật theo mặc định.

uag bao gồm chọn tham gia, theo dõi OpenTelemetry trung lập với nhà cung cấp và các số liệu cho Agent, LLM, công cụ, Context, Memory và các hoạt động truy xuất. Khả năng quan sát bị tắt theo mặc định.

Ưu tiên chạy cục bộ không có nghĩa là UAG hoàn toàn ngoại tuyến hoặc mọi công cụ đều được cách ly theo mặc định. Lời gọi tới mô hình và dịch vụ bên ngoài phụ thuộc vào cấu hình.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Bản dịch đa ngôn ngữ

- `translate_text` hỗ trợ Google Translate và ứng dụng khách Python chính thức của DeepL thông qua các tùy chọn `provider=auto`, `provider=deepl` hoặc `provider=google`.
- Các định nghĩa công cụ có sẵn trong 37 ngôn ngữ địa phương cùng với tiếng Anh (tổng cộng 38), trong đó các ký hiệu giữ chỗ và mã định danh kỹ thuật được giữ nguyên.

Thoại song công hoàn toàn khả dụng thông qua OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live
và Bedrock Nova Sonic, cùng tính năng khử tiếng vọng AEC3 tùy chọn và gọi hàm thời gian thực bị giới hạn bởi an toàn.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Tài liệu

| Chủ đề | Tài liệu |
|---|---|
| Biến môi trường | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Kiến trúc và bất biến | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Công cụ repository | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| Trường hợp sử dụng IoT | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Công cụ giao tiếp | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Auto-pilot | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| Extension VS Code | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Hướng dẫn nhà phát triển | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Luồng công cụ | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## Phát triển và đóng góp

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Chạy các kiểm tra trước khi tạo PR:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

Để xem toàn bộ quy trình phát triển, hãy xem [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md).

Hoan nghênh báo cáo lỗi, ý tưởng tính năng, cải thiện tài liệu, bản dịch, công cụ, skill và pull request.
Vui lòng mở issue hoặc discussion trước khi thực hiện thay đổi lớn. Đọc [Hướng dẫn nhà phát triển](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
và chạy các kiểm tra ở trên trước khi gửi pull request.

## Giấy phép

Được cấp phép theo [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
