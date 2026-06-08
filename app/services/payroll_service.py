from __future__ import annotations

from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session

from app.database import BASE_DIR
from app.timezone import month_bounds, now_vietnam


def calculate_class_revenue(db: Session, class_id: int, month: int, year: int) -> int:
    from app.models import TuitionRecordItem, TuitionRecord
    revenue = db.scalar(
        select(func.sum(TuitionRecordItem.amount))
        .join(TuitionRecord, TuitionRecordItem.record_id == TuitionRecord.id)
        .where(
            TuitionRecordItem.class_id == class_id,
            TuitionRecord.month == month,
            TuitionRecord.year == year
        )
    ) or 0
    return revenue


def calculate_class_sessions(db: Session, class_id: int, month: int, year: int) -> int:
    """Đếm số buổi dạy từ bảng Attendance (học sinh) – dùng cho tính học phí."""
    from app.models import Attendance
    start_dt, end_dt = month_bounds(year, month)
    sessions = db.scalar(
        select(func.count(func.distinct(Attendance.date)))
        .where(
            Attendance.class_id == class_id,
            Attendance.date >= start_dt,
            Attendance.date < end_dt
        )
    ) or 0
    return sessions


def calculate_teacher_sessions(db: Session, teacher_id: int, class_id: int, month: int, year: int) -> int:
    """Đếm số buổi dạy thực tế của giáo viên từ bảng TeacherAttendance (trạng thái P hoặc M)."""
    from app.models import TeacherAttendance
    start_dt, end_dt = month_bounds(year, month)
    sessions = db.scalar(
        select(func.count(TeacherAttendance.id))
        .where(
            TeacherAttendance.teacher_id == teacher_id,
            TeacherAttendance.class_id == class_id,
            TeacherAttendance.date >= start_dt,
            TeacherAttendance.date < end_dt,
            TeacherAttendance.status.in_(["P", "M"]),
        )
    ) or 0
    return sessions


def build_payroll_preview(db: Session, month: int, year: int) -> list[dict]:
    from app.models import Teacher, TeacherSalaryRecord, TeacherClassAssignment

    teachers = db.scalars(select(Teacher).where(Teacher.is_active.is_(True))).all()

    results = []
    for teacher in teachers:
        # Tính nợ lương cũ
        prior_unpaid_stmt = (
            select(func.coalesce(func.sum(TeacherSalaryRecord.total_amount - TeacherSalaryRecord.paid_amount), 0))
            .where(
                TeacherSalaryRecord.teacher_id == teacher.id,
                (TeacherSalaryRecord.year < year) | ((TeacherSalaryRecord.year == year) & (TeacherSalaryRecord.month < month))
            )
        )
        prior_unpaid = db.scalar(prior_unpaid_stmt) or 0

        record = db.scalar(
            select(TeacherSalaryRecord)
            .where(
                TeacherSalaryRecord.teacher_id == teacher.id,
                TeacherSalaryRecord.month == month,
                TeacherSalaryRecord.year == year
            )
        )

        if record:
            class_items = []
            for item in record.items:
                class_items.append({
                    "class_id": item.class_id,
                    "class_name": item.class_name,
                    "sessions": item.sessions_count,
                    "sessions_present": getattr(item, "sessions_present", 0),
                    "sessions_late": getattr(item, "sessions_late", 0),
                    "sessions_absent": getattr(item, "sessions_absent", 0),
                    "revenue": item.class_revenue,
                    "salary_type": item.salary_type,
                    "applied_rate": item.applied_rate,
                    "fixed_present_salary": getattr(item, "fixed_present_salary", 0),
                    "fixed_late_salary": getattr(item, "fixed_late_salary", 0),
                    "fixed_absent_salary": getattr(item, "fixed_absent_salary", 0),
                    "amount": item.calculated_amount
                })
            results.append({
                "teacher_id": teacher.id,
                "teacher_name": teacher.full_name,
                "is_locked": True,
                "total_salary": record.total_amount,
                "paid_amount": record.paid_amount,
                "payment_status": record.payment_status,
                "prior_unpaid": prior_unpaid,
                "grand_total": record.total_amount + prior_unpaid,
                "classes": class_items
            })
        else:
            class_items = []
            total_salary = 0

            # Lấy tất cả phân công của giáo viên này (cả hoạt động và ngừng dạy)
            assignments = db.scalars(
                select(TeacherClassAssignment)
                .where(
                    TeacherClassAssignment.teacher_id == teacher.id,
                )
            ).all()

            # Fallback: nếu chưa có assignment mới, dùng cách cũ (classes.teacher_id)
            if not assignments:
                from app.models import Class
                teacher_classes = db.scalars(
                    select(Class)
                    .where(Class.teacher_id == teacher.id, Class.is_active.is_(True))
                ).all()

                for class_ in teacher_classes:
                    sessions = calculate_class_sessions(db, class_.id, month, year)
                    revenue = calculate_class_revenue(db, class_.id, month, year)

                    if class_.salary_type == "fixed":
                        applied_rate = float(class_.fixed_salary_per_session)
                        amount = sessions * class_.fixed_salary_per_session
                        sessions_present = sessions
                        sessions_late = 0
                        sessions_absent = 0
                        fps = class_.fixed_present_salary
                        fls = class_.fixed_late_salary
                        fas = class_.fixed_absent_salary
                    else:  # "coefficient"
                        if class_.salary_coefficient != 1.0:
                            applied_rate = class_.salary_coefficient
                        else:
                            applied_rate = teacher.default_salary_coefficient
                        amount = int(revenue * applied_rate)
                        sessions_present = sessions
                        sessions_late = 0
                        sessions_absent = 0
                        fps = 0
                        fls = 0
                        fas = 0

                    class_items.append({
                        "class_id": class_.id,
                        "class_name": class_.name,
                        "sessions": sessions,
                        "revenue": revenue,
                        "salary_type": class_.salary_type,
                        "applied_rate": applied_rate,
                        "amount": amount,
                        "sessions_present": sessions_present,
                        "sessions_late": sessions_late,
                        "sessions_absent": sessions_absent,
                        "fixed_present_salary": fps,
                        "fixed_late_salary": fls,
                        "fixed_absent_salary": fas,
                    })
                    total_salary += amount
            else:
                # Dùng cơ chế mới: TeacherClassAssignment + TeacherAttendance
                for assignment in assignments:
                    # Lấy điểm danh của giáo viên trong kỳ
                    from app.models import TeacherAttendance
                    start_dt, end_dt = month_bounds(year, month)
                    attendances = db.scalars(
                        select(TeacherAttendance)
                        .where(
                            TeacherAttendance.teacher_id == teacher.id,
                            TeacherAttendance.class_id == assignment.class_id,
                            TeacherAttendance.date >= start_dt,
                            TeacherAttendance.date < end_dt
                        )
                    ).all()

                    # Nếu phân công đã ngưng hoạt động và không có dữ liệu điểm danh nào trong kỳ thì bỏ qua
                    if not assignment.is_active and not attendances:
                        continue

                    count_p = sum(1 for a in attendances if a.status == "P")
                    count_m = sum(1 for a in attendances if a.status == "M")
                    count_v = sum(1 for a in attendances if a.status == "V")
                    sessions = count_p + count_m

                    revenue = calculate_class_revenue(db, assignment.class_id, month, year)

                    if assignment.salary_type == "fixed":
                        applied_rate = float(assignment.fixed_salary_per_session)
                        amount = (count_p * assignment.fixed_present_salary) + \
                                 (count_m * assignment.fixed_late_salary) + \
                                 (count_v * assignment.fixed_absent_salary)
                        fps = assignment.fixed_present_salary
                        fls = assignment.fixed_late_salary
                        fas = assignment.fixed_absent_salary
                    else:  # "coefficient"
                        applied_rate = assignment.salary_coefficient
                        amount = int(revenue * applied_rate)
                        fps = 0
                        fls = 0
                        fas = 0

                    # Lấy tên lớp
                    from app.models import Class
                    class_ = db.get(Class, assignment.class_id)
                    class_name = class_.name if class_ else str(assignment.class_id)

                    class_items.append({
                        "class_id": assignment.class_id,
                        "class_name": class_name,
                        "sessions": sessions,
                        "revenue": revenue,
                        "salary_type": assignment.salary_type,
                        "applied_rate": applied_rate,
                        "amount": amount,
                        "sessions_present": count_p,
                        "sessions_late": count_m,
                        "sessions_absent": count_v,
                        "fixed_present_salary": fps,
                        "fixed_late_salary": fls,
                        "fixed_absent_salary": fas,
                    })
                    total_salary += amount

            results.append({
                "teacher_id": teacher.id,
                "teacher_name": teacher.full_name,
                "is_locked": False,
                "total_salary": total_salary,
                "paid_amount": 0,
                "payment_status": "unpaid",
                "prior_unpaid": prior_unpaid,
                "grand_total": total_salary + prior_unpaid,
                "classes": class_items
            })
    return results


def lock_payroll_period(db: Session, month: int, year: int, user_id: int) -> list:
    from app.models import TeacherSalaryRecord, TeacherSalaryRecordItem

    # Kiểm tra xem có bảng ghi nào của tháng/năm này đã khóa chưa
    existing = db.scalar(
        select(TeacherSalaryRecord)
        .where(
            TeacherSalaryRecord.month == month,
            TeacherSalaryRecord.year == year,
            TeacherSalaryRecord.is_locked.is_(True)
        )
    )
    if existing:
        raise ValueError(f"Bảng lương tháng {month:02d}/{year} đã được khóa trước đó.")

    preview_list = build_payroll_preview(db, month, year)
    records = []

    for p in preview_list:
        # Xóa các bản ghi cũ nếu có để ghi đè (chỉ khi chưa khóa)
        db.execute(
            delete(TeacherSalaryRecord)
            .where(
                TeacherSalaryRecord.teacher_id == p["teacher_id"],
                TeacherSalaryRecord.month == month,
                TeacherSalaryRecord.year == year
            )
        )

        record = TeacherSalaryRecord(
            teacher_id=p["teacher_id"],
            month=month,
            year=year,
            total_amount=p["total_salary"],
            is_locked=True,
            locked_at=now_vietnam(),
            locked_by=user_id
        )
        db.add(record)
        db.flush()

        for c in p["classes"]:
            item = TeacherSalaryRecordItem(
                record_id=record.id,
                class_id=c["class_id"],
                class_name=c["class_name"],
                sessions_count=c["sessions"],
                class_revenue=c["revenue"],
                salary_type=c["salary_type"],
                applied_rate=c["applied_rate"],
                calculated_amount=c["amount"],
                sessions_present=c.get("sessions_present", 0),
                sessions_late=c.get("sessions_late", 0),
                sessions_absent=c.get("sessions_absent", 0),
                fixed_present_salary=c.get("fixed_present_salary", 0),
                fixed_late_salary=c.get("fixed_late_salary", 0),
                fixed_absent_salary=c.get("fixed_absent_salary", 0),
            )
            db.add(item)
        records.append(record)

    db.commit()
    return records


def allocate_teacher_payment(db: Session, teacher_id: int, total_paid_amount: int, month: int, year: int) -> None:
    """Phân bổ khoản chi trả lương gộp cho giáo viên.

    Tự động tất toán các tháng cũ còn nợ theo thứ tự thời gian (FIFO)
    trước khi dồn số tiền còn lại vào tháng hiện tại.
    """
    from app.models import TeacherSalaryRecord
    records = db.scalars(
        select(TeacherSalaryRecord)
        .where(
            TeacherSalaryRecord.teacher_id == teacher_id,
            (TeacherSalaryRecord.year < year) | ((TeacherSalaryRecord.year == year) & (TeacherSalaryRecord.month <= month))
        )
        .order_by(TeacherSalaryRecord.year.asc(), TeacherSalaryRecord.month.asc())
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
