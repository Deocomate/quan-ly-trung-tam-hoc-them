from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Attendance, Class, Enrollment, Student, TuitionPeriod, TuitionRecord, TuitionRecordItem, User
from app.timezone import month_bounds, now_vietnam


@dataclass
class TuitionItemPreview:
    class_id: int
    class_name: str
    subject: str
    sessions: int
    unit_fee: int
    amount: int
    notes: str


@dataclass
class TuitionPreview:
    student_id: int
    student_code: str
    student_name: str
    total_sessions: int
    total_amount: int
    items: list[TuitionItemPreview]
    prior_debt: int = 0
    grand_total: int = 0


def get_period(db: Session, month: int, year: int) -> TuitionPeriod | None:
    return db.scalar(select(TuitionPeriod).where(TuitionPeriod.month == month, TuitionPeriod.year == year))


def is_period_locked(db: Session, month: int, year: int) -> bool:
    period = get_period(db, month, year)
    return bool(period and period.is_locked)


def build_tuition_preview(db: Session, month: int, year: int, class_id: int | None = None) -> list[TuitionPreview]:
    start, end = month_bounds(year, month)
    enrollment_stmt = (
        select(Enrollment)
        .join(Enrollment.student)
        .join(Enrollment.class_)
        .options(selectinload(Enrollment.student), selectinload(Enrollment.class_))
        .where(Enrollment.is_active.is_(True), Student.is_active.is_(True), Class.is_active.is_(True))
        .order_by(Student.full_name, Class.name)
    )
    if class_id:
        enrollment_stmt = enrollment_stmt.where(Enrollment.class_id == class_id)
    enrollments = db.scalars(enrollment_stmt).all()

    grouped: dict[int, TuitionPreview] = {}
    for enrollment in enrollments:
        counted_sessions = db.scalar(
            select(func.count(Attendance.id)).where(
                Attendance.student_id == enrollment.student_id,
                Attendance.class_id == enrollment.class_id,
                Attendance.date >= start,
                Attendance.date < end,
                Attendance.status.in_(["P", "M"]),
            )
        ) or 0
        unit_fee = enrollment.custom_fee if enrollment.custom_fee is not None else enrollment.class_.default_fee
        amount = 0 if enrollment.is_exempt else counted_sessions * unit_fee
        notes = "Miễn học phí" if enrollment.is_exempt else (enrollment.notes or "")
        preview = grouped.setdefault(
            enrollment.student_id,
            TuitionPreview(
                student_id=enrollment.student_id,
                student_code=enrollment.student.student_code,
                student_name=enrollment.student.full_name,
                total_sessions=0,
                total_amount=0,
                items=[],
            ),
        )
        preview.items.append(
            TuitionItemPreview(
                class_id=enrollment.class_id,
                class_name=enrollment.class_.name,
                subject=enrollment.class_.subject,
                sessions=counted_sessions,
                unit_fee=unit_fee,
                amount=amount,
                notes=notes,
            )
        )
        preview.total_sessions += counted_sessions
        preview.total_amount += amount

    for preview in grouped.values():
        prior_debt_stmt = (
            select(func.coalesce(func.sum(TuitionRecord.total_amount - TuitionRecord.paid_amount), 0))
            .where(
                TuitionRecord.student_id == preview.student_id,
                (TuitionRecord.year < year) | ((TuitionRecord.year == year) & (TuitionRecord.month < month))
            )
        )
        prior_debt = db.scalar(prior_debt_stmt) or 0
        preview.prior_debt = prior_debt
        preview.grand_total = preview.total_amount + prior_debt

    return list(grouped.values())


def lock_tuition_period(db: Session, month: int, year: int, user: User, class_id: int | None = None) -> list[TuitionRecord]:
    from sqlalchemy import delete
    previews = build_tuition_preview(db, month, year, class_id)
    records: list[TuitionRecord] = []
    for preview in previews:
        record = db.scalar(
            select(TuitionRecord).where(
                TuitionRecord.student_id == preview.student_id,
                TuitionRecord.month == month,
                TuitionRecord.year == year,
            )
        )
        if record:
            # Chỉ xóa chi tiết bên trong, GIỮ LẠI record vỏ
            if class_id:
                db.execute(
                    delete(TuitionRecordItem).where(
                        TuitionRecordItem.record_id == record.id,
                        TuitionRecordItem.class_id == class_id
                    )
                )
            else:
                db.execute(delete(TuitionRecordItem).where(TuitionRecordItem.record_id == record.id))
            db.flush()
            # Cập nhật updated_at khi tính toán lại
            record.updated_at = now_vietnam()
        else:
            record = TuitionRecord(
                student_id=preview.student_id,
                month=month,
                year=year,
                total_sessions=0,
                total_amount=0,
                paid_amount=0,
                created_at=now_vietnam(),
                updated_at=now_vietnam()
            )
            db.add(record)
            db.flush()

        # Thêm các chi tiết học phí mới
        for item in preview.items:
            db.add(
                TuitionRecordItem(
                    record_id=record.id,
                    class_id=item.class_id,
                    class_name=item.class_name,
                    subject=item.subject,
                    sessions=item.sessions,
                    unit_fee=item.unit_fee,
                    amount=item.amount,
                    notes=item.notes,
                )
            )
        db.flush()

        # Tính toán lại tổng số buổi và tổng tiền của TuitionRecord dựa trên toàn bộ các TuitionRecordItem hiện có trong DB
        items_in_db = db.scalars(
            select(TuitionRecordItem).where(TuitionRecordItem.record_id == record.id)
        ).all()
        
        # Nếu không còn chi tiết học phí nào
        if not items_in_db:
            if record.paid_amount == 0:
                db.delete(record)
                db.flush()
                continue
            else:
                record.total_sessions = 0
                record.total_amount = 0
        else:
            record.total_sessions = sum(it.sessions for it in items_in_db)
            record.total_amount = sum(it.amount for it in items_in_db)
            
        # Ensure transfer_code is set
        if not record.transfer_code:
            from app.services.settings_service import get_settings_map
            settings = get_settings_map(db)
            payment_template = settings.get("payment_content_template", "HP {student_code} {month:02d}{year_short}")
            
            from app.services.vietqr_service import safe_format_payment_content, normalize_transfer_content
            raw_code = safe_format_payment_content(
                payment_template,
                preview.student_name,
                preview.student_code,
                record.month,
                record.year
            )
            record.transfer_code = normalize_transfer_content(raw_code)
            
        # Recalculate status based on paid_amount and new total_amount
        if record.paid_amount > record.total_amount:
            record.payment_status = "overpaid"
        elif record.paid_amount == record.total_amount:
            record.payment_status = "paid"
        elif record.paid_amount > 0:
            record.payment_status = "partial"
        else:
            record.payment_status = "unpaid"
            
        records.append(record)

    period = get_period(db, month, year)
    if not period:
        period = TuitionPeriod(month=month, year=year)
        db.add(period)
    period.is_locked = True
    period.locked_at = now_vietnam()
    period.locked_by = user.id
    db.commit()
    return records


def list_records(db: Session, month: int | None = None, year: int | None = None, class_id: int | None = None) -> list[TuitionRecord]:
    stmt = select(TuitionRecord).options(selectinload(TuitionRecord.student), selectinload(TuitionRecord.items))
    if month:
        stmt = stmt.where(TuitionRecord.month == month)
    if year:
        stmt = stmt.where(TuitionRecord.year == year)
    if class_id:
        stmt = stmt.join(TuitionRecord.items).where(TuitionRecordItem.class_id == class_id).distinct()
    stmt = stmt.order_by(TuitionRecord.year.desc(), TuitionRecord.month.desc(), Student.full_name)
    return db.scalars(stmt.join(TuitionRecord.student)).all()


def sync_class_fee_to_records(db: Session, class_id: int, new_fee: int):
    # Tìm các TuitionRecordItem thuộc lớp học này
    items = db.scalars(
        select(TuitionRecordItem)
        .join(TuitionRecordItem.record)
        .where(TuitionRecordItem.class_id == class_id)
    ).all()
    
    updated_records = set()
    for item in items:
        # Tìm phân lớp tương ứng của học sinh này
        enrollment = db.scalar(
            select(Enrollment).where(
                Enrollment.student_id == item.record.student_id,
                Enrollment.class_id == class_id
            )
        )
        # Nếu học sinh không có học phí riêng, đồng bộ học phí mới
        if not enrollment or enrollment.custom_fee is None:
            item.unit_fee = new_fee
            item.amount = 0 if (enrollment and enrollment.is_exempt) else (item.sessions * new_fee)
            updated_records.add(item.record)
            
    # Tính lại tổng tiền của các bản ghi TuitionRecord bị ảnh hưởng
    for record in updated_records:
        record.total_amount = sum(it.amount for it in record.items)
    db.flush()


def sync_enrollment_fee_to_records(db: Session, student_id: int, class_id: int, custom_fee: int | None, is_exempt: bool):
    # Tìm các TuitionRecordItem của học sinh và lớp cụ thể
    items = db.scalars(
        select(TuitionRecordItem)
        .join(TuitionRecordItem.record)
        .where(
            TuitionRecordItem.class_id == class_id,
            TuitionRecord.student_id == student_id
        )
    ).all()
    
    # Lấy học phí mặc định của lớp học để dự phòng
    cls = db.get(Class, class_id)
    default_fee = cls.default_fee if cls else 0
    
    unit_fee = custom_fee if custom_fee is not None else default_fee
    
    updated_records = set()
    for item in items:
        item.unit_fee = unit_fee
        item.amount = 0 if is_exempt else (item.sessions * unit_fee)
        updated_records.add(item.record)
        
    for record in updated_records:
        record.total_amount = sum(it.amount for it in record.items)
    db.flush()


def sync_attendance_to_tuition(db: Session, student_id: int, class_id: int, att_date: date) -> None:
    """Auto-sync: Khi điểm danh thay đổi, tự động cập nhật TuitionRecord đã chốt (nếu có).

    Chỉ cập nhật TuitionRecordItem cụ thể theo student_id + class_id cho tháng/năm
    của att_date. Nếu kỳ chưa chốt hoặc chưa có record → không làm gì.
    """
    month = att_date.month
    year = att_date.year

    # 1. Kiểm tra kỳ đã chốt chưa
    if not is_period_locked(db, month, year):
        return

    # 2. Tìm TuitionRecord đã chốt cho học sinh này
    record = db.scalar(
        select(TuitionRecord).where(
            TuitionRecord.student_id == student_id,
            TuitionRecord.month == month,
            TuitionRecord.year == year,
        )
    )
    if not record:
        return

    # 3. Tìm TuitionRecordItem cho lớp cụ thể
    item = db.scalar(
        select(TuitionRecordItem).where(
            TuitionRecordItem.record_id == record.id,
            TuitionRecordItem.class_id == class_id,
        )
    )
    if not item:
        return

    # 4. Đếm lại số buổi P/M trong tháng
    start, end = month_bounds(year, month)
    new_sessions = db.scalar(
        select(func.count(Attendance.id)).where(
            Attendance.student_id == student_id,
            Attendance.class_id == class_id,
            Attendance.date >= start,
            Attendance.date < end,
            Attendance.status.in_(["P", "M"]),
        )
    ) or 0

    # 5. Lấy thông tin học phí từ Enrollment
    enrollment = db.scalar(
        select(Enrollment).where(
            Enrollment.student_id == student_id,
            Enrollment.class_id == class_id,
        )
    )
    is_exempt = enrollment.is_exempt if enrollment else False

    # 6. Cập nhật item
    item.sessions = new_sessions
    item.amount = 0 if is_exempt else (new_sessions * item.unit_fee)

    # 7. Tính lại tổng cho TuitionRecord
    all_items = db.scalars(
        select(TuitionRecordItem).where(TuitionRecordItem.record_id == record.id)
    ).all()
    record.total_sessions = sum(it.sessions for it in all_items)
    record.total_amount = sum(it.amount for it in all_items)

    # 8. Cập nhật trạng thái thanh toán và updated_at
    if record.paid_amount > record.total_amount:
        record.payment_status = "overpaid"
    elif record.paid_amount == record.total_amount:
        record.payment_status = "paid"
    elif record.paid_amount > 0:
        record.payment_status = "partial"
    else:
        record.payment_status = "unpaid"

    record.updated_at = now_vietnam()
    db.flush()


def check_tuition_staleness(
    db: Session, month: int, year: int, class_id: int | None = None
) -> dict:
    """So sánh dữ liệu TuitionRecord đã chốt với dữ liệu điểm danh realtime.

    Trả về dict: { is_stale, stale_count, details: [...] }
    """
    if not is_period_locked(db, month, year):
        return {"is_stale": False, "stale_count": 0, "details": []}

    # Lấy dữ liệu realtime từ điểm danh
    previews = build_tuition_preview(db, month, year, class_id)
    preview_map: dict[int, tuple] = {}
    for p in previews:
        preview_map[p.student_id] = (p.total_sessions, p.total_amount)

    # Lấy records đã chốt
    records = list_records(db, month, year, class_id)
    record_map: dict[int, tuple] = {}
    for r in records:
        record_map[r.student_id] = (r.total_sessions, r.total_amount, r)

    details = []

    # Kiểm tra records đã chốt vs preview
    all_student_ids = set(preview_map.keys()) | set(record_map.keys())
    for sid in all_student_ids:
        p_sessions, p_amount = preview_map.get(sid, (0, 0))
        if sid in record_map:
            r_sessions, r_amount, rec = record_map[sid]
            if r_sessions != p_sessions or r_amount != p_amount:
                details.append({
                    "student_name": rec.student.full_name,
                    "student_code": rec.student.student_code,
                    "old_sessions": r_sessions,
                    "new_sessions": p_sessions,
                    "old_amount": r_amount,
                    "new_amount": p_amount,
                })

    return {
        "is_stale": len(details) > 0,
        "stale_count": len(details),
        "details": details,
    }


def allocate_student_payment(db: Session, student_id: int, total_paid_amount: int, month: int, year: int) -> None:
    """Phân bổ khoản thu học phí gộp cho học sinh.

    Tự động tất toán các tháng cũ còn nợ theo thứ tự thời gian (FIFO)
    trước khi dồn số tiền còn lại vào tháng hiện tại.
    """
    records = db.scalars(
        select(TuitionRecord)
        .where(
            TuitionRecord.student_id == student_id,
            (TuitionRecord.year < year) | ((TuitionRecord.year == year) & (TuitionRecord.month <= month))
        )
        .order_by(TuitionRecord.year.asc(), TuitionRecord.month.asc())
    ).all()
    
    prior_paid = sum(r.paid_amount for r in records if r.year < year or (r.year == year and r.month < month))
    remaining_pool = prior_paid + total_paid_amount
    for r in records:
        if r.year < year or (r.year == year and r.month < month):
            allocated = min(r.total_amount, remaining_pool)
            r.paid_amount = allocated
            remaining_pool -= allocated
        else:
            r.paid_amount = remaining_pool
            remaining_pool = 0
            
        if r.paid_amount > r.total_amount:
            r.payment_status = "overpaid"
        elif r.paid_amount == r.total_amount:
            r.payment_status = "paid"
        elif r.paid_amount > 0:
            r.payment_status = "partial"
        else:
            r.payment_status = "unpaid"
            
    db.commit()

