from __future__ import annotations

from io import BytesIO
import ctypes.util
import platform
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.database import BASE_DIR
from app.models import TuitionRecord


def format_currency(value: int | None) -> str:
    if value is None:
        return "-"
    return f"{value:,}".replace(",", ".")


def _build_logo_elements(settings: dict[str, str], styles: dict, mm) -> list:
    from reportlab.platypus import Image as RLImage, Paragraph
    logo_elements = []
    logo_file = BASE_DIR / "static" / "assets" / "logo.png"
    
    if logo_file.exists():
        from PIL import Image as PILImage
        try:
            with PILImage.open(logo_file) as img:
                w, h = img.size
            aspect = h / w
            img_w = 40 * mm
            img_h = img_w * aspect
            if img_h > 25 * mm:
                img_h = 25 * mm
                img_w = img_h / aspect
            logo_elements.append(RLImage(str(logo_file), width=img_w, height=img_h))
        except Exception:
            pass
            
    if not logo_elements:
        logo_elements.append(Paragraph(_linebreaks(settings.get("center_logo_text", "HH\nEDUCATION")), styles["center_bold"]))
        
    return logo_elements


def render_receipt_html(records: list[TuitionRecord] | TuitionRecord, settings: dict[str, str]) -> str:
    env = Environment(
        loader=FileSystemLoader(str(BASE_DIR / "templates")),
        autoescape=select_autoescape(["html", "xml"]),
    )
    
    # Định nghĩa hàm helper lấy nội dung chuyển khoản động
    def get_payment_content(rec):
        from app.services.vietqr_service import safe_format_payment_content
        payment_template = settings.get("payment_content_template", "HP {student_code} {month:02d}{year_short}")
        return safe_format_payment_content(
            payment_template,
            rec.student.full_name,
            rec.student.student_code,
            rec.month,
            rec.year
        )
        
    env.filters["currency"] = format_currency
    env.globals["get_payment_content"] = get_payment_content
    
    template = env.get_template("phieu-thu.html")
    qr_path = (BASE_DIR / "static" / "assets" / "qr.png").resolve().as_uri()
    logo_path = (BASE_DIR / "static" / "assets" / "logo.png").resolve().as_uri()
    
    # Kiểm tra nếu là một bản ghi đơn lẻ, đóng gói thành danh sách để xử lý đồng nhất trong template
    if not isinstance(records, list):
        records_list = [records]
    else:
        records_list = records

    # Populate qr_src and check recalculation for each record
    from app.services.vietqr_service import generate_vietqr_url
    bank_id = settings.get("vietqr_bank_id", "").strip()
    account_no = settings.get("vietqr_account_no", "").strip()
    account_name = settings.get("vietqr_account_name", "").strip()

    for rec in records_list:
        # Check recalculation
        rec.is_recalculated = False
        if getattr(rec, "updated_at", None) and getattr(rec, "created_at", None) and getattr(rec, "paid_amount", 0) > 0:
            if (rec.updated_at - rec.created_at).total_seconds() > 60:
                rec.is_recalculated = True
                rec.recalculated_at_str = rec.updated_at.strftime('%H:%M %d/%m/%Y')

        if bank_id and account_no:
            amount = rec.total_amount - (rec.paid_amount or 0)
            t_code = rec.transfer_code
            if not t_code:
                t_code = get_payment_content(rec)
            rec.qr_src = generate_vietqr_url(bank_id, account_no, account_name, amount, t_code)
        else:
            rec.qr_src = (BASE_DIR / "static" / "assets" / "qr.png").resolve().as_uri()
        
    return template.render(records=records_list, settings=settings, logo_path=logo_path)


def html_to_pdf(html: str) -> bytes:
    if platform.system() == "Windows" and not ctypes.util.find_library("libgobject-2.0-0"):
        raise RuntimeError("WEASYPRINT_UNAVAILABLE")
    try:
        from weasyprint import HTML
    except Exception:
        raise RuntimeError("WEASYPRINT_UNAVAILABLE")
    return HTML(string=html, base_url=str(Path.cwd())).write_pdf()


def receipt_to_pdf(records: list[TuitionRecord] | TuitionRecord, settings: dict[str, str]) -> bytes:
    html = render_receipt_html(records, settings)
    try:
        return html_to_pdf(html)
    except Exception:
        # Sử dụng ReportLab Fallback
        if isinstance(records, list):
            return render_multiple_receipts_reportlab(records, settings)
        return render_receipt_reportlab(records, settings)


def render_receipt_reportlab(record: TuitionRecord, settings: dict[str, str]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    regular_font, bold_font = _register_vietnamese_fonts()
    styles = {
        "normal": ParagraphStyle("normal", fontName=regular_font, fontSize=10.5, leading=13, alignment=TA_LEFT),
        "bold": ParagraphStyle("bold", fontName=bold_font, fontSize=10.5, leading=13, alignment=TA_LEFT),
        "center_bold": ParagraphStyle("center_bold", fontName=bold_font, fontSize=10.5, leading=13, alignment=TA_CENTER),
        "center_normal": ParagraphStyle("center_normal", fontName=regular_font, fontSize=10.5, leading=13, alignment=TA_CENTER),
        "title": ParagraphStyle("title", fontName=bold_font, fontSize=16, leading=20, alignment=TA_CENTER),
    }

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4), # Khổ ngang
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )

    payment_content = _payment_content(record, settings)
    story = []

    logo_elements = _build_logo_elements(settings, styles, mm)
    header = Table(
        [
            [
                logo_elements,
                [
                    Paragraph(settings.get("center_name", ""), styles["bold"]),
                    Paragraph(settings.get("center_address", ""), styles["normal"]),
                    Paragraph(settings.get("center_hotline", ""), styles["normal"]),
                ],
            ]
        ],
        colWidths=[52 * mm, 218 * mm], # Tổng 270mm
    )
    header.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 1, colors.black),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )

    title = Table([[Paragraph(f"THÔNG BÁO HỌC PHÍ THÁNG {record.month}", styles["title"])]], colWidths=[270 * mm])
    title.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1, colors.black), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))

    # Check if recalculated
    is_recalculated = False
    if getattr(record, "updated_at", None) and getattr(record, "created_at", None) and getattr(record, "paid_amount", 0) > 0:
        if (record.updated_at - record.created_at).total_seconds() > 60:
            is_recalculated = True

    intro = [
        Paragraph(
            f"<b>Kính gửi: Phụ huynh em:</b> {record.student.full_name} &nbsp;&nbsp;&nbsp; <b>{record.student.student_code}</b>",
            styles["normal"],
        ),
        Paragraph(settings.get("receipt_intro", ""), styles["normal"]),
    ]

    rows = [
        [
            Paragraph("Môn học", styles["center_bold"]),
            Paragraph("Buổi học", styles["center_bold"]),
            Paragraph("Học phí", styles["center_bold"]),
            Paragraph("Tổng tiền", styles["center_bold"]),
            Paragraph("Ghi chú", styles["center_bold"]),
        ]
    ]
    for item in record.items:
        rows.append(
            [
                Paragraph(item.subject, styles["bold"]),
                Paragraph(str(item.sessions), styles["center_normal"]),
                Paragraph(format_currency(item.unit_fee), styles["center_normal"]),
                Paragraph(format_currency(item.amount), styles["center_normal"]),
                Paragraph(item.notes or "", styles["center_normal"]),
            ]
        )
    rows.append(
        [
            Paragraph("Tổng tiền (VNĐ) HỌC PHÍ", styles["center_bold"]),
            "",
            "",
            Paragraph(format_currency(record.total_amount), styles["center_bold"]),
            "",
        ]
    )
    if record.paid_amount and record.paid_amount > 0:
        rows.append(
            [
                Paragraph("Đã thanh toán (VNĐ)", styles["center_bold"]),
                "",
                "",
                Paragraph(f"- {format_currency(record.paid_amount)}", styles["center_bold"]),
                "",
            ]
        )
    
    debt = record.total_amount - (record.paid_amount or 0)
    if debt > 0:
        rows.append(
            [
                Paragraph("SỐ TIỀN CÒN PHẢI NỘP (VNĐ)", styles["center_bold"]),
                "",
                "",
                Paragraph(format_currency(debt), styles["center_bold"]),
                "",
            ]
        )
    elif debt < 0:
        rows.append(
            [
                Paragraph("<font color='#16a34a'><b>SỐ TIỀN ĐÓNG DƯ KỲ NÀY (VNĐ)</b></font>", styles["center_bold"]),
                "",
                "",
                Paragraph(f"<font color='#16a34a'><b>{format_currency(abs(debt))}</b></font>", styles["center_bold"]),
                Paragraph("<font color='#555555'>Sẽ trừ vào tháng sau</font>", styles["center_normal"]),
            ]
        )
    else:
        rows.append(
            [
                Paragraph("SỐ TIỀN PHẢI NỘP (VNĐ)", styles["center_bold"]),
                "",
                "",
                Paragraph("0", styles["center_bold"]),
                "",
            ]
        )

    detail_table = Table(rows, colWidths=[44 * mm, 24 * mm, 34 * mm, 34 * mm, 34 * mm], repeatRows=1)
    
    t_style = [
        ("BOX", (0, 0), (-1, -1), 1, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 1, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    num_bottom_rows = len(rows) - 1 - len(record.items)
    items_end_idx = -(num_bottom_rows + 1)
    t_style.append(("ALIGN", (0, 1), (0, items_end_idx), "LEFT"))
    for r_idx in range(-num_bottom_rows, 0):
        t_style.append(("ALIGN", (0, r_idx), (0, r_idx), "CENTER"))
        t_style.append(("SPAN", (0, r_idx), (2, r_idx)))
    detail_table.setStyle(TableStyle(t_style))

    payment = [
        Paragraph(settings.get("payment_deadline", ""), styles["normal"]),
        Paragraph(f"Nội dung chuyển khoản: <b>{record.transfer_code or payment_content}</b>", styles["normal"]),
        Paragraph(clean_html_for_reportlab(settings.get('receipt_footer', 'Trân trọng cảm ơn!')), styles["normal"]),
    ]

    left = [*intro, Spacer(1, 4), detail_table, Spacer(1, 6), *payment]
    right = _qr_image(record, settings, Image, styles)

    body = Table([[left, right]], colWidths=[190 * mm, 80 * mm])
    body.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 1, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    # Bọc toàn bộ phiếu thu trong một master table có chiều cao 182mm và căn giữa dọc
    master_table = Table([[ [header, title, body] ]], colWidths=[270 * mm], rowHeights=[182 * mm])
    master_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(master_table)
    doc.build(story)
    return buffer.getvalue()


def render_multiple_receipts_reportlab(records: list[TuitionRecord], settings: dict[str, str]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak

    regular_font, bold_font = _register_vietnamese_fonts()
    styles = {
        "normal": ParagraphStyle("normal", fontName=regular_font, fontSize=10.5, leading=13, alignment=TA_LEFT),
        "bold": ParagraphStyle("bold", fontName=bold_font, fontSize=10.5, leading=13, alignment=TA_LEFT),
        "center_bold": ParagraphStyle("center_bold", fontName=bold_font, fontSize=10.5, leading=13, alignment=TA_CENTER),
        "center_normal": ParagraphStyle("center_normal", fontName=regular_font, fontSize=10.5, leading=13, alignment=TA_CENTER),
        "title": ParagraphStyle("title", fontName=bold_font, fontSize=16, leading=20, alignment=TA_CENTER),
    }

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4), # Khổ ngang
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )

    story = []
    for idx, record in enumerate(records):
        if idx > 0:
            story.append(PageBreak())

        logo_elements = _build_logo_elements(settings, styles, mm)
        header = Table(
            [
                [
                    logo_elements,
                    [
                        Paragraph(settings.get("center_name", ""), styles["bold"]),
                        Paragraph(settings.get("center_address", ""), styles["normal"]),
                        Paragraph(settings.get("center_hotline", ""), styles["normal"]),
                    ],
                ]
            ],
            colWidths=[52 * mm, 218 * mm],
        )
        header.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 1, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 1, colors.black),
            ("ALIGN", (0, 0), (0, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))

        title = Table([[Paragraph(f"THÔNG BÁO HỌC PHÍ THÁNG {record.month}", styles["title"])]], colWidths=[270 * mm])
        title.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1, colors.black), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))

        # Check if recalculated
        is_recalculated = False
        if getattr(record, "updated_at", None) and getattr(record, "created_at", None) and getattr(record, "paid_amount", 0) > 0:
            if (record.updated_at - record.created_at).total_seconds() > 60:
                is_recalculated = True

        intro = [
            Paragraph(f"<b>Kính gửi: Phụ huynh em:</b> {record.student.full_name} &nbsp;&nbsp;&nbsp; <b>{record.student.student_code}</b>", styles["normal"]),
            Paragraph(settings.get("receipt_intro", ""), styles["normal"]),
        ]

        rows = [
            [
                Paragraph("Môn học", styles["center_bold"]),
                Paragraph("Buổi học", styles["center_bold"]),
                Paragraph("Học phí", styles["center_bold"]),
                Paragraph("Tổng tiền", styles["center_bold"]),
                Paragraph("Ghi chú", styles["center_bold"]),
            ]
        ]
        for item in record.items:
            rows.append([
                Paragraph(item.subject, styles["bold"]),
                Paragraph(str(item.sessions), styles["center_normal"]),
                Paragraph(format_currency(item.unit_fee), styles["center_normal"]),
                Paragraph(format_currency(item.amount), styles["center_normal"]),
                Paragraph(item.notes or "", styles["center_normal"]),
            ])
        rows.append(
            [Paragraph("Tổng tiền (VNĐ) HỌC PHÍ", styles["center_bold"]), "", "", Paragraph(format_currency(record.total_amount), styles["center_bold"]), ""]
        )
        if record.paid_amount and record.paid_amount > 0:
            rows.append(
                [Paragraph("Đã thanh toán (VNĐ)", styles["center_bold"]), "", "", Paragraph(f"- {format_currency(record.paid_amount)}", styles["center_bold"]), ""]
            )
        
        debt = record.total_amount - (record.paid_amount or 0)
        if debt > 0:
            rows.append(
                [Paragraph("SỐ TIỀN CÒN PHẢI NỘP (VNĐ)", styles["center_bold"]), "", "", Paragraph(format_currency(debt), styles["center_bold"]), ""]
            )
        elif debt < 0:
            rows.append(
                [
                    Paragraph("<font color='#16a34a'><b>SỐ TIỀN ĐÓNG DƯ KỲ NÀY (VNĐ)</b></font>", styles["center_bold"]),
                    "",
                    "",
                    Paragraph(f"<font color='#16a34a'><b>{format_currency(abs(debt))}</b></font>", styles["center_bold"]),
                    Paragraph("<font color='#555555'>Sẽ trừ vào tháng sau</font>", styles["center_normal"]),
                ]
            )
        else:
            rows.append(
                [Paragraph("SỐ TIỀN PHẢI NỘP (VNĐ)", styles["center_bold"]), "", "", Paragraph("0", styles["center_bold"]), ""]
            )

        detail_table = Table(rows, colWidths=[44 * mm, 24 * mm, 34 * mm, 34 * mm, 34 * mm])
        
        t_style = [
            ("BOX", (0, 0), (-1, -1), 1, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 1, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        num_bottom_rows = len(rows) - 1 - len(record.items)
        items_end_idx = -(num_bottom_rows + 1)
        t_style.append(("ALIGN", (0, 1), (0, items_end_idx), "LEFT"))
        for r_idx in range(-num_bottom_rows, 0):
            t_style.append(("ALIGN", (0, r_idx), (0, r_idx), "CENTER"))
            t_style.append(("SPAN", (0, r_idx), (2, r_idx)))
        detail_table.setStyle(TableStyle(t_style))

        payment_content = _payment_content(record, settings)
        payment = [
            Paragraph(settings.get("payment_deadline", ""), styles["normal"]),
            Paragraph(f"Nội dung chuyển khoản: <b>{record.transfer_code or payment_content}</b>", styles["normal"]),
            Paragraph(clean_html_for_reportlab(settings.get('receipt_footer', 'Trân trọng cảm ơn!')), styles["normal"]),
        ]

        left = [*intro, Spacer(1, 4), detail_table, Spacer(1, 4), *payment]
        right = _qr_image(record, settings, Image, styles)

        body = Table([[left, right]], colWidths=[190 * mm, 80 * mm])
        body.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 1, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 1, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))

        # Bọc mỗi phiếu thu vào master table và căn giữa dọc
        master_table = Table([[ [header, title, body] ]], colWidths=[270 * mm], rowHeights=[182 * mm])
        master_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(master_table)

    doc.build(story)
    return buffer.getvalue()


def _register_vietnamese_fonts() -> tuple[str, str]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from pathlib import Path
    
    # Hỗ trợ tìm font trên cả Windows và Linux (Docker)
    font_dirs = [
        Path("C:/Windows/Fonts"),
        Path("/usr/share/fonts/truetype/liberation"),
        Path("/usr/share/fonts/truetype/dejavu")
    ]
    
    # Danh sách các bộ font hỗ trợ tiếng Việt (ưu tiên Times New Roman, dự phòng Liberation Serif)
    candidates = [
        (
            "TimesNewRomanQL", "TimesNewRomanQLBold", "TimesNewRomanQLItalic", "TimesNewRomanQLBoldItalic",
            "times.ttf", "timesbd.ttf", "timesi.ttf", "timesbi.ttf"
        ),
        (
            "LiberationSerifQL", "LiberationSerifQLBold", "LiberationSerifQLItalic", "LiberationSerifQLBoldItalic",
            "LiberationSerif-Regular.ttf", "LiberationSerif-Bold.ttf", "LiberationSerif-Italic.ttf", "LiberationSerif-BoldItalic.ttf"
        ),
        (
            "ArialQL", "ArialQLBold", "ArialQLItalic", "ArialQLBoldItalic",
            "arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf"
        ),
    ]

    for font_dir in font_dirs:
        if not font_dir.exists():
            continue
        for reg_name, bold_name, italic_name, bi_name, reg_file, bold_file, italic_file, bi_file in candidates:
            reg_path = font_dir / reg_file
            bold_path = font_dir / bold_file
            italic_path = font_dir / italic_file
            bi_path = font_dir / bi_file

            if reg_path.exists() and bold_path.exists():
                if reg_name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(reg_name, str(reg_path)))
                if bold_name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(bold_name, str(bold_path)))
                if italic_path.exists():
                    if italic_name not in pdfmetrics.getRegisteredFontNames():
                        pdfmetrics.registerFont(TTFont(italic_name, str(italic_path)))
                else:
                    italic_name = reg_name
                if bi_path.exists():
                    if bi_name not in pdfmetrics.getRegisteredFontNames():
                        pdfmetrics.registerFont(TTFont(bi_name, str(bi_path)))
                else:
                    bi_name = bold_name
                
                pdfmetrics.registerFontFamily(
                    reg_name,
                    normal=reg_name,
                    bold=bold_name,
                    italic=italic_name,
                    boldItalic=bi_name
                )
                return reg_name, bold_name

    return "Helvetica", "Helvetica-Bold"


def _linebreaks(value: str) -> str:
    return value.replace("\n", "<br/>")


from html.parser import HTMLParser

class ReportLabHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = []
        self.span_tags_stack = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs_dict = dict(attrs)
        
        if tag in ('p', 'div', 'li'):
            if tag == 'li':
                self.result.append("• ")
        elif tag == 'br':
            self.result.append("<br/>")
        elif tag in ('b', 'strong'):
            self.result.append("<b>")
        elif tag in ('i', 'em'):
            self.result.append("<i>")
        elif tag in ('u', 'ins'):
            self.result.append("<u>")
        elif tag == 'span':
            style = attrs_dict.get('style', '').lower()
            opened = []
            if 'font-weight: bold' in style or 'font-weight:bold' in style:
                self.result.append("<b>")
                opened.append("b")
            if 'font-style: italic' in style or 'font-style:italic' in style:
                self.result.append("<i>")
                opened.append("i")
            if 'text-decoration: underline' in style or 'text-decoration:underline' in style:
                self.result.append("<u>")
                opened.append("u")
            self.span_tags_stack.append(opened)
        elif tag == 'font':
            color = attrs_dict.get('color')
            size = attrs_dict.get('size')
            font_attrs = []
            if color:
                font_attrs.append(f'color="{color}"')
            if size:
                font_attrs.append(f'size="{size}"')
            if font_attrs:
                self.result.append(f"<font {' '.join(font_attrs)}>")
            else:
                self.result.append("<font>")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ('p', 'div', 'li'):
            self.result.append("<br/>")
        elif tag in ('b', 'strong'):
            self.result.append("</b>")
        elif tag in ('i', 'em'):
            self.result.append("</i>")
        elif tag in ('u', 'ins'):
            self.result.append("</u>")
        elif tag == 'span':
            if self.span_tags_stack:
                opened = self.span_tags_stack.pop()
                for t in reversed(opened):
                    self.result.append(f"</{t}>")
        elif tag == 'font':
            self.result.append("</font>")

    def handle_data(self, data):
        escaped_data = data.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.result.append(escaped_data)

    def handle_entityref(self, name):
        self.result.append(f"&{name};")

    def handle_charref(self, name):
        self.result.append(f"&#{name};")


def clean_html_for_reportlab(html: str) -> str:
    if not html:
        return ""
    import re
    # Normalise linebreaks and strip whitespace
    html = html.replace("\r\n", "").replace("\n", "").strip()
    
    parser = ReportLabHTMLParser()
    parser.feed(html)
    parsed_text = "".join(parser.result)
    
    # Merge excessive br tags and strip trailing ones
    parsed_text = re.sub(r"(<br/>){3,}", "<br/><br/>", parsed_text)
    parsed_text = re.sub(r"(<br/>)+$", "", parsed_text)
    return parsed_text


def _payment_content(record: TuitionRecord, settings: dict[str, str]) -> str:
    from app.services.vietqr_service import safe_format_payment_content
    payment_template = settings.get("payment_content_template", "HP {student_code} {month:02d}{year_short}")
    return safe_format_payment_content(
        payment_template,
        record.student.full_name,
        record.student.student_code,
        record.month,
        record.year
    )


def _qr_image(record: TuitionRecord, settings: dict[str, str], image_cls, styles: dict) -> list:
    debt = record.total_amount - (record.paid_amount or 0)
    if debt <= 0:
        from reportlab.platypus import Paragraph, Spacer
        return [
            Spacer(1, 20),
            Paragraph("<font color='#16a34a'><b>ĐÃ THANH TOÁN ĐỦ</b></font>", styles["center_bold"]),
            Spacer(1, 20)
        ]

    bank_id = settings.get("vietqr_bank_id", "").strip()
    account_no = settings.get("vietqr_account_no", "").strip()
    account_name = settings.get("vietqr_account_name", "").strip()
    
    fallback_path = BASE_DIR / "static" / "assets" / "qr.png"
    
    if bank_id and account_no:
        from app.services.vietqr_service import generate_vietqr_url
        t_code = record.transfer_code or _payment_content(record, settings)
        url = generate_vietqr_url(bank_id, account_no, account_name, debt, t_code)
        
        import urllib.request
        from io import BytesIO
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                img_data = BytesIO(response.read())
                image = image_cls(img_data, width=58 * 2.834645669, height=58 * 2.834645669)
                image.hAlign = "CENTER"
                return [image]
        except Exception as e:
            print(f"Error downloading VietQR image in ReportLab: {e}")
            
    if fallback_path.exists():
        image = image_cls(str(fallback_path), width=58 * 2.834645669, height=58 * 2.834645669)
        image.hAlign = "CENTER"
        return [image]
    return []


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


def generate_revenue_report_pdf(db: Session, month: int | list[int], year: int, settings: dict[str, str]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from sqlalchemy import func, select, distinct
    from app.models import TuitionRecord, TuitionRecordItem

    if isinstance(month, int):
        months = [month]
    else:
        months = month

    period_title, _ = format_period_label(months, year)

    # Lấy dữ liệu
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

    regular_font, bold_font = _register_vietnamese_fonts()
    
    styles = {
        "normal": ParagraphStyle("normal", fontName=regular_font, fontSize=10.5, leading=14, alignment=TA_LEFT),
        "bold": ParagraphStyle("bold", fontName=bold_font, fontSize=10.5, leading=14, alignment=TA_LEFT),
        "center_bold": ParagraphStyle("center_bold", fontName=bold_font, fontSize=11, leading=14, alignment=TA_CENTER),
        "header_white": ParagraphStyle("header_white", fontName=bold_font, fontSize=10.5, leading=14, alignment=TA_CENTER, textColor=colors.white),
        "right_bold": ParagraphStyle("right_bold", fontName=bold_font, fontSize=10.5, leading=14, alignment=TA_RIGHT),
        "right_normal": ParagraphStyle("right_normal", fontName=regular_font, fontSize=10.5, leading=14, alignment=TA_RIGHT),
        "center_normal": ParagraphStyle("center_normal", fontName=regular_font, fontSize=10.5, leading=14, alignment=TA_CENTER),
        "title": ParagraphStyle("title", fontName=bold_font, fontSize=18, leading=22, alignment=TA_CENTER, textColor=colors.HexColor("#0F2A33")),
        "section_title": ParagraphStyle("section_title", fontName=bold_font, fontSize=13, leading=16, alignment=TA_LEFT, textColor=colors.HexColor("#0F766E"))
    }

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4, # Khổ đứng
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    story = []

    # Tên trung tâm ở góc trên bên trái
    center_logo = settings.get("center_logo_text", "HH EDUCATION")
    story.append(Paragraph(f"<b>{center_logo.upper()}</b>", ParagraphStyle("logo", fontName=bold_font, fontSize=11, leading=14, textColor=colors.HexColor("#0F766E"))))
    story.append(Spacer(1, 4 * mm))

    # Tiêu đề báo cáo
    story.append(Paragraph(f"BÁO CÁO DOANH THU {period_title}", styles["title"]))
    import datetime
    now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    story.append(Paragraph(f"Ngày xuất báo cáo: {now_str}", ParagraphStyle("sub", fontName=regular_font, fontSize=9, leading=12, alignment=TA_CENTER, textColor=colors.HexColor("#526672"))))
    story.append(Spacer(1, 10 * mm))

    # Phần 1: Tổng quan doanh thu
    story.append(Paragraph("I. TỔNG QUAN DOANH THU", styles["section_title"]))
    story.append(Spacer(1, 3 * mm))

    overview_rows = [
        [Paragraph("Chỉ số", styles["header_white"]), Paragraph("Giá trị", styles["header_white"])]
    ]
    
    overview_data = [
        ("Tổng số học sinh đã chốt học phí", f"{total_students} học sinh", False),
        ("Tổng số lớp học phát sinh học phí", f"{total_classes} lớp", False),
        ("Tổng số buổi học đã tham gia", f"{total_sessions} buổi", False),
        ("Tổng doanh thu thực tế", f"{format_currency(total_revenue)} VNĐ", True)
    ]
    
    for label, val, is_bold in overview_data:
        v_style = styles["bold"] if is_bold else styles["normal"]
        overview_rows.append([
            Paragraph(label, styles["normal"]),
            Paragraph(val, v_style)
        ])
        
    overview_table = Table(overview_rows, colWidths=[110 * mm, 70 * mm])
    overview_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (1, 0), colors.HexColor("#0F766E")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5DC")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("BACKGROUND", (1, 4), (1, 4), colors.HexColor("#E6F4F1")), # tô màu tổng doanh thu
    ]))
    story.append(overview_table)
    story.append(Spacer(1, 10 * mm))

    # Phần 2: Chi tiết doanh thu theo lớp học
    story.append(Paragraph("II. CHI TIẾT DOANH THU THEO TỪNG LỚP HỌC", styles["section_title"]))
    story.append(Spacer(1, 3 * mm))

    class_headers = [
        Paragraph("STT", styles["header_white"]),
        Paragraph("Tên lớp", styles["header_white"]),
        Paragraph("Môn học", styles["header_white"]),
        Paragraph("Sỹ số", styles["header_white"]),
        Paragraph("Số buổi", styles["header_white"]),
        Paragraph("Doanh thu (VNĐ)", styles["header_white"]),
        Paragraph("Tỷ lệ", styles["header_white"])
    ]
    
    class_table_rows = [class_headers]
    for idx, r in enumerate(class_rows, start=1):
        ratio = r.revenue / total_revenue if total_revenue > 0 else 0
        ratio_str = f"{ratio * 100:.1f}%"
        class_table_rows.append([
            Paragraph(str(idx), styles["center_normal"]),
            Paragraph(r.class_name, styles["bold"]),
            Paragraph(r.subject, styles["normal"]),
            Paragraph(str(r.students_count), styles["center_normal"]),
            Paragraph(str(r.sessions_count), styles["center_normal"]),
            Paragraph(format_currency(r.revenue), styles["right_bold"]),
            Paragraph(ratio_str, styles["right_normal"])
        ])
        
    # Dòng tổng cộng
    class_table_rows.append([
        Paragraph("Tổng cộng", styles["bold"]),
        "",
        "",
        Paragraph(str(sum(r.students_count for r in class_rows)), styles["center_bold"]),
        Paragraph(str(sum(r.sessions_count for r in class_rows)), styles["center_bold"]),
        Paragraph(format_currency(total_revenue), styles["right_bold"]),
        Paragraph("100.0%", styles["right_bold"])
    ])
    
    # Tổng chiều ngang 180mm (A4 printable width)
    class_table = Table(class_table_rows, colWidths=[12 * mm, 38 * mm, 38 * mm, 18 * mm, 18 * mm, 38 * mm, 18 * mm])
    class_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F766E")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5DC")),
        ("SPAN", (0, -1), (2, -1)), # gộp "Tổng cộng"
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E6F4F1")), # tô màu dòng tổng
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    
    # Zebra striping
    for r_idx in range(1, len(class_table_rows) - 1):
        if r_idx % 2 == 0:
            class_table.setStyle(TableStyle([
                ("BACKGROUND", (0, r_idx), (-1, r_idx), colors.HexColor("#F8FAFC"))
            ]))
            
    story.append(class_table)
    doc.build(story)
    return buffer.getvalue()


def render_payroll_html(records, settings: dict[str, str]) -> str:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    env = Environment(
        loader=FileSystemLoader(str(BASE_DIR / "templates")),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["currency"] = format_currency
    template = env.get_template("phieu-luong.html")
    logo_path = (BASE_DIR / "static" / "assets" / "logo.png").resolve().as_uri()
    
    if not isinstance(records, list):
        records_list = [records]
    else:
        records_list = records
        
    return template.render(records=records_list, settings=settings, logo_path=logo_path)


def payroll_to_pdf(records, settings: dict[str, str]) -> bytes:
    if not isinstance(records, list):
        records_list = [records]
    else:
        records_list = records
        
    html = render_payroll_html(records_list, settings)
    try:
        return html_to_pdf(html)
    except Exception:
        if len(records_list) == 1:
            return render_payroll_reportlab(records_list[0], settings)
        return render_multiple_payrolls_reportlab(records_list, settings)


def render_payroll_reportlab(record, settings: dict[str, str]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    
    regular_font, bold_font = _register_vietnamese_fonts()
    styles = {
        "normal": ParagraphStyle("normal", fontName=regular_font, fontSize=10.5, leading=14, alignment=TA_LEFT),
        "bold": ParagraphStyle("bold", fontName=bold_font, fontSize=10.5, leading=14, alignment=TA_LEFT),
        "center_bold": ParagraphStyle("center_bold", fontName=bold_font, fontSize=10.5, leading=14, alignment=TA_CENTER),
        "center_normal": ParagraphStyle("center_normal", fontName=regular_font, fontSize=10.5, leading=14, alignment=TA_CENTER),
        "right_bold": ParagraphStyle("right_bold", fontName=bold_font, fontSize=10.5, leading=14, alignment=TA_RIGHT),
        "title": ParagraphStyle("title", fontName=bold_font, fontSize=16, leading=22, alignment=TA_CENTER),
    }
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    
    story = []
    
    logo_elements = []
    logo_file = BASE_DIR / "static" / "assets" / "logo.png"
    if logo_file.exists():
        from PIL import Image as PILImage
        try:
            with PILImage.open(logo_file) as img:
                w, h = img.size
            aspect = h / w
            img_w = 45 * mm
            img_h = img_w * aspect
            if img_h > 30 * mm:
                img_h = 30 * mm
                img_w = img_h / aspect
            logo_elements.append(RLImage(str(logo_file), width=img_w, height=img_h))
        except Exception:
            pass
            
    if not logo_elements:
        logo_elements.append(Paragraph(_linebreaks(settings.get("center_logo_text", "HH\nEDUCATION")), styles["center_bold"]))
        
    header = Table(
        [
            [
                logo_elements,
                [
                    Paragraph(settings.get("center_name", ""), styles["bold"]),
                    Paragraph(settings.get("center_address", ""), styles["normal"]),
                    Paragraph(settings.get("center_hotline", ""), styles["normal"]),
                ],
            ]
        ],
        colWidths=[55 * mm, 125 * mm],
    )
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(header)
    story.append(Spacer(1, 10 * mm))
    
    story.append(Paragraph("PHIẾU XÁC NHẬN LƯƠNG GIÁO VIÊN", styles["title"]))
    story.append(Paragraph(f"Kỳ lương: Tháng {record.month:02d} năm {record.year}", styles["center_bold"]))
    story.append(Spacer(1, 8 * mm))
    
    meta_data = [
        [Paragraph("<b>Họ và tên:</b>", styles["normal"]), Paragraph(record.teacher.full_name, styles["bold"])],
        [Paragraph("<b>Số điện thoại:</b>", styles["normal"]), Paragraph(record.teacher.phone or "-", styles["normal"])],
        [Paragraph("<b>Địa chỉ email:</b>", styles["normal"]), Paragraph(record.teacher.email or "-", styles["normal"])],
    ]
    meta_table = Table(meta_data, colWidths=[35 * mm, 145 * mm])
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 6 * mm))
    
    table_data = [
        [
            Paragraph("<b>Lớp / Môn học</b>", styles["center_bold"]),
            Paragraph("<b>Số buổi dạy</b>", styles["center_bold"]),
            Paragraph("<b>Doanh thu lớp</b>", styles["center_bold"]),
            Paragraph("<b>Hình thức tính</b>", styles["center_bold"]),
            Paragraph("<b>Đơn giá / Hệ số</b>", styles["center_bold"]),
            Paragraph("<b>Thành tiền</b>", styles["center_bold"]),
        ]
    ]
    
    for item in record.items:
        rev_str = format_currency(item.class_revenue) if item.salary_type == "coefficient" else "-"
        type_str = "Lương cứng" if item.salary_type == "fixed" else "Doanh thu"
        
        if item.salary_type == "fixed":
            sess_present = getattr(item, "sessions_present", 0)
            sess_late = getattr(item, "sessions_late", 0)
            sess_absent = getattr(item, "sessions_absent", 0)
            sess_p = Paragraph(f"{item.sessions_count} buổi<br/><font size='8' color='grey'>(Đủ: {sess_present}, Trễ: {sess_late}, Vắng: {sess_absent})</font>", styles["center_normal"])
            
            fps = getattr(item, "fixed_present_salary", 0) or getattr(item, "applied_rate", 0)
            fls = getattr(item, "fixed_late_salary", 0) or round(getattr(item, "applied_rate", 0) * 0.7)
            fas = getattr(item, "fixed_absent_salary", 0)
            rate_p = Paragraph(f"<font size='8'>Đủ: {format_currency(int(fps))}<br/>Trễ: {format_currency(int(fls))}<br/>Vắng: {format_currency(int(fas))}</font>", styles["normal"])
        else:
            sess_p = Paragraph(str(item.sessions_count), styles["center_normal"])
            rate_p = Paragraph(str(item.applied_rate), styles["center_normal"])
            
        table_data.append([
            Paragraph(item.class_name, styles["normal"]),
            sess_p,
            Paragraph(rev_str, styles["normal"]),
            Paragraph(type_str, styles["normal"]),
            rate_p,
            Paragraph(format_currency(item.calculated_amount), styles["normal"]),
        ])
        
    table_data.append([
        Paragraph("<b>TỔNG CỘNG LƯƠNG NHẬN (VNĐ):</b>", styles["right_bold"]),
        "", "", "", "",
        Paragraph(format_currency(record.total_amount), styles["right_bold"]),
    ])
    
    col_widths = [45 * mm, 20 * mm, 30 * mm, 28 * mm, 27 * mm, 30 * mm]
    details_table = Table(table_data, colWidths=col_widths)
    
    t_style = [
        ("BOX", (0, 0), (-1, -2), 0.5, colors.black),
        ("INNERGRID", (0, 0), (-1, -2), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("SPAN", (0, -1), (4, -1)),
    ]
    details_table.setStyle(TableStyle(t_style))
    story.append(details_table)
    story.append(Spacer(1, 15 * mm))
    
    sig_data = [
        [Paragraph("<b>Giáo viên ký nhận</b>", styles["center_bold"]), Paragraph("<b>Người lập phiếu</b>", styles["center_bold"])],
        [Paragraph("<i>(Ký và ghi rõ họ tên)</i>", styles["center_normal"]), Paragraph("<i>(Ký và ghi rõ họ tên)</i>", styles["center_normal"])],
    ]
    sig_table = Table(sig_data, colWidths=[90 * mm, 90 * mm])
    sig_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 40 * mm),
    ]))
    story.append(sig_table)
    
    doc.build(story)
    return buffer.getvalue()


def render_multiple_payrolls_reportlab(records: list, settings: dict[str, str]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak
    
    regular_font, bold_font = _register_vietnamese_fonts()
    styles = {
        "normal": ParagraphStyle("normal", fontName=regular_font, fontSize=10.5, leading=14, alignment=TA_LEFT),
        "bold": ParagraphStyle("bold", fontName=bold_font, fontSize=10.5, leading=14, alignment=TA_LEFT),
        "center_bold": ParagraphStyle("center_bold", fontName=bold_font, fontSize=10.5, leading=14, alignment=TA_CENTER),
        "center_normal": ParagraphStyle("center_normal", fontName=regular_font, fontSize=10.5, leading=14, alignment=TA_CENTER),
        "right_bold": ParagraphStyle("right_bold", fontName=bold_font, fontSize=10.5, leading=14, alignment=TA_RIGHT),
        "title": ParagraphStyle("title", fontName=bold_font, fontSize=16, leading=22, alignment=TA_CENTER),
    }
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    
    story = []
    
    for idx, record in enumerate(records):
        if idx > 0:
            story.append(PageBreak())
            
        logo_elements = []
        logo_file = BASE_DIR / "static" / "assets" / "logo.png"
        if logo_file.exists():
            from PIL import Image as PILImage
            try:
                with PILImage.open(logo_file) as img:
                    w, h = img.size
                aspect = h / w
                img_w = 45 * mm
                img_h = img_w * aspect
                if img_h > 30 * mm:
                    img_h = 30 * mm
                    img_w = img_h / aspect
                logo_elements.append(RLImage(str(logo_file), width=img_w, height=img_h))
            except Exception:
                pass
                
        if not logo_elements:
            logo_elements.append(Paragraph(_linebreaks(settings.get("center_logo_text", "HH\nEDUCATION")), styles["center_bold"]))
            
        header = Table(
            [
                [
                    logo_elements,
                    [
                        Paragraph(settings.get("center_name", ""), styles["bold"]),
                        Paragraph(settings.get("center_address", ""), styles["normal"]),
                        Paragraph(settings.get("center_hotline", ""), styles["normal"]),
                    ],
                ]
            ],
            colWidths=[45 * mm, 135 * mm],
        )
        header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, 0), "CENTER"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(header)
        story.append(Spacer(1, 10 * mm))
        
        story.append(Paragraph("PHIẾU XÁC NHẬN LƯƠNG GIÁO VIÊN", styles["title"]))
        story.append(Paragraph(f"Kỳ lương: Tháng {record.month:02d} năm {record.year}", styles["center_bold"]))
        story.append(Spacer(1, 8 * mm))
        
        meta_data = [
            [Paragraph("<b>Họ và tên:</b>", styles["normal"]), Paragraph(record.teacher.full_name, styles["bold"])],
            [Paragraph("<b>Số điện thoại:</b>", styles["normal"]), Paragraph(record.teacher.phone or "-", styles["normal"])],
            [Paragraph("<b>Địa chỉ email:</b>", styles["normal"]), Paragraph(record.teacher.email or "-", styles["normal"])],
        ]
        meta_table = Table(meta_data, colWidths=[35 * mm, 145 * mm])
        meta_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 6 * mm))
        
        table_data = [
            [
                Paragraph("<b>Lớp / Môn học</b>", styles["center_bold"]),
                Paragraph("<b>Số buổi dạy</b>", styles["center_bold"]),
                Paragraph("<b>Doanh thu lớp</b>", styles["center_bold"]),
                Paragraph("<b>Hình thức tính</b>", styles["center_bold"]),
                Paragraph("<b>Đơn giá / Hệ số</b>", styles["center_bold"]),
                Paragraph("<b>Thành tiền</b>", styles["center_bold"]),
            ]
        ]
        
        for item in record.items:
            rev_str = format_currency(item.class_revenue) if item.salary_type == "coefficient" else "-"
            type_str = "Lương cứng" if item.salary_type == "fixed" else "Doanh thu"
            
            if item.salary_type == "fixed":
                sess_present = getattr(item, "sessions_present", 0)
                sess_late = getattr(item, "sessions_late", 0)
                sess_absent = getattr(item, "sessions_absent", 0)
                sess_p = Paragraph(f"{item.sessions_count} buổi<br/><font size='8' color='grey'>(Đủ: {sess_present}, Trễ: {sess_late}, Vắng: {sess_absent})</font>", styles["center_normal"])
                
                fps = getattr(item, "fixed_present_salary", 0) or getattr(item, "applied_rate", 0)
                fls = getattr(item, "fixed_late_salary", 0) or round(getattr(item, "applied_rate", 0) * 0.7)
                fas = getattr(item, "fixed_absent_salary", 0)
                rate_p = Paragraph(f"<font size='8'>Đủ: {format_currency(int(fps))}<br/>Trễ: {format_currency(int(fls))}<br/>Vắng: {format_currency(int(fas))}</font>", styles["normal"])
            else:
                sess_p = Paragraph(str(item.sessions_count), styles["center_normal"])
                rate_p = Paragraph(str(item.applied_rate), styles["center_normal"])
                
            table_data.append([
                Paragraph(item.class_name, styles["normal"]),
                sess_p,
                Paragraph(rev_str, styles["normal"]),
                Paragraph(type_str, styles["normal"]),
                rate_p,
                Paragraph(format_currency(item.calculated_amount), styles["normal"]),
            ])
            
        table_data.append([
            Paragraph("<b>TỔNG CỘNG LƯƠNG NHẬN (VNĐ):</b>", styles["right_bold"]),
            "", "", "", "",
            Paragraph(format_currency(record.total_amount), styles["right_bold"]),
        ])
        
        col_widths = [45 * mm, 20 * mm, 30 * mm, 28 * mm, 27 * mm, 30 * mm]
        details_table = Table(table_data, colWidths=col_widths)
        
        t_style = [
            ("BOX", (0, 0), (-1, -2), 0.5, colors.black),
            ("INNERGRID", (0, 0), (-1, -2), 0.5, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("SPAN", (0, -1), (4, -1)),
        ]
        details_table.setStyle(TableStyle(t_style))
        story.append(details_table)
        story.append(Spacer(1, 15 * mm))
        
        sig_data = [
            [Paragraph("<b>Giáo viên ký nhận</b>", styles["center_bold"]), Paragraph("<b>Người lập phiếu</b>", styles["center_bold"])],
            [Paragraph("<i>(Ký và ghi rõ họ tên)</i>", styles["center_normal"]), Paragraph("<i>(Ký và ghi rõ họ tên)</i>", styles["center_normal"])],
        ]
        sig_table = Table(sig_data, colWidths=[90 * mm, 90 * mm])
        sig_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 40 * mm),
        ]))
        story.append(sig_table)
        
    doc.build(story)
    return buffer.getvalue()
