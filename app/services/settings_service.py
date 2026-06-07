from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bootstrap import DEFAULT_SETTINGS
from app.models import Setting


def get_settings_map(db: Session) -> dict[str, str]:
    rows = db.scalars(select(Setting)).all()
    data = {row.key: row.value for row in rows}
    for key, value in DEFAULT_SETTINGS.items():
        data.setdefault(key, value)
    return data


def upsert_setting(db: Session, key: str, value: str) -> Setting:
    setting = db.scalar(select(Setting).where(Setting.key == key))
    if setting:
        setting.value = value
    else:
        setting = Setting(key=key, value=value)
        db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting

