# 🏫 Hệ thống Quản lý Lớp học & Trung tâm Giáo dục

Một giải pháp phần mềm toàn diện, nhẹ và tốc độ cao dành cho các trung tâm giáo dục, lớp học thêm. Hệ thống giúp số hóa toàn bộ quy trình: Quản lý học sinh, Điểm danh, Tính học phí (tích hợp VietQR), Trả lương giáo viên, và Báo cáo thống kê.

Được xây dựng trên nền tảng **Python / FastAPI** hiện đại, kết hợp với giao diện **Jinja2 + Tailwind CSS**.

---

## ✨ Tính năng nổi bật

### 👥 Quản lý Học vụ & Nhân sự
- **Lớp học & Môn học:** Quản lý danh sách lớp, gán giáo viên (Chính/Phụ), thiết lập mức học phí mặc định.
- **Học sinh:** Quản lý hồ sơ, gán học sinh vào nhiều lớp khác nhau, hỗ trợ tùy chỉnh học phí riêng hoặc miễn giảm hoàn toàn.
- **Giáo viên:** Quản lý hồ sơ giáo viên, hệ số lương. Hỗ trợ đa dạng hình thức tính lương (Lương cứng theo số buổi / Hưởng % doanh thu lớp).

### ✅ Điểm danh (Real-time)
- **Điểm danh Học sinh:** Đánh dấu Có mặt/Vắng mặt/Đi muộn. Tự động đồng bộ với module Tính học phí.
- **Điểm danh Giáo viên:** Ghi nhận số buổi dạy thực tế để tự động cấu thành bảng lương cuối tháng.

### 💰 Quản lý Học phí & Thu chi
- **Tính học phí tự động:** Tính tiền dựa trên số buổi điểm danh thực tế trong tháng.
- **Thanh toán VietQR:** Tự động tạo mã VietQR động trên từng Phiếu thu để phụ huynh quét mã thanh toán chính xác số tiền.
- **In Phiếu thu (PDF):** Xuất phiếu thu hàng loạt hoặc cá nhân. Tùy chỉnh mẫu phiếu thu với Logo và chữ ký.
- **Quản lý công nợ:** Theo dõi trạng thái Chưa thu, Thu một phần, Thu đủ, hoặc Thu dư (chuyển qua tháng sau). Chốt kỳ học phí cố định.

### 💵 Lương Giáo viên (Payroll)
- **Tạm tính & Chốt lương:** Tự động tính lương dựa trên số buổi dạy (Đủ/Trễ/Vắng) hoặc theo tỷ lệ % doanh thu thực tế của lớp.
- **In Phiếu xác nhận lương:** Xuất PDF bảng kê chi tiết lương của từng giáo viên.

### 📊 Báo cáo & Lưu trữ
- **Dashboard Tổng quan:** Biểu đồ doanh thu, thống kê nhanh số lượng học sinh/lớp học.
- **Trích xuất dữ liệu:** Xuất báo cáo ra Excel (.xlsx), PDF, hoặc nén ZIP chứa các file CSV.
- **Sao lưu & Khôi phục (Backup/Restore):** Cấu hình tự động sao lưu định kỳ, xuất file `.sql` và phục hồi toàn bộ hệ thống bằng 1 click.

---

## 🛠 Công nghệ sử dụng

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.0 (ORM)
- **Database:** SQLite (File-based, nhỏ gọn, không cần cài đặt DB server riêng)
- **Frontend:** HTML5, Tailwind CSS (CDN), Vanilla JS, jQuery, DataTables, Select2, Chart.js, Summernote.
- **Template Engine:** Jinja2
- **Export / Báo cáo:** WeasyPrint & ReportLab (Xuất PDF), OpenPyXL (Xuất Excel)
- **Bảo mật:** Passlib (Bcrypt), JWT (Lưu trữ qua HTTPOnly Cookie)

---

## 🚀 Hướng dẫn Cài đặt & Chạy dự án

### Cách 1: Chạy trực tiếp (Môi trường Local)

**1. Yêu cầu hệ thống:**
- Python 3.11 trở lên.
- (Tùy chọn nhưng khuyên dùng) Cài đặt thư viện GTK3/Pango trên hệ điều hành để `WeasyPrint` xuất PDF đẹp nhất (Nếu không có, hệ thống tự Fallback sang `ReportLab`).

**2. Cài đặt:**
```bash
# Clone dự án (nếu dùng Git) hoặc giải nén mã nguồn
cd hoang-quanlylophoc

# Tạo môi trường ảo (Khuyên dùng)
python -m venv venv

# Kích hoạt môi trường ảo
# - Trên Windows:
venv\Scripts\activate
# - Trên Linux/Mac:
source venv/bin/activate

# Cài đặt thư viện
pip install -r requirements.txt
```

**3. Khởi chạy:**
```bash
python main.py
```
> Script `main.py` sẽ tự động tìm Port trống, khởi động Server Uvicorn và tự động mở trình duyệt.

---

### Cách 2: Chạy bằng Docker (Khuyên dùng cho Server/VPS)

Dự án đã tích hợp sẵn cấu hình Docker hoàn chỉnh, tự động xử lý các dependencies môi trường (fonts, weasyprint).

```bash
# Build và chạy ngầm dự án
docker compose up -d
```
Ứng dụng sẽ chạy tại địa chỉ: `http://localhost:8000`

> **Lưu ý:** Dữ liệu database và hình ảnh (Logo/QR) được lưu cố định thông qua volumes (`ql_db_data` và `ql_assets_data`), không bị mất khi khởi động lại container.

---

## 🔐 Thông tin đăng nhập mặc định

Ngay lần đầu khởi chạy, hệ thống tự động sinh tài khoản Quản trị viên mặc định:
- **Tên đăng nhập:** `admin`
- **Mật khẩu:** `123456`

*(Hãy đổi mật khẩu ngay sau khi đăng nhập lần đầu).*

---

## 🧪 Dữ liệu mẫu (Seeder)

Để dễ dàng test các chức năng, dự án có tích hợp sẵn Seeder dữ liệu mẫu (Giáo viên, Học sinh, Lớp học, Điểm danh, Học phí tháng 06/2026).

Chạy lệnh sau:
```bash
python -m app.seeder
```
*(Lưu ý: Bạn có thể chạy lệnh này nhiều lần, hệ thống sẽ xóa và tạo lại nguyên bản bộ dữ liệu mẫu mà không ảnh hưởng tới dữ liệu thực tế khác của bạn).*

---

## 📁 Cấu trúc thư mục

```text
hoang-quanlylophoc/
├── app/
│   ├── routers/          # Chứa các API/Controller (Auth, Classes, Students, Tuition, Payroll...)
│   ├── services/         # Chứa Logic nghiệp vụ (Tính lương, Học phí, Xuất PDF, Excel, VietQR...)
│   ├── seeder/           # Công cụ sinh dữ liệu mẫu
│   ├── models.py         # Định nghĩa các bảng Database (SQLAlchemy)
│   ├── schemas.py        # Định nghĩa Pydantic Models (Validate API In/Out)
│   ├── database.py       # Cấu hình kết nối SQLite
│   └── bootstrap.py      # Script khởi tạo cài đặt mặc định
├── database/             # Nơi lưu trữ file Database (quanlylophoc.sqlite3)
├── static/               # File tĩnh (CSS, JS, Uploaded Assets: Logo, QR)
├── templates/            # Các file giao diện HTML (Jinja2)
├── tests/                # Unit test / Integration test (Pytest)
├── docker-compose.yml    # Cấu hình Docker Compose
├── Dockerfile            # Cấu hình build Docker Image
├── requirements.txt      # Danh sách thư viện Python
└── main.py               # File script chạy dự án local & khởi tạo FastAPI App
```

---

## 🛡️ Cảnh báo về Sao lưu (Backup)

Dữ liệu của hệ thống được lưu hoàn toàn trong thư mục `database/` (file `quanlylophoc.sqlite3`).
- Hệ thống có tính năng **Tự động tải về bản sao lưu hàng tháng** tại giao diện **Quản lý dữ liệu**. Hãy tận dụng tính năng này.
- Bất kỳ lúc nào, bạn cũng có thể vào phần **Quản lý Dữ liệu -> Xuất bản sao SQL** để tải về máy toàn bộ dữ liệu hiện tại đề phòng rủi ro.

---
*Phát triển bởi đội ngũ HH Education / Nguyễn Vũ Minh Long.*