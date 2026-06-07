from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Attendance, Class, Student, TuitionRecord

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_user)])


@router.get("/summary")
def summary(month: int, year: int, db: Session = Depends(get_db)):
    students = db.scalar(select(func.count(Student.id)).where(Student.is_active.is_(True))) or 0
    classes = db.scalar(select(func.count(Class.id)).where(Class.is_active.is_(True))) or 0
    sessions = db.scalar(
        select(func.count(Attendance.id)).where(
            func.strftime("%m", Attendance.date) == f"{month:02d}",
            func.strftime("%Y", Attendance.date) == str(year),
            Attendance.status.in_(["P", "M"]),
        )
    ) or 0
    revenue = db.scalar(
        select(func.coalesce(func.sum(TuitionRecord.total_amount), 0)).where(
            TuitionRecord.month == month,
            TuitionRecord.year == year,
        )
    ) or 0
    return {"students": students, "classes": classes, "sessions": sessions, "revenue": revenue}


@router.get("/revenue")
def revenue(year: int, db: Session = Depends(get_db)):
    rows = db.execute(
        select(TuitionRecord.month, func.coalesce(func.sum(TuitionRecord.total_amount), 0))
        .where(TuitionRecord.year == year)
        .group_by(TuitionRecord.month)
    ).all()
    values = {month: amount for month, amount in rows}
    return [{"month": month, "amount": values.get(month, 0)} for month in range(1, 13)]


@router.get("/export-excel")
def export_excel(month: int, year: int, db: Session = Depends(get_db)):
    from app.services.excel_service import generate_revenue_report_excel
    from app.services.settings_service import get_settings_map
    from fastapi.responses import StreamingResponse
    from io import BytesIO

    settings = get_settings_map(db)
    data = generate_revenue_report_excel(db, month, year, settings)
    filename = f"bao-cao-doanh-thu-{month:02d}-{year}.xlsx"
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export-pdf")
def export_pdf(month: int, year: int, db: Session = Depends(get_db)):
    from app.services.pdf_service import generate_revenue_report_pdf
    from app.services.settings_service import get_settings_map
    from fastapi import Response

    settings = get_settings_map(db)
    data = generate_revenue_report_pdf(db, month, year, settings)
    filename = f"bao-cao-doanh-thu-{month:02d}-{year}.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
