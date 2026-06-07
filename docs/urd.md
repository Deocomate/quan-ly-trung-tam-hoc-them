Dựa trên các thông tin, dữ liệu mẫu và yêu cầu bạn đã cung cấp, dưới đây là Tài liệu Yêu cầu Người dùng (URD) hoàn chỉnh cho dự án Quản lý lớp học.

# TÀI LIỆU YÊU CẦU NGƯỜI DÙNG (URD) - HỆ THỐNG QUẢN LÝ LỚP HỌC

## 1. TỔNG QUAN DỰ ÁN

Hệ thống quản lý lớp học được xây dựng nhằm mục đích tự động hóa và tối ưu hóa quy trình quản lý thông tin học sinh, theo dõi điểm danh, tính toán học phí và báo cáo doanh thu cho trung tâm giáo dục. Hệ thống giúp giảm thiểu sai sót trong việc tính toán tài chính và cung cấp giao diện minh bạch, chuyên nghiệp cho cả quản lý trung tâm lẫn phụ huynh học sinh.

## 2. YÊU CẦU CHỨC NĂNG (FUNCTIONAL REQUIREMENTS)

### 2.1. Quản lý Danh sách Học sinh

* Hệ thống cho phép thêm, sửa, xóa và lưu trữ thông tin của học sinh.
* Các trường dữ liệu cơ bản cần quản lý bao gồm: Mã học sinh, Họ và tên, Lớp, Học phí/buổi, Số điện thoại phụ huynh và Ghi chú.
* Hệ thống phải hỗ trợ phân loại các học sinh đặc biệt, bao gồm việc thiết lập miễn học phí hoặc áp dụng hệ số học phí riêng biệt cho từng cá nhân.

### 2.2. Quản lý Lớp học

* Hệ thống thiết lập cấu trúc dữ liệu theo quy tắc: 1 lớp học có thể bao gồm nhiều học sinh.
* Cho phép thiết lập mức học phí cố định áp dụng chung cho từng lớp.

### 2.3. Quản lý Điểm danh

* Hệ thống cung cấp bảng điểm danh chi tiết theo ngày cho từng lớp học.
* Cần hỗ trợ ghi nhận các trạng thái điểm danh khác nhau (ví dụ: P - Có mặt, V - Vắng mặt, M - Đi muộn).

### 2.4. Tính toán Học phí

* Hệ thống cho phép lọc (filter) và xuất dữ liệu số buổi học theo mã học sinh trong một tháng cụ thể.
* Tính năng tự động tổng hợp số buổi học thực tế của học sinh trong tháng để làm cơ sở tính tiền.
* Công thức tính tổng học phí cơ bản dựa trên tổng số buổi học nhân với đơn giá học phí của một buổi.
* Sau khi tính toán, hệ thống sẽ đẩy thông tin học phí của từng học sinh lên để chuẩn bị cho việc xuất phiếu thu.

### 2.5. Xuất Phiếu thu Học phí (Định dạng PDF)

* Cho phép người dùng xuất phiếu thu học phí cho phụ huynh dưới định dạng file PDF dựa trên dữ liệu học phí đã tính toán trong tháng.
* Mẫu phiếu thu xuất ra phải tuân thủ chuẩn form mẫu thực tế, bao gồm các thành phần sau:
* **Phần Header:** Tên trung tâm (ví dụ: Hộ kinh doanh Trung tâm giáo dục Hoa Tuyết), Địa chỉ và Hotline liên hệ.
* **Thông tin học sinh:** Tiêu đề thông báo học phí theo tháng, Kính gửi phụ huynh em (Tên học sinh), Lớp.
* **Bảng kê chi tiết:** Bao gồm các cột Môn học, Buổi học, Học phí (đơn giá), Tổng tiền và Ghi chú.
* **Tổng kết thanh toán:** Dòng tính "Tổng tiền (VNĐ) HỌC PHÍ" và "SỐ TIỀN PHẢI NỘP (VNĐ)".
* **Hướng dẫn thanh toán:** Thời hạn đóng học phí, Cú pháp Nội dung chuyển khoản (VD: Tên học sinh + Mã lớp/Tháng).
* **Mã QR Thanh toán:** Mã QR Thanh toán là ảnh, có thể chỉnh sửa trong phần admin quản lý.


### 2.6. Dashboard Phân tích Doanh thu

* Hệ thống cung cấp giao diện Dashboard để thống kê và phân tích tổng doanh thu theo các mốc thời gian: tháng, quý và năm.
* Báo cáo doanh thu chi tiết cần hiển thị các trường dữ liệu: Năm, Tháng, Lớp, Số học sinh, Tổng số buổi và Doanh thu thực tế.

### 2.7. Sửa template phiếu thu.
* Có thể sửa được các phần thông tin tĩnh trong template phiếu thu, như các phần header, footer, các phần chữ in đậm...

### 2.8. Quản lý tài khoản admin, đăng nhập đăng xuất với username + password

## 3. YÊU CẦU PHI CHỨC NĂNG (NON-FUNCTIONAL REQUIREMENTS)

*(Đề xuất thêm để hoàn thiện hệ thống)*

* **Giao diện người dùng (UI/UX):** Trực quan, dễ sử dụng, đặc biệt phần điểm danh và bộ lọc (filter) cần thao tác nhanh chóng để tiết kiệm thời gian cho giáo viên/trợ giảng.
* **Tính toàn vẹn dữ liệu:** Dữ liệu điểm danh không được phép chỉnh sửa sau khi đã chốt phiếu thu của tháng, trừ khi có quyền quản trị viên cấp cao.
* **Hiệu năng:** Tốc độ xuất hàng loạt file PDF phiếu thu cần nhanh chóng và mượt mà, không gây đứng hệ thống khi số lượng học sinh lớn.
* **Khả năng tương thích:** Hệ thống có thể xem tốt trên cả màn hình máy tính (PC) và thiết bị di động (để hỗ trợ việc điểm danh tại lớp).