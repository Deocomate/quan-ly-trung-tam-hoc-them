# Codebase Summary

This document provides a technical summary of the codebase structure, file distribution, and line counts (LOC).

---

## 1. Directory Tree & Line Counts (LOC)

Based on the latest repository scan:

| Directory | Files Count | Total LOC | Primary Purpose |
| :--- | :---: | :---: | :--- |
| `app/services/` | 8 | 3,397 | Business logic, PDF/Excel reports, VietQR calculations |
| `app/routers/` | 13 | 1,959 | FastAPI controller routes, HTTP endpoints |
| `app/` (root) | 7 | 806 | Models, database settings, auth, timezones |
| `app/seeder/` | 5 | 521 | Seed scripts, sample datasets for dev environment |
| `templates/` | 15 | 4,747 | Jinja2 templates, UI views, dynamic tables |
| `static/` | 2 | 663 | Custom stylesheet (`app.css`) and scripts (`app.js`) |
| `root` | 3 | 1,864 | Main executable (`main.py`), readme, configs |
| `database/` | 3 | 944 | SQLite database files |

*Note: The backup/cache directory `_codebase` is omitted from developer summaries.*

---

## 2. Key Modules & Technical Descriptions

### 2.1. Core Application Setup (`app/`)
* **[main.py](file:///c:/Users/minhlong/Desktop/projects/hoang-quanlylophoc/main.py)**: Main entry point of the application. It creates the FastAPI instance, mounts static files, registers all routers, and handles the local development startup flow (locates an available port, starts Uvicorn, and automatically opens the user's web browser).
* **[app/models.py](file:///c:/Users/minhlong/Desktop/projects/hoang-quanlylophoc/app/models.py)**: Defines the SQLAlchemy ORM models representing the database schema (e.g., `Student`, `Teacher`, `Class`, `Enrollment`, `Attendance`, `TuitionRecord`, `TuitionPeriod`, `TeacherAttendance`, `User`, `Setting`).
* **[app/schemas.py](file:///c:/Users/minhlong/Desktop/projects/hoang-quanlylophoc/app/schemas.py)**: Holds the Pydantic schemas used for request body validation and API response serialization.
* **[app/database.py](file:///c:/Users/minhlong/Desktop/projects/hoang-quanlylophoc/app/database.py)**: Configures the SQLAlchemy session engine connected to a local SQLite database (`quanlylophoc.sqlite3`). Contains the `init_db()` migration script which checks table structures on startup and runs dynamic DDL statements to ensure backward compatibility across updates.
* **[app/auth.py](file:///c:/Users/minhlong/Desktop/projects/hoang-quanlylophoc/app/auth.py)**: Authentication logic containing password hashing (bcrypt), token issuance, and middleware-style helpers to extract active users from HTTPOnly cookies.
* **[app/timezone.py](file:///c:/Users/minhlong/Desktop/projects/hoang-quanlylophoc/app/timezone.py)**: Provides Vietnam-local date/time functions (`Asia/Ho_Chi_Minh` timezone) to avoid database timestamp timezone discrepancies on different servers.

### 2.2. Service Layer (`app/services/`)
* **[pdf_service.py](file:///c:/Users/minhlong/Desktop/projects/hoang-quanlylophoc/app/services/pdf_service.py)**: Generates invoice/receipt PDFs. It utilizes `WeasyPrint` to render modern HTML templates into PDFs, with a robust fallback to `ReportLab` if the system lacks the native GTK3/Pango system library.
* **[excel_service.py](file:///c:/Users/minhlong/Desktop/projects/hoang-quanlylophoc/app/services/excel_service.py)**: Builds spreadsheet reports (Excel spreadsheets `.xlsx` format) using `openpyxl`. Used for student rosters, attendance templates, and payroll sheets.
* **[tuition_service.py](file:///c:/Users/minhlong/Desktop/projects/hoang-quanlylophoc/app/services/tuition_service.py)**: Contains core math for calculating student tuition (aggregates total active attendances, processes custom fee overrides, and maps discount exemptions).
* **[payroll_service.py](file:///c:/Users/minhlong/Desktop/projects/hoang-quanlylophoc/app/services/payroll_service.py)**: Implements the teacher salary calculation model, processing fixed rates (per attended/late/absent session) vs. coefficient rates (class revenue percentage share).
* **[vietqr_service.py](file:///c:/Users/minhlong/Desktop/projects/hoang-quanlylophoc/app/services/vietqr_service.py)**: Strips diacritics/accents from Vietnamese text to output valid ASCII transfer content and constructs dynamic `img.vietqr.io` payment URLs.
* **[student_code_service.py](file:///c:/Users/minhlong/Desktop/projects/hoang-quanlylophoc/app/services/student_code_service.py)**: Dynamic student code format interpreter parsing dynamic configurations (e.g. `YYYYHS000001`).

### 2.3. Controller Routes (`app/routers/`)
* **[tuition.py](file:///c:/Users/minhlong/Desktop/projects/hoang-quanlylophoc/app/routers/tuition.py)**: Billing endpoints (calculating month-end totals, locking tuition periods, confirming payments, and serving generated receipt PDFs).
* **[payroll.py](file:///c:/Users/minhlong/Desktop/projects/hoang-quanlylophoc/app/routers/payroll.py)**: Payroll endpoints (calculating salaries, generating payslips, chosing teacher salary payments).
* **[attendance.py](file:///c:/Users/minhlong/Desktop/projects/hoang-quanlylophoc/app/routers/attendance.py)**: Endpoints to record student check-ins.
* **[teacher_attendance.py](file:///c:/Users/minhlong/Desktop/projects/hoang-quanlylophoc/app/routers/teacher_attendance.py)**: Endpoints to record teacher check-ins.
* **[data_management.py](file:///c:/Users/minhlong/Desktop/projects/hoang-quanlylophoc/app/routers/data_management.py)**: Utility endpoints for importing data, exporting SQL scripts, executing manual backup/restore tasks, and seeding the database.
* **[settings.py](file:///c:/Users/minhlong/Desktop/projects/hoang-quanlylophoc/app/routers/settings.py)**: Receipt configurations and code templates.
* **[students.py](file:///c:/Users/minhlong/Desktop/projects/hoang-quanlylophoc/app/routers/students.py)** & **[teachers.py](file:///c:/Users/minhlong/Desktop/projects/hoang-quanlylophoc/app/routers/teachers.py)**: Basic REST routers for administrative student and teacher profile creation.
