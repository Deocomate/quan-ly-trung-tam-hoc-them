from io import BytesIO
import datetime
from sqlalchemy import func, select, distinct
from sqlalchemy.orm import Session
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from app.models import TuitionRecord, TuitionRecordItem, Student, Class, Enrollment


def format_period_label(months: list[int], year: int) -> tuple[str, str]:
    if len(months) == 1:
        m = months[0]
        return f"THÁNG {m:02d}/{year}", f"T{m:02d}-{year}"
    elif len(months) == 3:
        sorted_m = sorted(months)
        if sorted_m == [1, 2, 3]:
            q = 1
        elif sorted_m == [4, 5, 6]:
            q = 2
        elif sorted_m == [7, 8, 9]:
            q = 3
        else:
            q = 4
        return f"QUÝ {q}/{year}", f"Quy {q}-{year}"
    elif len(months) == 12:
        return f"NĂM {year}", f"{year}"
    else:
        sorted_m = sorted(months)
        m_range = f"{sorted_m[0]:02d}-{sorted_m[-1]:02d}"
        return f"KỲ {m_range}/{year}", f"Ky {m_range}-{year}"


def generate_revenue_report_excel(db: Session, month: int | list[int], year: int, settings: dict[str, str]) -> bytes:
    if isinstance(month, int):
        months = [month]
    else:
        months = month

    # 1. Lấy dữ liệu tổng quan
    total_students = db.scalar(
        select(func.count(distinct(TuitionRecord.student_id)))
        .where(TuitionRecord.month.in_(months), TuitionRecord.year == year)
    ) or 0

    total_classes = db.scalar(
        select(func.count(distinct(TuitionRecordItem.class_id)))
        .join(TuitionRecordItem.record)
        .where(TuitionRecord.month.in_(months), TuitionRecord.year == year)
    ) or 0

    total_sessions = db.scalar(
        select(func.coalesce(func.sum(TuitionRecordItem.sessions), 0))
        .join(TuitionRecordItem.record)
        .where(TuitionRecord.month.in_(months), TuitionRecord.year == year)
    ) or 0

    total_revenue = db.scalar(
        select(func.coalesce(func.sum(TuitionRecord.total_amount), 0))
        .where(TuitionRecord.month.in_(months), TuitionRecord.year == year)
    ) or 0

    class_rows = db.execute(
        select(
            TuitionRecordItem.class_name,
            TuitionRecordItem.subject,
            func.count(distinct(TuitionRecord.student_id)).label("students_count"),
            func.coalesce(func.sum(TuitionRecordItem.sessions), 0).label("sessions_count"),
            func.coalesce(func.sum(TuitionRecordItem.amount), 0).label("revenue")
        )
        .join(TuitionRecordItem.record)
        .where(TuitionRecord.month.in_(months), TuitionRecord.year == year)
        .group_by(TuitionRecordItem.class_id, TuitionRecordItem.class_name, TuitionRecordItem.subject)
        .order_by(TuitionRecordItem.class_name)
    ).all()

    # 2. Tạo workbook và sheet
    wb = Workbook()
    ws = wb.active
    period_title, sheet_title = format_period_label(months, year)
    ws.title = f"Doanh thu {sheet_title}"

    # Bật hiển thị đường lưới
    ws.views.sheetView[0].showGridLines = True

    # 3. Định nghĩa style và font
    font_family = "Segoe UI"
    title_font = Font(name=font_family, size=16, bold=True, color="0F2A33")
    subtitle_font = Font(name=font_family, size=10, italic=True, color="526672")
    header_font = Font(name=font_family, size=11, bold=True, color="FFFFFF")
    bold_font = Font(name=font_family, size=11, bold=True, color="10202B")
    regular_font = Font(name=font_family, size=11, color="10202B")
    
    fill_header = PatternFill(start_color="0F766E", end_color="0F766E", fill_type="solid")
    fill_summary = PatternFill(start_color="E6F4F1", end_color="E6F4F1", fill_type="solid")
    fill_zebra = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

    thin_border = Border(
        left=Side(style="thin", color="CBD5DC"),
        right=Side(style="thin", color="CBD5DC"),
        top=Side(style="thin", color="CBD5DC"),
        bottom=Side(style="thin", color="CBD5DC")
    )
    double_bottom_border = Border(
        left=Side(style="thin", color="CBD5DC"),
        right=Side(style="thin", color="CBD5DC"),
        top=Side(style="thin", color="CBD5DC"),
        bottom=Side(style="double", color="10202B")
    )

    # 4. Phần đầu đề (Header báo cáo)
    center_name = settings.get("center_name", "HH EDUCATION")
    ws["A1"] = center_name.upper()
    ws["A1"].font = Font(name=font_family, size=11, bold=True, color="0F766E")
    
    ws["A2"] = f"BÁO CÁO DOANH THU {period_title}"
    ws["A2"].font = title_font
    
    now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    ws["A3"] = f"Ngày xuất báo cáo: {now_str}"
    ws["A3"].font = subtitle_font
    
    ws.row_dimensions[2].height = 25

    # 5. Bảng Tóm tắt Tổng quan
    ws["A5"] = "TỔNG QUAN DOANH THU"
    ws["A5"].font = Font(name=font_family, size=12, bold=True, color="0F766E")
    
    summary_headers = ["Chỉ số", "Giá trị"]
    for col_idx, h in enumerate(summary_headers, start=1):
        cell = ws.cell(row=6, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border
    
    summary_data = [
        ("Tổng số học sinh đã chốt học phí", total_students, "students"),
        ("Tổng số lớp học phát sinh học phí", total_classes, "classes"),
        ("Tổng số buổi học đã tham gia", total_sessions, "sessions"),
        ("Tổng doanh thu thực tế (VNĐ)", total_revenue, "revenue")
    ]
    
    for row_idx, (label, val, unit) in enumerate(summary_data, start=7):
        c1 = ws.cell(row=row_idx, column=1, value=label)
        c1.font = regular_font
        c1.border = thin_border
        c1.alignment = Alignment(horizontal="left", vertical="center")
        
        c2 = ws.cell(row=row_idx, column=2, value=val)
        c2.font = bold_font if unit == "revenue" else regular_font
        c2.border = thin_border
        c2.alignment = Alignment(horizontal="right", vertical="center")
        if unit == "revenue":
            c2.number_format = "#,##0"
            c2.fill = fill_summary
            
    # 6. Bảng Chi tiết theo Từng Lớp Học
    start_class_row = 13
    ws.cell(row=start_class_row - 1, column=1, value="CHI TIẾT DOANH THU THEO TỪNG LỚP HỌC").font = Font(name=font_family, size=12, bold=True, color="0F766E")
    
    class_headers = ["STT", "Tên lớp", "Môn học", "Sỹ số (HS)", "Tổng buổi học", "Doanh thu (VNĐ)", "Tỷ lệ (%)"]
    ws.row_dimensions[start_class_row].height = 25
    for col_idx, h in enumerate(class_headers, start=1):
        cell = ws.cell(row=start_class_row, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border

    current_row = start_class_row + 1
    for idx, row in enumerate(class_rows, start=1):
        ws.row_dimensions[current_row].height = 20
        row_fill = fill_zebra if idx % 2 == 0 else PatternFill(fill_type=None)
        
        c_stt = ws.cell(row=current_row, column=1, value=idx)
        c_stt.alignment = Alignment(horizontal="center", vertical="center")
        
        c_name = ws.cell(row=current_row, column=2, value=row.class_name)
        c_name.alignment = Alignment(horizontal="left", vertical="center")
        
        c_subject = ws.cell(row=current_row, column=3, value=row.subject)
        c_subject.alignment = Alignment(horizontal="left", vertical="center")
        
        c_stud = ws.cell(row=current_row, column=4, value=row.students_count)
        c_stud.alignment = Alignment(horizontal="center", vertical="center")
        c_stud.number_format = "#,##0"
        
        c_sess = ws.cell(row=current_row, column=5, value=row.sessions_count)
        c_sess.alignment = Alignment(horizontal="center", vertical="center")
        c_sess.number_format = "#,##0"
        
        c_rev = ws.cell(row=current_row, column=6, value=row.revenue)
        c_rev.alignment = Alignment(horizontal="right", vertical="center")
        c_rev.number_format = "#,##0"
        c_rev.font = bold_font
        
        # Công thức tính tỷ lệ phần trăm so với tổng doanh thu nằm ở ô B10
        c_ratio = ws.cell(row=current_row, column=7, value=f"=F{current_row}/$B$10")
        c_ratio.alignment = Alignment(horizontal="right", vertical="center")
        c_ratio.number_format = "0.0%"
        
        for c in [c_stt, c_name, c_subject, c_stud, c_sess, c_rev, c_ratio]:
            c.font = regular_font if c != c_rev else bold_font
            c.border = thin_border
            if row_fill.fill_type:
                c.fill = row_fill
                
        current_row += 1

    # Dòng tổng cộng cho bảng chi tiết lớp học
    ws.row_dimensions[current_row].height = 22
    ws.cell(row=current_row, column=1, value="Tổng cộng").font = bold_font
    ws.cell(row=current_row, column=1).alignment = Alignment(horizontal="left", vertical="center")
    ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=3)
    
    c_tot_stud = ws.cell(row=current_row, column=4, value=f"=SUM(D{start_class_row+1}:D{current_row-1})")
    c_tot_stud.alignment = Alignment(horizontal="center", vertical="center")
    c_tot_stud.number_format = "#,##0"
    
    c_tot_sess = ws.cell(row=current_row, column=5, value=f"=SUM(E{start_class_row+1}:E{current_row-1})")
    c_tot_sess.alignment = Alignment(horizontal="center", vertical="center")
    c_tot_sess.number_format = "#,##0"
    
    c_tot_rev = ws.cell(row=current_row, column=6, value=f"=SUM(F{start_class_row+1}:F{current_row-1})")
    c_tot_rev.alignment = Alignment(horizontal="right", vertical="center")
    c_tot_rev.number_format = "#,##0"
    
    c_tot_ratio = ws.cell(row=current_row, column=7, value=f"=SUM(G{start_class_row+1}:G{current_row-1})")
    c_tot_ratio.alignment = Alignment(horizontal="right", vertical="center")
    c_tot_ratio.number_format = "0.0%"

    for col in range(1, 8):
        c = ws.cell(row=current_row, column=col)
        c.font = bold_font
        c.fill = fill_summary
        c.border = double_bottom_border

    # 7. Tự động co giãn kích thước cột vừa văn dữ liệu
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            # Bỏ qua đo độ dài dòng tiêu đề lớn ở cột A để tránh cột A quá rộng
            if col_letter == "A" and cell.row in [1, 2, 3, 5, 12]:
                continue
            if cell.value is not None:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    # Lưu workbook vào BytesIO để trả về
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
