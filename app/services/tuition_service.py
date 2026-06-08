from __future__ import annotations

from dataclasses import dataclass

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
            if class_id:
                # Nếu lọc theo lớp, chỉ xóa các chi tiết học phí của lớp đó
                db.execute(
                    delete(TuitionRecordItem).where(
                        TuitionRecordItem.record_id == record.id,
                        TuitionRecordItem.class_id == class_id
                    )
                )
                db.flush()
            else:
                # Nếu không lọc lớp, xóa toàn bộ bản ghi cũ
                db.delete(record)
                db.flush()
                record = None

        if not record:
            record = TuitionRecord(
                student_id=preview.student_id,
                month=month,
                year=year,
                total_sessions=0,
                total_amount=0,
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
        
        # Nếu không còn chi tiết học phí nào (ví dụ bị xóa hết), có thể xóa bản ghi TuitionRecord
        if not items_in_db:
            db.delete(record)
            db.flush()
        else:
            record.total_sessions = sum(it.sessions for it in items_in_db)
            record.total_amount = sum(it.amount for it in items_in_db)
            
            # Ensure transfer_code is set
            if not record.transfer_code:
                year_short = str(record.year)[-2:]
                from app.services.vietqr_service import normalize_transfer_content
                raw_code = f"HP {preview.student_code} {record.month:02d}{year_short}"
                record.transfer_code = normalize_transfer_content(raw_code)
                
            # Recalculate status based on paid_amount and new total_amount
            if record.paid_amount >= record.total_amount:
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

