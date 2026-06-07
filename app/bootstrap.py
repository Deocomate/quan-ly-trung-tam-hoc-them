from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import Setting, User

DEFAULT_SETTINGS = {
    "center_logo_text": "HOA TUYẾT\nEDUCATION",
    "center_name": "HỘ KINH DOANH TRUNG TÂM GIÁO DỤC HOA TUYẾT",
    "center_address": "Số 15, ngõ 52/3 phố Quan Nhân, Trung Hoà, Cầu Giấy, Hà Nội",
    "center_hotline": "Hotline: Chị Hoa: 0982927578 ; anh Sơn: 0969651968",
    "receipt_intro": "Hoa Tuyết Edu gửi tới Quý Phụ Huynh thông báo học phí Tháng của con như sau:",
    "payment_deadline": "Quý Phụ Huynh vui lòng hoàn thành học phí cho con trong ngày 15,16,17,18 hàng tháng",
    "payment_content_template": "{student_name} {month:02d}{year_short}",
    "receipt_footer": "Trân trọng cảm ơn!",
    "backup_schedule_day": "",
    "last_auto_backup_date": "",
    "center_phone": "",
    "center_email": "",
    "center_zalo": "",
    "receipt_logo_display": "both",
}


def seed_defaults(db: Session) -> None:
    if db.scalar(select(User).limit(1)) is None:
        db.add(
            User(
                username="admin",
                password_hash=hash_password("123456"),
                full_name="Quản trị viên",
                is_active=True,
                must_change_password=True,
            )
        )

    existing_keys = set(db.scalars(select(Setting.key)).all())
    for key, value in DEFAULT_SETTINGS.items():
        if key not in existing_keys:
            db.add(Setting(key=key, value=value))
    db.commit()
