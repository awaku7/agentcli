# CÁCH SỬ DỤNG (Tùy chọn dòng lệnh)

Tài liệu này mô tả các tùy chọn dòng lệnh có sẵn cho các điểm vào uag.

______________________________________________________________________

## Điểm vào

| Lệnh | Mô-đun Python | Giao diện |
|---|---|---|
| `uag` | `python -m uagent` | CLI (vòng lặp stdin) |
| `uagg` | `python -m uagent.gui` | Giao diện đồ họa (tkinter) |
| `uagw` | `python -m uagent.web` | Máy chủ web (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | Máy chủ A2A HTTP |

______________________________________________________________________

## Tùy chọn khởi động CLI (`uag`)

### `--workdir` / `-C <path>`

Thư mục làm việc. Nếu không được đặt, sẽ sử dụng biến môi trường `UAGENT_WORKDIR`, sau đó là thư mục hiện tại.
Thư mục sẽ được tạo nếu nó không tồn tại.

### `--tool-genre-mask <int>`

Mặt nạ bit thể loại công cụ. Khi được cung cấp, lời nhắc chọn thể loại tương tác sẽ bị bỏ qua.

| Bit | Thể loại | Mô tả |
|-----|-------|-------------|
| 1 | basic | Công cụ tệp/trò chuyện cơ bản |
| 2 | comm | Công cụ giao tiếp (Bluesky, Teams) |
| 4 | office | Công cụ bộ ứng dụng văn phòng (Excel, PDF, PPTX) |
| 8 | devel | Công cụ phát triển (git, lint, compile) |
| 16 | iot | Công cụ thiết bị IoT (SwitchBot, ECHONET, Matter, UPnP) |
| 32 | exec | Công cụ thực thi lệnh |
| 64 | external | Công cụ plugin bên ngoài |
| 128 | media | Tạo và phân tích hình ảnh/âm thanh |
| 256 | file | Công cụ quản lý tệp |
| 512 | index | Công cụ điều hướng nguồn/chỉ mục |
| 1024 | dev | Công cụ dành cho nhà phát triển và kho lưu trữ |
| 2048 | web | Công cụ web và trình duyệt |
| 4096 | tiện ích | Công cụ tiện ích và hỗ trợ |
| 8191 | tất cả | Tất cả các công cụ |

Ví dụ:

```
uag --tool-genre-mask 1 # chỉ cơ bản
uag --tool-genre-mask 9 # cơ bản + phát triển (1 + 8)
uag --tool-genre-mask 8191    # tất cả các công cụ
```

### `--use-tool` / `--no-use-tool`

Bật hoặc tắt việc gửi định nghĩa công cụ đến LLM. Ghi đè biến môi trường `UAGENT_USE_TOOL`.

- `--use-tool` buộc bật việc gửi định nghĩa công cụ.
- `--no-use-tool` buộc tắt việc gửi định nghĩa công cụ.

Khi bị tắt, LLM sẽ không nhận được định nghĩa công cụ nào và không thể gọi bất kỳ công cụ nào.

### `--computer-use` / `--no-computer-use`

Bật hoặc tắt tính năng Sử dụng máy tính. Ghi đè biến môi trường `UAGENT_COMPUTER_USE`.

### `--inject-message` / `-M <message>`

Chèn một thông báo vào LLM khi khởi động và thoát sau khi hoàn tất. Điều này ngụ ý tùy chọn `--non-interactive`.

### `--embedded`

Chế độ nhúng dành cho các triển khai có giới hạn hoặc nhạy cảm với tính tái tạo.

- Vô hiệu hóa bộ lưu trữ phiên.
- Ẩn các công cụ quản lý công cụ (`tool_catalog`, `tool_load`, `unload_tool`) trừ khi được bật rõ ràng.
- Bỏ qua `--tool-genre-mask`; sử dụng `--enable-tool` để tải công cụ một cách rõ ràng.

### `--enable-tool <name>`

Tải công cụ một cách rõ ràng khi khởi động. Tùy chọn này có thể được lặp lại, và các tên được phân tách bằng dấu phẩy cũng được chấp nhận.

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

Thứ tự được chỉ định sẽ được giữ nguyên và phản ánh trong thứ tự công cụ được hiển thị cho LLM. Các công cụ được bật rõ ràng sẽ không bị gỡ bỏ tự động.

### `--plugin-dir <path>`

Tải các plugin từ thư mục được chỉ định. Tùy chọn này có thể được lặp lại.

______________________________________________________________________

## Các tùy chọn chỉ dành cho CLI

### `--inject-message-auto <goal-options>`

Khởi động chế độ tự động từ một mục tiêu được chèn không tương tác. Giá trị sử dụng các tùy chọn giống như `:auto`; hãy đặt giá trị hoàn chỉnh trong dấu ngoặc kép khi nó chứa các tùy chọn.

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sắp xếp các mục --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sắp xếp các mục --infinite"
```

Chế độ bình thường sử dụng lộ trình đánh giá của người đánh giá. Đặt `UAGENT_AUTO_SENTINEL=1` để chọn chế độ sentinel đơn LLM. Trong chế độ đó, mục tiêu LLM phải kết thúc mỗi phản hồi bằng chính xác một trong các dấu hiệu sau:

- `<AUTO_CONTINUE>` — chạy một vòng khác
- `<AUTO_COMPLETE>` — hoàn thành thành công

Các dấu hiệu thiếu hoặc không hợp lệ sẽ dừng chế độ tự động một cách an toàn. Điều này vẫn thực thi mục tiêu `LLM`; nó chỉ tránh việc gọi thêm `LLM` của người đánh giá.

### `--non-interactive`

Chế độ không tương tác. Không khởi động vòng lặp stdin. Nếu đường dẫn tệp được cung cấp dưới dạng đối số vị trí, nó sẽ được xử lý và chương trình sẽ thoát ngay lập tức.

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Tùy chọn máy chủ web (`uagw`)

### `--host <address>`

Địa chỉ gán cho máy chủ web (mặc định: `127.0.0.1`, có thể ghi đè bằng `UAGENT_WEB_HOST`).

Theo mặc định, máy chủ web chỉ lắng nghe trên localhost (`127.0.0.1`). Để cho phép truy cập từ các máy khác trong mạng, hãy sử dụng `--host 0.0.0.0`.

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <int>`

Chọn các thể loại công cụ bằng cách sử dụng bitmask tương tự như đã mô tả ở trên. Khi được chỉ định, lời nhắc thể loại tương tác sẽ bị bỏ qua.

### `--use-tool` / `--no-use-tool`

Bật hoặc tắt việc gửi định nghĩa công cụ đến LLM. Ghi đè `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Bật hoặc tắt Chế độ sử dụng máy tính. Ghi đè `UAGENT_COMPUTER_USE`.

### `--no-frontend`

Chỉ chạy API mà không có các mẫu HTML hoặc tệp frontend tĩnh.

### `--embedded`

Vô hiệu hóa bộ lưu trữ phiên và ẩn các công cụ quản lý công cụ (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Tùy chọn máy chủ A2A (`uaga`)

### `--host <address>`

Địa chỉ kết nối cho máy chủ A2A HTTP (mặc định: `0.0.0.0`, có thể ghi đè bằng `UAGENT_A2A_HOST`).

### `--port <số>`

Số cổng cho máy chủ A2A HTTP (mặc định: `8765`, có thể thay đổi bằng biến môi trường `UAGENT_A2A_PORT`).

### `--reload`

Bật tính năng tải lại nóng khi có thay đổi mã (mặc định: tắt, có thể thay đổi bằng biến môi trường `UAGENT_A2A_RELOAD`).

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <int>`

Chọn các thể loại công cụ bằng cách sử dụng mặt nạ bit được mô tả ở trên. Khi được chỉ định, lời nhắc tương tác về thể loại sẽ bị bỏ qua.

### `--use-tool` / `--no-use-tool`

Bật hoặc tắt việc gửi định nghĩa công cụ đến LLM. Ghi đè `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Bật hoặc tắt tính năng Sử dụng Máy tính. Ghi đè lên `UAGENT_COMPUTER_USE`.

### `--embedded`

Vô hiệu hóa bộ lưu trữ phiên và ẩn các công cụ quản lý công cụ (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Các biến môi trường liên quan

| Biến | Mô tả |
|---|---|
| `UAGENT_PROVIDER` | Tên nhà cung cấp LLM (bắt buộc khi khởi động) |
| `UAGENT_*_API_KEY` | Khóa API cho nhà cung cấp đã chọn |
| `UAGENT_WORKDIR` | Thư mục làm việc mặc định |
| `UAGENT_WEB_HOST` | Địa chỉ liên kết máy chủ web (mặc định: `127.0.0.1`) |
| `UAGENT_A2A_HOST` | A2A địa chỉ liên kết máy chủ (mặc định: `0.0.0.0`) |
| `UAGENT_A2A_PORT` | Cổng máy chủ A2A (mặc định: `8765`) |
| `UAGENT_A2A_RELOAD` | Bật tính năng tải lại nóng A2A theo mặc định |
| `UAGENT_USE_TOOL` | Tắt các công cụ khi được đặt thành `0`, `false`, `no` hoặc `off` |
| `UAGENT_COMPUTER_USE` | Bật hoặc tắt Tính năng sử dụng máy tính theo mặc định |
| `UAGENT_SESSION_STORE` | Bật hoặc tắt bộ lưu trữ phiên; Chế độ nhúng bắt buộc phải là `0` |
| `UAGENT_PLUGIN_DIRS` | Các thư mục tìm kiếm plugin bổ sung |
| `UAGENT_AUTO_SENTINEL` | Chọn tham gia chế độ sentinel tự động điều khiển duy nhất khi đặt thành `1` |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | Số lần gọi công cụ mới liên tiếp tối đa (mặc định: `100`) |
| `UAGENT_MAX_TOOL_ROUNDS` | Số vòng LLM/công cụ tối đa cho mỗi thao tác của người dùng (mặc định: `200`) |
| `UAGENT_SHRINK_CNT` | Ngưỡng thu gọn tự động tùy chọn trong tin nhắn (`0`/chưa thiết lập = tắt) |
| `UAGENT_SHRINK_KEEP_LAST` | Số tin nhắn cần giữ lại sau khi thu gọn (mặc định: `20`) |
| `UAGENT_LANG` | Ngôn ngữ giao diện (`ja`, `en`, v.v.) |

Để xem danh sách đầy đủ các biến môi trường, hãy tham khảo [ENVIRONMENT.md](ENVIRONMENT.md).

______________________________________________________________________

## Ví dụ

### Cài đặt tối thiểu với OpenAI

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### Cài đặt cục bộ Ollama chỉ với các công cụ cơ bản

```
set UAGENT_PROVIDER=ollama
set UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### Máy chủ web trên tất cả các giao diện

```
set UAGENT_WEB_HOST=0.0.0.0
uagw
```

hoặc

```
uagw --host 0.0.0.0
```

### Máy chủ A2A trên localhost với cổng tùy chỉnh

```
uaga --host 127.0.0.1 --port 8080
```

### Tắt các công cụ cho mô hình nhỏ

```
uag --no-use-tool --tool-genre-mask 1
```

### Xử lý tệp không tương tác

```
uag --non-interactive README.md
```
