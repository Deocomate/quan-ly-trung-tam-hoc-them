from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_DIR = BASE_DIR / "database"
DATABASE_DIR.mkdir(exist_ok=True)
DATABASE_URL = f"sqlite:///{DATABASE_DIR / 'quanlylophoc.sqlite3'}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401
    from sqlalchemy import text

    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        # --- Backward compatibility columns on 'classes' ---
        cursor = conn.execute(text("PRAGMA table_info(classes)"))
        columns = [row[1] for row in cursor.fetchall()]
        if "teacher_id" not in columns:
            conn.execute(text("ALTER TABLE classes ADD COLUMN teacher_id INTEGER REFERENCES teachers(id)"))
        if "salary_type" not in columns:
            conn.execute(text("ALTER TABLE classes ADD COLUMN salary_type VARCHAR(20) DEFAULT 'fixed' NOT NULL"))
        if "fixed_salary_per_session" not in columns:
            conn.execute(text("ALTER TABLE classes ADD COLUMN fixed_salary_per_session INTEGER DEFAULT 450000 NOT NULL"))
        if "salary_coefficient" not in columns:
            conn.execute(text("ALTER TABLE classes ADD COLUMN salary_coefficient FLOAT DEFAULT 1.0 NOT NULL"))

        # --- Data migration: classes.teacher_id → teacher_class_assignments ---
        # Tạo phân công cho các lớp có teacher_id cũ nhưng chưa có bản ghi trong bảng mới
        rows = conn.execute(
            text(
                "SELECT id, teacher_id, salary_type, fixed_salary_per_session, salary_coefficient "
                "FROM classes WHERE teacher_id IS NOT NULL"
            )
        ).fetchall()
        for row in rows:
            class_id, teacher_id, salary_type, fixed_sal, coeff = row
            existing = conn.execute(
                text(
                    "SELECT id FROM teacher_class_assignments "
                    "WHERE class_id = :cid AND teacher_id = :tid"
                ),
                {"cid": class_id, "tid": teacher_id},
            ).fetchone()
            if not existing:
                conn.execute(
                    text(
                        "INSERT INTO teacher_class_assignments "
                        "(class_id, teacher_id, role, salary_type, fixed_salary_per_session, salary_coefficient, is_active) "
                        "VALUES (:cid, :tid, 'main', :stype, :fixed, :coeff, 1)"
                    ),
                    {
                        "cid": class_id,
                        "tid": teacher_id,
                        "stype": salary_type,
                        "fixed": fixed_sal,
                        "coeff": coeff,
                    },
                )
        conn.commit()

