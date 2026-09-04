# Nén bối cảnh và bối cảnh mô hình có giới hạn

uag sử dụng nhiều lớp để giữ cho bối cảnh mô hình đang hoạt động nằm trong giới hạn. Mục tiêu là giảm các token đầu vào không cần thiết mà không loại bỏ các tệp, kết quả công cụ hoặc dữ liệu phiên mà người dùng có thể vẫn cần.

Tài liệu này mô tả cách triển khai hiện tại. Nó cũng phân biệt hành vi xác định với hành vi cụ thể của nhà cung cấp hoặc hành vi được hỗ trợ bởi LLM.

## 1. Bề mặt công cụ động

Không phải mọi định nghĩa công cụ đều cần được gửi đến mô hình ở mỗi lượt.

- `tool_catalog` tìm kiếm các khả năng có sẵn.
- `tool_load` chỉ kích hoạt các công cụ cần thiết cho tác vụ hiện tại.
- `tool_catalog`, `tool_load` và `unload_tool` vẫn có sẵn dưới dạng các công cụ quản lý.
- Các luồng Responses API tương thích với GPT-5.4 có thể sử dụng Tool Search gốc phía máy chủ.
- Chế độ Tool Search cũ thu hẹp các thông số kỹ thuật của công cụ bằng `tool_catalog` ở phía máy khách.

Điều này giúp giảm số lượng token đầu vào được sử dụng bởi các lược đồ công cụ, đặc biệt là trong các cài đặt có nhiều công cụ.

## 2. Kết quả văn bản dài của công cụ sẽ trở thành Artifacts

Khi kết quả văn bản của công cụ vượt quá ngưỡng Artifact, uag sẽ lưu trữ kết quả đầy đủ dưới dạng Artifact và gửi cho mô hình một tham chiếu có giới hạn cùng bản xem trước thay vì toàn bộ văn bản.

Các giới hạn mặc định là:

```text
UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS=100000
UAGENT_TOOL_RESULT_MAX_CHARS=12000
```

Biểu diễn hiển thị cho mô hình bao gồm tên công cụ, độ dài ban đầu, tham chiếu `artifact://`, đường dẫn lưu trữ và bản xem trước có giới hạn. Kết quả đầy đủ vẫn có sẵn thông qua kho lưu trữ Artifact.

Giá trị ngưỡng có thể được thay đổi bằng `UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS`. Giá trị `0` vô hiệu hóa tính năng nâng cấp Artifact. `UAGENT_TOOL_RESULT_MAX_CHARS` kiểm soát chính sách kết quả giới hạn thông thường; `0` vô hiệu hóa giới hạn thông thường đó.

## 3. Truy xuất Artifact có giới hạn

Công cụ cơ sở hạ tầng `artifact_read` chỉ truy xuất phần được yêu cầu của một Artifact:

- `start_line` chọn dòng đầu tiên.
- `max_lines` bị giới hạn ở 500.
- `max_chars` bị giới hạn ở 50.000 ký tự.
- Có thể sử dụng cả ID Artifact và URI `artifact://`.

Điều này cho phép kiểm tra một phạm vi nhỏ có liên quan thay vì đưa lại toàn bộ tệp hoặc kết quả lệnh vào lượt chạy mô hình tiếp theo.

Các đối tượng mới được lưu trữ dưới đây:

```text
~/.uag/artifacts/
```

Các đường dẫn Artifact cũ vẫn có thể đọc được để đảm bảo tương thích.

## 4. Cách ly dữ liệu nhị phân

Dữ liệu nhị phân nội tuyến không được gửi dưới dạng kết quả công cụ dạng văn bản đến lượt mô hình tiếp theo. Các trường có dạng Base64 được thay thế bằng một dấu hiệu ngắn như:

```text
[dữ liệu nhị phân bị bỏ qua khỏi bối cảnh LLM]
```

Giao diện người dùng và các máy khách từ xa vẫn có thể nhận các tệp đính kèm trong bộ nhớ, và các tệp đã lưu vẫn có sẵn thông qua đường dẫn hoặc tham chiếu Artifact của chúng. Điều này ngăn chặn hình ảnh, âm thanh, ảnh chụp màn hình và các tải trọng nhị phân khác làm phình to bối cảnh mô hình văn bản.

Cùng loại tải trọng nhị phân này sẽ được làm sạch trước khi lưu trữ vào SQLite và JSONL, ngăn không cho nó xuất hiện trở lại dưới dạng tải trọng lớn sau khi tải lại phiên làm việc.

## 5. Nén lịch sử tự động

uag có thể nén lịch sử cuộc trò chuyện cũ hơn khi số lượng tin nhắn hoặc số token ước tính đạt đến giới hạn đã cấu hình.

Chính sách nén sử dụng:

- số lượng tin nhắn không phải hệ thống;
- cửa sổ bối cảnh đã giải quyết của mô hình (nếu có);
- `UAGENT_SHRINK_KEEP_LAST` (mặc định là 20);
- `UAGENT_SHRINK_MAX_TOKENS` hoặc giá trị ghi đè cụ thể cho mô hình;
- `UAGENT_SHRINK_CNT`; và
- `UAGENT_SHRINK_RATIO` (mặc định là 0,5 khi có cửa sổ bối cảnh đã biết).

Giới hạn cụ thể cho từng mô hình có thể được cung cấp như sau:

```text
UAGENT_SHRINK_MAX_TOKENS_<MODEL_NAME>
```

Tóm tắt trước đó sẽ không được tạo lại ở mỗi lượt. Hiệu ứng trễ (hysteresis) yêu cầu phải tích lũy đủ lịch sử mới, hoặc xảy ra tràn ngân sách token khác, trước khi quá trình nén được thực hiện lại.

## 6. Tóm tắt lịch sử có sự hỗ trợ của LLM

Khi tính năng nén tự động sử dụng LLM, các tin nhắn cũ của người dùng, trợ lý và công cụ sẽ được tóm tắt thành một tin nhắn hệ thống liên tục, trong khi phần cuối gần đây nhất vẫn được giữ lại.

Lịch sử dài có thể được tóm tắt theo từng đoạn. Các tham số điều khiển liên quan là:

```text
UAGENT_SHRINK_CHUNK_SIZE=100
UAGENT_SHRINK_SINGLE_SHOT=1
```

Tóm tắt được gấp lại về phía trước thay vì tạo ra một chuỗi tin nhắn tóm tắt không giới hạn. Đây là thao tác được hỗ trợ bởi LLM và có thể yêu cầu các yêu cầu bổ sung từ nhà cung cấp.

## 7. Nén dự phòng xác định

Nếu bản tóm tắt LLM không khả dụng, uag có thể giữ lại các thông báo hệ thống ở đầu và chỉ các thông báo gần đây nhất. Các ranh giới cuộc gọi công cụ được sửa chữa để lịch sử kết quả không bắt đầu hoặc kết thúc bằng một cuộc gọi công cụ bị cô lập.

Trình nạp và trình làm sạch cũng loại bỏ các mục không liên quan đến mô hình hoặc không hợp lệ, bao gồm các tin nhắn chỉ dành cho giao diện người dùng, tin nhắn điều khiển nội bộ, các dòng nhật ký bị hỏng, các vai trò không được hỗ trợ, kết quả công cụ bị cô lập và các khối cuộc gọi công cụ không đầy đủ.

Khi một phiên làm việc được tải lại, lời nhắc hệ thống hiện tại sẽ được khôi phục và chỉ các thông báo hệ thống được chèn có liên quan, chẳng hạn như bối cảnh kỹ năng hoặc hook, mới được giữ lại.

## 8. Khôi phục khi bão hòa bối cảnh

Nếu nhà cung cấp báo cáo rằng cửa sổ bối cảnh đã bị vượt quá, uag sẽ xác định một thông điệp lịch sử gần đây có kích thước lớn và hoàn tác thông điệp đó cùng với lịch sử tiếp theo trước khi thử lại. Đây là cơ chế dự phòng phản ứng, không phải là sự thay thế cho việc quản lý ngân sách thông thường.

## 9. Tiếp tục và nén phía nhà cung cấp

Ở những nơi được hỗ trợ, Responses API sử dụng `previous_response_id` để tiếp tục chuỗi phản hồi mà không cần gửi lại toàn bộ lịch sử phản hồi do nhà cung cấp quản lý từ phía khách hàng.

Các luồng Responses API cũng gửi cấu hình nén phía nhà cung cấp bằng cách sử dụng cùng một ngưỡng thu nhỏ cục bộ. Hành vi chính xác phụ thuộc vào nhà cung cấp; các chính sách Artifact và lịch sử cục bộ vẫn là các biện pháp bảo vệ trung lập đối với nhà cung cấp.

## 10. Hiệu quả đếm token

Số lượng token được sử dụng để ra quyết định nén được lưu trong bộ nhớ đệm và cập nhật theo từng phần khi chỉ có tin nhắn mới được thêm vào. Điều này không trực tiếp giảm bối cảnh mô hình, nhưng giúp giảm chi phí CPU và độ trễ khi quyết định thời điểm cần nén.

## Những gì chưa phải là một lớp thống nhất hoàn chỉnh

Việc triển khai hiện tại vẫn chưa cung cấp tất cả các yếu tố sau đây dưới dạng một trình quản lý trung lập với nhà cung cấp:

- `ContextManager` và `ContextBudget` thống nhất;
- `ToolResultRecord` với siêu dữ liệu về mức độ quan trọng và loại bỏ;
- các bản tóm tắt ngữ nghĩa không yêu cầu `LLM`;
- việc tự động truy xuất và tái chèn các Artifacts có liên quan;
- một Trình quản lý Kết quả trung tâm đảm bảo chuyển đổi `Artifact` cho mọi công cụ tạo mã nhị phân; hoặc
- việc loại bỏ dựa trên mức độ ưu tiên trên tất cả các danh mục hệ thống, lịch sử, lược đồ công cụ và kết quả.

Tóm lại, uag hiện kết hợp các yếu tố: cắt bớt xác định, tham chiếu Artifact, cách ly mã nhị phân, lựa chọn công cụ động, tóm tắt lịch sử, tiếp tục từ nhà cung cấp và phục hồi tràn. Lộ trình thiết kế cho một lớp bối cảnh thống nhất được ghi chép trong [UAG_CONTEXT_MANAGEMENT_DESIGN.md](UAG_CONTEXT_MANAGEMENT_DESIGN.md).
