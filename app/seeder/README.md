# Seeder dữ liệu mẫu

Chạy lệnh sau ở thư mục gốc dự án:

```powershell
python -m app.seeder
```

Seeder sẽ tạo dữ liệu test tháng `06/2026`:

- 4 lớp/môn học: `6A`, `6B`, `7A`, `8A`.
- 5 học sinh: `HS001` đến `HS005`.
- 16 bản ghi điểm danh cho lớp `6A`.
- Kỳ học phí `06/2026` đã chốt với doanh thu kỳ vọng `2.100.000 VNĐ`.

Seeder có thể chạy lại nhiều lần. Mỗi lần chạy sẽ xóa và tạo lại đúng bộ dữ liệu mẫu, không đụng dữ liệu khác.

Nếu kỳ `06/2026` đã có phiếu học phí của học sinh không thuộc bộ mẫu, seeder sẽ dừng để tránh ảnh hưởng dữ liệu thật.

Tài khoản đăng nhập mặc định vẫn là:

```text
admin / Admin@123*#
```
