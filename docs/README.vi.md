<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Mô hình AI của bạn. Công cụ của bạn. Môi trường của bạn.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Ngôn ngữ khác</a></p>

---

**UAG là môi trường chạy tác nhân AI mã nguồn mở, ưu tiên hoạt động cục bộ.** UAG kết nối mô hình ngôn ngữ do bạn chọn với những công cụ và hệ thống bạn sử dụng. Bạn có thể làm việc với mã nguồn, tệp, trình duyệt, dịch vụ và thiết bị thông qua một giao diện nhất quán mà không bị ràng buộc vào một nhà cung cấp mô hình.

| **Chọn mô hình** | **Kết nối công cụ thực tế** | **Giữ quyền kiểm soát** |
| :--- | :--- | :--- |
| Mô hình đám mây và cục bộ như OpenAI, Claude, Gemini, Grok, Bedrock và Ollama | Tệp, mã nguồn, web, MCP, Agent Skills, plugin, dịch vụ đám mây và IoT | Thực thi cục bộ, xác nhận của con người, lưu thông tin xác thực và chính sách có thể cấu hình |

> UAG là **lớp thực thi tác nhân, không phải nhà cung cấp mô hình**. Việc gọi mô hình và dịch vụ bên ngoài phụ thuộc vào cấu hình. Ưu tiên cục bộ không có nghĩa là hoàn toàn ngoại tuyến hoặc mọi công cụ đều được cách ly theo mặc định.

## Bắt đầu nhanh
<!-- README-SYNC:quick-start -->

Cần **Python 3.11 trở lên**. Cài UAG từ [PyPI](https://pypi.org/project/uag/) và khởi động CLI tương tác:

~~~bash
python -m pip install --upgrade uag
uag
~~~

Ở lần khởi động đầu tiên, trình hướng dẫn giúp chọn nhà cung cấp mô hình và cấu hình thông tin xác thực. Bạn cũng có thể dùng biến môi trường hoặc kho thông tin xác thực. Để cài đặt trước nhiều phụ thuộc của mô hình và công cụ:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Sau đó hãy thử các yêu cầu sau:

~~~text
> Kho Git này đã thay đổi những gì? Hãy tóm tắt rủi ro.
> Tìm tài liệu mới nhất của thư viện này và giải thích các bước chuyển đổi.
> Kiểm tra các tệp này và tạo báo cáo ngắn gọn.
> :help
~~~

Người mới có thể tham khảo hướng dẫn cài đặt Windows, bao gồm Git và môi trường ảo, cùng tài liệu cấu hình: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Giao diện
<!-- README-SYNC:interfaces -->

Mọi giao diện đều dùng chung môi trường chạy tác nhân và danh mục công cụ.

| Giao diện | Khởi động | Phù hợp với |
| :--- | :--- | :--- |
| **CLI** | `uag` | Công việc dòng lệnh và tự động hóa |
| **Desktop** | `uagg` | Hội thoại trong ứng dụng máy tính |
| **Web** | `uagw` | Hội thoại và phòng trong trình duyệt |
| **A2A** | `uaga` | Kết nối giữa các tác nhân |
| **VS Code** | [Hướng dẫn tiện ích](VSCODE.md) | Làm việc cùng mã nguồn |

Desktop và Web cần phụ thuộc bổ sung, không có trong bộ cài ban đầu `uag[core,providers,tools]`:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Máy chủ Web cũng có thể thử cài FastAPI và Uvicorn lúc khởi động. Cài trước giúp tránh phụ thuộc vào việc cài tự động. Chi tiết: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## Bạn có thể làm gì với UAG
<!-- README-SYNC:capabilities -->

| Khả năng | UAG cung cấp |
| :--- | :--- |
| **Quy trình không phụ thuộc mô hình** | Đổi nhà cung cấp đám mây hoặc cục bộ bằng `UAGENT_PROVIDER` mà không viết lại công cụ |
| **Mã nguồn và tệp** | Duyệt kho mã, kiểm tra Git, lint, chạy thử nghiệm, thao tác tệp và tự động hóa trình duyệt |
| **Công cụ mở rộng** | Hơn 200 công cụ, khám phá động với `tool_catalog` / `tool_load`, công cụ Python và Rust tùy chỉnh |
| **Tác nhân kết nối** | MCP, A2A, plugin tương thích Claude Code, Agent Skills và tác nhân con |
| **Tác vụ kéo dài** | Tự động chạy, đọc độc lập song song, lịch tác vụ, khôi phục và phiên lưu bền vững |
| **Ngoài dòng lệnh** | Đám mây, giao tiếp, tài liệu, đa phương tiện, giọng nói thời gian thực và giao thức IoT được hỗ trợ |

### Một môi trường chạy, nhiều tích hợp
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

**Ví dụ các nhà cung cấp mô hình được hỗ trợ** ở bên dưới; xem tài liệu môi trường để biết cài đặt riêng.

### Tùy chỉnh bằng kỹ năng và plugin
<!-- README-SYNC:extensions -->

Mở rộng UAG mà không thay đổi lõi. Cài Agent Skills từ SkillsMP hoặc ClawHub, kết nối máy chủ MCP, hoặc tải plugin tương thích Claude Code chứa công cụ, kỹ năng, tác nhân và hook.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Công cụ tùy chỉnh có thể cung cấp `TOOL_SPEC` và `run_tool()`; cũng hỗ trợ công cụ xây dựng bằng Rust. Tham khảo hướng dẫn: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## Dành cho quy trình làm việc thực tế
<!-- README-SYNC:workflows -->

### Ngữ cảnh và bộ nhớ
<!-- README-SYNC:context-memory -->

Kết quả công cụ quá lớn có thể lưu dưới dạng **Artifacts** thay vì chiếm ngữ cảnh hoạt động của mô hình. Tác nhân truy xuất phần cần thiết về sau bằng `artifact_read`. Phiên mặc định được lưu trong SQLite, có tìm kiếm lịch sử và quy trình xem xét bộ nhớ rõ ràng.

- [Context compression](CONTEXT_COMPRESSION.vi.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Tự động hóa và cộng tác
<!-- README-SYNC:automation -->

UAG hỗ trợ thao tác đọc độc lập song song, phối hợp nhiều tác nhân, khôi phục phiên và chế độ tự động cho công việc nhiều lượt. Bắt đầu bằng `:auto`; nhấn **F12** để ngắt phản hồi hiện tại và yêu cầu dừng chế độ tự động.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Bảo mật và khả năng quan sát
<!-- README-SYNC:security -->

Hành động nhạy cảm có thể yêu cầu xác nhận qua `human_ask`. Thông tin xác thực có thể lưu trong trình quản lý hệ điều hành hoặc tệp mã hóa. Giao diện Web hỗ trợ đăng nhập OIDC và kiểm soát truy cập khi được cấu hình. Theo dõi và số liệu OpenTelemetry là **tùy chọn**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Những biện pháp này có thể cấu hình nhưng **không bảo đảm** mọi công cụ đều chạy trong sandbox cách ly. Hãy đọc hướng dẫn triển khai và chính sách trước khi mở UAG cho người dùng hay mạng không đáng tin cậy.

### Ngôn ngữ, thiết bị và giọng nói
<!-- README-SYNC:languages -->

UAG có tài nguyên cho **38 khu vực ngôn ngữ** (tiếng Anh và 37 bản dịch), tích hợp giọng nói hai chiều tùy chọn và công cụ cho SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP và OPC UA.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Tài liệu
<!-- README-SYNC:documentation -->

Bắt đầu từ các tài liệu sau rồi tìm hiểu sâu hơn:

| Bắt đầu tại đây | Tìm hiểu sâu |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

Bạn cũng có thể duyệt toàn bộ tài liệu và các bản dịch: [Documentation](./) · [Other languages](README.translations.md).

## Phát triển và đóng góp
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

Trước khi gửi pull request có thay đổi **mã Python**, hãy chạy các bài kiểm thử và kiểm tra dự án liên quan:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Quy tắc đóng góp và hướng dẫn nhà phát triển ở bên dưới. Chúng tôi hoan nghênh báo lỗi, cải thiện tài liệu, công cụ, bản dịch và pull request có phạm vi rõ ràng: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Giấy phép
<!-- README-SYNC:license -->

UAG được phân phối theo giấy phép: [Apache License 2.0](../LICENSE).
