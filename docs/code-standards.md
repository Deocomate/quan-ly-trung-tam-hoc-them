# Code Standards & Guidelines

This document outlines the coding standards, structure, and design conventions used across the Hoang Classroom Management System.

---

## 1. Python Syntax & Style

* **Python Version**: Python 3.11+
* **Modern Type Annotations**: Use `from __future__ import annotations` at the top of every file to enable forward-referencing and modern union typing (`int | None`).
* **Formatting**: Follow PEP 8 guidelines. Match the existing codebase style (using a code formatter like Ruff or Black).
* **Naming Conventions**:
  - Class names: `CamelCase` (e.g., `TuitionRecord`).
  - Functions & Variables: `snake_case` (e.g., `calculate_tuition`).
  - Constants: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_SETTINGS`).

---

## 2. Database & ORM (SQLAlchemy 2.0)

We use SQLAlchemy 2.0 declarative style mappings:
* **Annotations**: Models must use type-annotated Mapped types:
  ```python
  class Student(Base):
      __tablename__ = "students"
      id: Mapped[int] = mapped_column(Integer, primary_key=True)
      full_name: Mapped[str] = mapped_column(String(160), nullable=False)
      parent_phone: Mapped[str | None] = mapped_column(String(40))
  ```
* **Relationships**: Use `Mapped[list[OtherModel]]` with `relationship(back_populates="...")`.
* **Migrations / Schema Updates**: 
  - To maintain portability and zero-configuration SQLite, we do not use Alembic.
  - Instead, schema migrations are written programmatically in `app/database.py` within `init_db()`. When database structure updates are needed, write DDL statements targeting existing SQLite tables using SQL query checks (e.g., `PRAGMA table_info`).

---

## 3. Web Framework Structure & API Routers

* **Routing Separation**:
  - HTML pages are served directly under `main.py` or their respective routers using `Jinja2Templates` rendering.
  - API routers (AJAX endpoints) live in `app/routers/` and return Pydantic models, dicts, or status objects.
* **Database Sessions**:
  - Always inject the database session in route handlers using FastAPI's dependency injection:
    ```python
    @router.get("/api/endpoint")
    def get_data(db: Session = Depends(get_db)):
        ...
    ```
* **Authentication Guards**:
  - Protect sensitive administrator endpoints using `get_current_user` in `Depends(...)` or validating the session cookie.

---

## 4. Services (Business Logic)

* **Separation of Concerns**:
  - Do not put database querying logic or complex calculations directly inside the router controllers.
  - Router functions should handle requests/responses and delegate the business logic to the service layer under `app/services/` (e.g., PDF generation, Excel compilation, or tuition math).
* **Timezone Safety**:
  - Never use naive python datetime functions like `datetime.utcnow()` or `date.today()`.
  - Always import timezone-safe utilities from `app/timezone.py` (`now_vietnam()`, `today_vietnam()`) to ensure datetime fields are localized to `Asia/Ho_Chi_Minh` timezone.
