```
██╗   ██╗ █████╗  ██████╗ ███████╗███╗   ██╗████████╗ ██████╗██╗     ██╗
██║   ██║██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██╔════╝██║     ██║
██║   ██║███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ██║     ██║     ██║
██║   ██║██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ██║     ██║     ██║
╚██████╔╝██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ╚██████╗███████╗██║
 ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝╚══════╝╚═╝
```

# uag (Tác nhân AI cục bộ)

`uag` là một tác nhân tương tác có thể thực thi **lệnh**, thao tác **tệp tin**, và đọc **nhiều định dạng dữ liệu** như PDF/PPTX/Excel trên máy tính cục bộ của bạn. Ứng dụng cung cấp ba giao diện: CLI, GUI và Web.


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

### Tài liệu dành cho nhà phát triển và quốc tế hóa
- **Tài liệu nhà phát triển**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Thêm locale**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **README các ngôn ngữ khác**: [English](https://github.com/awaku7/agentcli/blob/main/README.md) / [日本語](https://github.com/awaku7/agentcli/blob/main/README.ja.md) / [Deutsch](https://github.com/awaku7/agentcli/blob/main/README.de.md) / [Español](https://github.com/awaku7/agentcli/blob/main/README.es.md) / [Français](https://github.com/awaku7/agentcli/blob/main/README.fr.md) / [Italiano](https://github.com/awaku7/agentcli/blob/main/README.it.md) / [한국어](https://github.com/awaku7/agentcli/blob/main/README.ko.md) / [Português](https://github.com/awaku7/agentcli/blob/main/README.pt_BR.md) / [Русский](https://github.com/awaku7/agentcli/blob/main/README.ru.md) / [ไทย](https://github.com/awaku7/agentcli/blob/main/README.th.md) / [简体中文](https://github.com/awaku7/agentcli/blob/main/README.zh_CN.md) / [繁體中文](https://github.com/awaku7/agentcli/blob/main/README.zh_TW.md) / [Polski](https://github.com/awaku7/agentcli/blob/main/README.pl.md) / [Tiếng Việt](https://github.com/awaku7/agentcli/blob/main/README.vi.md) / [Bahasa Indonesia](https://github.com/awaku7/agentcli/blob/main/README.id.md)
