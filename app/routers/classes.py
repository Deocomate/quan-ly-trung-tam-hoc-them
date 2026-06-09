from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, delete, func
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user
from app.database import get_db
from app.models import Class, TeacherClassAssignment, TeacherAttendance
from app.schemas import ClassCreate, ClassOut, ClassUpdate

router = APIRouter(prefix="/api/classes", tags=["classes"], dependencies=[Depends(get_current_user)])


def _add_has_attendance(db: Session, class_objs: list[Class] | Class) -> None:
    pairs = set(
        db.execute(
            select(TeacherAttendance.class_id, TeacherAttendance.teacher_id).distinct()
        ).all()
    )
    objs = class_objs if isinstance(class_objs, list) else [class_objs]
    for c in objs:
        if c and c.assignments:
            for ass in c.assignments:
                ass.has_attendance = (ass.class_id, ass.teacher_id) in pairs


def _sync_assignments(db: Session, class_id: int, assignments_payload: list) -> None:
    """Đồng bộ danh sách phân công giáo viên cho một lớp học."""
    # Lấy phân công hiện tại
    existing_assignments = db.scalars(
        select(TeacherClassAssignment).where(TeacherClassAssignment.class_id == class_id)
    ).all()
    existing_by_teacher = {ass.teacher_id: ass for ass in existing_assignments}
    payload_teachers = {a.teacher_id for a in assignments_payload}

    # Cập nhật hoặc thêm mới
    for a in assignments_payload:
        fps = a.fixed_present_salary if a.fixed_present_salary is not None else a.fixed_salary_per_session
        fls = a.fixed_late_salary if a.fixed_late_salary is not None else round(a.fixed_salary_per_session * 0.7)
        fas = a.fixed_absent_salary if a.fixed_absent_salary is not None else 0

        if a.teacher_id in existing_by_teacher:
            ass = existing_by_teacher[a.teacher_id]
            ass.role = a.role
            ass.salary_type = a.salary_type
            ass.fixed_salary_per_session = a.fixed_salary_per_session
            ass.salary_coefficient = a.salary_coefficient
            ass.is_active = a.is_active
            ass.fixed_present_salary = fps
            ass.fixed_late_salary = fls
            ass.fixed_absent_salary = fas
        else:
            assignment = TeacherClassAssignment(
                class_id=class_id,
                teacher_id=a.teacher_id,
                role=a.role,
                salary_type=a.salary_type,
                fixed_salary_per_session=a.fixed_salary_per_session,
                salary_coefficient=a.salary_coefficient,
                is_active=a.is_active,
                fixed_present_salary=fps,
                fixed_late_salary=fls,
                fixed_absent_salary=fas,
            )
            db.add(assignment)

    # Kiểm tra và xóa phân công bị loại bỏ
    for tid, ass in existing_by_teacher.items():
        if tid not in payload_teachers:
            # Kiểm tra xem giáo viên này đã có dữ liệu điểm danh chưa
            has_att = db.scalar(
                select(func.count(TeacherAttendance.id))
                .where(TeacherAttendance.class_id == class_id, TeacherAttendance.teacher_id == tid)
            ) > 0
            if has_att:
                raise HTTPException(
                    status_code=400,
                    detail=f"Không thể xóa giáo viên {ass.teacher.full_name} vì đã có dữ liệu giảng dạy. Vui lòng chuyển trạng thái sang Ngừng dạy."
                )
            db.delete(ass)


@router.get("", response_model=list[ClassOut])
def list_classes(q: str | None = None, active: bool | None = None, db: Session = Depends(get_db)):
    stmt = select(Class).options(selectinload(Class.assignments))
    if q:
        text = f"%{q.strip()}%"
        stmt = stmt.where((Class.name.like(text)) | (Class.subject.like(text)))
    if active is not None:
        stmt = stmt.where(Class.is_active.is_(active))
    classes = db.scalars(stmt.order_by(Class.name)).all()
    _add_has_attendance(db, classes)
    return classes


@router.post("", response_model=ClassOut)
def create_class(payload: ClassCreate, db: Session = Depends(get_db)):
    # Tách trường assignments ra trước khi tạo Class
    assignments = payload.assignments
    class_data = payload.model_dump(exclude={"assignments"})
    
    # Resolve fallback rates for Class itself (backward compatibility)
    fsp = class_data.get("fixed_salary_per_session", 450000)
    fps = class_data.get("fixed_present_salary")
    fls = class_data.get("fixed_late_salary")
    fas = class_data.get("fixed_absent_salary")
    
    class_data["fixed_present_salary"] = fps if fps is not None else fsp
    class_data["fixed_late_salary"] = fls if fls is not None else round(fsp * 0.7)
    class_data["fixed_absent_salary"] = fas if fas is not None else 0

    item = Class(**class_data)
    db.add(item)
    db.flush()  # Lấy item.id trước khi commit

    # Nếu có assignments mới thì dùng chúng; nếu không nhưng có teacher_id cũ thì tự động tạo 1 assignment
    if assignments is not None:
        _sync_assignments(db, item.id, assignments)
    elif item.teacher_id:
        db.add(TeacherClassAssignment(
            class_id=item.id,
            teacher_id=item.teacher_id,
            role="main",
            salary_type=item.salary_type,
            fixed_salary_per_session=item.fixed_salary_per_session,
            fixed_present_salary=item.fixed_present_salary,
            fixed_late_salary=item.fixed_late_salary,
            fixed_absent_salary=item.fixed_absent_salary,
            salary_coefficient=item.salary_coefficient,
            is_active=True,
        ))

    db.commit()
    db.refresh(item)
    res = db.scalar(select(Class).options(selectinload(Class.assignments)).where(Class.id == item.id))
    _add_has_attendance(db, res)
    return res


@router.put("/{class_id}", response_model=ClassOut)
def update_class(class_id: int, payload: ClassUpdate, db: Session = Depends(get_db)):
    item = db.get(Class, class_id)
    if not item:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp/môn học.")
    old_fee = item.default_fee

    assignments = payload.assignments
    class_data = payload.model_dump(exclude={"assignments"})
    
    # Resolve fallback rates for Class itself (backward compatibility)
    fsp = class_data.get("fixed_salary_per_session", 450000)
    fps = class_data.get("fixed_present_salary")
    fls = class_data.get("fixed_late_salary")
    fas = class_data.get("fixed_absent_salary")
    
    class_data["fixed_present_salary"] = fps if fps is not None else fsp
    class_data["fixed_late_salary"] = fls if fls is not None else round(fsp * 0.7)
    class_data["fixed_absent_salary"] = fas if fas is not None else 0

    for key, value in class_data.items():
        setattr(item, key, value)
    db.flush()

    if item.default_fee != old_fee:
        from app.services.tuition_service import sync_class_fee_to_records
        sync_class_fee_to_records(db, class_id=item.id, new_fee=item.default_fee)

    # Đồng bộ assignments
    if assignments is not None:
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
            existing.fixed_present_salary = item.fixed_present_salary
            existing.fixed_late_salary = item.fixed_late_salary
            existing.fixed_absent_salary = item.fixed_absent_salary
            existing.salary_coefficient = item.salary_coefficient
        else:
            db.add(TeacherClassAssignment(
                class_id=item.id,
                teacher_id=item.teacher_id,
                role="main",
                salary_type=item.salary_type,
                fixed_salary_per_session=item.fixed_salary_per_session,
                fixed_present_salary=item.fixed_present_salary,
                fixed_late_salary=item.fixed_late_salary,
                fixed_absent_salary=item.fixed_absent_salary,
                salary_coefficient=item.salary_coefficient,
                is_active=True,
            ))

    db.commit()
    res = db.scalar(select(Class).options(selectinload(Class.assignments)).where(Class.id == item.id))
    _add_has_attendance(db, res)
    return res


@router.delete("/{class_id}")
def delete_class(class_id: int, db: Session = Depends(get_db)):
    item = db.get(Class, class_id)
    if not item:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp/môn học.")
    item.is_active = False
    db.commit()
    return {"message": "Đã ngưng hoạt động lớp/môn học."}


@router.get("/{class_id}/students")
def get_class_students(class_id: int, db: Session = Depends(get_db)):
    cls = db.get(Class, class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học.")
    
    from app.models import Enrollment, Student
    stmt = (
        select(Student, Enrollment.custom_fee, Enrollment.is_exempt)
        .join(Enrollment, Enrollment.student_id == Student.id)
        .where(
            Enrollment.class_id == class_id,
            Enrollment.is_active == True,
            Student.is_active == True
        )
    )
    rows = db.execute(stmt).all()
    
    students_list = []
    for student, custom_fee, is_exempt in rows:
        students_list.append({
            "id": student.id,
            "student_code": student.student_code,
            "full_name": student.full_name,
            "date_of_birth": student.date_of_birth.isoformat() if student.date_of_birth else None,
            "parent_name": student.parent_name,
            "parent_phone": student.parent_phone,
            "custom_fee": custom_fee,
            "is_exempt": is_exempt,
            "default_fee": cls.default_fee
        })
        
    from app.routers.students import get_vietnamese_name_sort_key
    students_list.sort(key=lambda x: get_vietnamese_name_sort_key(x["full_name"]))
    
    return students_list


@router.get("/{class_id}/export-attendance")
def export_class_attendance(
    class_id: int,
    month: int,
    year: int,
    session_days: str | None = None,
    fill_attendance: bool = False,
    db: Session = Depends(get_db)
):
    from app.services.excel_service import generate_class_attendance_excel
    from urllib.parse import quote
    
    cls = db.get(Class, class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học.")
        
    excel_data = generate_class_attendance_excel(
        db=db,
        class_id=class_id,
        month=month,
        year=year,
        session_days_str=session_days,
        fill_attendance=fill_attendance
    )
    
    raw_filename = f"chuyen-can-{cls.name.replace(' ', '_')}-{month:02d}-{year}.xlsx"
    encoded_filename = quote(raw_filename)
    
    return Response(
        content=excel_data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=utf-8''{encoded_filename}"},
    )
