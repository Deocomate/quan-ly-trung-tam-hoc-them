# System Architecture

This document describes the system architecture, components, database relationships, and key data flows.

---

## 1. Component Diagram

```mermaid
graph TD
    Client[Web Browser: HTML/Tailwind/JS] <-->|HTTP / JSON / HTML| FastAPI[FastAPI Backend Application]
    
    subgraph FastAPI App
        Auth[Auth Middleware: JWT Cookies] --> Routers[Route Controllers: app/routers/]
        Routers --> Services[Business Services: app/services/]
        
        subgraph Services
            Tuition[tuition_service.py]
            Payroll[payroll_service.py]
            PDF[pdf_service.py: WeasyPrint / ReportLab]
            Excel[excel_service.py: OpenPyXL]
            QR[vietqr_service.py]
        end
    end
    
    FastAPI <-->|SQLAlchemy ORM| DB[(SQLite Database: database/quanlylophoc.sqlite3)]
    PDF -->|Fetch QR Code| VietQR[External VietQR API: img.vietqr.io]
```

---

## 2. Entity-Relationship Schema

The database relies on SQLite mapped via SQLAlchemy. The core models and their relationships are:

```mermaid
erDiagram
    users {
        int id PK
        string username
        string password_hash
        string full_name
        boolean is_active
        boolean must_change_password
        datetime created_at
        datetime updated_at
    }

    students {
        int id PK
        string student_code
        string full_name
        string parent_name
        string parent_phone
        date date_of_birth
        string notes
        boolean is_active
    }

    teachers {
        int id PK
        string full_name
        string phone
        string email
        float default_salary_coefficient
        boolean is_active
    }

    classes {
        int id PK
        string name
        string subject
        string school_year
        int default_fee
        int teacher_id FK
        string salary_type
        int fixed_salary_per_session
        float salary_coefficient
        boolean is_active
    }

    teacher_class_assignments {
        int id PK
        int class_id FK
        int teacher_id FK
        string role
        string salary_type
        int fixed_salary_per_session
        float salary_coefficient
    }

    teacher_attendance {
        int id PK
        int teacher_id FK
        int class_id FK
        date date
        string status
    }

    enrollments {
        int id PK
        int student_id FK
        int class_id FK
        int custom_fee
        boolean is_exempt
        date start_date
        boolean is_active
    }

    attendance {
        int id PK
        int student_id FK
        int class_id FK
        date date
        string status
    }

    tuition_periods {
        int id PK
        int month
        int year
        boolean is_locked
        datetime locked_at
        int locked_by FK
    }

    tuition_records {
        int id PK
        int student_id FK
        int month
        int year
        int total_sessions
        int total_amount
        int paid_amount
        string payment_status
        string transfer_code
    }

    students ||--o{ enrollments : "has"
    classes ||--o{ enrollments : "hosts"
    students ||--o{ attendance : "logs"
    classes ||--o{ attendance : "records"
    teachers ||--o{ classes : "teaches"
    teachers ||--o{ teacher_class_assignments : "assigned"
    classes ||--o{ teacher_class_assignments : "has"
    teachers ||--o{ teacher_attendance : "logs"
    classes ||--o{ teacher_attendance : "records"
    students ||--o{ tuition_records : "bills"
    users ||--o{ tuition_periods : "locks"
```

---

## 3. Core Workflows & Data Flows

### 3.1. Attendance Tracking & Tuition Math
1. **Attendance Input**: Teacher/admin logs daily attendance for a class. The system inserts/updates `attendance` records with statuses: `P` (Present), `V` (Absent), or `M` (Late).
2. **Billing Generation**:
   - The user selects a month to generate tuition.
   - `tuition_service.py` queries `enrollments` for all active students in target classes.
   - It filters student `attendance` for that month, counting valid sessions (e.g., status is `P` or `M`).
   - If `enrollments.is_exempt` is `True`, the tuition defaults to `0`. If `enrollments.custom_fee` is set, it overrides the class standard fee.
   - The tuition record is calculated: `total_sessions * fee_per_session`.
   - A `tuition_records` row is created/updated in the database in "unpaid" status.

### 3.2. QR Code Invoicing
1. **Invoice Request**: Admin exports a PDF receipt for a student's monthly fee.
2. **VietQR Link Generation**:
   - `vietqr_service.py` is invoked. It checks receipt configurations (bank ID, account number, template format).
   - Formats a payment transaction content code using templates (e.g. `HP HS001 0626`).
   - Constructs the QR image URL pointing to `img.vietqr.io` using the syntax: `https://img.vietqr.io/image/{bank_id}-{account_no}-{template}.png?amount={amount}&addInfo={addInfo}&accountName={accountName}`.
3. **HTML to PDF compilation**:
   - `pdf_service.py` loads the invoice HTML template, passes student details and the generated VietQR image URL.
   - It renders it using `WeasyPrint` into a high-quality PDF. If `WeasyPrint` dependencies are absent locally, it falls back to `ReportLab`.
