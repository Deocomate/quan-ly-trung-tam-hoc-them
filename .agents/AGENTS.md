# Lịch sử hoạt động của Agent & Hướng dẫn phát triển

Tập tin này ghi lại lịch sử các agent đã tham gia phát triển dự án và các quy tắc phát triển quan trọng để các agent tiếp theo tuân thủ.

## Danh sách Agent đã đóng góp

### 1. Antigravity (Google DeepMind) - Tháng 06/2026
- **Nhiệm vụ:** Nâng cấp 6 tính năng cốt lõi cho ứng dụng Quản lý Lớp học:
  1. Tái cấu trúc UI/UX trang Học sinh (`/students`) thành dạng Grid 2 cột, tối ưu form Modal.
  2. Tích hợp thư viện `DataTables.js` vào cả 4 trang chính (`/students`, `/classes`, `/tuition`, `/admin-users`) để tìm kiếm, sắp xếp và phân trang tức thời.
  3. Tự động sinh mã học sinh dạng `{Năm}HS{Số_TT}` ở backend.
  4. Chuyển đổi phiếu thu PDF sang khổ ngang `A4 landscape`, căn giữa dọc hoàn hảo khi in bằng Flexbox (WeasyPrint) và Spacer (ReportLab fallback).
  5. Phát triển tính năng xuất PDF gộp hàng loạt qua API `/api/tuition/export-pdf` thay thế cho tệp ZIP.
  6. Hỗ trợ Soft Lock học phí: cho phép điểm danh và chốt lại học phí đè dữ liệu cũ bất cứ lúc nào.

---

## Hướng dẫn quan trọng dành cho các Agent tiếp theo

> [!IMPORTANT]
> **Quy tắc khôi phục dữ liệu mẫu:**
> Mỗi khi chạy kiểm thử tự động bằng lệnh `pytest`, cơ sở dữ liệu mẫu sẽ bị xóa sạch hoặc reset về trạng thái trắng.
> Sau khi chạy test xong, bạn **bắt buộc** phải chạy lệnh seeder để khôi phục lại dữ liệu mẫu cho người dùng:
> ```powershell
> python -X utf8 -m app.seeder
> ```
