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
        if "school_year" not in columns:
            conn.execute(text("ALTER TABLE classes ADD COLUMN school_year VARCHAR(40)"))
        if "fixed_present_salary" not in columns:
            conn.execute(text("ALTER TABLE classes ADD COLUMN fixed_present_salary INTEGER DEFAULT 450000 NOT NULL"))
        if "fixed_late_salary" not in columns:
            conn.execute(text("ALTER TABLE classes ADD COLUMN fixed_late_salary INTEGER DEFAULT 315000 NOT NULL"))
        if "fixed_absent_salary" not in columns:
            conn.execute(text("ALTER TABLE classes ADD COLUMN fixed_absent_salary INTEGER DEFAULT 0 NOT NULL"))

        # --- Columns on 'teacher_class_assignments' ---
        cursor = conn.execute(text("PRAGMA table_info(teacher_class_assignments)"))
        tca_columns = [row[1] for row in cursor.fetchall()]
        if "fixed_present_salary" not in tca_columns:
            conn.execute(text("ALTER TABLE teacher_class_assignments ADD COLUMN fixed_present_salary INTEGER DEFAULT 450000 NOT NULL"))
        if "fixed_late_salary" not in tca_columns:
            conn.execute(text("ALTER TABLE teacher_class_assignments ADD COLUMN fixed_late_salary INTEGER DEFAULT 315000 NOT NULL"))
        if "fixed_absent_salary" not in tca_columns:
            conn.execute(text("ALTER TABLE teacher_class_assignments ADD COLUMN fixed_absent_salary INTEGER DEFAULT 0 NOT NULL"))

        # --- Columns on 'teacher_salary_record_items' ---
        cursor = conn.execute(text("PRAGMA table_info(teacher_salary_record_items)"))
        tsri_columns = [row[1] for row in cursor.fetchall()]
        if "sessions_present" not in tsri_columns:
            conn.execute(text("ALTER TABLE teacher_salary_record_items ADD COLUMN sessions_present INTEGER DEFAULT 0 NOT NULL"))
        if "sessions_late" not in tsri_columns:
            conn.execute(text("ALTER TABLE teacher_salary_record_items ADD COLUMN sessions_late INTEGER DEFAULT 0 NOT NULL"))
        if "sessions_absent" not in tsri_columns:
            conn.execute(text("ALTER TABLE teacher_salary_record_items ADD COLUMN sessions_absent INTEGER DEFAULT 0 NOT NULL"))
        if "fixed_present_salary" not in tsri_columns:
            conn.execute(text("ALTER TABLE teacher_salary_record_items ADD COLUMN fixed_present_salary INTEGER DEFAULT 0 NOT NULL"))
        if "fixed_late_salary" not in tsri_columns:
            conn.execute(text("ALTER TABLE teacher_salary_record_items ADD COLUMN fixed_late_salary INTEGER DEFAULT 0 NOT NULL"))
        if "fixed_absent_salary" not in tsri_columns:
            conn.execute(text("ALTER TABLE teacher_salary_record_items ADD COLUMN fixed_absent_salary INTEGER DEFAULT 0 NOT NULL"))

        # --- Columns on 'tuition_records' ---
        cursor = conn.execute(text("PRAGMA table_info(tuition_records)"))
        tr_columns = [row[1] for row in cursor.fetchall()]
        if "transfer_code" not in tr_columns:
            conn.execute(text("ALTER TABLE tuition_records ADD COLUMN transfer_code VARCHAR(50)"))
        if "paid_amount" not in tr_columns:
            conn.execute(text("ALTER TABLE tuition_records ADD COLUMN paid_amount INTEGER DEFAULT 0 NOT NULL"))
        if "payment_status" not in tr_columns:
            conn.execute(text("ALTER TABLE tuition_records ADD COLUMN payment_status VARCHAR(20) DEFAULT 'unpaid' NOT NULL"))

        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_tuition_record_transfer_code ON tuition_records(transfer_code)"))

        # --- Data migration: classes.teacher_id → teacher_class_assignments ---
        # Tạo phân công cho các lớp có teacher_id cũ nhưng chưa có bản ghi trong bảng mới
        rows = conn.execute(
            text(
                "SELECT id, teacher_id, salary_type, fixed_salary_per_session, salary_coefficient, "
                "fixed_present_salary, fixed_late_salary, fixed_absent_salary "
                "FROM classes WHERE teacher_id IS NOT NULL"
            )
        ).fetchall()
        for row in rows:
            class_id, teacher_id, salary_type, fixed_sal, coeff, fps, fls, fas = row
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
                        "(class_id, teacher_id, role, salary_type, fixed_salary_per_session, salary_coefficient, is_active, "
                        "fixed_present_salary, fixed_late_salary, fixed_absent_salary) "
                        "VALUES (:cid, :tid, 'main', :stype, :fixed, :coeff, 1, :fps, :fls, :fas)"
                    ),
                    {
                        "cid": class_id,
                        "tid": teacher_id,
                        "stype": salary_type,
                        "fixed": fixed_sal,
                        "coeff": coeff,
                        "fps": fps,
                        "fls": fls,
                        "fas": fas,
                    },
                )
        conn.commit()

