# Project Overview & Product Development Requirements (PDR)

This document provides a comprehensive overview of the **Hoang Classroom Management System** (Hệ thống Quản lý Lớp học) and defines its Product Development Requirements (PDR).

---

## 1. Executive Summary

Managing tutoring centers or small-to-medium educational institutions requires significant manual overhead in tracking student enrollment, monitoring daily attendance, calculating variable tuition fees, processing teacher payroll, and issuing transparent invoices. 

This project is a lightweight, high-performance web application designed to digitize and automate all of these core workflows:
* **Học vụ & Nhân sự**: Dual tracking of student registration and teacher-class assignments.
* **Điểm danh (Attendance)**: Daily check-in system for both students and teachers.
* **Học phí & VietQR**: Auto-calculating monthly tuition fees based on attendance and outputting dynamic QR code-enabled invoices.
* **Lương giáo viên (Payroll)**: Automated teacher salary calculation using fixed session fees or class revenue percentages.
* **Báo cáo & Backup**: Detailed revenue dashboards, Excel/PDF exports, and database backups.

---

## 2. Business Objectives & Use Cases

1. **Minimize Manual Overhead**: Replaces Excel sheets and paper logs with a central, automated database.
2. **Tuition Precision**: Computes fees dynamically based on actual student attendance (sessions attended, late, or excused/unexcused absences).
3. **VietQR Payment Automation**: Simplifies the checkout process for parents by embedding dynamic VietQR codes directly on generated PDF invoices (using `img.vietqr.io` quick links).
4. **Accurate Teacher Compensation**: Computes payroll dynamically by crossing teacher attendance with specialized formulas (per-session rates, late penalizations, and class revenue sharing).
5. **Data Protection**: Facilitates data resilience with 1-click database backup and SQL migration.

---

## 3. Product Development Requirements (PDR)

### 3.1. Student Directory Management
* **Record Attributes**: Student code (Mã học sinh), Full Name (Họ và tên), Date of Birth (Ngày sinh), Parent/Guardian Name (Họ tên phụ huynh), Phone Number (Số điện thoại phụ huynh), and Notes.
* **Class Enrollment**: Students can enroll in multiple classes.
* **Custom Tuition Override**: Supports custom session fees for individual enrollments (overriding the class default rate) or setting a tuition-exempt flag (`is_exempt`).

### 3.2. Class & Course Structure
* **Class Attributes**: Class name, Subject, School Year, and Default Fee per Session.
* **Teacher Assignment**: Connects a class to a main or assistant teacher. Supports salary configuration override per teacher-class assignment.

### 3.3. Student & Teacher Attendance (Điểm danh)
* **Student Attendance**: Daily grid interface with statuses:
  - `P` (Present - Có mặt)
  - `V` (Absent - Vắng mặt)
  - `M` (Late - Đi muộn)
* **Teacher Attendance**: Tracks teacher participation for classes to feed into the payroll calculation, with the same status values (`P`, `V`, `M`).

### 3.4. Tuition Calculation & Invoice Generation
* **Automatic Aggregation**: Collates the total number of monthly sessions attended per student.
* **Formula**: `Total Fee = Sessions Attended * Tuition/Session`.
* **VietQR Generation**: Generates a standard VietQR quick link utilizing the bank details, account number, amount, and structured description (e.g., `HP <StudentCode> <Month><Year>`).
* **PDF Invoicing**: Generates professional PDF invoices formatted with:
  - Header: Center name, address, hotline.
  - Body: Student details, target month, billing list table.
  - QR Code: Rendered VietQR quick link image.
  - Payment Instructions: Deadline, bank instructions, and footer notes.

### 3.5. Teacher Payroll Management (Quản lý Lương)
* **Flexible Salary Models**:
  - **Fixed Per Session**: Pays a flat rate for each session. Can define individual rates for Present, Late, or Absent (e.g., full pay for present, partial for late, zero for absent).
  - **Coefficient/Percentage**: Salary based on a percentage of the total class tuition revenue generated in that period.
* **Payroll Chosing**: Allows admins to generate payroll summaries per month, view items, and print teacher salary payslips in PDF.

### 3.6. Configuration & System Utilities
* **Receipt Settings**: Customize center details (Organization, Hotline, Address, Payment Instructions, deadline, and logo/QR display options).
* **Code Generator**: Configurable JSON structure defining how student codes are automatically generated (e.g., `YYYY` + `HS` + Sequential number).
* **Backup/Restore**: Manual database backups via SQL exports, automated periodic backups, and 1-click database restores.

---

## 4. Non-Functional Requirements

* **Performance & Speed**: Fast local page loads and rapid PDF compilation.
* **Data Integrity**: Tuition periods can be locked (`is_locked`) to prevent retroactive attendance/tuition updates.
* **Responsiveness**: Friendly mobile view to support teachers taking attendance directly inside the classroom on mobile phones.
* **Zero Configuration Storage**: Built-in SQLite database requires no local DB engine installations, simplifying deployment.
