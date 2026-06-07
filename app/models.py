from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.timezone import now_vietnam, today_vietnam


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_vietnam, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_vietnam, onupdate=now_vietnam, nullable=False
    )

    locked_periods: Mapped[list["TuitionPeriod"]] = relationship(back_populates="locked_by_user")


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_code: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    parent_phone: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_vietnam, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_vietnam, onupdate=now_vietnam, nullable=False
    )

    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="student", cascade="all, delete-orphan")
    attendance: Mapped[list["Attendance"]] = relationship(back_populates="student")
    tuition_records: Mapped[list["TuitionRecord"]] = relationship(back_populates="student")


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(120))
    default_salary_coefficient: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_vietnam, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_vietnam, onupdate=now_vietnam, nullable=False
    )

    classes: Mapped[list["Class"]] = relationship(back_populates="teacher")
    class_assignments: Mapped[list["TeacherClassAssignment"]] = relationship(back_populates="teacher", cascade="all, delete-orphan")
    salary_records: Mapped[list["TeacherSalaryRecord"]] = relationship(back_populates="teacher", cascade="all, delete-orphan")
    teacher_attendance: Mapped[list["TeacherAttendance"]] = relationship(back_populates="teacher", cascade="all, delete-orphan")


class Class(Base):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    subject: Mapped[str] = mapped_column(String(120), nullable=False)
    default_fee: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_vietnam, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_vietnam, onupdate=now_vietnam, nullable=False
    )

    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id"), nullable=True)
    salary_type: Mapped[str] = mapped_column(String(20), default="fixed", nullable=False) # "fixed" hoặc "coefficient"
    fixed_salary_per_session: Mapped[int] = mapped_column(Integer, default=450000, nullable=False)
    salary_coefficient: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    teacher: Mapped[Teacher | None] = relationship(back_populates="classes")
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="class_")
    attendance: Mapped[list["Attendance"]] = relationship(back_populates="class_")
    assignments: Mapped[list["TeacherClassAssignment"]] = relationship(back_populates="class_", cascade="all, delete-orphan")
    teacher_attendance: Mapped[list["TeacherAttendance"]] = relationship(back_populates="class_", cascade="all, delete-orphan")


class TeacherClassAssignment(Base):
    """Phân công giáo viên vào lớp (Many-to-Many) với cấu hình lương riêng."""
    __tablename__ = "teacher_class_assignments"
    __table_args__ = (UniqueConstraint("class_id", "teacher_id", name="uq_teacher_class_assignment"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="main", nullable=False)  # "main" hoặc "assistant"
    salary_type: Mapped[str] = mapped_column(String(20), default="fixed", nullable=False)
    fixed_salary_per_session: Mapped[int] = mapped_column(Integer, default=450000, nullable=False)
    salary_coefficient: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    class_: Mapped[Class] = relationship(back_populates="assignments")
    teacher: Mapped[Teacher] = relationship(back_populates="class_assignments")


class TeacherAttendance(Base):
    """Điểm danh giáo viên, độc lập với điểm danh học sinh."""
    __tablename__ = "teacher_attendance"
    __table_args__ = (UniqueConstraint("teacher_id", "class_id", "date", name="uq_teacher_attendance"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(1), nullable=False)  # "P" (Có mặt), "V" (Vắng), "M" (Trễ)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_vietnam, nullable=False)

    class_: Mapped[Class] = relationship(back_populates="teacher_attendance")
    teacher: Mapped[Teacher] = relationship(back_populates="teacher_attendance")


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("student_id", "class_id", name="uq_student_class"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False)
    custom_fee: Mapped[int | None] = mapped_column(Integer)
    is_exempt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, default=today_vietnam, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    student: Mapped[Student] = relationship(back_populates="enrollments")
    class_: Mapped[Class] = relationship(back_populates="enrollments")


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("student_id", "class_id", "date", name="uq_attendance_student_class_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(1), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_vietnam, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_vietnam, onupdate=now_vietnam, nullable=False
    )

    student: Mapped[Student] = relationship(back_populates="attendance")
    class_: Mapped[Class] = relationship(back_populates="attendance")


class TuitionPeriod(Base):
    __tablename__ = "tuition_periods"
    __table_args__ = (UniqueConstraint("month", "year", name="uq_tuition_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    locked_by_user: Mapped[User | None] = relationship(back_populates="locked_periods")


class TuitionRecord(Base):
    __tablename__ = "tuition_records"
    __table_args__ = (UniqueConstraint("student_id", "month", "year", name="uq_tuition_record_student_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    total_sessions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_vietnam, nullable=False)

    student: Mapped[Student] = relationship(back_populates="tuition_records")
    items: Mapped[list["TuitionRecordItem"]] = relationship(back_populates="record", cascade="all, delete-orphan")


class TuitionRecordItem(Base):
    __tablename__ = "tuition_record_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("tuition_records.id"), nullable=False)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("classes.id"))
    class_name: Mapped[str] = mapped_column(String(120), nullable=False)
    subject: Mapped[str] = mapped_column(String(120), nullable=False)
    sessions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unit_fee: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    record: Mapped[TuitionRecord] = relationship(back_populates="items")
    class_: Mapped[Class | None] = relationship()


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class TeacherSalaryRecord(Base):
    __tablename__ = "teacher_salary_records"
    __table_args__ = (UniqueConstraint("teacher_id", "month", "year", name="uq_teacher_salary_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    total_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    teacher: Mapped[Teacher] = relationship(back_populates="salary_records")
    items: Mapped[list["TeacherSalaryRecordItem"]] = relationship(back_populates="record", cascade="all, delete-orphan")


class TeacherSalaryRecordItem(Base):
    __tablename__ = "teacher_salary_record_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("teacher_salary_records.id"), nullable=False)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("classes.id"), nullable=True)
    class_name: Mapped[str] = mapped_column(String(120), nullable=False)
    sessions_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    class_revenue: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    salary_type: Mapped[str] = mapped_column(String(20), nullable=False)
    applied_rate: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    calculated_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    record: Mapped[TeacherSalaryRecord] = relationship(back_populates="items")
    class_: Mapped[Class | None] = relationship()
