from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Attendance, Class, Student, TuitionRecord

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_user)])


def resolve_months_and_label(
    month: int | None,
    period_type: str | None,
    period_value: int | None
) -> list[int]:
    if month is not None:
        return [month]
    
    if period_type == "quarter":
        val = period_value or 1
        if val == 1:
            return [1, 2, 3]
        elif val == 2:
            return [4, 5, 6]
        elif val == 3:
            return [7, 8, 9]
        else:
            return [10, 11, 12]
    elif period_type == "year":
        return list(range(1, 13))
    else:
        return [period_value or 1]


@router.get("/summary")
def summary(
    year: int,
    month: int | None = None,
    period_type: str | None = None,
    period_value: int | None = None,
    db: Session = Depends(get_db)
):
    months = resolve_months_and_label(month, period_type, period_value)
    students = db.scalar(select(func.count(Student.id)).where(Student.is_active.is_(True))) or 0
    classes = db.scalar(select(func.count(Class.id)).where(Class.is_active.is_(True))) or 0
    
    month_strs = [f"{m:02d}" for m in months]
    sessions = db.scalar(
        select(func.count(Attendance.id)).where(
            func.strftime("%m", Attendance.date).in_(month_strs),
            func.strftime("%Y", Attendance.date) == str(year),
            Attendance.status.in_(["P", "M"]),
        )
    ) or 0
    
    revenue = db.scalar(
        select(func.coalesce(func.sum(TuitionRecord.total_amount), 0)).where(
            TuitionRecord.month.in_(months),
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
def export_excel(
    year: int,
    month: int | None = None,
    period_type: str | None = None,
    period_value: int | None = None,
    db: Session = Depends(get_db)
):
    from app.services.excel_service import generate_revenue_report_excel, format_period_label
    from app.services.settings_service import get_settings_map
    from fastapi.responses import StreamingResponse
    from io import BytesIO

    months = resolve_months_and_label(month, period_type, period_value)
    settings = get_settings_map(db)
    data = generate_revenue_report_excel(db, months, year, settings)
    
    _, sheet_title = format_period_label(months, year)
    filename = f"bao-cao-doanh-thu-{sheet_title}.xlsx"
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export-pdf")
def export_pdf(
    year: int,
    month: int | None = None,
    period_type: str | None = None,
    period_value: int | None = None,
    db: Session = Depends(get_db)
):
    from app.services.pdf_service import generate_revenue_report_pdf, format_period_label
    from app.services.settings_service import get_settings_map
    from fastapi import Response

    months = resolve_months_and_label(month, period_type, period_value)
    settings = get_settings_map(db)
    data = generate_revenue_report_pdf(db, months, year, settings)
    
    _, sheet_title = format_period_label(months, year)
    filename = f"bao-cao-doanh-thu-{sheet_title}.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
