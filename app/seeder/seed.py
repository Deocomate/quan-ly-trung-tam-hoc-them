from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.bootstrap import seed_defaults
from app.database import SessionLocal, init_db
from app.models import (
    Attendance,
    Class,
    Enrollment,
    Student,
    TuitionPeriod,
    TuitionRecord,
    TuitionRecordItem,
    User,
    Teacher,
    TeacherSalaryRecord,
    TeacherSalaryRecordItem,
    TeacherClassAssignment,
    TeacherAttendance,
)
from app.seeder.sample_data import (
    ATTENDANCE_DAYS,
    EXPECTED_REVENUE,
    SAMPLE_ATTENDANCE,
    SAMPLE_CLASSES,
    SAMPLE_MONTH,
    SAMPLE_STUDENTS,
    SAMPLE_TEACHERS,
    SAMPLE_YEAR,
    sample_class_names,
    sample_student_codes,
    SAMPLE_ASSIGNMENTS,
    SAMPLE_TEACHER_ATTENDANCE,
)
from app.services.tuition_service import build_tuition_preview
from app.timezone import now_vietnam


@dataclass(frozen=True)
class SeedSummary:
    classes: int
    students: int
    enrollments: int
    attendance: int
    tuition_records: int
    expected_revenue: int
    month: int
    year: int


class UnsafeSeedError(RuntimeError):
    pass


def seed_sample_data() -> SeedSummary:
    init_db()
    with SessionLocal() as db:
        seed_defaults(db)
        _reset_sample_data(db)
        teacher_by_name = _create_teachers(db)
        class_by_name = _create_classes(db, teacher_by_name)
        student_by_code = _create_students_and_enrollments(db, class_by_name)
        attendance_count = _create_attendance(db, student_by_code, class_by_name)
        _create_teacher_attendance(db, teacher_by_name, class_by_name)
        admin = _first_admin(db)
        records = _create_locked_tuition_records(db, class_by_name, admin)
        return SeedSummary(
            classes=len(SAMPLE_CLASSES),
            students=len(SAMPLE_STUDENTS),
            enrollments=len(SAMPLE_STUDENTS),
            attendance=attendance_count,
            tuition_records=len(records),
            expected_revenue=EXPECTED_REVENUE,
            month=SAMPLE_MONTH,
            year=SAMPLE_YEAR,
        )


def _reset_sample_data(db: Session) -> None:
    sample_codes = sample_student_codes()
    sample_classes = sample_class_names()

    sample_student_ids = set(
        db.scalars(select(Student.id).where(Student.student_code.in_(sample_codes))).all()
    )
    sample_class_ids = set(db.scalars(select(Class.id).where(Class.name.in_(sample_classes))).all())

    if sample_class_ids:
        enrollment_student_ids = set(
            db.scalars(select(Enrollment.student_id).where(Enrollment.class_id.in_(sample_class_ids))).all()
        )
        attendance_student_ids = set(
            db.scalars(select(Attendance.student_id).where(Attendance.class_id.in_(sample_class_ids))).all()
        )
        foreign_class_refs = (enrollment_student_ids | attendance_student_ids) - sample_student_ids
        if foreign_class_refs:
            raise UnsafeSeedError(
                "Các lớp mẫu đang có dữ liệu ngoài bộ mẫu. "
                "Seeder dừng để tránh xóa nhầm phân lớp hoặc điểm danh thật."
            )

    period_record_student_ids = set(
        db.scalars(
            select(TuitionRecord.student_id).where(
                TuitionRecord.month == SAMPLE_MONTH,
                TuitionRecord.year == SAMPLE_YEAR,
            )
        ).all()
    )
    foreign_student_ids = period_record_student_ids - sample_student_ids
    if foreign_student_ids:
        raise UnsafeSeedError(
            "Kỳ học phí 06/2026 đã có dữ liệu ngoài bộ mẫu. "
            "Seeder dừng để tránh xóa hoặc khóa nhầm dữ liệu thật."
        )

    sample_record_ids = set(
        db.scalars(
            select(TuitionRecord.id).where(
                TuitionRecord.month == SAMPLE_MONTH,
                TuitionRecord.year == SAMPLE_YEAR,
                TuitionRecord.student_id.in_(sample_student_ids) if sample_student_ids else False,
            )
        ).all()
    )
    if sample_record_ids:
        db.execute(delete(TuitionRecordItem).where(TuitionRecordItem.record_id.in_(sample_record_ids)))
        db.execute(delete(TuitionRecord).where(TuitionRecord.id.in_(sample_record_ids)))

    if sample_student_ids:
        db.execute(delete(Attendance).where(Attendance.student_id.in_(sample_student_ids)))
        db.execute(delete(Enrollment).where(Enrollment.student_id.in_(sample_student_ids)))
        db.execute(delete(Student).where(Student.id.in_(sample_student_ids)))

    if sample_class_ids:
        db.execute(delete(TeacherClassAssignment).where(TeacherClassAssignment.class_id.in_(sample_class_ids)))
        db.execute(delete(TeacherAttendance).where(TeacherAttendance.class_id.in_(sample_class_ids)))
        db.execute(delete(Attendance).where(Attendance.class_id.in_(sample_class_ids)))
        db.execute(delete(Enrollment).where(Enrollment.class_id.in_(sample_class_ids)))
        db.execute(delete(Class).where(Class.id.in_(sample_class_ids)))

    # Delete sample teachers and their salary records
    sample_teacher_names = {t.full_name for t in SAMPLE_TEACHERS}
    sample_teacher_ids = set(
        db.scalars(
            select(Teacher.id).where(Teacher.full_name.in_(sample_teacher_names))
        ).all()
    )
    if sample_teacher_ids:
        db.execute(delete(TeacherClassAssignment).where(TeacherClassAssignment.teacher_id.in_(sample_teacher_ids)))
        db.execute(delete(TeacherAttendance).where(TeacherAttendance.teacher_id.in_(sample_teacher_ids)))
        db.execute(
            update(Class)
            .where(Class.teacher_id.in_(sample_teacher_ids))
            .values(teacher_id=None)
        )
        salary_record_ids = set(
            db.scalars(
                select(TeacherSalaryRecord.id).where(
                    TeacherSalaryRecord.teacher_id.in_(sample_teacher_ids)
                )
            ).all()
        )
        if salary_record_ids:
            db.execute(delete(TeacherSalaryRecordItem).where(TeacherSalaryRecordItem.record_id.in_(salary_record_ids)))
            db.execute(delete(TeacherSalaryRecord).where(TeacherSalaryRecord.id.in_(salary_record_ids)))
        db.execute(delete(Teacher).where(Teacher.id.in_(sample_teacher_ids)))

    db.execute(delete(TuitionPeriod).where(TuitionPeriod.month == SAMPLE_MONTH, TuitionPeriod.year == SAMPLE_YEAR))
    db.commit()


def _create_teachers(db: Session) -> dict[str, Teacher]:
    teacher_by_name: dict[str, Teacher] = {}
    for item in SAMPLE_TEACHERS:
        teacher = Teacher(
            full_name=item.full_name,
            phone=item.phone,
            email=item.email,
            default_salary_coefficient=item.default_salary_coefficient,
            is_active=True,
        )
        db.add(teacher)
        db.flush()
        teacher_by_name[item.full_name] = teacher
    db.commit()
    return teacher_by_name


def _create_classes(db: Session, teacher_by_name: dict[str, Teacher]) -> dict[str, Class]:
    class_by_name: dict[str, Class] = {}
    for item in SAMPLE_CLASSES:
        teacher = teacher_by_name.get(item.teacher_name) if item.teacher_name else None
        class_ = Class(
            name=item.name,
            subject=item.subject,
            default_fee=item.default_fee,
            notes="Dữ liệu mẫu để kiểm thử",
            is_active=True,
            teacher_id=teacher.id if teacher else None,
            salary_type=item.salary_type,
            fixed_salary_per_session=item.fixed_salary_per_session,
            salary_coefficient=item.salary_coefficient,
        )
        db.add(class_)
        db.flush()
        class_by_name[item.name] = class_
    
    # Tạo teacher assignments
    for item in SAMPLE_ASSIGNMENTS:
        teacher = teacher_by_name.get(item.teacher_name)
        class_ = class_by_name.get(item.class_name)
        if teacher and class_:
            assignment = TeacherClassAssignment(
                class_id=class_.id,
                teacher_id=teacher.id,
                role=item.role,
                salary_type=item.salary_type,
                fixed_salary_per_session=item.fixed_salary_per_session,
                salary_coefficient=item.salary_coefficient,
                is_active=True
            )
            db.add(assignment)
    db.commit()
    return class_by_name


def _create_teacher_attendance(
    db: Session, teacher_by_name: dict[str, Teacher], class_by_name: dict[str, Class]
) -> int:
    count = 0
    for (teacher_name, class_name), statuses in SAMPLE_TEACHER_ATTENDANCE.items():
        teacher = teacher_by_name.get(teacher_name)
        class_ = class_by_name.get(class_name)
        if not (teacher and class_):
            continue
        for day, status in zip(ATTENDANCE_DAYS, statuses, strict=True):
            db.add(
                TeacherAttendance(
                    class_id=class_.id,
                    teacher_id=teacher.id,
                    date=date(SAMPLE_YEAR, SAMPLE_MONTH, day),
                    status=status,
                )
            )
            count += 1
    db.commit()
    return count



def _create_students_and_enrollments(db: Session, class_by_name: dict[str, Class]) -> dict[str, Student]:
    student_by_code: dict[str, Student] = {}
    for item in SAMPLE_STUDENTS:
        student = Student(
            student_code=item.student_code,
            full_name=item.full_name,
            parent_phone=item.parent_phone,
            notes=item.notes,
            is_active=True,
        )
        db.add(student)
        db.flush()
        db.add(
            Enrollment(
                student_id=student.id,
                class_id=class_by_name[item.class_name].id,
                custom_fee=item.fee_per_session,
                is_exempt=False,
                start_date=date(SAMPLE_YEAR, SAMPLE_MONTH, 1),
                is_active=True,
                notes="Dữ liệu mẫu",
            )
        )
        student_by_code[item.student_code] = student
    db.commit()
    return student_by_code


def _create_attendance(db: Session, student_by_code: dict[str, Student], class_by_name: dict[str, Class]) -> int:
    target_class = class_by_name["Toán 6 Nâng cao"]
    count = 0
    for student_code, statuses in SAMPLE_ATTENDANCE.items():
        student = student_by_code[student_code]
        for day, status in zip(ATTENDANCE_DAYS, statuses, strict=True):
            db.add(
                Attendance(
                    student_id=student.id,
                    class_id=target_class.id,
                    date=date(SAMPLE_YEAR, SAMPLE_MONTH, day),
                    status=status,
                )
            )
            count += 1
    db.commit()
    return count


def _first_admin(db: Session) -> User:
    user = db.scalar(select(User).order_by(User.id))
    if not user:
        raise RuntimeError("Không tìm thấy tài khoản admin để chốt học phí mẫu.")
    return user


def _create_locked_tuition_records(db: Session, class_by_name: dict[str, Class], admin: User) -> list[TuitionRecord]:
    records_by_student: dict[int, TuitionRecord] = {}
    for class_ in class_by_name.values():
        for preview in build_tuition_preview(db, SAMPLE_MONTH, SAMPLE_YEAR, class_.id):
            record = records_by_student.get(preview.student_id)
            if not record:
                record = TuitionRecord(
                    student_id=preview.student_id,
                    month=SAMPLE_MONTH,
                    year=SAMPLE_YEAR,
                    total_sessions=0,
                    total_amount=0,
                )
                db.add(record)
                db.flush()
                records_by_student[preview.student_id] = record
            for item in preview.items:
                record.total_sessions += item.sessions
                record.total_amount += item.amount
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

    period = TuitionPeriod(
        month=SAMPLE_MONTH,
        year=SAMPLE_YEAR,
        is_locked=True,
        locked_at=now_vietnam(),
        locked_by=admin.id,
    )
    db.add(period)
    db.commit()
    return list(records_by_student.values())


def format_summary(summary: SeedSummary) -> str:
    revenue = f"{summary.expected_revenue:,}".replace(",", ".")
    return "\n".join(
        [
            "Đã seed dữ liệu mẫu thành công.",
            f"- Lớp/môn học: {summary.classes}",
            f"- Học sinh: {summary.students}",
            f"- Phân lớp: {summary.enrollments}",
            f"- Bản ghi điểm danh: {summary.attendance}",
            f"- Phiếu học phí đã chốt: {summary.tuition_records}",
            f"- Kỳ học phí: {summary.month:02d}/{summary.year} đã khóa",
            f"- Doanh thu kỳ vọng: {revenue} VNĐ",
        ]
    )
