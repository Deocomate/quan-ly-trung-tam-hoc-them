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
                    "revenue": item.class_revenue,
                    "salary_type": item.salary_type,
                    "applied_rate": item.applied_rate,
                    "amount": item.calculated_amount
                })
            results.append({
                "teacher_id": teacher.id,
                "teacher_name": teacher.full_name,
                "is_locked": True,
                "total_salary": record.total_amount,
                "classes": class_items
            })
        else:
            class_items = []
            total_salary = 0

            # Lấy tất cả phân công đang hoạt động của giáo viên này
            assignments = db.scalars(
                select(TeacherClassAssignment)
                .where(
                    TeacherClassAssignment.teacher_id == teacher.id,
                    TeacherClassAssignment.is_active.is_(True),
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
                    else:  # "coefficient"
                        if class_.salary_coefficient != 1.0:
                            applied_rate = class_.salary_coefficient
                        else:
                            applied_rate = teacher.default_salary_coefficient
                        amount = int(revenue * applied_rate)

                    class_items.append({
                        "class_id": class_.id,
                        "class_name": class_.name,
                        "sessions": sessions,
                        "revenue": revenue,
                        "salary_type": class_.salary_type,
                        "applied_rate": applied_rate,
                        "amount": amount
                    })
                    total_salary += amount
            else:
                # Dùng cơ chế mới: TeacherClassAssignment + TeacherAttendance
                for assignment in assignments:
                    sessions = calculate_teacher_sessions(
                        db, teacher.id, assignment.class_id, month, year
                    )
                    revenue = calculate_class_revenue(db, assignment.class_id, month, year)

                    if assignment.salary_type == "fixed":
                        applied_rate = float(assignment.fixed_salary_per_session)
                        amount = sessions * assignment.fixed_salary_per_session
                    else:  # "coefficient"
                        applied_rate = assignment.salary_coefficient
                        amount = int(revenue * applied_rate)

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
                        "amount": amount
                    })
                    total_salary += amount

            results.append({
                "teacher_id": teacher.id,
                "teacher_name": teacher.full_name,
                "is_locked": False,
                "total_salary": total_salary,
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
                calculated_amount=c["amount"]
            )
            db.add(item)
        records.append(record)

    db.commit()
    return records
