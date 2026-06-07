from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user
from app.database import get_db
from app.models import Class, TeacherClassAssignment
from app.schemas import ClassCreate, ClassOut, ClassUpdate

router = APIRouter(prefix="/api/classes", tags=["classes"], dependencies=[Depends(get_current_user)])


def _sync_assignments(db: Session, class_id: int, assignments_payload: list) -> None:
    """Đồng bộ danh sách phân công giáo viên cho một lớp học."""
    # Xóa tất cả phân công hiện tại
    db.execute(delete(TeacherClassAssignment).where(TeacherClassAssignment.class_id == class_id))
    # Thêm lại theo payload mới
    for a in assignments_payload:
        assignment = TeacherClassAssignment(
            class_id=class_id,
            teacher_id=a.teacher_id,
            role=a.role,
            salary_type=a.salary_type,
            fixed_salary_per_session=a.fixed_salary_per_session,
            salary_coefficient=a.salary_coefficient,
            is_active=True,
        )
        db.add(assignment)


@router.get("", response_model=list[ClassOut])
def list_classes(q: str | None = None, active: bool | None = None, db: Session = Depends(get_db)):
    stmt = select(Class).options(selectinload(Class.assignments))
    if q:
        text = f"%{q.strip()}%"
        stmt = stmt.where((Class.name.like(text)) | (Class.subject.like(text)))
    if active is not None:
        stmt = stmt.where(Class.is_active.is_(active))
    return db.scalars(stmt.order_by(Class.name)).all()


@router.post("", response_model=ClassOut)
def create_class(payload: ClassCreate, db: Session = Depends(get_db)):
    # Tách trường assignments ra trước khi tạo Class
    assignments = payload.assignments
    class_data = payload.model_dump(exclude={"assignments"})
    item = Class(**class_data)
    db.add(item)
    db.flush()  # Lấy item.id trước khi commit

    # Nếu có assignments mới thì dùng chúng; nếu không nhưng có teacher_id cũ thì tự động tạo 1 assignment
    if assignments:
        _sync_assignments(db, item.id, assignments)
    elif item.teacher_id:
        db.add(TeacherClassAssignment(
            class_id=item.id,
            teacher_id=item.teacher_id,
            role="main",
            salary_type=item.salary_type,
            fixed_salary_per_session=item.fixed_salary_per_session,
            salary_coefficient=item.salary_coefficient,
            is_active=True,
        ))

    db.commit()
    db.refresh(item)
    # Reload với assignments
    return db.scalar(select(Class).options(selectinload(Class.assignments)).where(Class.id == item.id))


@router.put("/{class_id}", response_model=ClassOut)
def update_class(class_id: int, payload: ClassUpdate, db: Session = Depends(get_db)):
    item = db.get(Class, class_id)
    if not item:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp/môn học.")
    old_fee = item.default_fee

    assignments = payload.assignments
    class_data = payload.model_dump(exclude={"assignments"})
    for key, value in class_data.items():
        setattr(item, key, value)
    db.flush()

    if item.default_fee != old_fee:
        from app.services.tuition_service import sync_class_fee_to_records
        sync_class_fee_to_records(db, class_id=item.id, new_fee=item.default_fee)

    # Đồng bộ assignments
    if assignments:
        _sync_assignments(db, item.id, assignments)
    elif item.teacher_id:
        # Nếu không có assignments mới nhưng có teacher_id, cập nhật assignment chính
        existing = db.scalar(
            select(TeacherClassAssignment).where(
                TeacherClassAssignment.class_id == item.id,
                TeacherClassAssignment.teacher_id == item.teacher_id,
            )
        )
        if existing:
            existing.salary_type = item.salary_type
            existing.fixed_salary_per_session = item.fixed_salary_per_session
            existing.salary_coefficient = item.salary_coefficient
        else:
            db.add(TeacherClassAssignment(
                class_id=item.id,
                teacher_id=item.teacher_id,
                role="main",
                salary_type=item.salary_type,
                fixed_salary_per_session=item.fixed_salary_per_session,
                salary_coefficient=item.salary_coefficient,
                is_active=True,
            ))

    db.commit()
    return db.scalar(select(Class).options(selectinload(Class.assignments)).where(Class.id == item.id))


@router.delete("/{class_id}")
def delete_class(class_id: int, db: Session = Depends(get_db)):
    item = db.get(Class, class_id)
    if not item:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp/môn học.")
    item.is_active = False
    db.commit()
    return {"message": "Đã ngưng hoạt động lớp/môn học."}
