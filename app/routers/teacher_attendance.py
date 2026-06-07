from __future__ import annotations

from datetime import date
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user
from app.database import get_db
from app.models import TeacherAttendance, TeacherClassAssignment
from app.timezone import month_bounds

router = APIRouter(
    prefix="/api/teacher-attendance",
    tags=["teacher-attendance"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/month")
def get_teacher_attendance_month(class_id: int, month: int, year: int, db: Session = Depends(get_db)):
    """Lấy dữ liệu điểm danh giáo viên theo tháng cho một lớp."""
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="Tháng phải từ 1 đến 12.")
    if not (2000 <= year <= 2100):
        raise HTTPException(status_code=400, detail="Năm không hợp lệ.")

    start_date, end_date = month_bounds(year, month)

    # 1. Lấy danh sách giáo viên được phân công vào lớp
    assignments = db.scalars(
        select(TeacherClassAssignment)
        .options(selectinload(TeacherClassAssignment.teacher))
        .where(
            TeacherClassAssignment.class_id == class_id,
            TeacherClassAssignment.is_active.is_(True),
        )
        .order_by(TeacherClassAssignment.id)
    ).all()

    # 2. Lấy toàn bộ điểm danh của giáo viên trong lớp trong tháng
    attendances = db.scalars(
        select(TeacherAttendance).where(
            TeacherAttendance.class_id == class_id,
            TeacherAttendance.date >= start_date,
            TeacherAttendance.date < end_date,
        )
    ).all()

    # Map điểm danh: { teacher_id: { "YYYY-MM-DD": status } }
    att_map: dict[int, dict[str, str]] = {}
    for att in attendances:
        teacher_att = att_map.setdefault(att.teacher_id, {})
        teacher_att[att.date.isoformat()] = att.status

    return {
        "teachers": [
            {
                "teacher_id": a.teacher_id,
                "full_name": a.teacher.full_name,
                "role": a.role,
                "salary_type": a.salary_type,
                "attendance": att_map.get(a.teacher_id, {}),
            }
            for a in assignments
        ]
    }


class TeacherAttendanceSingle(BaseModel):
    class_id: int
    teacher_id: int
    date: date
    status: str | None = None  # None / "" → xóa bản ghi


@router.put("/single")
def save_teacher_attendance_single(payload: TeacherAttendanceSingle, db: Session = Depends(get_db)):
    """Lưu hoặc xóa điểm danh đơn lẻ của một giáo viên."""
    row = db.scalar(
        select(TeacherAttendance).where(
            TeacherAttendance.teacher_id == payload.teacher_id,
            TeacherAttendance.class_id == payload.class_id,
            TeacherAttendance.date == payload.date,
        )
    )

    if payload.status in ("P", "V", "M"):
        if row:
            row.status = payload.status
        else:
            db.add(
                TeacherAttendance(
                    class_id=payload.class_id,
                    teacher_id=payload.teacher_id,
                    date=payload.date,
                    status=payload.status,
                )
            )
    else:
        # status = None hoặc rỗng → xóa bản ghi
        if row:
            db.delete(row)

    db.commit()
    return {"message": "Saved"}
