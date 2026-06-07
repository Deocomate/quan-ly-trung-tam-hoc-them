from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user
from app.database import get_db
from app.models import Teacher
from app.schemas import TeacherCreate, TeacherOut, TeacherUpdate

router = APIRouter(prefix="/api/teachers", tags=["teachers"], dependencies=[Depends(get_current_user)])


@router.get("")
def list_teachers(active: bool | None = None, db: Session = Depends(get_db)):
    stmt = select(Teacher).options(selectinload(Teacher.classes))
    if active is not None:
        stmt = stmt.where(Teacher.is_active.is_(active))
    teachers = db.scalars(stmt.order_by(Teacher.full_name)).all()
    return [
        {
            "id": t.id,
            "full_name": t.full_name,
            "phone": t.phone,
            "email": t.email,
            "default_salary_coefficient": t.default_salary_coefficient,
            "is_active": t.is_active,
            "classes": [
                {
                    "id": c.id,
                    "name": c.name,
                    "subject": c.subject,
                    "salary_type": c.salary_type,
                    "fixed_salary_per_session": c.fixed_salary_per_session,
                    "salary_coefficient": c.salary_coefficient,
                }
                for c in t.classes if c.is_active
            ]
        }
        for t in teachers
    ]


@router.post("", response_model=TeacherOut)
def create_teacher(payload: TeacherCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    teacher = Teacher(**data)
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return teacher


@router.put("/{teacher_id}", response_model=TeacherOut)
def update_teacher(teacher_id: int, payload: TeacherUpdate, db: Session = Depends(get_db)):
    teacher = db.get(Teacher, teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail="Không tìm thấy giáo viên.")
    data = payload.model_dump()
    for key, value in data.items():
        setattr(teacher, key, value)
    db.commit()
    db.refresh(teacher)
    return teacher


@router.delete("/{teacher_id}")
def delete_teacher(teacher_id: int, db: Session = Depends(get_db)):
    teacher = db.get(Teacher, teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail="Không tìm thấy giáo viên.")
    teacher.is_active = False
    db.commit()
    return {"message": "Đã ngưng hoạt động giáo viên."}
