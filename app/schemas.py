from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AttendanceStatus = Literal["P", "V", "M"]


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=6)
    full_name: str = Field(min_length=1, max_length=160)
    is_active: bool = True


class UserUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)
    is_active: bool = True


class PasswordUpdate(BaseModel):
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    username: str
    password: str


class TeacherAssignmentIn(BaseModel):
    teacher_id: int
    role: Literal["main", "assistant"] = "main"
    salary_type: Literal["fixed", "coefficient"] = "fixed"
    fixed_salary_per_session: int = Field(default=450000, ge=0)
    salary_coefficient: float = Field(default=1.0, ge=0.0)
    is_active: bool = True
    fixed_present_salary: int | None = None
    fixed_late_salary: int | None = None
    fixed_absent_salary: int | None = None


class ClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    subject: str = Field(min_length=1, max_length=120)
    school_year: str | None = None
    default_fee: int = Field(ge=0)
    notes: str | None = None
    is_active: bool = True
    # Backward-compat fields (deprecated, kept for old tests/API consumers)
    teacher_id: int | None = None
    salary_type: Literal["fixed", "coefficient"] = "fixed"
    fixed_salary_per_session: int = Field(default=450000, ge=0)
    fixed_present_salary: int | None = None
    fixed_late_salary: int | None = None
    fixed_absent_salary: int | None = None
    salary_coefficient: float = Field(default=1.0, ge=0.0)
    # New: list of teacher assignments
    assignments: list[TeacherAssignmentIn] | None = None


class ClassUpdate(ClassCreate):
    pass


class StudentCreate(BaseModel):
    student_code: str | None = Field(default=None, max_length=80)
    full_name: str = Field(min_length=1, max_length=160)
    parent_name: str | None = None
    parent_phone: str | None = None
    date_of_birth: date | None = None
    notes: str | None = None
    is_active: bool = True


class StudentUpdate(BaseModel):
    student_code: str | None = Field(default=None, max_length=80)
    full_name: str = Field(min_length=1, max_length=160)
    parent_name: str | None = None
    parent_phone: str | None = None
    date_of_birth: date | None = None
    notes: str | None = None
    is_active: bool = True


class EnrollmentCreate(BaseModel):
    student_id: int
    class_ids: list[int]
    custom_fee: int | None = Field(default=None, ge=0)
    is_exempt: bool = False
    start_date: date | None = None
    is_active: bool = True
    notes: str | None = None


class EnrollmentUpdate(BaseModel):
    custom_fee: int | None = Field(default=None, ge=0)
    is_exempt: bool = False
    start_date: date | None = None
    is_active: bool = True
    notes: str | None = None


class AttendanceItem(BaseModel):
    student_id: int
    status: AttendanceStatus


class AttendanceBulkSave(BaseModel):
    class_id: int
    date: date
    items: list[AttendanceItem]


class TuitionLockRequest(BaseModel):
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=2100)
    class_id: int | None = None


class SettingUpdate(BaseModel):
    key: str
    value: str


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserOut(ORMModel):
    id: int
    username: str
    full_name: str
    is_active: bool
    must_change_password: bool


class TeacherAssignmentOut(ORMModel):
    id: int
    teacher_id: int
    role: str
    salary_type: str
    fixed_salary_per_session: int
    salary_coefficient: float
    is_active: bool
    fixed_present_salary: int = 450000
    fixed_late_salary: int = 315000
    fixed_absent_salary: int = 0
    has_attendance: bool = False


class ClassOut(ORMModel):
    id: int
    name: str
    subject: str
    school_year: str | None = None
    default_fee: int
    notes: str | None
    is_active: bool
    teacher_id: int | None = None
    salary_type: str = "fixed"
    fixed_salary_per_session: int = 450000
    fixed_present_salary: int = 450000
    fixed_late_salary: int = 315000
    fixed_absent_salary: int = 0
    salary_coefficient: float = 1.0
    assignments: list[TeacherAssignmentOut] = []


class StudentOut(ORMModel):
    id: int
    student_code: str
    full_name: str
    parent_name: str | None = None
    parent_phone: str | None
    date_of_birth: date | None = None
    notes: str | None
    is_active: bool


class TeacherCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)
    phone: str | None = None
    email: str | None = None
    default_salary_coefficient: float = Field(default=1.0, ge=0.0)
    is_active: bool = True


class TeacherUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)
    phone: str | None = None
    email: str | None = None
    default_salary_coefficient: float = Field(default=1.0, ge=0.0)
    is_active: bool = True


class TeacherOut(ORMModel):
    id: int
    full_name: str
    phone: str | None
    email: str | None
    default_salary_coefficient: float
    is_active: bool


class PayrollLockRequest(BaseModel):
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=2100)

