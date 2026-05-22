<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (Tác nhân AI cục bộ)

`uag` là một tác nhân tương tác có thể thực thi **lệnh**, thao tác **tệp tin**, và đọc **nhiều định dạng dữ liệu** như PDF/PPTX/Excel trên máy tính cục bộ của bạn. Ứng dụng cung cấp ba giao diện: CLI, GUI và Web.

uag được tạo ra để **giúp bạn thoát khỏi các ứng dụng bị khóa bởi nhà cung cấp**: hãy dùng giao diện phù hợp với quy trình làm việc của bạn, đổi nhà cung cấp và giữ quyền kiểm soát môi trường của bạn.

GitHub: https://github.com/awaku7/agentcli

## Cài đặt

Bạn có thể cài đặt `uag` bằng pip:

```bash
pip install uag
```

Sau khi cài đặt, khi chạy `uag` lần đầu tiên, trình hướng dẫn thiết lập tương tác sẽ tự động mở để cấu hình các biến môi trường của bạn. Để biết chi tiết về cấu hình và mã hóa, xem **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**.

## Tính năng chính

- **Bộ công cụ thực tiễn**: Cung cấp các công cụ để thao tác tệp tin, tìm kiếm web, trích xuất dữ liệu (PDF/PPTX/Excel), tạo ảnh và phân tích, tất cả đều có thể chạy trong môi trường cục bộ của bạn.
- **Hỗ trợ nhiều nhà cung cấp**: Hỗ trợ OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA.
- **Giao diện linh hoạt**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **A2A (Server)**: `uaga` / `python -m uagent.a2a.server`
- **MCP (Model Context Protocol)**: Hỗ trợ kết nối tới các máy chủ công cụ MCP bên ngoài.
- **Duy trì phiên làm việc**: Giữ nguyên ngữ cảnh hội thoại ngay cả khi chuyển đổi nhà cung cấp hoặc mô hình.
- **Web Inspector**: Tự động lưu lại các lần chuyển trang, DOM và ảnh chụp màn hình của trình duyệt bằng `playwright_inspector`.
- **Tài liệu tích hợp**: Truy cập ngay tài liệu nội bộ chi tiết bằng lệnh `uag docs`.

## Cách sử dụng

### Khởi động và thoát

Chạy `uag` từ terminal để bắt đầu. Gõ `:exit` để thoát.

### Máy chủ A2A (Agent2Agent)

Khởi chạy máy chủ HTTP tương thích với A2A:

```bash
uaga
```

### Ghi chú về Responses API

Nếu bạn đặt `UAGENT_RESPONSES=1`, Responses API sẽ được dùng cho các nhà cung cấp được hỗ trợ: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI sử dụng các đường dẫn API gốc của họ và không nằm trong phạm vi của Responses API.
Với các nhà cung cấp khác, uag sẽ quay về đường dẫn riêng của nhà cung cấp hoặc luồng chat-completions.

Xem [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) để biết các thiết lập `UAGENT_A2A_*` như xác thực, host, cổng, tải lại, URL gốc công khai, đồng thời và engine.

### Mẹo hữu ích (Duy trì và kiểm soát)

- `:tools`: Hiển thị danh sách công cụ đã tải.
- `:logs [n]`: Hiển thị nhật ký phiên (`n` là số lượng mục cần xem).
- `:load <index>`: Tải một phiên trước đó để tiếp tục hội thoại.
- `:skills`: Chọn và tải Agent Skills (vai trò hoặc chỉ dẫn bổ sung).
- `:shrink [n]`: Thu gọn lịch sử để chỉ giữ `n` tin nhắn gần nhất nhằm tiết kiệm token.

## Cấu hình và chi tiết

### Biến môi trường và thiết lập

Để xem các thiết lập chi tiết (khóa API, ngôn ngữ hiển thị `UAGENT_LANG`, cài đặt thu gọn lịch sử, v.v.), hãy xem **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**.

- **Thiết lập**: Cấu hình tương tác thông qua `python -m uagent.setup_cli`.
- **Mã hóa**: Mã hóa an toàn tệp `.env` của bạn bằng công cụ `uag_envsec`.
- **Cập nhật**: Dùng `uag_envsec add --file .env.sec --key NAME --value VALUE` để thêm hoặc cập nhật biến trong tệp đã mã hóa.

### Tài liệu dành cho nhà phát triển và quốc tế hóa

- **Tài liệu nhà phát triển**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Thêm locale**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **README các ngôn ngữ khác**: [English](https://github.com/awaku7/agentcli/blob/main/README.md) / [日本語](https://github.com/awaku7/agentcli/blob/main/docs/README.ja.md) / [Deutsch](https://github.com/awaku7/agentcli/blob/main/docs/README.de.md) / [Español](https://github.com/awaku7/agentcli/blob/main/docs/README.es.md) / [Français](https://github.com/awaku7/agentcli/blob/main/docs/README.fr.md) / [Italiano](https://github.com/awaku7/agentcli/blob/main/docs/README.it.md) / [한국어](https://github.com/awaku7/agentcli/blob/main/docs/README.ko.md) / [Português](https://github.com/awaku7/agentcli/blob/main/docs/README.pt_BR.md) / [Русский](https://github.com/awaku7/agentcli/blob/main/docs/README.ru.md) / [ไทย](https://github.com/awaku7/agentcli/blob/main/docs/README.th.md) / [简体中文](https://github.com/awaku7/agentcli/blob/main/docs/README.zh_CN.md) / [繁體中文](https://github.com/awaku7/agentcli/blob/main/docs/README.zh_TW.md) / [Polski](https://github.com/awaku7/agentcli/blob/main/docs/README.pl.md) / [Tiếng Việt](https://github.com/awaku7/agentcli/blob/main/docs/README.vi.md) / [Bahasa Indonesia](https://github.com/awaku7/agentcli/blob/main/docs/README.id.md) / [العربية](https://github.com/awaku7/agentcli/blob/main/docs/README.ar.md) / [हिन्दी](https://github.com/awaku7/agentcli/blob/main/docs/README.hi.md) / [Português](https://github.com/awaku7/agentcli/blob/main/docs/README.pt.md) / [Svenska](https://github.com/awaku7/agentcli/blob/main/docs/README.sv.md) / [Norsk bokmål](https://github.com/awaku7/agentcli/blob/main/docs/README.nb.md) / [Suomi](https://github.com/awaku7/agentcli/blob/main/docs/README.fi.md) / [Nederlands](https://github.com/awaku7/agentcli/blob/main/docs/README.nl.md) / [Čeština](https://github.com/awaku7/agentcli/blob/main/docs/README.cs.md) / [Українська](https://github.com/awaku7/agentcli/blob/main/docs/README.uk.md) / [Swahili](https://github.com/awaku7/agentcli/blob/main/docs/README.sw.md) / [Bengali](https://github.com/awaku7/agentcli/blob/main/docs/README.bn.md) / [Persian](https://github.com/awaku7/agentcli/blob/main/docs/README.fa.md) / [Mongolian](https://github.com/awaku7/agentcli/blob/main/docs/README.mn.md) / [Marathi](https://github.com/awaku7/agentcli/blob/main/docs/README.mr.md)
