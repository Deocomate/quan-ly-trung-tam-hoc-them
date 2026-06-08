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

# --- DỮ LIỆU THỰC TẾ ---
SAMPLE_TEACHERS: tuple[SampleTeacher, ...] = (
    SampleTeacher("ThS. Nguyễn Trường Giang", "0912888999", "giang.nt@hoatuyet.edu.vn", 1.0),
    SampleTeacher("Cô Lê Cẩm Tú", "0987333555", "tu.lc@hoatuyet.edu.vn", 1.2),
)

SAMPLE_CLASSES: tuple[SampleClass, ...] = (
    SampleClass(name="Toán 6 Nâng cao", subject="Toán", default_fee=150000, teacher_name="ThS. Nguyễn Trường Giang", salary_type="coefficient", salary_coefficient=1.0),
    SampleClass(name="Toán 6 Cơ bản", subject="Toán", default_fee=120000, teacher_name="Cô Lê Cẩm Tú", salary_type="fixed", fixed_salary_per_session=400000),
    SampleClass(name="Ngữ Văn 7", subject="Ngữ Văn", default_fee=180000, teacher_name="ThS. Nguyễn Trường Giang", salary_type="fixed", fixed_salary_per_session=450000),
    SampleClass(name="Tiếng Anh 8 Giao tiếp", subject="Tiếng Anh", default_fee=200000, teacher_name="Cô Lê Cẩm Tú", salary_type="coefficient", salary_coefficient=1.5),
)

SAMPLE_STUDENTS: tuple[SampleStudent, ...] = (
    SampleStudent("2026HS001", "Trần Nguyễn Bảo Nam", "Toán 6 Nâng cao", 150000, "0901112233", "Học sinh có năng khiếu toán"),
    SampleStudent("2026HS002", "Lê Hoàng Diệp Anh", "Toán 6 Nâng cao", 150000, "0902223344", ""),
    SampleStudent("2026HS003", "Vũ Hải Đăng", "Toán 6 Cơ bản", 120000, "0903334455", "Cần kèm cặp thêm"),
    SampleStudent("2026HS004", "Phạm Trà My", "Ngữ Văn 7", 180000, "0904445566", ""),
    SampleStudent("2026HS005", "Đinh Tuấn Kiệt", "Tiếng Anh 8 Giao tiếp", 200000, "0905556677", "Chuẩn bị thi IELTS"),
)

ATTENDANCE_DAYS: tuple[int, ...] = (2, 5, 9, 12, 16, 19, 23, 26)

SAMPLE_ATTENDANCE: dict[str, tuple[str, ...]] = {
    "2026HS001": ("P", "P", "V", "P", "P", "M", "P", "P"),
    "2026HS002": ("P", "P", "P", "P", "V", "P", "P", "P"),
}

EXPECTED_TUITION: dict[str, int] = {
    "2026HS001": 1050000,
    "2026HS002": 1050000,
    "2026HS003": 0,
    "2026HS004": 0,
    "2026HS005": 0,
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
    role: str
    salary_type: str
    fixed_salary_per_session: int
    salary_coefficient: float

SAMPLE_ASSIGNMENTS: tuple[SampleAssignment, ...] = (
    SampleAssignment("Toán 6 Nâng cao", "ThS. Nguyễn Trường Giang", "main", "coefficient", 450000, 1.0),
    SampleAssignment("Toán 6 Nâng cao", "Cô Lê Cẩm Tú", "assistant", "fixed", 150000, 1.0),
    SampleAssignment("Toán 6 Cơ bản", "Cô Lê Cẩm Tú", "main", "fixed", 400000, 1.0),
    SampleAssignment("Ngữ Văn 7", "ThS. Nguyễn Trường Giang", "main", "fixed", 450000, 1.0),
    SampleAssignment("Tiếng Anh 8 Giao tiếp", "Cô Lê Cẩm Tú", "main", "coefficient", 450000, 1.5),
)

SAMPLE_TEACHER_ATTENDANCE = {
    ("ThS. Nguyễn Trường Giang", "Toán 6 Nâng cao"): ("P", "P", "P", "P", "P", "P", "P", "P"),
    ("Cô Lê Cẩm Tú", "Toán 6 Nâng cao"): ("P", "P", "V", "P", "P", "M", "P", "P"),
    ("Cô Lê Cẩm Tú", "Toán 6 Cơ bản"): ("P", "P", "P", "P", "P", "P", "P", "P"),
    ("ThS. Nguyễn Trường Giang", "Ngữ Văn 7"): ("P", "P", "P", "P", "P", "P", "P", "P"),
    ("Cô Lê Cẩm Tú", "Tiếng Anh 8 Giao tiếp"): ("P", "P", "P", "P", "P", "P", "P", "P"),
}
