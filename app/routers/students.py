from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user
from app.database import get_db
from app.models import Enrollment, Student
from app.schemas import EnrollmentCreate, EnrollmentUpdate, StudentCreate, StudentOut, StudentUpdate
from app.timezone import today_vietnam

router = APIRouter(prefix="/api/students", tags=["students"], dependencies=[Depends(get_current_user)])
enrollment_router = APIRouter(prefix="/api/enrollments", tags=["enrollments"], dependencies=[Depends(get_current_user)])

VIETNAMESE_ALPHABET = "aàáảãạăằắẳẵặâầấẩẫậbcdđeèéẻẽẹêềếểễệghiìíỉĩịklmnoòóỏõọôồốổỗộơờớởỡợpqrstuuùúủũụưừứửữựvxyỳýỷỹỵ"
CHAR_TO_INDEX = {char: idx for idx, char in enumerate(VIETNAMESE_ALPHABET)}

def vietnamese_sort_key(s: str) -> list[int]:
    import unicodedata
    s = s.lower()
    s = unicodedata.normalize("NFC", s)
    key = []
    for char in s:
        if char in CHAR_TO_INDEX:
            key.append(CHAR_TO_INDEX[char])
        else:
            key.append(ord(char) + len(VIETNAMESE_ALPHABET))
    return key

def get_vietnamese_name_sort_key(full_name: str) -> tuple:
    if not full_name:
        return ()
    parts = full_name.strip().split()
    if not parts:
        return ()
    first_name = parts[-1]
    last_name = parts[0] if len(parts) > 1 else ""
    middle_names = " ".join(parts[1:-1]) if len(parts) > 2 else ""
    return (
        vietnamese_sort_key(first_name),
        vietnamese_sort_key(last_name),
        vietnamese_sort_key(middle_names)
    )


@router.get("")
def list_students(q: str | None = None, active: bool | None = None, db: Session = Depends(get_db)):
    stmt = select(Student).options(selectinload(Student.enrollments).selectinload(Enrollment.class_))
    if q:
        text = f"%{q.strip()}%"
        stmt = stmt.where((Student.full_name.like(text)) | (Student.student_code.like(text)))
    if active is not None:
        stmt = stmt.where(Student.is_active.is_(active))
    students = db.scalars(stmt.order_by(Student.full_name)).all()
    return [
        {
            "id": s.id,
            "student_code": s.student_code,
            "full_name": s.full_name,
            "date_of_birth": s.date_of_birth.isoformat() if s.date_of_birth else None,
            "parent_name": s.parent_name,
            "parent_phone": s.parent_phone,
            "notes": s.notes,
            "is_active": s.is_active,
            "classes": [
                {
                    "enrollment_id": e.id,
                    "class_id": e.class_id,
                    "name": e.class_.name,
                    "subject": e.class_.subject,
                    "custom_fee": e.custom_fee,
                    "is_exempt": e.is_exempt,
                    "is_active": e.is_active,
                }
                for e in s.enrollments
            ],
        }
        for s in students
    ]


@router.post("", response_model=StudentOut)
def create_student(payload: StudentCreate, db: Session = Depends(get_db)):
    from app.services.settings_service import get_settings_map
    from app.services.student_code_service import generate_custom_student_code

    data = payload.model_dump()
    if not data.get("student_code") or not data["student_code"].strip():
        settings = get_settings_map(db)
        template_json = settings.get("student_code_template_json", "")
        data["student_code"] = generate_custom_student_code(db, template_json)
    else:
        data["student_code"] = data["student_code"].strip()

    student = Student(**data)
    db.add(student)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Mã học sinh đã tồn tại.") from exc
    db.refresh(student)
    return student


@router.put("/{student_id}", response_model=StudentOut)
def update_student(student_id: int, payload: StudentUpdate, db: Session = Depends(get_db)):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Không tìm thấy học sinh.")
    data = payload.model_dump()
    if not data.get("student_code") or not data["student_code"].strip():
        data["student_code"] = student.student_code
    else:
        data["student_code"] = data["student_code"].strip()
    for key, value in data.items():
        setattr(student, key, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Mã học sinh đã tồn tại.") from exc
    db.refresh(student)
    return student


@router.get("/{student_id}/check-unpaid-tuition")
def check_unpaid_tuition(student_id: int, db: Session = Depends(get_db)):
    from app.models import TuitionRecord
    from sqlalchemy import select
    # Truy vấn các phiếu thu có trạng thái chưa thanh toán hoặc thanh toán một phần
    records = db.scalars(
        select(TuitionRecord)
        .where(
            TuitionRecord.student_id == student_id,
            TuitionRecord.payment_status.in_(["unpaid", "partial"])
        )
    ).all()
    
    total_unpaid = sum(max(0, r.total_amount - r.paid_amount) for r in records)
    details = [
        {
            "record_id": r.id,
            "month": r.month,
            "year": r.year,
            "total_amount": r.total_amount,
            "paid_amount": r.paid_amount,
            "unpaid_amount": max(0, r.total_amount - r.paid_amount)
        }
        for r in records
    ]
    return {
        "has_unpaid": len(records) > 0 and total_unpaid > 0,
        "unpaid_count": len(records),
        "total_unpaid": total_unpaid,
        "details": details
    }


@router.delete("/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db)):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Không tìm thấy học sinh.")
    student.is_active = False
    db.commit()
    return {"message": "Đã ngưng hoạt động học sinh."}


@enrollment_router.get("")
def list_enrollments(db: Session = Depends(get_db)):
    rows = db.scalars(select(Enrollment).options(selectinload(Enrollment.student), selectinload(Enrollment.class_))).all()
    return [
        {
            "id": e.id,
            "student_id": e.student_id,
            "student_name": e.student.full_name,
            "class_id": e.class_id,
            "class_name": e.class_.name,
            "subject": e.class_.subject,
            "custom_fee": e.custom_fee,
            "is_exempt": e.is_exempt,
            "start_date": e.start_date.isoformat(),
            "is_active": e.is_active,
            "notes": e.notes,
        }
        for e in rows
    ]


@enrollment_router.post("")
def create_enrollment(payload: EnrollmentCreate, db: Session = Depends(get_db)):
    from app.services.tuition_service import sync_enrollment_fee_to_records
    data = payload.model_dump()
    class_ids = data.pop("class_ids")
    if data["start_date"] is None:
        data["start_date"] = today_vietnam()
        
    for c_id in class_ids:
        # Check xem học sinh đã có trong lớp chưa để cập nhật hoặc thêm mới
        exists = db.scalar(
            select(Enrollment).where(
                Enrollment.student_id == data["student_id"],
                Enrollment.class_id == c_id,
            )
        )
        if exists:
            exists.custom_fee = data.get("custom_fee")
            exists.is_exempt = data.get("is_exempt", False)
            exists.is_active = data.get("is_active", True)
            exists.notes = data.get("notes")
            exists.start_date = data.get("start_date") or exists.start_date
            db.flush()
            sync_enrollment_fee_to_records(
                db,
                student_id=data["student_id"],
                class_id=c_id,
                custom_fee=exists.custom_fee,
                is_exempt=exists.is_exempt
            )
        else:
            enrollment = Enrollment(class_id=c_id, **data)
            db.add(enrollment)
            db.flush()
            sync_enrollment_fee_to_records(
                db,
                student_id=data["student_id"],
                class_id=c_id,
                custom_fee=enrollment.custom_fee,
                is_exempt=enrollment.is_exempt
            )
            
    db.commit()
    return {"message": "Đã gán và cập nhật học sinh vào (các) lớp/môn học."}


@enrollment_router.put("/{enrollment_id}")
def update_enrollment(enrollment_id: int, payload: EnrollmentUpdate, db: Session = Depends(get_db)):
    enrollment = db.get(Enrollment, enrollment_id)
    if not enrollment:
        raise HTTPException(status_code=404, detail="Không tìm thấy phân lớp.")
    data = payload.model_dump()
    if data["start_date"] is None:
        data["start_date"] = enrollment.start_date
    for key, value in data.items():
        setattr(enrollment, key, value)
    db.commit()
    return {"message": "Đã cập nhật phân lớp."}


@enrollment_router.delete("/{enrollment_id}")
def delete_enrollment(enrollment_id: int, db: Session = Depends(get_db)):
    enrollment = db.get(Enrollment, enrollment_id)
    if not enrollment:
        raise HTTPException(status_code=404, detail="Không tìm thấy phân lớp.")
    enrollment.is_active = False
    db.commit()
    return {"message": "Đã ngưng phân lớp."}
