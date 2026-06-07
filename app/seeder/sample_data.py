from __future__ import annotations

from dataclasses import dataclass

SAMPLE_YEAR = 2026
SAMPLE_MONTH = 6


@dataclass(frozen=True)
class SampleClass:
    name: str
    subject: str
    default_fee: int
    teacher_name: str | None = None
    salary_type: str = "fixed"
    fixed_salary_per_session: int = 450000
    salary_coefficient: float = 1.0


@dataclass(frozen=True)
class SampleStudent:
    student_code: str
    full_name: str
    class_name: str
    fee_per_session: int
    parent_phone: str
    notes: str = ""


@dataclass(frozen=True)
class SampleTeacher:
    full_name: str
    phone: str
    email: str
    default_salary_coefficient: float


SAMPLE_TEACHERS: tuple[SampleTeacher, ...] = (
    SampleTeacher("Nguyễn Văn Hùng", "0912345678", "hung.nguyen@example.com", 1.0),
    SampleTeacher("Trần Thị Mai", "0987654321", "mai.tran@example.com", 1.2),
)


SAMPLE_CLASSES: tuple[SampleClass, ...] = (
    SampleClass(name="6A", subject="Học phí lớp 6A", default_fee=150000, teacher_name="Nguyễn Văn Hùng", salary_type="coefficient", salary_coefficient=1.0),
    SampleClass(name="6B", subject="Học phí lớp 6B", default_fee=150000, teacher_name="Trần Thị Mai", salary_type="fixed", fixed_salary_per_session=400000),
    SampleClass(name="7A", subject="Học phí lớp 7A", default_fee=180000, teacher_name="Nguyễn Văn Hùng", salary_type="fixed", fixed_salary_per_session=450000),
    SampleClass(name="8A", subject="Học phí lớp 8A", default_fee=200000, teacher_name="Trần Thị Mai", salary_type="coefficient", salary_coefficient=1.5),
)

SAMPLE_STUDENTS: tuple[SampleStudent, ...] = (
    SampleStudent("HS001", "Nguyễn Văn A", "6A", 150000, "0901234567", "Học sinh mới"),
    SampleStudent("HS002", "Trần Thị B", "6A", 150000, "0902345678"),
    SampleStudent("HS003", "Lê Hoàng C", "6B", 150000, "0903456789"),
    SampleStudent("HS004", "Phạm Minh D", "7A", 180000, "0904567890"),
    SampleStudent("HS005", "Hoàng Quốc E", "8A", 200000, "0905678901"),
)

ATTENDANCE_DAYS: tuple[int, ...] = (1, 3, 5, 8, 10, 12, 15, 17)

SAMPLE_ATTENDANCE: dict[str, tuple[str, ...]] = {
    "HS001": ("P", "P", "V", "P", "P", "M", "P", "P"),
    "HS002": ("P", "P", "P", "P", "V", "P", "P", "P"),
}

EXPECTED_TUITION: dict[str, int] = {
    "HS001": 1050000,
    "HS002": 1050000,
    "HS003": 0,
    "HS004": 0,
    "HS005": 0,
}

EXPECTED_REVENUE = 2100000


def sample_student_codes() -> set[str]:
    return {student.student_code for student in SAMPLE_STUDENTS}


def sample_class_names() -> set[str]:
    return {class_.name for class_ in SAMPLE_CLASSES}


@dataclass(frozen=True)
class SampleAssignment:
    class_name: str
    teacher_name: str
    role: str  # "main" or "assistant"
    salary_type: str
    fixed_salary_per_session: int
    salary_coefficient: float


SAMPLE_ASSIGNMENTS: tuple[SampleAssignment, ...] = (
    SampleAssignment("6A", "Nguyễn Văn Hùng", "main", "coefficient", 450000, 1.0),
    SampleAssignment("6A", "Trần Thị Mai", "assistant", "fixed", 150000, 1.0),
    SampleAssignment("6B", "Trần Thị Mai", "main", "fixed", 400000, 1.0),
    SampleAssignment("7A", "Nguyễn Văn Hùng", "main", "fixed", 450000, 1.0),
    SampleAssignment("8A", "Trần Thị Mai", "main", "coefficient", 450000, 1.5),
)


# Teacher attendance for 06/2026, ATTENDANCE_DAYS = (1, 3, 5, 8, 10, 12, 15, 17)
SAMPLE_TEACHER_ATTENDANCE = {
    ("Nguyễn Văn Hùng", "6A"): ("P", "P", "P", "P", "P", "P", "P", "P"),  # 8 sessions
    ("Trần Thị Mai", "6A"): ("P", "P", "V", "P", "P", "M", "P", "P"),   # 7 sessions (P+M)
    ("Trần Thị Mai", "6B"): ("P", "P", "P", "P", "P", "P", "P", "P"),  # 8 sessions
    ("Nguyễn Văn Hùng", "7A"): ("P", "P", "P", "P", "P", "P", "P", "P"),
    ("Trần Thị Mai", "8A"): ("P", "P", "P", "P", "P", "P", "P", "P"),
}

